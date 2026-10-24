"""Prüfstand: jedes Modell und jede Regel unter denselben Bedingungen prüfen.

Im Projekt hat fast jedes Notebook sein Modell selbst geprüft, mit eigenem
Fenster, eigener Kontrollgruppe, eigener Alarmmenge und eigener
Prüfbasis. Die Zahlen lassen sich dann nicht nebeneinanderlegen (Notebook
23: „70 % gegen 53 %“ und „11–17 % gegen 13 %“ meinten Verschiedenes).
Dieses Modul sammelt die Prüfungen an einer Stelle, damit jeder Kandidat,
gelernt oder Regel, durch dieselbe Prüfung läuft.

Drei Aufgaben, drei Prüfungen
-----------------------------
1. **Alarm** (meldet ein Wächter, dass sich eine Station verändert?)

   - `trefferpruefung`: Alarm im Fenster von 7 Tagen vor bis 60 Tage nach
     einer Begehung, gegen Kontrollstationen im selben Fenster. Das ist
     Sebs Prüfung aus Notebook 17, Abschnitt 11, und Notebook 23.
   - Fair nur bei **gleichen Stationen und Tagen** (`gemeinsame_tage`) und
     **gleich vielen Alarmen** (`budget_anpassen`): Wer öfter alarmiert,
     trifft automatisch öfter.
   - `einrechnen`: Fehler mit bekanntem Beginn in echte Stundenwerte
     schreiben (Notebook 21, Abschnitt 7), für Trefferquote bei bekannter
     Fehlalarmquote.

2. **Fehler erkennen** (welche Stationen haben einen Dauerfehler, z. B. ein
   Ventil, das nicht schließt?)

   - Jeder Kandidat liefert **einen Wert je Station**, größer heißt
     verdächtiger. Gelernte Modelle liefern ihn aus der Kreuzvalidierung,
     Regeln direkt aus einer Kennzahl.
   - `bewerte_scores`: AUC mit Bootstrap-Intervall, Precision unter den
     ersten k, Zufallstest (vertauschte Labels) und gepaarte Differenz zu
     einem Bezug, alles auf denselben Stationen.

3. **Fehler unterteilen** (welche Handlung je Station?)

   - `vierfelder` und `kappa`: Übereinstimmung zweier Einteilungen und
     Treffer einer Klasse gegen einen Befund.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

#Sebs Prüfung (Notebook 17, Abschnitt 1)
FENSTER_VOR = 7
FENSTER_NACH = 60
MIN_TAGE_IM_FENSTER = 5
KONTROLL_VORLAUF = 60
MIN_KONTROLLEN = 5
SEED = 0


# --- Alarm --------------------------------------------------------------------

def als_tage(tab: pd.DataFrame, zaehler: str = "zaehler",
             datum: str = "datum") -> Dict[int, pd.DatetimeIndex]:
    """Tabelle mit Zähler und Datum als Dict Zähler -> sortierte Tage."""
    if tab is None or len(tab) == 0:
        return {}
    t = pd.DataFrame({"z": tab[zaehler].astype(int).to_numpy(),
                      "d": pd.to_datetime(tab[datum]).to_numpy()})
    return {int(z): pd.DatetimeIndex(np.sort(g["d"].unique()))
            for z, g in t.groupby("z")}


def gemeinsame_tage(*tabellen: pd.DataFrame, ab=None) -> pd.DataFrame:
    """Zähler-Tage, die alle Wächter überwachen (Spalten zaehler, datum)."""
    menge = None
    for t in tabellen:
        s = set(zip(t["zaehler"].astype(int), pd.to_datetime(t["datum"])))
        menge = s if menge is None else menge & s
    aus = pd.DataFrame(sorted(menge or []), columns=["zaehler", "datum"])
    if ab is not None:
        aus = aus[aus["datum"] >= pd.Timestamp(ab)]
    return aus.reset_index(drop=True)


def auf_tagen(alarme: pd.DataFrame, tage: pd.DataFrame) -> pd.DataFrame:
    """Nur Alarme an Tagen aus ``tage`` (z. B. den gemeinsamen Tagen)."""
    if len(alarme) == 0:
        return alarme
    erlaubt = set(zip(tage["zaehler"].astype(int), pd.to_datetime(tage["datum"])))
    maske = [(int(z), pd.Timestamp(d)) in erlaubt
             for z, d in zip(alarme["zaehler"], alarme["datum"])]
    return alarme[np.asarray(maske, dtype=bool)]


def begehung_zwischen(termine: Mapping[int, Sequence], zaehler: int,
                      von, bis) -> bool:
    return any(von <= pd.Timestamp(t) <= bis for t in termine.get(int(zaehler), []))


def trefferpruefung(alarme: pd.DataFrame, beobachtet: pd.DataFrame,
                    faelle: pd.DataFrame, termine: Mapping[int, Sequence],
                    stationen: Optional[Iterable[int]] = None,
                    vor: int = FENSTER_VOR, nach: int = FENSTER_NACH,
                    min_tage: int = MIN_TAGE_IM_FENSTER,
                    kontroll_vorlauf: int = KONTROLL_VORLAUF,
                    min_kontrollen: int = MIN_KONTROLLEN) -> pd.DataFrame:
    """Alarm im Fenster um jede Begehung, gegen Kontrollstationen.

    - ``alarme``: Spalten zaehler, datum (alle Kanäle zusammen)
    - ``beobachtet``: überwachte Zähler-Tage (zaehler, datum)
    - ``faelle``: Begehungen (zaehler, datum), die geprüft werden
    - ``termine``: alle Begehungstermine je Zähler, für die Kontrollregel

    Ein Fall zählt nur, wenn die Station im Fenster mindestens
    ``min_tage`` überwachte Tage hat. Kontrollen sind überwachte Stationen
    ohne eigene Begehung von ``kontroll_vorlauf`` Tagen vor dem Fenster bis
    zu seinem Ende. Identisch mit Notebook 17, Abschnitt 11 (dort Fall für
    Fall nachgeprüft in Notebook 23).
    """
    al = als_tage(alarme)
    beob = als_tage(beobachtet)
    stationen = sorted(beob) if stationen is None else sorted(int(s) for s in stationen)

    def alarm(z, von, bis):
        s = al.get(z)
        return s is not None and bool(((s >= von) & (s <= bis)).any())

    def beobachtbar(z, von, bis):
        s = beob.get(z)
        return s is not None and int(((s >= von) & (s <= bis)).sum()) >= min_tage

    zeilen = []
    for f in faelle.itertuples(index=False):
        z, datum = int(f.zaehler), pd.Timestamp(f.datum)
        von, bis = datum - pd.Timedelta(days=vor), datum + pd.Timedelta(days=nach)
        if not beobachtbar(z, von, bis):
            continue
        kontrollen = [k for k in stationen if k != z and beobachtbar(k, von, bis)
                      and not begehung_zwischen(
                          termine, k, von - pd.Timedelta(days=kontroll_vorlauf), bis)]
        if len(kontrollen) < min_kontrollen:
            continue
        zeilen.append({"zaehler": z, "datum": datum, "treffer": alarm(z, von, bis),
                       "kontrollquote": float(np.mean([alarm(k, von, bis)
                                                       for k in kontrollen])),
                       "n_kontrolle": len(kontrollen)})
    return pd.DataFrame(zeilen, columns=["zaehler", "datum", "treffer",
                                         "kontrollquote", "n_kontrolle"])


def bilanz(t: pd.DataFrame, name: str = "") -> dict:
    """Trefferquote gegen Kontrollquote, einseitiger Binomialtest."""
    n, k = len(t), int(t["treffer"].sum()) if len(t) else 0
    p0 = float(t["kontrollquote"].mean()) if n else np.nan
    p = (stats.binomtest(k, n, p0, alternative="greater").pvalue
         if n and 0 < p0 < 1 else np.nan)
    return {"Kandidat": name, "Fälle": n, "Treffer": k,
            "Quote": k / n if n else np.nan, "Kontrollquote": p0,
            "Hebel": (k / n) / p0 if n and p0 > 0 else np.nan, "p (einseitig)": p}


def budget_anpassen(alarme_fuer: Callable[[float], pd.DataFrame],
                    werte: Sequence[float], ziel: int,
                    tage: pd.DataFrame) -> Tuple[float, pd.DataFrame]:
    """Parameter (Schwelle, h), dessen Alarmzahl auf ``tage`` am nächsten an ``ziel`` liegt.

    Bei gleichem Abstand gewinnt der höhere Wert (weniger Alarme). Rückgabe:
    Wert und Tabelle Wert -> Alarme.
    """
    zeilen = [{"wert": w, "alarme": len(auf_tagen(alarme_fuer(w), tage))}
              for w in werte]
    tab = pd.DataFrame(zeilen)
    tab["abstand"] = (tab["alarme"] - ziel).abs()
    bester = tab.sort_values(["abstand", "wert"], ascending=[True, False]).iloc[0]
    return float(bester["wert"]), tab.drop(columns="abstand")


def mcnemar(a: pd.Series, b: pd.Series) -> dict:
    """Fall für Fall: nur A, nur B, exakter zweiseitiger Test."""
    a, b = a.astype(bool), b.astype(bool)
    nur_a, nur_b = int((a & ~b).sum()), int((~a & b).sum())
    p = (stats.binomtest(nur_b, nur_a + nur_b, 0.5).pvalue
         if nur_a + nur_b else 1.0)
    return {"nur A": nur_a, "nur B": nur_b, "beide": int((a & b).sum()),
            "keiner": int((~a & ~b).sum()), "p (McNemar)": p}


def alarme_je_jahr(alarme: pd.DataFrame, beobachtet: pd.DataFrame) -> float:
    """Alarme je Station und Jahr über die überwachte Spanne jeder Station."""
    if len(beobachtet) == 0:
        return np.nan
    spanne = (beobachtet.assign(datum=pd.to_datetime(beobachtet["datum"]))
              .groupby("zaehler")["datum"].agg(lambda s: (s.max() - s.min()).days + 1))
    jahre = spanne.sum() / 365.25
    return len(alarme) / jahre if jahre > 0 else np.nan


def erster_alarm_nach(alarme: pd.DataFrame, zaehler: int, datum,
                      bis_tage: int = 60) -> Optional[int]:
    """Tage von ``datum`` bis zum ersten Alarm der Station (None ohne Alarm)."""
    datum = pd.Timestamp(datum)
    a = pd.to_datetime(alarme.loc[alarme["zaehler"].astype(int) == int(zaehler), "datum"])
    a = a[(a >= datum) & (a <= datum + pd.Timedelta(days=bis_tage))]
    return int((a.min() - datum).days) if len(a) else None


def einrechnen(werte: np.ndarray, fenster: np.ndarray, fehler: str,
               rl: int = 0, fl: int = 1, vl: int = 2) -> np.ndarray:
    """Fehler in eine Kopie der Stundenwerte schreiben (Notebook 21, Abschnitt 7).

    ``werte`` ist das Feld Tage × 24 × Kanäle, ``fenster`` je Zeile die
    Positionen der gestörten Tage. Fehler:

    - ``"Bypass 50"`` / ``"Bypass 150"``: Durchfluss + 50 bzw. 150 l/h, der
      Rücklauf mischt sich mit Vorlaufwasser
    - ``"Fühler hängt"``: Rücklauf bleibt auf dem ersten Wert stehen
    - ``"Sollwert +5 K"``: Rücklauf + 5 K, wenn Wasser fließt
    - ``"ohne"``: nichts, für die Fehlalarmquote
    """
    feld = werte.copy()
    for f in fenster:
        teil = feld[f]
        if fehler.startswith("Bypass"):
            extra = float(fehler.split()[1])
            teil[:, :, rl] = ((teil[:, :, rl] * teil[:, :, fl] + teil[:, :, vl] * extra)
                              / (teil[:, :, fl] + extra))
            teil[:, :, fl] += extra
        elif fehler == "Fühler hängt":
            teil[:, :, rl] = teil[0, 0, rl]
        elif fehler == "Sollwert +5 K":
            teil[:, :, rl] += np.where(teil[:, :, fl] > 1, 5.0, 0.0)
        elif fehler != "ohne":
            raise ValueError(f"unbekannter Fehler {fehler}")
        feld[f] = teil
    return feld


# --- Fehler erkennen ----------------------------------------------------------

def _auc(y: np.ndarray, s: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def auc_mit_intervall(y, score, n: int = 2000, seed: int = SEED) -> Tuple[float, float, float]:
    """AUC und 95-%-Bootstrap-Intervall (wie Notebook 20 und 22)."""
    y, score = np.asarray(y, dtype=int), np.asarray(score, dtype=float)
    rng = np.random.default_rng(seed)
    ziehungen = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            ziehungen.append(_auc(y[i], score[i]))
    return _auc(y, score), float(np.quantile(ziehungen, 0.025)), float(np.quantile(ziehungen, 0.975))


def auc_differenz(y, a, b, n: int = 2000, seed: int = SEED) -> Tuple[float, float, float]:
    """Gepaarte Bootstrap-Differenz AUC(a) − AUC(b) auf denselben Stationen."""
    y, a, b = (np.asarray(v, dtype=float) for v in (y, a, b))
    y = y.astype(int)
    rng = np.random.default_rng(seed)
    ziehungen = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            ziehungen.append(_auc(y[i], a[i]) - _auc(y[i], b[i]))
    return (_auc(y, a) - _auc(y, b), float(np.quantile(ziehungen, 0.025)),
            float(np.quantile(ziehungen, 0.975)))


def precision_at_k(y, score, k: int = 10) -> float:
    """Anteil echter Befunde unter den k verdächtigsten Stationen."""
    y, score = np.asarray(y), np.asarray(score, dtype=float)
    return float(y[np.argsort(-score, kind="stable")[:k]].mean())


def zufallstest(y, score, n: int = 10000, seed: int = SEED) -> float:
    """Einseitiger p-Wert: AUC mit vertauschten Labels mindestens so hoch.

    Gilt für feste Werte je Station (Regeln, Werte aus der
    Kreuzvalidierung). Für gelernte Modelle ist der strengere Test, das
    ganze Lernen mit vertauschten Labels zu wiederholen (Notebook 22).
    """
    y, score = np.asarray(y, dtype=int), np.asarray(score, dtype=float)
    echt = _auc(y, score)
    rng = np.random.default_rng(seed)
    #Rangsummen statt roc_auc_score: gleiche Zahl, viel schneller
    r = stats.rankdata(score)
    n1 = int(y.sum())
    n0 = len(y) - n1
    zaehler = 0
    for _ in range(n):
        yp = rng.permutation(y)
        auc = (r[yp == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
        zaehler += auc >= echt - 1e-12
    return (zaehler + 1) / (n + 1)


def holm(p: Sequence[float]) -> np.ndarray:
    """Holm-Korrektur für mehrere Tests (NaN bleibt NaN)."""
    p = np.asarray(p, dtype=float)
    aus = np.full_like(p, np.nan)
    ok = np.flatnonzero(np.isfinite(p))
    reihenfolge = ok[np.argsort(p[ok])]
    m = len(reihenfolge)
    laufend = 0.0
    for rang, i in enumerate(reihenfolge):
        laufend = max(laufend, min(1.0, (m - rang) * p[i]))
        aus[i] = laufend
    return aus


def bewerte_scores(y: pd.Series, scores: Mapping[str, pd.Series],
                   bezug: Optional[str] = None, k: int = 10,
                   n_boot: int = 2000, n_zufall: int = 10000,
                   paarweise: bool = False) -> pd.DataFrame:
    """Alle Kandidaten bewerten, gepaart mit einem Bezug.

    ``y`` ist das Label (0/1) je Station, ``scores`` je Kandidat ein Wert je
    Station (größer = verdächtiger). Spalten: AUC mit Intervall,
    Precision@k, Zufallstest mit Holm-Korrektur und, wenn ``bezug``
    gesetzt ist, die gepaarte Differenz zum Bezug.

    - ``paarweise=False``: nur Stationen, für die **alle** Kandidaten einen
      Wert haben; alle Zahlen sind direkt vergleichbar.
    - ``paarweise=True``: je Kandidat die Stationen, auf denen er **und** der
      Bezug einen Wert haben. So fällt keine Station heraus, nur weil ein
      anderer Kandidat sie nicht kennt; verglichen wird dann über die
      gepaarte Differenz zum Bezug, die Spalte ``Stationen`` sagt, worauf.
    """
    alle = pd.DataFrame(dict(scores)).join(y.rename("_y"), how="inner")
    if not paarweise:
        alle = alle.dropna()
    zeilen = []
    for name in [c for c in alle.columns if c != "_y"]:
        spalten = [name, "_y"] + ([bezug] if bezug is not None and name != bezug else [])
        tab = alle[spalten].dropna()
        yy = tab["_y"].astype(int).to_numpy()
        if len(yy) < 4 or not 0 < yy.sum() < len(yy):
            continue
        s = tab[name].to_numpy(dtype=float)
        auc, unten, oben = auc_mit_intervall(yy, s, n_boot)
        z = {"Kandidat": name, "Stationen": len(yy), "Befunde": int(yy.sum()),
             "AUC": auc, "unten": unten, "oben": oben,
             f"P@{k}": precision_at_k(yy, s, k),
             "p (Zufall)": zufallstest(yy, s, n_zufall)}
        if bezug is not None and name != bezug:
            d, du, do = auc_differenz(yy, s, tab[bezug].to_numpy(dtype=float), n_boot)
            z.update({"Δ zum Bezug": d, "Δ unten": du, "Δ oben": do})
        zeilen.append(z)
    aus = pd.DataFrame(zeilen)
    aus["p (Holm)"] = holm(aus["p (Zufall)"])
    aus["besser als Raten"] = aus["p (Holm)"] < 0.05
    if bezug is not None:
        aus["gegen Bezug"] = np.select(
            [aus.get("Δ unten", pd.Series(np.nan)) > 0,
             aus.get("Δ oben", pd.Series(np.nan)) < 0],
            ["belegt besser", "belegt schlechter"], "nicht unterscheidbar")
        aus.loc[aus["Kandidat"] == bezug, "gegen Bezug"] = "Bezug"
    return aus


# --- Fehler unterteilen -------------------------------------------------------

def vierfelder(vorhersage: pd.Series, befund: pd.Series) -> dict:
    """Precision und Trefferquote einer Ja/Nein-Einstufung gegen einen Befund."""
    t = pd.concat([vorhersage.rename("v"), befund.rename("b")], axis=1,
                  join="inner").dropna()
    v, b = t["v"].astype(bool), t["b"].astype(bool)
    tp, fp = int((v & b).sum()), int((v & ~b).sum())
    fn, tn = int((~v & b).sum()), int((~v & ~b).sum())
    return {"Stationen": len(t), "richtig ja": tp, "falsch ja": fp,
            "übersehen": fn, "richtig nein": tn,
            "Precision": tp / (tp + fp) if tp + fp else np.nan,
            "Trefferquote": tp / (tp + fn) if tp + fn else np.nan,
            "Basisrate": float(b.mean()) if len(b) else np.nan}


def kappa(a: pd.Series, b: pd.Series) -> float:
    """Cohens Kappa zweier Einteilungen auf den gemeinsamen Stationen."""
    from sklearn.metrics import cohen_kappa_score
    t = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    if t["a"].nunique() < 2 and t["b"].nunique() < 2:
        return np.nan
    return float(cohen_kappa_score(t["a"].astype(str), t["b"].astype(str)))
