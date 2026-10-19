"""
Fehlende Stundenwerte in den NB-00-Reihen auffüllen.

Rund 30 % der Rasterstunden innerhalb der Messspanne eines Zählers sind
in der NB-00-Ausgabe leer. Der größte Teil sind Tagesphasen, in denen
der Export nur einen Wert pro Tag um 23 Uhr enthält, dazu kommen lange
Ausfälle über Wochen und vereinzelte kurze Lücken. Für das
Graphennetzwerk braucht es aber jede Stunde.

Das Verfahren in drei Fällen, jede Zeile bekommt in ``quelle`` ihre
Herkunft:

    gemessen      alle Momentankanäle gemessen, unverändert
    ergaenzt      Zeile gemessen, einzelne Kanäle aus den Beziehungen
                  dt = vl - rt und power = k * flow * dt, aus den
                  Nachbarstunden oder dem Stationsprofil ergänzt
    interpoliert  Lücke bis `KURZ_MAX` Stunden, linear zwischen den
                  Nachbarstunden
    bilanziert    längere Lücke, deren Energie- und Volumensumme aus
                  den Zählerständen links und rechts bekannt ist. Die
                  Stundenform kommt aus dem Profil der Station, die
                  Summe stimmt mit dem Zähler überein
    modelliert    längere Lücke ohne brauchbare Zählerstände (Stand
                  fehlt, Zählertausch, unplausibler Sprung). Werte
                  sind reines Stationsprofil

Das Stationsprofil ist der Mittelwert von Volumenstrom, Spreizung und
Vorlauf je Tagesstunde und Außentemperaturklasse des Tages, gerechnet
nur aus den gemessenen Stunden derselben Station. Bei der Bilanz wird
je Station der Faktor zwischen Summe der Momentanwerte und
Zählerdifferenz berücksichtigt (`rho_faktoren`). Die Zählerstände
werden am Ende aus der gefüllten Leistung bzw. dem Volumenstrom so
verteilt, dass jeder gemessene Stand unverändert bleibt.

Gefüllt wird nur innerhalb der Messspanne eines Zählers, also vom
ersten bis zum letzten gemessenen Zeitpunkt, wobei auch ein einzelner
Zählerstand als Messung zählt. Vor Beginn und nach Ende der
Aufzeichnung wird nichts erfunden.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from . import nb00_daten as nb

GEFUELLT_DIR = nb.REPO / "data" / "processed" / "real_meters_gefuellt"

MOMENT = ["flow", "power", "dt", "vl", "rt"]
STAENDE = ["energy", "volume"]
#kW = k * l/h * K; physikalisch 1,163e-3, gemessen im Median 1,152e-3
K_NENN = 1.163e-3
KURZ_MAX = 3
#Tagesmittel der Außentemperatur in °C, Klassen <=0, 0-5, 5-10, 10-15, >15
T_GRENZEN = [0.0, 5.0, 10.0, 15.0]
MIN_N = 5
#Abklingzeit in Stunden, mit der die Vorlaufabweichung am Lückenrand ins Profil übergeht
TAU_VL = 72.0
#Zählersprung gilt als unplausibel, wenn er mehr als das Doppelte der höchsten gemessenen Rate verlangt
SPRUNG_FAKTOR = 2.0
QUELLEN = ("gemessen", "ergaenzt", "interpoliert", "bilanziert", "modelliert")


def k_faktor(df: pd.DataFrame) -> float:
    """Median von power / (flow * dt) in Stunden mit klarem Betrieb."""
    d = df[(df["flow"] > 50) & (df["dt"] > 3) & (df["power"] > 0)]
    if len(d) < 50:
        return K_NENN
    return float((d["power"] / (d["flow"] * d["dt"])).median())


def rho_faktoren(d: pd.DataFrame, min_paare: int = 500):
    """Verhältnis Summe Momentanwert zu Zählerdifferenz je Station.

    Über alle Paare aufeinanderfolgender, vollständig gemessener
    Stunden: Trapezsumme der Leistung durch Energiedifferenz, ebenso
    Volumenstrom zu Volumendifferenz. Im Netz liegt das im Median bei
    1,00, einzelne Stationen weichen aber um bis zu 40 % ab. Ohne den
    Faktor würde die Bilanz dort die Leistung systematisch verschieben.
    """
    h = d[MOMENT + STAENDE]
    voll = h.notna().all(axis=1)
    ok = voll & voll.shift(1, fill_value=False)
    dE = h["energy"].diff()
    dV = h["volume"].diff() * 1000
    tp = (h["power"] + h["power"].shift(1)) / 2
    tf = (h["flow"] + h["flow"].shift(1)) / 2
    m = ok & (dE >= 0) & (dV >= 0)
    if m.sum() < min_paare or dE[m].sum() <= 0 or dV[m].sum() <= 0:
        return 1.0, 1.0
    rho_e = float(np.clip(tp[m].sum() / dE[m].sum(), 0.5, 2.0))
    rho_v = float(np.clip(tf[m].sum() / dV[m].sum(), 0.5, 2.0))
    return rho_e, rho_v


def tagesmittel_aussen(start, ende, **kwargs) -> pd.Series:
    """Tagesmittel der Außentemperatur aus `weather`, Index = Datum."""
    from . import weather

    w = weather.load_outdoor_temperature(start, ende, **kwargs)
    return w.set_index("timestamp")["t_out"].resample("D").mean()


def auf_raster(df: pd.DataFrame) -> pd.DataFrame:
    """Reihe auf lückenloses Stundenraster zwischen erster und letzter Messung.

    Als Messung zählt auch ein einzelner Zählerstand. Bei rund der Hälfte
    der Zähler steht vor dem Beginn der Momentanwerte ein Stand vom
    Exportanfang, die Monate dazwischen werden über die Bilanz gefüllt.
    """
    if not df[MOMENT].notna().any().any():
        raise ValueError("Reihe enthält keine gemessene Stunde")
    belegt = df[MOMENT + STAENDE].notna().any(axis=1)
    df = df.loc[belegt.idxmax():belegt[::-1].idxmax(), MOMENT + STAENDE]
    idx = pd.date_range(df.index[0], df.index[-1], freq="h")
    return df.reindex(idx)


def _beziehungen(d: pd.DataFrame, k: float) -> None:
    flow, power, dt, vl, rt = (d[c] for c in MOMENT)
    m = dt.isna() & vl.notna() & rt.notna()
    d.loc[m, "dt"] = (vl - rt)[m]
    dt = d["dt"]
    m = rt.isna() & vl.notna() & dt.notna()
    d.loc[m, "rt"] = (vl - dt)[m]
    m = vl.isna() & rt.notna() & dt.notna()
    d.loc[m, "vl"] = (rt + dt)[m]
    m = power.isna() & flow.notna() & dt.notna()
    d.loc[m, "power"] = (k * flow * dt)[m]
    m = flow.isna() & power.notna() & (dt > 0.5)
    d.loc[m, "flow"] = (d["power"] / (k * dt))[m]


def _klassen(index: pd.DatetimeIndex, t_tag: Optional[pd.Series]) -> np.ndarray:
    if t_tag is None:
        return np.zeros(len(index), dtype=int)
    t = t_tag.reindex(index.normalize()).to_numpy(dtype=float)
    kl = np.digitize(t, T_GRENZEN)
    kl[np.isnan(t)] = -1
    return kl


def stationsprofil(d: pd.DataFrame, gem: np.ndarray, kl: np.ndarray,
                   ersatz: Optional[Dict[str, float]] = None) -> Dict[str, np.ndarray]:
    """Profilwert für jede Rasterzeile, je Kanal flow, dt, vl.

    Erst Mittelwert je (Stunde, Temperaturklasse), wenn dort mindestens
    `MIN_N` gemessene Werte liegen, sonst je Stunde, sonst Mittel der
    Station, sonst `ersatz` (Netzmedian). Mittelwert statt Median, weil
    der Volumenstrom taktet: der Median einer Stunde mit vielen
    Nullwerten unterschätzt den Erwartungswert, und genau der wird für
    die Verteilung der Zählerbilanz gebraucht. In der Validierung war
    der Median in der Tagesphase schlechter als lineare Interpolation.
    """
    h = d.index.hour.to_numpy()
    g = pd.DataFrame({"h": h[gem], "kl": kl[gem]})
    out = {}
    for c in ("flow", "dt", "vl"):
        g["v"] = d[c].to_numpy()[gem]
        gg = g.dropna(subset=["v"])
        z = gg[gg["kl"] >= 0].groupby(["h", "kl"])["v"].agg(["mean", "count"])
        z = z.loc[z["count"] >= MIN_N, "mean"]
        e = gg.groupby("h")["v"].agg(["mean", "count"])
        e = e.loc[e["count"] >= MIN_N, "mean"]
        v = z.reindex(pd.MultiIndex.from_arrays([h, kl])).to_numpy(dtype=float)
        v = np.where(np.isnan(v), e.reindex(h).to_numpy(dtype=float), v)
        rest = gg["v"].mean() if len(gg) else np.nan
        if np.isnan(rest) and ersatz:
            rest = ersatz.get(c, np.nan)
        out[c] = np.where(np.isnan(v), rest, v)
    return out


def _laeufe(maske: np.ndarray):
    """Start- und Endposition (inklusiv) jeder True-Folge."""
    m = np.concatenate([[False], maske, [False]]).astype(np.int8)
    d = np.diff(m)
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1


def _kurz_interpolieren(s: pd.Series, n: int) -> pd.Series:
    """Linear interpolieren, aber nur NaN-Folgen bis Länge n."""
    a, b = _laeufe(s.isna().to_numpy())
    lang = np.zeros(len(s), dtype=bool)
    for i, j in zip(a, b):
        if j - i + 1 > n or i == 0 or j == len(s) - 1:
            lang[i:j + 1] = True
    out = s.interpolate(limit_area="inside")
    out[lang] = np.nan
    return out


def _staende(stand: np.ndarray, rate: np.ndarray, max_rate: float) -> np.ndarray:
    """Zählerstand auffüllen, gemessene Stände bleiben stehen.

    Zwischen zwei gemessenen Ständen wird die Differenz nach der
    Trapezfläche der Rate verteilt. Ist die Differenz negativ oder
    unplausibel groß (Zählertausch), wird ab dem linken Stand einfach
    aufsummiert und der Sprung bleibt beim rechten Stand.
    """
    n = len(stand)
    w = np.empty(n)
    w[0] = rate[0]
    w[1:] = (rate[1:] + rate[:-1]) / 2
    w = np.clip(np.nan_to_num(w), 0, None)
    out = stand.astype(float).copy()
    bek = np.flatnonzero(~np.isnan(stand))
    if len(bek) == 0:
        return np.cumsum(w) - w[0]
    k0, k1 = bek[0], bek[-1]
    if k0 > 0:
        rueck = np.cumsum(w[1:k0 + 1][::-1])[::-1]
        out[:k0] = stand[k0] - rueck
    if k1 < n - 1:
        out[k1 + 1:] = stand[k1] + np.cumsum(w[k1 + 1:])
    for p in np.flatnonzero(np.diff(bek) > 1):
        i, j = bek[p], bek[p + 1]
        seg = w[i + 1:j + 1]
        diff = stand[j] - stand[i]
        plausibel = 0 <= diff <= SPRUNG_FAKTOR * max_rate * (j - i)
        if plausibel and seg.sum() > 0:
            out[i + 1:j] = stand[i] + diff * np.cumsum(seg)[:-1] / seg.sum()
        elif plausibel:
            out[i + 1:j] = stand[i] + diff * np.arange(1, j - i) / (j - i)
        else:
            out[i + 1:j] = stand[i] + np.cumsum(seg)[:-1]
    return out


def fuelle_zaehler(df: pd.DataFrame, t_tag: Optional[pd.Series] = None,
                   kurz_max: int = KURZ_MAX, bilanz: bool = True,
                   ersatz: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """Eine Stundenreihe im Schema von `nb00_daten.lade_serien` füllen.

    Rückgabe auf lückenlosem Stundenraster über die Messspanne mit den
    Messkanälen, ``quelle`` (siehe Modulbeschreibung) und ``luecke_h``
    (Länge der Lücke, zu der die Stunde gehört, 0 bei gemessenen
    Stunden). Mit ``bilanz=False`` werden längere Lücken nur aus dem
    Profil gefüllt, das dient als Vergleich in der Validierung.
    """
    d = auf_raster(df).astype(float)
    n = len(d)
    k = k_faktor(d)
    rho_e, rho_v = rho_faktoren(d)
    gem = d[MOMENT].notna().any(axis=1).to_numpy()
    voll = d[MOMENT].notna().all(axis=1).to_numpy()
    roh_e = d["energy"].to_numpy().copy()
    roh_v = d["volume"].to_numpy().copy()
    pmax = np.nanpercentile(d["power"], 99.9) if np.isfinite(d["power"]).any() else 0.0
    fmax = np.nanpercentile(d["flow"], 99.9) if np.isfinite(d["flow"]).any() else 0.0

    quelle = np.where(voll, "gemessen", "ergaenzt").astype(object)
    luecke = np.zeros(n, dtype=int)

    _beziehungen(d, k)
    kl = _klassen(d.index, t_tag)
    prof = stationsprofil(d, gem, kl, ersatz)
    fp, dp, vp = prof["flow"], prof["dt"], prof["vl"]

    F = d["flow"].to_numpy().copy()
    P = d["power"].to_numpy().copy()
    DT = d["dt"].to_numpy().copy()
    VL = d["vl"].to_numpy().copy()
    RT = d["rt"].to_numpy().copy()

    def stand(i):
        return not (np.isnan(roh_e[i]) or np.isnan(roh_v[i]))

    for a, b in zip(*_laeufe(~gem)):
        L = b - a + 1
        luecke[a:b + 1] = L
        if L <= kurz_max and a > 0 and b < n - 1:
            quelle[a:b + 1] = "interpoliert"
            continue
        #am Rand ist der Anker die Randzeile selbst, wenn dort nur Zählerstände stehen
        i0 = a - 1 if a > 0 else (a if stand(a) else None)
        i1 = b + 1 if b < n - 1 else (b if stand(b) else None)
        fh, dh, vh = fp[a:b + 1], dp[a:b + 1], vp[a:b + 1]
        ok = bilanz and i0 is not None and i1 is not None and i1 > i0 and stand(i0) and stand(i1)
        if ok:
            dE = roh_e[i1] - roh_e[i0]
            dV = roh_v[i1] - roh_v[i0]
            ok = (0 <= dE <= SPRUNG_FAKTOR * pmax * (i1 - i0)
                  and 0 <= dV * 1000 <= SPRUNG_FAKTOR * fmax * (i1 - i0))
        if ok:
            #Trapez: rho * dE = P0/2 + Summe der Lückenstunden + P1/2
            e_rest = max(rho_e * dE - (np.nan_to_num(P[i0]) + np.nan_to_num(P[i1])) / 2, 0.0)
            v_rest = max(rho_v * 1000 * dV - (np.nan_to_num(F[i0]) + np.nan_to_num(F[i1])) / 2, 0.0)
            sf = np.nansum(fh)
            flow = fh * v_rest / sf if sf > 0 else np.full(L, v_rest / L)
            s = k * np.nansum(flow * dh)
            if s > 0:
                dt = dh * e_rest / s
            elif flow.sum() > 0:
                dt = np.full(L, e_rest / (k * flow.sum()))
            else:
                dt = dh.copy()
            quelle[a:b + 1] = "bilanziert"
        else:
            flow, dt = fh.copy(), dh.copy()
            quelle[a:b + 1] = "modelliert"
        r0 = np.nan_to_num(VL[a - 1] - vp[a - 1]) if a > 0 else 0.0
        r1 = np.nan_to_num(VL[b + 1] - vp[b + 1]) if b < n - 1 else 0.0
        t = np.arange(1, L + 1)
        s_lin = t / (L + 1)
        abkl = np.exp(-np.minimum(t, L + 1 - t) / TAU_VL)
        vl = vh + (r0 * (1 - s_lin) + r1 * s_lin) * abkl
        #Rücklauf nicht unter 10 °C drücken
        dt = np.clip(dt, 0, np.clip(vl - 10, 0, None))
        F[a:b + 1], DT[a:b + 1], VL[a:b + 1] = flow, dt, vl
        P[a:b + 1] = k * flow * dt
        RT[a:b + 1] = vl - dt

    d["flow"], d["power"], d["dt"], d["vl"], d["rt"] = F, P, DT, VL, RT
    for c in MOMENT:
        d[c] = _kurz_interpolieren(d[c], kurz_max)
    _beziehungen(d, k)
    for c, p in (("flow", fp), ("dt", dp), ("vl", vp)):
        m = d[c].isna().to_numpy()
        d.loc[m, c] = p[m]
    _beziehungen(d, k)

    d["energy"] = _staende(roh_e, d["power"].to_numpy(), pmax)
    d["volume"] = _staende(roh_v, d["flow"].to_numpy() / 1000, fmax / 1000)
    d["quelle"] = quelle
    d["luecke_h"] = luecke
    d.attrs.update(k=k, rho_e=rho_e, rho_v=rho_v)
    return d


def netz_ersatz(serien: Dict[int, pd.DataFrame]) -> Dict[str, float]:
    """Median je Kanal über alle Zähler, Rückfall für leere Kanäle."""
    return {c: float(pd.concat([s[c] for s in serien.values()]).median())
            for c in ("flow", "dt", "vl")}


def fuelle_alle(serien: Optional[Dict[int, pd.DataFrame]] = None,
                zaehler: Optional[Iterable[int]] = None,
                t_tag: Optional[pd.Series] = None,
                schreiben: bool = True,
                ziel: Path = GEFUELLT_DIR) -> Dict[int, pd.DataFrame]:
    """Alle Zähler füllen und optional nach `ziel` schreiben.

    Die Dateien haben dieselben Spaltennamen wie die NB-00-Ausgabe plus
    ``quelle`` und ``luecke_h`` und lassen sich mit `lade_gefuellt`
    wieder einlesen.
    """
    if serien is None:
        serien = nb.lade_serien(zaehler=zaehler, leere_stunden_entfernen=False,
                                zaehlerstaende_ergaenzen=False)
    if t_tag is None:
        start = min(s.index.min() for s in serien.values())
        ende = max(s.index.max() for s in serien.values())
        t_tag = tagesmittel_aussen(start.normalize(), ende.normalize() + pd.Timedelta(days=1),
                                   allow_download=False)
    ersatz = netz_ersatz(serien)
    zurueck = {v: k for k, v in nb.SPALTEN_MAP.items()}
    if schreiben:
        Path(ziel).mkdir(parents=True, exist_ok=True)
    out = {}
    for zid, df in serien.items():
        if not df[MOMENT].notna().any().any():
            continue
        g = fuelle_zaehler(df, t_tag=t_tag, ersatz=ersatz)
        out[zid] = g
        if schreiben:
            g.rename(columns=zurueck).rename_axis("Timestamp").to_csv(
                Path(ziel) / f"{zid}.csv", float_format="%.4f")
    return out


def lade_gefuellt(zaehler: Optional[Iterable[int]] = None,
                  ziel: Path = GEFUELLT_DIR) -> Dict[int, pd.DataFrame]:
    """Gefüllte Reihen wieder einlesen, Schema wie `lade_serien`."""
    return nb.lade_serien(ziel, zaehler=zaehler, leere_stunden_entfernen=False,
                          zaehlerstaende_ergaenzen=False)


def uebersicht(gefuellt: Dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Stunden je Quelle und Zähler."""
    z = {zid: g["quelle"].value_counts() for zid, g in gefuellt.items()}
    return (pd.DataFrame(z).T.reindex(columns=list(QUELLEN)).fillna(0)
            .astype(int).rename_axis("zaehler"))


def holdout_maske(df: pd.DataFrame, art: str, rng: np.random.Generator,
                  tage: int = 28, n_kurz: int = 10) -> Optional[np.ndarray]:
    """Positionen, die für die Validierung künstlich entfernt werden.

    Gesucht wird ein Fenster von `tage` Tagen, in dem alle Kanäle
    gemessen sind. Dort wird je nach `art` simuliert:

        tagesphase  nur der Wert um 23 Uhr bleibt stehen
        block       das ganze Fenster fällt aus
        kurz        `n_kurz` Lücken von je `KURZ_MAX` Stunden
    """
    voll = df[MOMENT + STAENDE].notna().all(axis=1).to_numpy()
    w = tage * 24
    if len(voll) < w + 48:
        return None
    ok = np.convolve(voll.astype(int), np.ones(w + 2, dtype=int), "valid") == w + 2
    starts = np.flatnonzero(ok)
    if len(starts) == 0:
        return None
    s = int(rng.choice(starts)) + 1
    m = np.zeros(len(df), dtype=bool)
    if art == "tagesphase":
        fenster = np.arange(s, s + w)
        m[fenster[df.index.hour[fenster] != 23]] = True
    elif art == "block":
        m[s:s + w] = True
    elif art == "kurz":
        pos = rng.choice(np.arange(s, s + w - KURZ_MAX, KURZ_MAX + 2),
                         size=n_kurz, replace=False)
        for p in pos:
            m[p:p + KURZ_MAX] = True
    else:
        raise ValueError(art)
    return m


def validiere(serien: Dict[int, pd.DataFrame], t_tag: Optional[pd.Series] = None,
              arten=("kurz", "tagesphase", "block"), seed: int = 0,
              kanaele=("flow", "power", "vl", "rt"),
              n_zaehler: Optional[int] = None) -> pd.DataFrame:
    """Hold-out-Vergleich des Verfahrens gegen zwei einfache Ansätze.

    Je Zähler und Lückenart wird ein vollständig gemessenes Fenster
    künstlich gelöscht und neu gefüllt. Verglichen werden das Verfahren
    (Profil mit Bilanz), nur Profil ohne Bilanz und lineare
    Interpolation. Mit `n_zaehler` wird eine Zufallsstichprobe gezogen.
    Rückgabe: mittlerer absoluter Fehler je Momentankanal und die
    relative Abweichung der Energie aus dem gefüllten Zählerstand,
    einmal je Stunde und einmal je Kalendertag, jeweils bezogen auf die
    wahre Energie im gelöschten Fenster.
    """
    rng = np.random.default_rng(seed)
    ersatz = netz_ersatz(serien)
    ids = sorted(serien)
    if n_zaehler is not None and n_zaehler < len(ids):
        ids = sorted(rng.choice(ids, size=n_zaehler, replace=False).tolist())
    zeilen = []
    for zid in ids:
        df = serien[zid]
        if not df[MOMENT].notna().any().any():
            continue
        d = auf_raster(df)
        for art in arten:
            #eigener Zufallsstrom je Zähler und Art, damit Fenster nicht von der Auswahl abhängen
            m = holdout_maske(d, art, np.random.default_rng([seed, zid, sum(map(ord, art))]))
            if m is None:
                continue
            maskiert = d.copy()
            maskiert.iloc[m, :] = np.nan
            wahr = d.loc[m]
            ergebnisse = {
                "verfahren": fuelle_zaehler(maskiert, t_tag, ersatz=ersatz),
                "nur_profil": fuelle_zaehler(maskiert, t_tag, bilanz=False, ersatz=ersatz),
                "linear": maskiert.interpolate(limit_area="inside"),
            }
            tage = wahr.index.normalize()
            inc_w = d["energy"].diff()[m]
            tag_w = inc_w.groupby(tage).sum()
            for name, g in ergebnisse.items():
                g = g.reindex(d.index)
                inc_g = g["energy"].diff()[m]
                g = g.loc[m]
                zeile = {"zaehler": zid, "art": art, "verfahren": name,
                         "stunden": int(m.sum())}
                for c in kanaele:
                    zeile[f"mae_{c}"] = float((g[c] - wahr[c]).abs().mean())
                nenner = max(inc_w.abs().sum(), 1e-9)
                zeile["stundenenergie_rel"] = float((inc_g - inc_w).abs().sum() / nenner)
                zeile["tagesenergie_rel"] = float(
                    (inc_g.groupby(tage).sum() - tag_w).abs().sum() / nenner)
                zeilen.append(zeile)
    return pd.DataFrame(zeilen)
