"""
ARIMA und SARIMAX auf Tagesmitteln der Rücklauftemperatur.

statsmodels ist in der Projektumgebung nicht installiert, deshalb sind
die Modelle hier mit scipy selbst gebaut. Gerechnet wird eine
Regression mit autoregressiven Fehlern (SARIMAX ohne MA-Teil) über die
bedingte Methode der kleinsten Quadrate:

    u_t = y_t - X_t * beta
    e_t = phi(L) * Phi(L^s) * (1 - L)^d * u_t

phi ist das gewöhnliche AR-Polynom der Ordnung p, Phi das saisonale der
Ordnung P mit Periode s (Standard 7, Wochenrhythmus). Ohne exogene
Spalten und mit d = 1 ist das ein ARIMA(p,1,0), mit Außentemperatur als
exogener Spalte und P = 1 ein SARIMAX(p,0,0)(1,0,0)_7. Ein MA-Teil fehlt
bewusst: er macht die Schätzung nichtlinear in den Residuen und ist bei
Tagesmitteln mit 50 bis 150 Beobachtungen kaum identifizierbar.

Warum Tagesmittel statt Stundenwerte: der 24-Stunden-Rhythmus der
Stundenreihe würde eine saisonale Ordnung von 24 verlangen, und die
Brenner- und Regelschwankungen im Stundenraster sind für die Frage
"hat sich der Rücklauf nach der Begehung verschoben" Rauschen. Der
Wochenrhythmus bleibt als saisonaler Teil erhalten.

Fehlende Tage bleiben NaN. Die Residuen an Gleichungen, in die ein
fehlender Tag hineinreicht, entfallen; nichts wird aufgefüllt, außer
den letzten Tagen vor dem Prognoseursprung (lineare Interpolation, nur
für den Start der Rekursion).

`rollender_vergleich()` rechnet die Modelle über viele Ursprünge ohne
Begehung im Fenster und liefert die Prognosefehler. `wirkung_begehung()`
wendet ein Modell auf eine Begehung an: Anpassung vor dem Datum,
Prognose danach, Abweichung der Messung von der Prognose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

SAISON = 7
HEIZGRENZE = 15.0
#gleiche Lastschwelle wie features.py ("loaded")
LAST_MIN_KW = 0.5
SCHRANKE = 0.98


@dataclass(frozen=True)
class ModellSpec:
    """Beschreibung eines Modells; `exog` nennt Spalten des Tagesframes."""

    name: str
    p: int = 0
    P: int = 0
    d: int = 0
    exog: Tuple[str, ...] = ()
    konstante: bool = True
    s: int = SAISON


@dataclass
class Anpassung:
    spec: ModellSpec
    spalten: List[str]
    beta: np.ndarray
    phi: np.ndarray
    Phi: np.ndarray
    koeff: np.ndarray
    sigma2: float
    n_eff: int
    aic: float
    ok: bool = True


def tagesreihe(df: pd.DataFrame,
               t_out: pd.DataFrame,
               spalte: str = "rt",
               min_stunden: int = 12,
               min_t_stunden: int = 18,
               heizgrenze: Optional[float] = HEIZGRENZE) -> pd.DataFrame:
    """Tagesframe mit Zielgröße und Witterungsspalten auf lückenlosem Raster.

    `df` ist die Stundenreihe eines Zählers (Index Zeitstempel, Spalten
    wie in `features.features_for_meter`), `t_out` die Ausgabe von
    `weather.load_outdoor_temperature`. Das Tagesmittel von `spalte`
    zählt nur Stunden mit Last (`power` über 0,5 kW), sonst steht dort
    die Stillstandstemperatur der Leitung. Tage mit weniger als
    `min_stunden` solcher Stunden bleiben NaN. Liegt das Tagesmittel der
    Außentemperatur über `heizgrenze`, wird die Zielgröße ebenfalls NaN
    gesetzt: im Sommer heizt die Station nicht, und das Modell soll
    nur Heizbetrieb abbilden. `heizgrenze=None` schaltet das ab.

    Spalten des Ergebnisses: y, t_out, t_out_l1 (Vortag), hgt
    (Heizgradtage zur Heizgrenze, bei None zur Grenze 15 °C).
    """
    bel = df["power"] > LAST_MIN_KW
    werte = df[spalte].where(bel)
    tag = werte.resample("D")
    y = tag.mean()
    y[tag.count() < min_stunden] = np.nan

    tt = t_out.set_index("timestamp")["t_out"].resample("D")
    tm = tt.mean()
    tm[tt.count() < min_t_stunden] = np.nan

    index = pd.date_range(y.index.min(), y.index.max(), freq="D")
    frame = pd.DataFrame(index=index)
    frame["y"] = y.reindex(index)
    frame["t_out"] = tm.reindex(index)
    frame["t_out_l1"] = frame["t_out"].shift(1)
    frame["hgt"] = (HEIZGRENZE - frame["t_out"]).clip(lower=0.0)
    if heizgrenze is not None:
        frame.loc[frame["t_out"] >= heizgrenze, "y"] = np.nan
    return frame


def _koeffizienten(phi: np.ndarray, Phi: np.ndarray, d: int, s: int) -> np.ndarray:
    """Koeffizienten von phi(L) * Phi(L^s) * (1 - L)^d, c[0] = 1."""
    ar = np.concatenate(([1.0], -np.asarray(phi, dtype=float)))
    sar = np.zeros(1 + s * len(Phi))
    sar[0] = 1.0
    for j, wert in enumerate(Phi, start=1):
        sar[j * s] = -wert
    koeff = np.convolve(ar, sar)
    for _ in range(d):
        koeff = np.convolve(koeff, [1.0, -1.0])
    return koeff


def _designmatrix(frame: pd.DataFrame, spec: ModellSpec) -> Tuple[np.ndarray, List[str]]:
    """Exogene Matrix; die Konstante gibt es nur ohne Differenzierung."""
    spalten = list(spec.exog)
    teile = [frame[c].to_numpy(dtype=float) for c in spalten]
    if spec.konstante and spec.d == 0:
        teile.insert(0, np.ones(len(frame)))
        spalten.insert(0, "konstante")
    if not teile:
        return np.zeros((len(frame), 0)), []
    return np.column_stack(teile), spalten


def _residuen(theta: np.ndarray, y: np.ndarray, X: np.ndarray, spec: ModellSpec):
    k = X.shape[1]
    beta = theta[:k]
    phi = theta[k:k + spec.p]
    Phi = theta[k + spec.p:k + spec.p + spec.P]
    koeff = _koeffizienten(phi, Phi, spec.d, spec.s)
    u = y - X @ beta if k else y.copy()
    e = np.convolve(u, koeff)[:len(u)]
    e[:len(koeff) - 1] = np.nan
    return e


def fit(frame: pd.DataFrame, spec: ModellSpec, ziel: str = "y") -> Anpassung:
    """Parameter über bedingte kleinste Quadrate schätzen.

    `ok` ist False, wenn zu wenige vollständige Gleichungen übrig bleiben
    oder der Optimierer nicht konvergiert; die Anpassung liefert dann
    Nullkoeffizienten und darf nicht für Prognosen benutzt werden.
    """
    y = frame[ziel].to_numpy(dtype=float)
    X, spalten = _designmatrix(frame, spec)
    k = X.shape[1]
    n_par = k + spec.p + spec.P

    koeff0 = _koeffizienten(np.zeros(spec.p), np.zeros(spec.P), spec.d, spec.s)
    leer = Anpassung(spec, spalten, np.zeros(k), np.zeros(spec.p),
                     np.zeros(spec.P), koeff0, np.nan, 0, np.nan, ok=False)

    #Startwert: OLS auf den (ggf. differenzierten) Daten
    yd, Xd = y.copy(), X.copy()
    for _ in range(spec.d):
        yd = np.diff(yd, prepend=np.nan)
        Xd = np.diff(Xd, axis=0, prepend=np.full((1, k), np.nan)) if k else Xd
    gueltig = np.isfinite(yd)
    if k:
        gueltig &= np.isfinite(Xd).all(axis=1)
    if gueltig.sum() < n_par + 5:
        return leer
    beta0 = (np.linalg.lstsq(Xd[gueltig], yd[gueltig], rcond=None)[0]
             if k else np.zeros(0))
    theta0 = np.concatenate([beta0, np.zeros(spec.p + spec.P)])

    e0 = _residuen(theta0, y, X, spec)
    n_eff = int(np.isfinite(e0).sum())
    if n_eff < n_par + 5:
        return leer

    def f(theta):
        e = _residuen(theta, y, X, spec)
        return e[np.isfinite(e)]

    untere = np.concatenate([np.full(k, -np.inf), np.full(spec.p + spec.P, -SCHRANKE)])
    obere = np.concatenate([np.full(k, np.inf), np.full(spec.p + spec.P, SCHRANKE)])
    if n_par == 0:
        e = f(theta0)
        sigma2 = float(np.mean(e ** 2))
        return Anpassung(spec, spalten, np.zeros(0), np.zeros(0), np.zeros(0),
                         koeff0, sigma2, n_eff, n_eff * np.log(sigma2 + 1e-12) + 2)
    try:
        res = least_squares(f, theta0, bounds=(untere, obere), method="trf")
    except (ValueError, np.linalg.LinAlgError):
        return leer
    theta = res.x
    e = f(theta)
    sigma2 = float(np.mean(e ** 2))
    phi = theta[k:k + spec.p]
    Phi = theta[k + spec.p:]
    return Anpassung(spec, spalten, theta[:k], phi, Phi,
                     _koeffizienten(phi, Phi, spec.d, spec.s), sigma2, n_eff,
                     n_eff * np.log(sigma2 + 1e-12) + 2 * (n_par + 1),
                     ok=bool(res.success))


def prognose(anp: Anpassung, historie: pd.DataFrame, zukunft: pd.DataFrame,
             ziel: str = "y") -> np.ndarray:
    """Prognose für die Zeilen von `zukunft` mit bekannter Exogenen.

    Die Fehlerterme der Zukunft werden auf null gesetzt. Fehlt in `zukunft`
    ein exogener Wert, ist die Prognose dieses Tages und der davon über
    die AR-Terme abhängigen NaN.
    """
    spec = anp.spec
    n_h = len(zukunft)
    if not anp.ok:
        return np.full(n_h, np.nan)
    X_h, _ = _designmatrix(historie, spec)
    X_z, _ = _designmatrix(zukunft, spec)
    k = len(anp.beta)
    xb_h = X_h @ anp.beta if k else np.zeros(len(historie))
    xb_z = X_z @ anp.beta if k else np.zeros(n_h)

    u_h = historie[ziel].to_numpy(dtype=float) - xb_h
    m = len(anp.koeff) - 1
    rest = pd.Series(u_h[-max(m, 1) * 2:]).interpolate(limit_area="inside")
    #stationärer Fehler hat Mittel null; ein differenzierter bleibt auf dem letzten Stand
    rest = (rest.ffill().bfill() if spec.d else rest.fillna(0.0)).to_numpy()
    if len(rest) < m or not np.isfinite(rest).all():
        return np.full(n_h, np.nan)
    u = list(rest[-m:]) if m else []
    out = np.empty(n_h)
    for h in range(n_h):
        if m:
            nxt = -float(np.dot(anp.koeff[1:], u[::-1][:m]))
        else:
            nxt = 0.0
        u.append(nxt)
        out[h] = xb_z[h] + nxt
    return out


def _naiv(train: pd.DataFrame, n_h: int, tage: int = 7) -> np.ndarray:
    letzte = train["y"].dropna().tail(tage)
    wert = float(letzte.mean()) if len(letzte) else np.nan
    return np.full(n_h, wert)


def standard_modelle() -> List[ModellSpec]:
    """Die verglichenen Modelle, vom einfachsten zum aufwendigsten."""
    return [
        ModellSpec("arima_110", p=1, d=1, konstante=False),
        ModellSpec("arma_200", p=2, d=0),
        ModellSpec("kennlinie", p=0, d=0, exog=("t_out",)),
        ModellSpec("arx_100", p=1, d=0, exog=("t_out",)),
        ModellSpec("sarimax_100_100", p=1, P=1, d=0, exog=("t_out",)),
        ModellSpec("sarimax_lag", p=1, P=1, d=0, exog=("t_out", "t_out_l1")),
    ]


def _vorhersage(spec_oder_naiv, train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    if spec_oder_naiv == "naiv_7":
        return _naiv(train, len(test))
    anp = fit(train, spec_oder_naiv)
    return prognose(anp, train, test)


def _begehung_im_fenster(index: pd.DatetimeIndex, sperrdaten: Iterable) -> bool:
    if not len(index):
        return False
    von, bis = index[0], index[-1]
    return any(von <= pd.Timestamp(d).normalize() <= bis for d in sperrdaten)


def rollender_vergleich(tage: pd.DataFrame,
                        specs: Sequence[ModellSpec],
                        train_tage: int = 56,
                        horizont: int = 14,
                        schritt: int = 14,
                        min_train_gueltig: int = 30,
                        min_test_gueltig: int = 7,
                        sperrdaten: Iterable = (),
                        mit_naiv: bool = True) -> pd.DataFrame:
    """Prognosefehler über viele Ursprünge einer Zählerreihe.

    Je Ursprung wird auf `train_tage` angepasst und `horizont` Tage
    vorhergesagt, wobei die tatsächliche Außentemperatur des Prognose-
    zeitraums eingeht (Szenario "was hätte der Rücklauf bei diesem
    Wetter sein sollen"). Gezählt wird in Kalendertagen, verlangt werden
    mindestens `min_train_gueltig` Heiztage zum Anpassen und
    `min_test_gueltig` zum Prüfen. Fenster, in denen ein Datum aus
    `sperrdaten` liegt (Begehungen), werden übersprungen, damit keine
    Intervention im Prüfzeitraum steckt. Ergebnis: eine Zeile je Ursprung
    und Modell mit mae, bias (Messung minus Prognose), rmse und n_test.
    """
    zeilen = []
    kandidaten: List = list(specs)
    if mit_naiv:
        kandidaten.append("naiv_7")
    for start in range(train_tage, len(tage) - horizont + 1, schritt):
        train = tage.iloc[start - train_tage:start]
        test = tage.iloc[start:start + horizont]
        if train["y"].notna().sum() < min_train_gueltig:
            continue
        if test["y"].notna().sum() < min_test_gueltig:
            continue
        if _begehung_im_fenster(tage.index[start - train_tage:start + horizont],
                                sperrdaten):
            continue
        for kand in kandidaten:
            pred = _vorhersage(kand, train, test)
            diff = test["y"].to_numpy() - pred
            gueltig = np.isfinite(diff)
            if gueltig.sum() < min_test_gueltig:
                continue
            d = diff[gueltig]
            zeilen.append({
                "ursprung": tage.index[start],
                "modell": kand if isinstance(kand, str) else kand.name,
                "mae": float(np.mean(np.abs(d))),
                "bias": float(np.mean(d)),
                "rmse": float(np.sqrt(np.mean(d ** 2))),
                "n_test": int(gueltig.sum()),
            })
    return pd.DataFrame(zeilen)


def wirkung_begehung(tage: pd.DataFrame,
                     datum,
                     spec: ModellSpec,
                     train_tage: int = 365,
                     post_tage: int = 90,
                     min_train_gueltig: int = 40,
                     min_post_gueltig: int = 10) -> Optional[Mapping[str, float]]:
    """Abweichung der Messung von der Prognose nach einer Begehung.

    Angepasst wird auf die bis zu `train_tage` Kalendertage vor dem
    Begehungstag, der Begehungstag selbst bleibt als Mischzustand draußen.
    Prognostiziert werden die `post_tage` danach. Gezählt wird in
    Kalendertagen, gerechnet nur mit den Heiztagen darin (siehe
    `tagesreihe`): eine Begehung im September hat kaum Heizbetrieb
    davor, die Anpassung greift dann auf den Winter davor zurück.
    `abw` ist der Mittelwert von Messung minus Prognose in °C: positiv
    heißt, der Rücklauf liegt höher als das Vorher-Modell bei demselben
    Wetter erwartet. Ob die Abweichung mehr ist als Prognoserauschen,
    entscheidet erst der Vergleich mit `rollender_vergleich` mit denselben
    Fensterlängen auf Zeiträumen ohne Begehung. Rückgabe None, wenn zu
    wenige gültige Heiztage davor oder danach vorliegen.
    """
    tag = pd.Timestamp(datum).normalize()
    if tag not in tage.index:
        return None
    pos = tage.index.get_loc(tag)
    train = tage.iloc[max(pos - train_tage, 0):pos]
    post = tage.iloc[pos + 1:pos + 1 + post_tage]
    if train["y"].notna().sum() < min_train_gueltig:
        return None
    if post["y"].notna().sum() < min_post_gueltig:
        return None
    anp = fit(train, spec)
    pred = prognose(anp, train, post)
    diff = post["y"].to_numpy() - pred
    gueltig = np.isfinite(diff)
    if gueltig.sum() < min_post_gueltig:
        return None
    return {
        "abw": float(np.mean(diff[gueltig])),
        "mae": float(np.mean(np.abs(diff[gueltig]))),
        "n_post": int(gueltig.sum()),
        "sigma": float(np.sqrt(anp.sigma2)),
        "rt_vor": float(train["y"].mean()),
        "rt_nach": float(post["y"].mean()),
    }
