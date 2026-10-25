"""Modellvergleich und Umsetzung nach Aufgabenstellung: Modell Ivelina gegen Modell LSTM (Notebook 34).

Beide Modelle werden hier aus denselben Notebook-00-Stundenreihen neu
gebaut, mit einer gemeinsamen, vorher festgelegten Zeitachse, und auf
denselben Fällen geprüft. Neu erfunden wird kaum etwas:

- **Modell Ivelina** (Kennlinien-Strang): Tagesmonitor aus
  `tagesmonitor` (Kennlinie + CUSUM), Netzvergleich und Potenzial aus
  `netzvergleich`, Fehlerbild und Priorität aus `alarmbewertung`. Hier wird
  nur die Lernzeit auf das gemeinsame Ende gesetzt.
- **Modell LSTM** (Modell-Strang): Prognose-LSTM als Wächter aus
  `prognose_waechter`, Embedding + logistische Regression und K-Means aus
  `fehlerklassen`. Dazu XGBoost aus Notebook 22 als dritter Kandidat.

Die Spielregeln stehen als Konstanten oben und gelten, bevor ein
Testergebnis angeschaut wird:

- Lernen bis ``LERN_ENDE`` (31.01.2024), Probezeit (Validierung) ab
  ``VAL_START`` bis ``VAL_ENDE``, Test ab ``TEST_START``. Die 7 Tage
  Abstand sind das Eingabefenster des LSTM, so teilen die Abschnitte keinen
  Rohdatentag.
- Schwellen und Alarmlast nur aus der Probezeit. Bezug ist Ivelinas Wächter
  mit ihrer eigenen Einstellung h = 5: Jeder andere Wächter bekommt so
  viele Alarme, wie er in der Probezeit gibt.
- Fehlerarten je Station: fünffache Kreuzvalidierung über physische
  Stationsgruppen, der LSTM-Encoder wird je Fold ohne die Teststationen
  neu gelernt, feste Grenze p ≥ 0,5.
- ``auslastung`` (Spitzenlast zum Anschlusswert) bleibt draußen: Der
  Anschlusswert ist bei 7 von 9 verkleinerten Verträgen schon der neue Wert.

Neu ist `stoerung_einrechnen`: Fehler mit bekanntem Beginn werden in die
NB-00-Stundenwerte geschrieben, **einschließlich der Energie- und
Volumenzähler**. Erst damit lässt sich Ivelinas Wächter, der aus
Zählerständen rechnet, genauso prüfen wie das LSTM.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import alarmbewertung as ab
from . import fehlerklassen as fk
from . import load_begehungen as lb
from . import modellpaket as mp
from . import nb00_daten as nb00
from . import netzvergleich as nv
from . import prognose_waechter as pw
from . import stationsbilder as sb
from . import tagesmonitor as tm
from . import weather

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
AUSGABE = ROOT / "outputs" / "finalvergleich"

# --- Spielregeln (Notebook 34, Abschnitt 4) ---------------------------------

LERN_ENDE = pd.Timestamp("2024-02-01")     # erster Tag, der nicht mehr gelernt wird
VAL_START = pd.Timestamp("2024-02-08")     # 7 Tage Abstand = Eingabefenster LSTM
#Probezeit in zwei Teilen: erst die normale Schwankung des LSTM kalibrieren,
#dann auf Tagen, die keins der Modelle gesehen hat, die Alarmlast einstellen
WAHL_START = pd.Timestamp("2024-04-01")
VAL_ENDE = pd.Timestamp("2024-06-01")
TEST_START = pd.Timestamp("2024-06-08")
SEED = 0
H_IVELINA = tm.CUSUM_H                     # Ivelinas Einstellung, nicht verändert
MIN_VAL_TAGE = pw.MIN_VAL_TAGE

#Raster für die Suche nach gleicher Alarmlast (nur Probezeit)
RASTER_SCHWELLE = [1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 8.0]
RASTER_CUSUM_H = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 30.0]

#Klassifikation (Notebook 18 und 20)
WINTER = fk.WINTER
SOMMER = fk.SOMMER
STICHTAG = fk.STICHTAG
KENNZAHLEN = [k for k in fk.KENNZAHLEN if k != "auslastung"]
EMB = fk.EMB_WINTER + fk.EMB_SOMMER
ZIELE = ["ventil", "daemmung", "durchfluss", "temperatur", "filter",
         "ueberdimensioniert"]
ZIEL_TEXT = {"ventil": "Ventil getauscht / Ventilbefund",
             "daemmung": "Leitungen gedämmt",
             "durchfluss": "Durchfluss neu eingestellt",
             "temperatur": "Rücklauf-Sollwert gesenkt",
             "filter": "Filter gereinigt",
             "ueberdimensioniert": "Vertrag verkleinert"}
GRENZE = 0.5
N_FOLDS = 5
FOLD_SEED = 42

#Ivelinas Fehlerbilder (alarmbewertung.FEHLERBILDER) als Hinweis auf eine Maßnahme
FEHLERBILD_ZU_ZIEL = {"ventil": {"ventil"},
                      "durchfluss": {"durchfluss", "durchfluss_je_kw"},
                      "temperatur": {"regelung", "unruhig", "rücklauf"}}
#Klassen nach Folie 5
F5_REPARATUR = "Reparatur (Ventil)"
F5_REGELUNG = "Regelungsoptimierung"
F5_KEINE = "kein Handlungsbedarf"
F5_KLASSEN = [F5_REPARATUR, F5_REGELUNG, F5_KEINE]

KWH_JE_LH_K = 1.163e-3                     # kW je (l/h · K), Wasser


# --- Daten ------------------------------------------------------------------

def lade_eingaben(root: Path = ROOT) -> dict:
    """Alles, was beide Modelle brauchen, aus einer Quelle.

    Stundenreihen nur aus Notebook 00 (`nb00_daten.lade_serien`), daraus
    auch die Stundentabelle des LSTM (`stunden_aus_serien`). Anschlusswert
    und BHKW wie im Stationsblatt (`stationsblatt.eingaben`), Labels aus
    Notebook 18.
    """
    from . import load_data as ld
    root = Path(root)
    serien = nb00.lade_serien(root / "data" / "processed" / "real_meters")
    start = min(s.index.min() for s in serien.values()).normalize()
    ende = max(s.index.max() for s in serien.values()).normalize() + pd.Timedelta(hours=23)
    wetter = weather.load_outdoor_temperature(start, ende)
    termine = {int(k): list(v) for k, v in lb.begehung_dates_by_meter().items()}
    labels = pd.read_csv(root / "data" / "processed" / "modell_labels.csv",
                         index_col="zaehler", parse_dates=["erste_begehung"])
    nodes = ld.load_logical_nodes()
    aw = pd.DataFrame({"meter": pd.to_numeric(nodes["Zählernummer"], errors="coerce"),
                       "kw": pd.to_numeric(nodes["Anschlusswert"], errors="coerce")}).dropna()
    anschluss = aw.groupby(aw["meter"].astype(int))["kw"].max().to_dict()
    blaetter = pd.read_excel(root / "data" / "raw" / "Zuordnung.xlsx", sheet_name=None,
                             dtype={"V-PIN": str})
    vpin = pd.concat([b[["Zählernummer", "V-PIN"]] for b in blaetter.values()
                      if {"Zählernummer", "V-PIN"} <= set(b.columns)])
    vpin["Zählernummer"] = pd.to_numeric(vpin["Zählernummer"], errors="coerce")
    bhkw = set(vpin.loc[vpin["V-PIN"] == "BHKW", "Zählernummer"].dropna().astype(int))
    return {"serien": serien, "wetter": wetter, "temp": tm.tagestemperatur(wetter),
            "stunden": stunden_aus_serien(serien, wetter), "termine": termine,
            "labels": labels, "anschluss": anschluss, "bhkw": bhkw,
            "gruppen": physische_gruppen(serien)}


def stunden_aus_serien(serien: Mapping[int, pd.DataFrame],
                       wetter: pd.DataFrame) -> pd.DataFrame:
    """Stundentabelle des LSTM (Schema von `modell_stunden.parquet`) aus den NB-00-Reihen."""
    teile = []
    for m, s in serien.items():
        teile.append(pd.DataFrame({
            "zaehler": int(m), "timestamp": s.index,
            "vorlauf": s["vl"].to_numpy(), "ruecklauf": s["rt"].to_numpy(),
            "spreizung": s["dt"].to_numpy(), "durchfluss": s["flow"].to_numpy(),
            "leistung": s["power"].to_numpy()}))
    st = pd.concat(teile, ignore_index=True)
    w = wetter.rename(columns={"t_out": "aussen"})[["timestamp", "aussen"]]
    return st.merge(w, on="timestamp", how="left")


def physische_gruppen(serien: Mapping[int, pd.DataFrame]) -> pd.Series:
    """Zähler an derselben Adresse (Zählerwechsel) als eine Gruppe.

    Wie im Audit (`docs/model_audit/lstm_validation.py`): Ein Zählertausch
    darf nicht dazu führen, dass dieselbe Station in Lern- und Testteil liegt.
    """
    eltern = {int(m): int(m) for m in serien}

    def finde(a):
        eltern.setdefault(a, a)
        if eltern[a] != a:
            eltern[a] = finde(eltern[a])
        return eltern[a]

    for _, block in lb.load_zuordnung().groupby("key"):
        ids = block["meter"].astype(int).unique()
        for m in ids[1:]:
            eltern[finde(int(m))] = finde(int(ids[0]))
    return pd.Series({int(m): finde(int(m)) for m in serien}, name="gruppe")


def gleiche_daten_pruefen(serien: Mapping[int, pd.DataFrame], stunden: pd.DataFrame,
                          nb18: Path = PROCESSED / "modell_stunden.parquet") -> pd.DataFrame:
    """Prüft, dass beide Modelle dieselben Messwerte bekommen.

    Vergleicht die LSTM-Stundentabelle mit den NB-00-Reihen (Ivelina) und,
    falls vorhanden, mit `modell_stunden.parquet` aus Notebook 18.
    """
    zeilen = [{"Prüfung": "Zähler in den NB-00-Reihen (Ivelina)", "Wert": len(serien)},
              {"Prüfung": "Zähler in der LSTM-Stundentabelle", "Wert": stunden["zaehler"].nunique()}]
    abw = 0.0
    for m, s in serien.items():
        t = stunden[stunden["zaehler"] == m].set_index("timestamp")
        abw = max(abw, float(np.nanmax(np.abs(t["ruecklauf"].to_numpy() - s["rt"].to_numpy()))
                             if len(t) else 0.0))
    zeilen.append({"Prüfung": "größte Abweichung Rücklauf LSTM-Tabelle zu NB 00 [K]", "Wert": abw})
    if Path(nb18).exists():
        alt = pd.read_parquet(nb18, columns=["zaehler", "timestamp", "ruecklauf", "durchfluss"])
        alt = alt.dropna(subset=["ruecklauf", "durchfluss"])
        neu = stunden.dropna(subset=["ruecklauf", "durchfluss"])
        m = alt.merge(neu, on=["zaehler", "timestamp"], suffixes=("_nb18", "_neu"))
        zeilen += [
            {"Prüfung": "gemessene Stunden in NB 18", "Wert": len(alt)},
            {"Prüfung": "gemessene Stunden hier", "Wert": len(neu)},
            {"Prüfung": "davon gleiche Zähler-Stunden", "Wert": len(m)},
            {"Prüfung": "größte Abweichung Rücklauf zu NB 18 [K]",
             "Wert": float((m["ruecklauf_nb18"] - m["ruecklauf_neu"]).abs().max())},
            {"Prüfung": "größte Abweichung Durchfluss zu NB 18 [l/h]",
             "Wert": float((m["durchfluss_nb18"] - m["durchfluss_neu"]).abs().max())}]
    return pd.DataFrame(zeilen)


# --- Fehler einbauen ----------------------------------------------------------

STOERUNGEN: Dict[str, Tuple[str, Optional[float]]] = {
    "Dauerdurchfluss 50 l/h": ("bypass", 50.0),
    "Dauerdurchfluss 150 l/h": ("bypass", 150.0),
    "Rücklauf +5 K": ("ruecklauf", 5.0),
    "schleichend +5 K in 30 Tagen": ("rampe", 5.0),
    "Regelhysterese 6 h": ("hysterese", 0.3),
    "Fühler hängt": ("fuehler", None),
}
STOERUNG_DAUER = 30          # Tage
RAMPE_TAGE = 30
HYSTERESE_HALB_H = 3         # 3 h auf, 3 h zu
MIN_RUECKLAUF_C = 20.0


def stoerung_einrechnen(serie: pd.DataFrame, start, art: str,
                        staerke: Optional[float] = None,
                        tage: int = STOERUNG_DAUER) -> pd.DataFrame:
    """Einen Fehler mit bekanntem Beginn in eine NB-00-Stundenreihe schreiben.

    Alle Spalten bleiben zueinander stimmig: Aus neuem Durchfluss und
    Rücklauf folgen Spreizung und Leistung, und die Energie- und
    Volumenzähler laufen ab dem Beginn um die Summe der Änderungen weiter.

    - ``bypass``: ``staerke`` l/h fließen zusätzlich, mit Vorlauftemperatur.
      Der Rücklauf mischt sich, die Leistung bleibt gleich.
    - ``ruecklauf``: Rücklauf + ``staerke`` K bei gleicher Leistung, also mehr
      Durchfluss (die Spreizung bleibt mindestens 1 K).
    - ``rampe``: wie ``ruecklauf``, aber linear von 0 auf ``staerke`` K in
      ``RAMPE_TAGE`` Tagen (schleichende Verschlechterung).
    - ``hysterese``: Das Ventil pendelt, 3 h ``1 + staerke``, 3 h
      ``1 - staerke`` des Durchflusses bei gleicher Stundenleistung.
      Tagesvolumen und Tagesenergie bleiben fast gleich.
    - ``fuehler``: Der Rücklauffühler bleibt auf seinem ersten Wert stehen.
      Der Zähler rechnet die Energie mit dem falschen Wert.
    """
    s = serie.copy()
    beginn = pd.Timestamp(start).normalize()
    ende = beginn + pd.Timedelta(days=tage)
    im = np.asarray((s.index >= beginn) & (s.index < ende))
    if not im.any():
        return s
    f0 = s.loc[im, "flow"].to_numpy(dtype=float)
    vl = s.loc[im, "vl"].to_numpy(dtype=float)
    rt0 = s.loc[im, "rt"].to_numpy(dtype=float)
    p0 = s.loc[im, "power"].to_numpy(dtype=float)
    dt0 = vl - rt0
    f1, rt1 = f0.copy(), rt0.copy()
    stunden = (s.index[im] - beginn) / pd.Timedelta(hours=1)
    mess = np.isfinite(f0) & np.isfinite(vl) & np.isfinite(rt0)
    zusatz_m3 = np.zeros(im.sum())
    if art == "bypass":
        q = float(staerke)
        f1 = np.where(np.isfinite(f0), f0 + q, np.nan)
        rt1 = np.where(mess, (rt0 * f0 + vl * q) / (f0 + q), rt0)
        #der Bypass fließt auch in Stunden ohne Messwert
        zusatz_m3 = np.where(np.isfinite(f0), 0.0, q / 1000.0)
    elif art in ("ruecklauf", "rampe"):
        anstieg = float(staerke) * (np.clip(stunden / (24.0 * RAMPE_TAGE), 0, 1)
                                    if art == "rampe" else 1.0)
        d = np.clip(anstieg, 0.0, np.clip(dt0 - 1.0, 0.0, None))
        d = np.where(mess & (f0 > 0), d, 0.0)
        rt1 = rt0 + d
        f1 = np.where(mess & (dt0 - d > 0), f0 * dt0 / np.where(dt0 - d > 0, dt0 - d, 1.0), f0)
    elif art == "hysterese":
        a = float(staerke)
        faktor = np.where((stunden // HYSTERESE_HALB_H) % 2 == 0, 1 + a, 1 - a)
        f1 = np.where(np.isfinite(f0), f0 * faktor, np.nan)
        rt1 = np.where(mess & (f0 > 0), np.maximum(vl - dt0 / faktor, MIN_RUECKLAUF_C), rt0)
        rt1 = np.minimum(rt1, vl)
    elif art == "fuehler":
        gueltig = np.flatnonzero(np.isfinite(rt0))
        if len(gueltig):
            rt1 = np.where(np.isfinite(rt0), rt0[gueltig[0]], np.nan)
    else:
        raise ValueError(f"unbekannte Störung {art}")
    dt1 = vl - rt1
    alt = f0 * dt0
    neu = f1 * dt1
    #Leistung im selben Verhältnis wie Durchfluss mal Spreizung; ohne Messwert physikalisch
    teiler = np.where(np.isfinite(alt) & (np.abs(alt) > 1e-9), alt, np.nan)
    p1 = np.where(np.isfinite(teiler) & np.isfinite(p0), p0 * neu / teiler,
                  np.where(np.isfinite(neu), KWH_JE_LH_K * neu, p0))
    p1 = np.clip(p1, 0.0, None)
    s.loc[im, "flow"] = f1
    s.loc[im, "rt"] = rt1
    s.loc[im, "dt"] = np.where(np.isfinite(dt1), dt1, s.loc[im, "dt"].to_numpy(dtype=float))
    s.loc[im, "power"] = p1
    #Zähler: Änderung je Stunde aufsummieren, danach bleibt der Versatz
    de = np.nan_to_num(p1 - p0) * 1.0
    dv = np.nan_to_num((f1 - f0) / 1000.0) + zusatz_m3
    kum_e, kum_v = np.cumsum(de), np.cumsum(dv)
    nach = np.asarray(s.index >= ende)
    for spalte, kum in (("energy", kum_e), ("volume", kum_v)):
        if spalte not in s.columns:
            continue
        werte = s[spalte].to_numpy(dtype=float).copy()
        werte[im] = werte[im] + kum
        werte[nach] = werte[nach] + kum[-1]
        s[spalte] = werte
    return s


# --- Modell Ivelina: Tagesmonitor ---------------------------------------------

def ivelina_tage(serien: Mapping[int, pd.DataFrame], temp: pd.Series) -> pd.DataFrame:
    """Nutzbare Heiztage mit Abkühlung und Tagesvolumen (`tagesmonitor`)."""
    return tm.modelltage(tm.alle_tageswerte(serien, temp))


def ivelina_referenz(mt: pd.DataFrame, termine: Mapping[int, Sequence],
                     lern_ende: Optional[pd.Timestamp] = LERN_ENDE) -> pd.DataFrame:
    """Referenzzeit je Station.

    ``lern_ende=None`` ist Ivelinas eigene Regel (`tagesmonitor.referenz`:
    erstes Jahr, spätestens 14 Tage vor der ersten Begehung). Sonst endet
    die Referenz am gemeinsamen Lernende oder 14 Tage vor einer früheren
    Begehung. Mindestens 60 Referenztage und 8 K Temperaturspanne wie bei ihr.
    """
    if lern_ende is None:
        return tm.referenz(mt, termine)
    zeilen = []
    for meter, d in mt.groupby("meter"):
        start = d["datum"].min()
        ende, grund = pd.Timestamp(lern_ende), "Lernende"
        spaeter = sorted(pd.Timestamp(t) for t in termine.get(int(meter), [])
                         if pd.Timestamp(t) > start)
        if spaeter and spaeter[0] - pd.Timedelta(days=tm.ABSTAND_BEGEHUNG) < ende:
            ende, grund = spaeter[0] - pd.Timedelta(days=tm.ABSTAND_BEGEHUNG), "vor Begehung"
        ref = d[(d["datum"] >= start) & (d["datum"] < ende)]
        spanne = float(ref["t_mittel_c"].max() - ref["t_mittel_c"].min()) if len(ref) else 0.0
        nachher = int((d["datum"] >= ende).sum())
        if len(ref) < tm.MIN_REF_TAGE:
            status = "zu wenige Referenztage"
        elif spanne < tm.MIN_REF_SPANNE_K:
            status = "zu kleine Temperaturspanne"
        elif nachher == 0:
            status = "keine Tage nach der Referenz"
        else:
            status = "ok"
        zeilen.append({"meter": int(meter), "ref_start": start, "ref_ende": ende,
                       "ende_grund": grund, "ref_tage": len(ref), "ref_spanne_k": spanne,
                       "ueberwachte_tage": nachher, "status": status,
                       "bhkw": int(meter) in nv.REFERENZ_AUSSCHLUSS})
    return pd.DataFrame(zeilen).set_index("meter")


def ivelina_verlauf(mt: pd.DataFrame, ref: pd.DataFrame, mod: dict) -> pd.DataFrame:
    """z-Werte je Station, Kanal und Heiztag nach der Referenz (ohne CUSUM)."""
    verlauf, _ = tm.monitor(mt, ref, mod)
    return verlauf


def ivelina_alarme(verlauf: pd.DataFrame, h: float = H_IVELINA) -> pd.DataFrame:
    """CUSUM je Station und Kanal wie `tagesmonitor.monitor`, mit Grenze ``h``.

    Bei h = 5 identisch mit `tagesmonitor.monitor`. Der Deckel des Kontos
    liegt bei mindestens 2 h (wie `prognose_waechter.cusum_alarme`).
    """
    zeilen = []
    for (meter, kanal), g in verlauf.groupby(["meter", "kanal"], sort=False):
        _, _, al = tm.cusum(g["z"].to_numpy(dtype=float), h=h,
                            deckel=max(tm.CUSUM_MAX, 2 * h))
        datum = g["datum"].to_numpy()
        for i, richtung, start in al:
            zeilen.append({"zaehler": int(meter), "datum": pd.Timestamp(datum[i]),
                           "kanal": kanal, "richtung": int(richtung),
                           "beginn": pd.Timestamp(datum[start])})
    a = pd.DataFrame(zeilen, columns=["zaehler", "datum", "kanal", "richtung", "beginn"])
    a["bewertung"] = ["schlechter" if (k, r) in ab.SCHLECHTER else "besser"
                      for k, r in zip(a["kanal"], a["richtung"])]
    return a


def ivelina_beobachtet(verlauf: pd.DataFrame) -> pd.DataFrame:
    v = verlauf[verlauf["kanal"] == "kwh_pro_m3"]
    return pd.DataFrame({"zaehler": v["meter"].astype(int).to_numpy(),
                         "datum": pd.to_datetime(v["datum"]).to_numpy()})


def ivelina_station(serie: pd.DataFrame, meter: int, temp: pd.Series,
                    ref: pd.DataFrame, mod: dict,
                    h: float = H_IVELINA) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Tagesmonitor für eine (z. B. gestörte) Stundenreihe mit festen Kennlinien."""
    mt = ivelina_tage({int(meter): serie}, temp)
    verlauf = ivelina_verlauf(mt, ref.loc[[int(meter)]], mod)
    return ivelina_beobachtet(verlauf), ivelina_alarme(verlauf, h)


# --- Modell LSTM: Prognose-Wächter -------------------------------------------

def trainiere(bauplan, lern: tuple, val: tuple, epochen: int, geduld: int, lr: float,
              geraet: Optional[str] = None, stapel: int = 512, seed: int = SEED,
              log=print, name: str = "") -> Tuple[object, pd.DataFrame]:
    """Training mit frühem Stopp nur auf der Validierung (wie das Audit).

    ``bauplan`` erzeugt das Netz, erst nach dem Setzen des Seeds, damit
    jeder Lauf mit denselben Startgewichten beginnt. Kein Testwert steuert
    das Training. Rückgabe: Modell mit den besten Gewichten und die Lernkurve.
    """
    import torch
    geraet = geraet or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(seed)
    modell = bauplan().to(geraet)
    lern = tuple(t.to(geraet) for t in lern)
    val = tuple(t.to(geraet) for t in val)
    opt = torch.optim.Adam(modell.parameters(), lr=lr)
    plan = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=max(4, geduld // 4),
                                                      min_lr=1e-5)
    gen = torch.Generator(device=geraet).manual_seed(seed)
    bester, zustand, stillstand, kurve = np.inf, None, 0, []
    t0 = time.monotonic()
    for epoche in range(1, epochen + 1):
        modell.train()
        summe = 0.0
        for teil in torch.randperm(len(lern[0]), generator=gen, device=geraet).split(stapel):
            opt.zero_grad(set_to_none=True)
            verlust = torch.nn.functional.mse_loss(modell(lern[0][teil], lern[1][teil]), lern[2][teil])
            verlust.backward()
            opt.step()
            summe += verlust.item() * len(teil)
        modell.eval()
        v = 0.0
        with torch.no_grad():
            for a in range(0, len(val[0]), 2048):
                sl = slice(a, a + 2048)
                v += torch.nn.functional.mse_loss(modell(val[0][sl], val[1][sl]), val[2][sl],
                                                  reduction="sum").item()
        v /= val[2].numel()
        plan.step(v)
        kurve.append({"runde": epoche, "lernen": summe / len(lern[0]), "validierung": v})
        if v < bester - 1e-5:
            bester, stillstand, zustand = v, 0, copy.deepcopy(modell.state_dict())
        else:
            stillstand += 1
        if stillstand >= geduld:
            break
    if zustand is None:
        raise ValueError(f"{name}: Validierungsfehler nie endlich (NaN in den Eingängen?)")
    modell.load_state_dict(zustand)
    log(f"{name}: {len(kurve)} Runden, bester Validierungsfehler {bester:.4f}, "
        f"{time.monotonic() - t0:.0f} s")
    return modell.eval(), pd.DataFrame(kurve)


def lstm_lernen(stunden: pd.DataFrame, stationen: Optional[Iterable[int]] = None,
                seed: int = SEED, log=print, nur_warm: bool = False) -> dict:
    """Prognose-LSTM aus `prognose_waechter` neu lernen, gemeinsame Zeitachse.

    Lernziele vor ``LERN_ENDE``, frühes Stoppen auf der Probezeit. Mit
    ``stationen`` lernt es nur auf diesen (für den Test mit neuen HAST).
    Die Skalierung des Durchflusses je Station kommt nur aus ihren eigenen
    Tagen vor ``LERN_ENDE``.
    """
    werte, tage = pw.tagesfeld(stunden)
    voll = tage["mit_vorgeschichte"].to_numpy()
    erlaubt = (np.ones(len(tage), bool) if stationen is None
               else tage["zaehler"].isin([int(s) for s in stationen]).to_numpy())
    lz = np.flatnonzero(voll & erlaubt & (tage["tag"] < LERN_ENDE).to_numpy())
    vz = np.flatnonzero(voll & erlaubt & (tage["tag"] >= VAL_START).to_numpy()
                        & (tage["tag"] < VAL_ENDE).to_numpy())
    if nur_warm:
        #Sommer-Fassung: nur warme Tage als Ziel (Tagesmittel ab 15 °C), Eingänge bleiben die 7 Vortage
        warm = ~tage["heiztag"].to_numpy()
        lz, vz = lz[warm[lz]], vz[warm[vz]]
    roh = [np.unique((i[:, None] + np.arange(-pw.VORGESCHICHTE, 1)).ravel()) for i in (lz, vz)]
    assert not np.intersect1d(*roh).size, "Lern- und Probezeit teilen Rohdatentage"
    lern_roh = np.zeros(len(tage), bool)
    lern_roh[roh[0]] = True
    skal = pw.skalierung_lernen(werte, tage, lern_roh)
    #eigene Vergangenheit vor dem Lernende für Stationen, die nicht mitlernen
    eigen = (tage["tag"] < LERN_ENDE).to_numpy()
    fluss = pd.DataFrame({"zaehler": np.repeat(tage["zaehler"].to_numpy()[eigen], 24),
                          "fl": werte[eigen, :, pw.FL].ravel()})
    q = fluss.groupby("zaehler")["fl"].quantile(0.95).clip(lower=1.0)
    n = tage[eigen].groupby("zaehler").size()
    skal["fl_teiler"] = skal["fl_teiler"].combine_first(q[n >= MIN_VAL_TAGE])
    #ohne eigenen Teiler keine Skala: solche Stationen sind nicht vorhersagbar
    vz = vz[tage.loc[vz, "zaehler"].isin(skal["fl_teiler"].index).to_numpy()]
    x = pw.skalieren(werte, tage, skal)
    netz, kurve = trainiere(pw.netz, pw.eingaenge(x, lz), pw.eingaenge(x, vz), 200, 15, 0.002,
                            seed=seed, log=log, name="Prognose-LSTM")
    return {"modell": netz, "skalierung": skal, "lernkurve": kurve,
            "lern_ziele": int(len(lz)), "val_ziele": int(len(vz)),
            "lern_stationen": sorted(tage.loc[lz, "zaehler"].unique().tolist()),
            "werte": werte, "tage": tage}


def lstm_tage(modell, skal: dict, stunden: Optional[pd.DataFrame] = None,
              feld: Optional[Tuple[np.ndarray, pd.DataFrame]] = None,
              erwartung: str = "lstm", ab: pd.Timestamp = VAL_START) -> pd.DataFrame:
    """Tagesabweichungen (gemessen minus erwartet) ab ``ab``, wie `prognose_waechter`."""
    werte, tage = feld if feld is not None else pw.tagesfeld(stunden)
    ziel = np.flatnonzero(tage["mit_vorgeschichte"].to_numpy()
                          & tage["zaehler"].isin(skal["fl_teiler"].index).to_numpy()
                          & (tage["tag"] >= ab).to_numpy())
    if erwartung == "lstm":
        x = pw.skalieren(werte, tage, skal)
        rl, fl = pw.vorhersagen(modell, x, tage, ziel, skal)
    else:
        rl, fl = pw.wochenmittel(werte, ziel)
    abw = pw.abweichungen(werte, tage, ziel, rl, fl)
    abw["mae_rl"] = np.abs(werte[ziel][:, :, pw.RL] - rl).mean(axis=1)
    abw["mae_fluss"] = np.abs(werte[ziel][:, :, pw.FL] - fl).mean(axis=1)
    return abw.sort_values(["zaehler", "tag"]).reset_index(drop=True)


def lstm_kalibrieren(abw: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Normale Schwankung je Station und Faktor je Tagesart.

    Lage und Streuung je Station kommen aus dem ersten Teil der Probezeit
    (`prognose_waechter.kalibrieren`, mindestens 10 Tage je Station). Im
    Februar und März gibt es fast nur Heiztage, deshalb kommen die zwei
    Faktoren (Heiztag, warmer Tag) aus der ganzen Probezeit.
    """
    kal, _ = pw.kalibrieren(abw[(abw["tag"] >= VAL_START) & (abw["tag"] < WAHL_START)])
    val = abw[(abw["tag"] >= VAL_START) & (abw["tag"] < VAL_ENDE) & abw["zaehler"].isin(kal.index)]
    roh = pw.z_werte(val, kal, None)
    faktor = pd.DataFrame({k: roh.groupby("heiztag")[k].apply(pw.mad)
                           for k in ("z_rl", "z_fluss")}).clip(lower=pw.MIN_FAKTOR)
    return kal, faktor


def lstm_z(abw: pd.DataFrame, kal: pd.DataFrame, faktor: pd.DataFrame) -> pd.DataFrame:
    z = pw.z_werte(abw[abw["zaehler"].isin(kal.index)], kal, faktor)
    return z.sort_values(["zaehler", "tag"]).reset_index(drop=True)


def _alarmzeilen(z: pd.DataFrame, maske: np.ndarray) -> pd.DataFrame:
    a = z.loc[maske, ["zaehler", "tag", "z_rl", "z_fluss"]]
    rl = a["z_rl"].abs() >= a["z_fluss"].abs()
    kanal = np.where(rl, "ruecklauf", "nachtdurchfluss")
    richtung = np.sign(np.where(rl, a["z_rl"], a["z_fluss"])).astype(int)
    return pd.DataFrame({"zaehler": a["zaehler"].astype(int).to_numpy(),
                         "datum": pd.to_datetime(a["tag"]).to_numpy(),
                         "kanal": kanal, "richtung": richtung})


def lstm_alarme(z: pd.DataFrame, kal: pd.DataFrame, regel: str, wert: float) -> pd.DataFrame:
    """Alarme nach Schwellenregel (|z| ≥ wert an 2 Tagen) oder CUSUM (Grenze h = wert).

    Gleiche Regeln wie `prognose_waechter` (Warnung an zwei Tagen, 7 Tage
    Ruhe; CUSUM mit Vergrößerung der Streuung für ähnliche Folgetage).
    Höherer Rücklauf oder mehr Nachtdurchfluss heißt schlechter.
    """
    if regel == "schwelle":
        warn = pw.warnungen(z, wert)
        a = _alarmzeilen(z, pw.alarme_aus_warnungen(z, warn, pw.RUHE).to_numpy())
    elif regel == "cusum":
        zeilen = []
        for meter, g in z.groupby("zaehler", sort=False):
            if meter not in kal.index:
                continue
            for kanal, spalte, phi_spalte in (("ruecklauf", "z_rl", "phi_rl"),
                                              ("nachtdurchfluss", "z_fluss", "phi_fluss")):
                phi = float(kal.at[meter, phi_spalte])
                werte = g[spalte].to_numpy(dtype=float) / np.sqrt((1 + phi) / (1 - phi))
                ok = np.isfinite(werte)
                _, _, al = tm.cusum(werte[ok], k=pw.CUSUM_K, h=wert,
                                    deckel=max(tm.CUSUM_MAX, 2 * wert))
                tage = g["tag"].to_numpy()[ok]
                zeilen += [{"zaehler": int(meter), "datum": pd.Timestamp(tage[i]),
                            "kanal": kanal, "richtung": int(r)} for i, r, _ in al]
        a = pd.DataFrame(zeilen, columns=["zaehler", "datum", "kanal", "richtung"])
    else:
        raise ValueError("regel muss 'schwelle' oder 'cusum' sein")
    a["bewertung"] = np.where(a["richtung"] > 0, "schlechter", "besser")
    return a


def lstm_beobachtet(z: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"zaehler": z["zaehler"].astype(int).to_numpy(),
                         "datum": pd.to_datetime(z["tag"]).to_numpy(),
                         "heiztag": z["heiztag"].to_numpy()})


# --- Alarmlast -----------------------------------------------------------------

def nur_tage(alarme: pd.DataFrame, tage: pd.DataFrame) -> pd.DataFrame:
    """Alarme an den Zähler-Tagen aus ``tage`` (schnelle Fassung von `pruefstand.auf_tagen`)."""
    if len(alarme) == 0:
        return alarme
    erlaubt = pd.MultiIndex.from_arrays([tage["zaehler"].astype(int),
                                         pd.to_datetime(tage["datum"])])
    schluessel = pd.MultiIndex.from_arrays([alarme["zaehler"].astype(int),
                                            pd.to_datetime(alarme["datum"])])
    return alarme[schluessel.isin(erlaubt)]


def gemeinsame_tage(*tabellen: pd.DataFrame) -> pd.DataFrame:
    menge = None
    for t in tabellen:
        idx = pd.MultiIndex.from_arrays([t["zaehler"].astype(int), pd.to_datetime(t["datum"])])
        menge = idx.unique() if menge is None else menge.intersection(idx)
    return (pd.DataFrame({"zaehler": menge.get_level_values(0), "datum": menge.get_level_values(1)})
            .sort_values(["zaehler", "datum"]).reset_index(drop=True))


def je_station_und_jahr(n_alarme: int, tage: pd.DataFrame) -> float:
    """Alarme je Station und Jahr: Alarme durch beobachtete Stationstage / 365,25."""
    return n_alarme / (len(tage) / 365.25) if len(tage) else np.nan


def gleiche_alarmlast(alarme_fuer, raster: Sequence[float], ziel: int,
                      tage: pd.DataFrame) -> Tuple[float, pd.DataFrame]:
    """Wert aus ``raster``, dessen Alarmzahl auf ``tage`` am nächsten an ``ziel`` liegt.

    Bei gleichem Abstand gewinnt der strengere Wert (weniger Alarme), wie
    `pruefstand.budget_anpassen`.
    """
    zeilen = [{"wert": w, "alarme": len(nur_tage(alarme_fuer(w), tage))} for w in raster]
    tab = pd.DataFrame(zeilen)
    tab["abstand"] = (tab["alarme"] - ziel).abs()
    bester = tab.sort_values(["abstand", "wert"], ascending=[True, False]).iloc[0]
    return float(bester["wert"]), tab.drop(columns="abstand")


# --- Test A: echte Begehungen ---------------------------------------------------

def begehungsfaelle(termine: Mapping[int, Sequence], ab: pd.Timestamp = TEST_START) -> pd.DataFrame:
    zeilen = [(int(m), pd.Timestamp(d).normalize()) for m, ds in termine.items() for d in ds
              if pd.Timestamp(d) >= ab + pd.Timedelta(days=7)]
    return pd.DataFrame(sorted(set(zeilen)), columns=["zaehler", "datum"])


def konfusion_begehungen(treffer: pd.DataFrame) -> dict:
    """Vierfeldertafel: Begehungsfenster und Kontrollfenster gegen Alarm.

    Die Kontrollfenster sind dieselben Datumsfenster an Stationen ohne
    Begehung. Sie überlappen sich und sind deshalb keine unabhängigen
    Fälle; sie zeigen die Grundrate der Alarme.
    """
    n_k = treffer["n_kontrolle"].sum()
    k_alarm = float((treffer["kontrollquote"] * treffer["n_kontrolle"]).sum())
    return {"Begehung, Alarm": int(treffer["treffer"].sum()),
            "Begehung, kein Alarm": int((~treffer["treffer"].astype(bool)).sum()),
            "Kontrolle, Alarm": int(round(k_alarm)),
            "Kontrolle, kein Alarm": int(round(n_k - k_alarm))}


# --- Test B: eingebaute Fehler --------------------------------------------------

def stoerfaelle(serien: Mapping[int, pd.DataFrame], stationen: Sequence[int],
                termine: Mapping[int, Sequence], saisons: Mapping[str, Tuple[str, str]],
                seed: int = SEED, min_anteil: float = 0.8) -> pd.DataFrame:
    """Je Station und Jahreszeit ein zufälliger Beginn ohne Begehung in der Nähe.

    Erlaubt sind Tage, ab denen die Station in den folgenden 30 Tagen zu
    mindestens ``min_anteil`` der Stunden gemessen hat, und ohne Begehung
    von 60 Tagen vor dem Beginn bis 14 Tage nach dem Ende der Störung. So
    liegt keine echte Maßnahme im Fenster. Die Auswahl hängt nur von Daten
    und Terminen ab, nicht von den Modellen.
    """
    rng = np.random.default_rng(seed)
    zeilen = []
    for saison, (von, bis) in saisons.items():
        tage = pd.date_range(von, bis, freq="D")
        for m in sorted(int(s) for s in stationen):
            stunden = serien[m]["flow"].dropna().index.normalize().value_counts()
            erlaubt = []
            for beginn in tage:
                lo = beginn - pd.Timedelta(days=60)
                hi = beginn + pd.Timedelta(days=STOERUNG_DAUER + 14)
                if any(lo <= pd.Timestamp(t) <= hi for t in termine.get(m, [])):
                    continue
                fenster = pd.date_range(beginn, periods=STOERUNG_DAUER, freq="D")
                if stunden.reindex(fenster).fillna(0).sum() >= min_anteil * 24 * STOERUNG_DAUER:
                    erlaubt.append(beginn)
            if erlaubt:
                zeilen.append({"zaehler": m, "saison": saison,
                               "beginn": erlaubt[rng.integers(0, len(erlaubt))]})
    return pd.DataFrame(zeilen, columns=["zaehler", "saison", "beginn"])


def fensterergebnis(alarme: pd.DataFrame, beobachtet: pd.DataFrame, beginn: pd.Timestamp,
                    fenster: int, min_tage: int = 5) -> dict:
    """Alarm im Fenster ab ``beginn``? Mit Verzögerung und Zahl beobachteter Tage."""
    bis = beginn + pd.Timedelta(days=fenster)
    d = pd.to_datetime(beobachtet["datum"])
    n = int(((d >= beginn) & (d < bis)).sum())
    a = pd.to_datetime(alarme["datum"]) if len(alarme) else pd.Series(dtype="datetime64[ns]")
    im = a[(a >= beginn) & (a < bis)]
    return {"bewertbar": n >= min_tage, "beobachtet": n, "alarm": bool(len(im)),
            "tage_bis_alarm": int((im.min() - beginn).days) if len(im) else np.nan}


# --- Fehlerart je Station ----------------------------------------------------

def grenze_vor_begehung(labels: pd.DataFrame, zaehler: Iterable[int]) -> pd.Series:
    return fk.grenze_vor_begehung(labels, list(zaehler))


def kennzahlen_vor_begehung(stunden: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Kennzahlen aus Winter 23/24 und Sommer 2024, nur vor der ersten Begehung (NB 18).

    Die Auslastung zum Vertrag vor der Begehung (``auslastung_vertrag``)
    wird nur für die Regel Überdimensionierung gebraucht.
    """
    grenze = grenze_vor_begehung(labels, stunden["zaehler"].unique())
    return fk.kennzahlen(stunden, WINTER, SOMMER, grenze=grenze,
                         vertrag=labels["vertrag_alt_kw"])


def basis_stationen(kz: pd.DataFrame, labels: pd.DataFrame, emb_alle: pd.DataFrame) -> pd.DataFrame:
    """Begangene Stationen mit Winter-Embedding und Sommerkennzahl (Notebook 22, 32 und Audit)."""
    return fk.trainingsdaten(kz, emb_alle, labels)


def _embedding_skalieren(werte: np.ndarray, tage: pd.DataFrame, lern_roh: np.ndarray,
                         eigen: np.ndarray) -> np.ndarray:
    """Temperaturen mit Mittel/Streuung der Lerntage, Leistung/Durchfluss je Station
    durch das eigene 95-%-Quantil vor der Begehung (eigene Vergangenheit)."""
    x = werte.copy()
    ids = tage["zaehler"].to_numpy()
    for j, kanal in enumerate(fk.EMB_KANAELE):
        if kanal in ("leistung", "durchfluss"):
            f = pd.DataFrame({"m": np.repeat(ids[eigen], 24), "v": werte[eigen, :, j].ravel()})
            q = f.groupby("m")["v"].quantile(0.95).clip(lower=1e-3)
            lern_q = pd.DataFrame({"m": np.repeat(ids[lern_roh], 24),
                                   "v": werte[lern_roh, :, j].ravel()}).groupby("m")["v"].quantile(0.95)
            teiler = pd.Series(ids).map(q).fillna(float(lern_q.median())).to_numpy(np.float32)
            x[:, :, j] = werte[:, :, j] / teiler[:, None]
        else:
            mittel, streu = werte[lern_roh, :, j].mean(), werte[lern_roh, :, j].std()
            x[:, :, j] = (werte[:, :, j] - mittel) / max(streu, 1e-6)
    return x


def embedding_lernen(stunden: pd.DataFrame, labels: pd.DataFrame,
                     ohne: Iterable[int] = (), seed: int = SEED, log=print,
                     feld: Optional[tuple] = None) -> dict:
    """LSTM-Encoder aus Notebook 20 ohne die Stationen ``ohne`` lernen.

    Gelernt wird auf allen anderen Stationen (auch unbegangenen, das Netz
    sieht keine Labels), nur aus Tagen vor der ersten Begehung bzw. dem
    Stichtag. Zeitliche Trennung für das frühe Stoppen: Zieltage vor dem
    01.07.2024 lernen, ab dem 02.07.2024 prüfen (wie das Audit).
    Rückgabe: Netz und mittlere Embeddings je Station für Winter und Sommer.
    """
    import torch
    ohne = [int(m) for m in ohne]
    werte, tage, _ = feld if feld is not None else fk._tagesfeld(stunden)
    grenze = tage["zaehler"].map(grenze_vor_begehung(labels, tage["zaehler"].unique())).fillna(STICHTAG)
    vorher = (tage["tag"] < grenze).to_numpy()
    folge = (tage["zaehler"].shift(-1).eq(tage["zaehler"])
             & tage["tag"].shift(-1).eq(tage["tag"] + pd.Timedelta(days=1))).to_numpy()
    heute = np.flatnonzero(folge & vorher & np.roll(vorher, -1))
    morgen = heute + 1
    lernbar = ~tage["zaehler"].isin(ohne).to_numpy()
    lz = np.flatnonzero(lernbar[heute] & (tage["tag"].to_numpy()[morgen] < np.datetime64("2024-07-01")))
    vz = np.flatnonzero(lernbar[heute] & (tage["tag"].to_numpy()[heute] >= np.datetime64("2024-07-02")))
    lern_roh = np.zeros(len(tage), bool)
    lern_roh[np.r_[heute[lz], morgen[lz]]] = True
    assert not tage.loc[lern_roh, "zaehler"].isin(ohne).any(), "Teststation im Encodertraining"
    x = _embedding_skalieren(werte, tage, lern_roh, vorher)

    def tensoren(i):
        return (torch.from_numpy(x[heute[i]]), torch.from_numpy(x[morgen[i], :, 5:6]),
                torch.from_numpy(x[morgen[i], :, :5]))

    netz, kurve = trainiere(fk.embedding_netz, tensoren(lz), tensoren(vz), 300, 20, 0.003,
                            seed=seed, log=log, name="LSTM-Encoder")
    geraet = next(netz.parameters()).device
    with torch.no_grad():
        kern = np.concatenate([netz.einbetten(torch.from_numpy(x[a:a + 4096]).to(geraet)).cpu().numpy()
                               for a in range(0, len(x), 4096)])
    tab = pd.DataFrame(kern, columns=[f"z{i}" for i in range(8)])
    tab["zaehler"], tab["tag"] = tage["zaehler"].to_numpy(), tage["tag"].to_numpy()
    tab = tab[vorher]
    teile = []
    for name, (von, bis) in (("w2324", WINTER), ("s2024", SOMMER)):
        t = tab[(tab["tag"] >= von) & (tab["tag"] < bis)]
        m = t.groupby("zaehler")[[f"z{i}" for i in range(8)]].mean()
        m = m[t.groupby("zaehler").size() >= fk.EMB_MIN_TAGE]
        teile.append(m.add_prefix(f"lstm_{name}_"))
    emb = pd.concat(teile, axis=1).reindex(columns=EMB)
    return {"netz": netz, "embedding": emb, "lernkurve": kurve,
            "skalierung": embedding_skalierung_paket(werte, tage, lern_roh, vorher),
            "lern_paare": int(len(lz)), "val_paare": int(len(vz)),
            "lern_stationen": int(tage.loc[lern_roh, "zaehler"].nunique())}


try:
    from xgboost import XGBClassifier as _XGBClassifier

    class XGBAusgeglichen(_XGBClassifier):
        """XGBoost, das die seltene Klasse in jedem Lernteil neu gewichtet (Notebook 22, Zelle 14)."""

        def fit(self, X, y, **kwargs):
            self.set_params(scale_pos_weight=(len(y) - np.sum(y)) / max(np.sum(y), 1))
            return super().fit(X, y, **kwargs)
except ImportError:          # xgboost fehlt: nur die XGBoost-Kandidaten fallen weg
    XGBAusgeglichen = None


def kandidat(name: str):
    """Modell und Suchraster; das Raster wird nur im inneren Lernteil durchsucht."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if name.startswith("LR"):
        pipe = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                             StandardScaler(),
                             LogisticRegression(class_weight="balanced", max_iter=5000))
        return pipe, {"logisticregression__C": [0.03, 0.1, 0.3, 1.0]}
    if name.startswith("XGBoost"):
        xgb = XGBAusgeglichen(learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                              min_child_weight=2, n_jobs=1, random_state=SEED, verbosity=0)
        return xgb, {"max_depth": [1, 2, 3], "n_estimators": [100, 300]}
    raise ValueError(name)


MERKMALSSAETZE = {"LR Kennzahlen": KENNZAHLEN,
                  "LR Kennzahlen + LSTM": KENNZAHLEN + EMB,
                  "LR nur LSTM-Embedding": EMB,
                  "XGBoost Kennzahlen": KENNZAHLEN,
                  "XGBoost Kennzahlen + LSTM": KENNZAHLEN + EMB}


def innen_suchen(name: str, X: pd.DataFrame, y: np.ndarray, gruppen: np.ndarray):
    """GridSearch mit gruppierter innerer Kreuzvalidierung, nur auf dem Lernteil."""
    from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
    modell, raster = kandidat(name)
    n_pos = int(y.sum())
    k = max(2, min(4, n_pos, len(y) - n_pos))
    folds = list(StratifiedGroupKFold(k, shuffle=True, random_state=0).split(X, y, gruppen))
    suche = GridSearchCV(modell, raster, cv=folds, scoring="roc_auc", n_jobs=1, error_score=np.nan)
    return suche.fit(X, y)


def aeussere_folds(basis: pd.DataFrame, gruppen: pd.Series) -> List[Tuple[np.ndarray, np.ndarray]]:
    from sklearn.model_selection import StratifiedGroupKFold
    return list(StratifiedGroupKFold(N_FOLDS, shuffle=True, random_state=FOLD_SEED).split(
        basis, basis["ventil"].astype(int), gruppen.reindex(basis.index)))


def xgb_beitraege(modell, X: pd.DataFrame) -> pd.DataFrame:
    """Beitrag jedes Merkmals zum Ergebnis (TreeSHAP, in XGBoost eingebaut).

    Spalte ``basis`` ist der Ausgangswert; Summe aller Spalten ist der
    Logit des Modells, daraus p = 1 / (1 + exp(-Summe)).
    """
    import xgboost
    b = modell.get_booster().predict(xgboost.DMatrix(X, missing=np.nan), pred_contribs=True)
    return pd.DataFrame(b, index=X.index, columns=[*X.columns, "basis"])


# --- Modell Ivelina: Netzvergleich, Fehlerbild, Priorität ------------------------

def netzvergleich(serien: Mapping[int, pd.DataFrame], termine: Mapping[int, Sequence],
                  anschluss: Mapping[int, float], bhkw: Iterable[int]) -> dict:
    """Ivelinas Netzvergleich je Kernwinter, genau wie `stationsblatt.rechne`.

    Ohne Labels: Jede Station wird gegen den Median der übrigen Stationen
    desselben Winters gemessen. Stunden um eine Begehung fallen heraus.
    """
    ref_aus = tuple(sorted(int(m) for m in bhkw)) or nv.REFERENZ_AUSSCHLUSS
    punkte = {int(m): sb.punkttabelle(df, int(m), "stunde") for m, df in serien.items()}
    tabelle, ausschluss = nv.winterkennzahlen(punkte, anschluss, termine)
    bezogen = nv.netzbezug(tabelle, referenz_ausschluss=ref_aus)
    kz, _ = nv.score_kennzahlen(bezogen)
    markiert = nv.markiere(bezogen, kz)
    potenzial = nv.potenzial_je_winter(tabelle, kz, ref_aus)
    fehlerbild = ab.fehlerbild_je_winter(markiert, list(kz))
    return {"tabelle": tabelle, "ausschluss": ausschluss, "markiert": markiert,
            "kennzahlen": kz, "potenzial": potenzial, "fehlerbild": fehlerbild,
            "referenz_ausschluss": ref_aus}


def ivelina_je_station(netz: dict, winter: str, alarme_wie_gebaut: Optional[pd.DataFrame] = None
                       ) -> pd.DataFrame:
    """Ivelinas Ausgaben für einen Winter je Station: Score, Fehlerbild, Potenzial, Priorität."""
    m = netz["markiert"]
    m = m[(m["winter"] == winter) & m["score"].notna()].set_index("meter")
    fb = netz["fehlerbild"]
    fb = fb[fb["winter"] == winter].set_index("meter")
    pot = netz["potenzial"]
    pot = pot[pot["winter"] == winter].set_index("meter")
    out = pd.DataFrame({"netz_score": m["score"], "auffaellig": m["auffaellig"].astype(bool),
                        "rang": m["rang"], "fehlerbild": fb["fehlerbild"].reindex(m.index).fillna(""),
                        "schlechte_kennzahlen": fb["schlechte_kennzahlen"].reindex(m.index).fillna(""),
                        "potenzial_score": pot["potenzial_score"].reindex(m.index),
                        "potenzial": pot["potenzial"].reindex(m.index)})
    if alarme_wie_gebaut is not None:
        a = alarme_wie_gebaut.rename(columns={"zaehler": "meter"})
        prio = ab.prioritaet_je_winter(netz["markiert"][netz["markiert"]["winter"] == winter], a)
        prio = prio.set_index("meter")
        out["prioritaet"] = prio["prioritaet"].reindex(out.index)
        out["alarme_schlechter"] = prio["alarme_schlechter"].reindex(out.index)
    out.index.name = "zaehler"
    return out


def folie5_ivelina(fehlerbild: pd.Series) -> pd.Series:
    regelung = FEHLERBILD_ZU_ZIEL["durchfluss"] | FEHLERBILD_ZU_ZIEL["temperatur"]
    return pd.Series(np.select([fehlerbild.eq("ventil"), fehlerbild.isin(regelung)],
                               [F5_REPARATUR, F5_REGELUNG], F5_KEINE), index=fehlerbild.index)


def folie5_lstm(p_ventil: pd.Series, kmeans: pd.Series) -> pd.Series:
    return pd.Series(np.select([p_ventil >= GRENZE, kmeans.eq("schlechter")],
                               [F5_REPARATUR, F5_REGELUNG], F5_KEINE), index=p_ventil.index)


def folie5_befund(labels: pd.DataFrame) -> pd.Series:
    """Was bei der Begehung gemacht wurde, in den drei Klassen nach Folie 5.

    Reparatur: Ventil. Regelungsoptimierung: Durchfluss neu eingestellt
    oder Rücklauf-Sollwert gesenkt. Sonst keine dieser Maßnahmen (das heißt
    nicht, dass die Station in Ordnung war).
    """
    v = labels["ventil"].astype(bool)
    r = labels["durchfluss"].astype(bool) | labels["temperatur"].astype(bool)
    return pd.Series(np.select([v, r], [F5_REPARATUR, F5_REGELUNG], F5_KEINE), index=labels.index)


# --- Kennzahlen ----------------------------------------------------------------

def vierfeld(y, entscheidung) -> dict:
    """Konfusionsmatrix einer Ja/Nein-Entscheidung gegen den Befund, mit Precision und Recall."""
    y = np.asarray(y, dtype=bool)
    e = np.asarray(entscheidung, dtype=bool)
    tp, fn = int((y & e).sum()), int((y & ~e).sum())
    fp, tn = int((~y & e).sum()), int((~y & ~e).sum())
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * prec * rec / (prec + rec) if tp else 0.0
    return {"gefunden": tp, "übersehen": fn, "Fehlalarm": fp,
            "richtig ruhig": tn, "Precision": prec, "Recall": rec, "F1": f1}


def bootstrap_auc(y, score, gruppen=None, n: int = 2000, seed: int = SEED) -> Tuple[float, float, float]:
    """AUC und 95-%-Intervall, gezogen werden ganze Stationsgruppen."""
    from sklearn.metrics import roc_auc_score
    y, s = np.asarray(y, dtype=int), np.asarray(score, dtype=float)
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    g = np.arange(len(y)) if gruppen is None else np.asarray(gruppen)[ok]
    if len(np.unique(y)) < 2:
        return np.nan, np.nan, np.nan
    einheiten = [np.flatnonzero(g == u) for u in np.unique(g)]
    rng = np.random.default_rng(seed)
    werte = []
    for _ in range(n):
        i = np.concatenate([einheiten[j] for j in rng.integers(0, len(einheiten), len(einheiten))])
        if 0 < y[i].sum() < len(i):
            werte.append(roc_auc_score(y[i], s[i]))
    return (float(roc_auc_score(y, s)), float(np.quantile(werte, 0.025)),
            float(np.quantile(werte, 0.975)))


def bootstrap_auc_differenz(y, a, b, gruppen=None, n: int = 2000, seed: int = SEED
                            ) -> Tuple[float, float, float]:
    """AUC(a) - AUC(b) auf denselben Stationen, gepaartes Intervall."""
    from sklearn.metrics import roc_auc_score
    y, a, b = (np.asarray(y, dtype=int), np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    ok = np.isfinite(a) & np.isfinite(b)
    y, a, b = y[ok], a[ok], b[ok]
    g = np.arange(len(y)) if gruppen is None else np.asarray(gruppen)[ok]
    einheiten = [np.flatnonzero(g == u) for u in np.unique(g)]
    rng = np.random.default_rng(seed)
    werte = []
    for _ in range(n):
        i = np.concatenate([einheiten[j] for j in rng.integers(0, len(einheiten), len(einheiten))])
        if 0 < y[i].sum() < len(i):
            werte.append(roc_auc_score(y[i], a[i]) - roc_auc_score(y[i], b[i]))
    d = roc_auc_score(y, a) - roc_auc_score(y, b)
    return float(d), float(np.quantile(werte, 0.025)), float(np.quantile(werte, 0.975))


def bootstrap_anteil(werte, gruppen=None, n: int = 2000, seed: int = SEED
                     ) -> Tuple[float, float, float]:
    """Anteil mit 95-%-Intervall, gezogen werden ganze Stationen."""
    w = np.asarray(werte, dtype=float)
    g = np.arange(len(w)) if gruppen is None else np.asarray(gruppen)
    einheiten = [np.flatnonzero(g == u) for u in np.unique(g)]
    if not einheiten:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    z = [w[np.concatenate([einheiten[j] for j in rng.integers(0, len(einheiten), len(einheiten))])].mean()
         for _ in range(n)]
    return float(w.mean()), float(np.quantile(z, 0.025)), float(np.quantile(z, 0.975))


def kappa(a: pd.Series, b: pd.Series) -> float:
    from sklearn.metrics import cohen_kappa_score
    ok = a.notna() & b.notna()
    return float(cohen_kappa_score(a[ok].astype(str), b[ok].astype(str)))


# --- Grafiken --------------------------------------------------------------------

FARBE_IVELINA = "#2563EB"
FARBE_LSTM = "#DC2626"
FARBE_XGB = "#7C3AED"
FARBE_REGEL = "#6B7280"


def zeichne_vierfeld(ax, werte: Mapping[str, int], titel: str,
                     zeile_ja: str = "mit Befund", zeile_nein: str = "ohne Befund",
                     spalte_ja: str = "Modell meldet", spalte_nein: str = "Modell meldet nicht",
                     woerter: Sequence[str] = ("gefunden", "übersehen", "Fehlalarm", "richtig ruhig"),
                     schluessel: Optional[Sequence[str]] = None) -> None:
    """Konfusionsmatrix mit Wörtern statt TP/FN/FP/TN."""
    schluessel = list(schluessel or woerter)
    zahlen = np.array([[werte[schluessel[0]], werte[schluessel[1]]],
                       [werte[schluessel[2]], werte[schluessel[3]]]], dtype=float)
    farben = np.array([["#BBF7D0", "#FECACA"], ["#FDE68A", "#E5E7EB"]])
    for i in range(2):
        for j in range(2):
            ax.add_patch(__import__("matplotlib").patches.Rectangle((j, 1 - i), 1, 1,
                                                                   color=farben[i, j], ec="white", lw=2))
            ax.text(j + 0.5, 1.5 - i + 0.12, f"{int(zahlen[i, j])}", ha="center", va="center",
                    fontsize=17, fontweight="bold")
            ax.text(j + 0.5, 1.5 - i - 0.2, woerter[2 * i + j], ha="center", va="center", fontsize=9)
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.set_xticks([0.5, 1.5], [spalte_ja, spalte_nein], fontsize=9)
    ax.set_yticks([1.5, 0.5], [zeile_ja, zeile_nein], fontsize=9)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(titel, fontsize=10)


def zeichne_matrix(ax, tabelle: pd.DataFrame, titel: str, xlabel: str, ylabel: str) -> None:
    """Mehrklassen-Konfusionsmatrix (Zeilen: Befund, Spalten: Modell)."""
    z = tabelle.to_numpy(dtype=float)
    ax.imshow(z, cmap="Blues", vmin=0, vmax=max(z.max(), 1))
    for i in range(z.shape[0]):
        for j in range(z.shape[1]):
            ax.text(j, i, f"{int(z[i, j])}", ha="center", va="center", fontsize=13,
                    color="white" if z[i, j] > 0.6 * z.max() else "black", fontweight="bold")
    import textwrap
    ax.set_xticks(range(z.shape[1]), [textwrap.fill(str(c), 13) for c in tabelle.columns], fontsize=8)
    ax.set_yticks(range(z.shape[0]), [textwrap.fill(str(c), 16) for c in tabelle.index], fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(titel, fontsize=10)


def speichere(fig, name: str, ordner: Path = AUSGABE / "abbildungen") -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{name}.png"
    fig.savefig(pfad, dpi=130, bbox_inches="tight", facecolor="white")
    return pfad


# --- Modellpakete ----------------------------------------------------------------

def paket_normalmodell(ref: pd.DataFrame, mod: dict, modtab: pd.DataFrame, version: str,
                       kennzahlen: dict, lernzeitraum: str, datenstand) -> mp.Paket:
    """Paket ``normalmodell`` im Format, das `normalmodell_waechter.lade` liest."""
    from . import normalmodell_waechter as nw
    kennlinien = [{"zaehler": int(m), "kanal": k, "kennlinie": nw._kennlinie_json(v["kennlinie"]),
                   "s": float(v["s"]), "s_eff": float(v["s_eff"])} for (m, k), v in mod.items()]
    dateien = {"referenz.csv": lambda p: ref.to_csv(p, index_label="zaehler"),
               "kennlinien.json": lambda p: p.write_text(json.dumps(kennlinien, indent=1), encoding="utf-8"),
               "modelltabelle.csv": lambda p: modtab.to_csv(p, index=False)}
    return mp.schreibe_paket(
        nw.PAKETNAME, "Alarm (Wächter)", dateien,
        parameter={"kanaele": list(tm.KANAELE), "form_je_kanal": tm.FORM_JE_KANAL,
                   "heizgrenze_c": tm.T_HEIZGRENZE, "cusum_k": tm.CUSUM_K, "cusum_h": tm.CUSUM_H,
                   "cusum_max": tm.CUSUM_MAX, "phi_max": tm.PHI_MAX,
                   "min_ref_tage": tm.MIN_REF_TAGE, "abstand_begehung_tage": tm.ABSTAND_BEGEHUNG},
        kennzahlen=kennzahlen, datenstand=datenstand, lernzeitraum=lernzeitraum,
        beschreibung=("Modell Ivelina: Kennlinie je Station und Kanal gegen die Tagesmitteltemperatur "
                      "(Abkühlung kWh/m³, Tagesvolumen), CUSUM h = 5 auf den Abweichungen"),
        quelle="notebooks/34_modellvergleich_und_umsetzung_nach_aufgabenstellung.ipynb, src/tagesmonitor.py",
        version=version, aktuell=False)


def paket_prognose(gelernt: dict, kal: pd.DataFrame, faktor: pd.DataFrame, regel: str,
                   schwelle: float, cusum_h: float, version: str, kennzahlen: dict,
                   datenstand) -> mp.Paket:
    """Paket ``prognose_lstm`` im Format, das `prognose_waechter.lade` liest."""
    import torch
    skal = gelernt["skalierung"]
    dateien = {
        "gewichte.pt": lambda p: torch.save({k: v.cpu() for k, v in gelernt["modell"].state_dict().items()}, p),
        "durchfluss_teiler.csv": lambda p: skal["fl_teiler"].rename("teiler_lph").to_csv(p, index_label="zaehler"),
        "skalierung.json": lambda p: p.write_text(pd.Series({"mittel": skal["mittel"],
                                                              "streuung": skal["streuung"]}).to_json(indent=2),
                                                   encoding="utf-8"),
        "kalibrierung.csv": lambda p: kal.to_csv(p),
        "faktor_jahreszeit.csv": lambda p: faktor.rename(index={True: "heiztag", False: "warmer_tag"}).to_csv(
            p, index_label="tagesart"),
        "lernkurve.csv": lambda p: gelernt["lernkurve"].rename(
            columns={"lernen": "training", "validierung": "validierung"}).to_csv(p, index=False)}
    return mp.schreibe_paket(
        pw.PAKETNAME, "Alarm (Wächter)", dateien,
        parameter={"kanaele": pw.KANAELE, "vorgeschichte_tage": pw.VORGESCHICHTE,
                   "versteckt": pw.VERSTECKT, "nacht_stunden": pw.NACHT_STUNDEN,
                   "heizgrenze_c": pw.HEIZGRENZE_C, "schwelle": schwelle, "ruhe_tage": pw.RUHE,
                   "cusum_k": pw.CUSUM_K, "cusum_h": cusum_h, "alarmregel": regel, "seed": SEED,
                   "lernen_bis": LERN_ENDE, "probezeit": [VAL_START, VAL_ENDE],
                   "lernzaehler": gelernt["lern_stationen"]},
        kennzahlen=kennzahlen, datenstand=datenstand,
        lernzeitraum=(gelernt["tage"]["tag"].min(), LERN_ENDE - pd.Timedelta(days=1)),
        beschreibung=("Modell LSTM: Encoder–Decoder-LSTM sagt aus 7 Vortagen, Wetter und Vorlauf "
                      "Rücklauf und Durchfluss des Tages voraus; z-Werte je Station aus der Probezeit, "
                      f"Alarm nach Regel {regel}"),
        quelle="notebooks/34_modellvergleich_und_umsetzung_nach_aufgabenstellung.ipynb, src/prognose_waechter.py",
        version=version, aktuell=False)


def paket_fehlerklassen(netz, x_skal: dict, ventil, daemmung, kmeans: dict, lernbereich: dict,
                        oof: pd.DataFrame, par: dict, version: str, kennzahlen: dict,
                        datenstand) -> mp.Paket:
    """Paket ``fehlerklassen`` im Format, das `fehlerklassen.lade` liest."""
    import joblib
    import torch
    teiler = pd.DataFrame(x_skal["teiler"])
    dateien = {
        "embedding_gewichte.pt": lambda p: torch.save({k: v.cpu() for k, v in netz.state_dict().items()}, p),
        "embedding_skalierung.json": lambda p: p.write_text(json.dumps(
            {"mittel": x_skal["mittel"], "streuung": x_skal["streuung"]}, indent=2), encoding="utf-8"),
        "embedding_teiler.csv": lambda p: teiler.to_csv(p, index_label="zaehler"),
        "ventil_modell.joblib": lambda p: joblib.dump(ventil, p),
        "daemmung_modell.joblib": lambda p: joblib.dump(daemmung, p),
        "kmeans.json": lambda p: p.write_text(json.dumps(kmeans, indent=2), encoding="utf-8"),
        "lernbereich.json": lambda p: p.write_text(json.dumps(lernbereich, indent=2), encoding="utf-8"),
        "kreuzvalidierung.csv": lambda p: oof.to_csv(p, index_label="zaehler")}
    return mp.schreibe_paket(
        fk.PAKETNAME, "Fehler erkennen und unterteilen (Folie 5)", dateien, parameter=par,
        kennzahlen=kennzahlen, datenstand=datenstand,
        lernzeitraum=f"Winter {WINTER[0]}–{WINTER[1]}, Sommer {SOMMER[0]}–{SOMMER[1]}, vor der ersten Begehung",
        beschreibung=("Modell LSTM: Kennzahlen (ohne Auslastung zum Anschlusswert) + LSTM-Embedding → "
                      "logistische Regression (Ventil, Dämmung), Auslastungsregel (Vertrag), "
                      "K-Means Optimum/schlechter → Klasse nach Folie 5"),
        quelle="notebooks/34_modellvergleich_und_umsetzung_nach_aufgabenstellung.ipynb, src/fehlerklassen.py",
        version=version, aktuell=False)


def embedding_skalierung_paket(werte: np.ndarray, tage: pd.DataFrame, lern_roh: np.ndarray,
                               vorher: np.ndarray) -> dict:
    """Skalierung des Encoders im Format von `fehlerklassen.embedding_skalierung`."""
    ids = tage["zaehler"].to_numpy()
    skal = {"teiler": {}, "mittel": {}, "streuung": {}}
    for j, kanal in enumerate(fk.EMB_KANAELE):
        if kanal in ("leistung", "durchfluss"):
            f = pd.DataFrame({"m": np.repeat(ids[vorher], 24), "v": werte[vorher, :, j].ravel()})
            skal["teiler"][kanal] = f.groupby("m")["v"].quantile(0.95).clip(lower=1e-3)
        else:
            skal["mittel"][kanal] = float(werte[lern_roh, :, j].mean())
            skal["streuung"][kanal] = float(werte[lern_roh, :, j].std())
    return skal


# --- Ablauf für Notebook 34 --------------------------------------------------------

WAECHTER = {"ivelina": "Modell Ivelina (Kennlinie + CUSUM)",
            "nv": "LSTM mit fester Referenz (gebaut wie Ivelinas Wächter)",
            "lstm_s": "Modell LSTM + Schwelle",
            "lstm_c": "Modell LSTM + CUSUM",
            "lstm_beg": "Modell LSTM + CUSUM, nur begangene Stationen gelernt",
            "wm_s": "Wochenmittel + Schwelle (ohne Lernen)",
            "wm_c": "Wochenmittel + CUSUM (ohne Lernen)"}
RASTER_H_IVELINA = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 30.0, 40.0]


def _quelle(w: dict, key: str):
    """Woraus ein Wächter seine Alarme rechnet: Tagesverlauf (Kennlinien-Art) oder z-Werte (LSTM-Art)."""
    if key == "ivelina":
        return "verlauf", w["verlauf"], None
    if key == "nv":
        return "verlauf", w["nv"]["verlauf"], None
    if key == "lstm_beg":
        return "z", w["beg"]["z"], w["beg"]["kal"]
    if key.startswith("lstm"):
        return "z", w["z"], w["kal"]
    return "z", w["z_wm"], w["kal_wm"]


def _alarme_fuer(quelle, regel: str, wert: float) -> pd.DataFrame:
    art, daten, kal = quelle
    return ivelina_alarme(daten, wert) if art == "verlauf" else lstm_alarme(daten, kal, regel, wert)


def _raster(key: str) -> List[Tuple[str, float]]:
    if key in ("ivelina", "nv"):
        return [("cusum", h) for h in RASTER_H_IVELINA]
    if key.endswith("_s"):
        return [("schwelle", s) for s in RASTER_SCHWELLE]
    return [("cusum", h) for h in RASTER_CUSUM_H]


def waechter_bauen(e: dict, log=print) -> dict:
    """Beide Wächter mit gemeinsamer Lernzeit bauen und auf gleiche Alarmlast einstellen.

    Ivelina behält h = 5. Ihre Alarmzahl auf den gemeinsamen Tagen von
    April und Mai 2024 ist das Ziel für alle anderen (`gleiche_alarmlast`).
    """
    mt = ivelina_tage(e["serien"], e["temp"])
    ref = ivelina_referenz(mt, e["termine"])
    mod, modtab = tm.modelle(mt, ref)
    verl = ivelina_verlauf(mt, ref, mod)
    g = lstm_lernen(e["stunden"], log=log)
    feld = (g["werte"], g["tage"])
    abw = lstm_tage(g["modell"], g["skalierung"], feld=feld)
    kal, fak = lstm_kalibrieren(abw)
    z = lstm_z(abw, kal, fak)
    abw_wm = lstm_tage(None, g["skalierung"], feld=feld, erwartung="wochenmittel")
    kal_wm, fak_wm = lstm_kalibrieren(abw_wm)
    z_wm = lstm_z(abw_wm, kal_wm, fak_wm)
    beob = {"ivelina": ivelina_beobachtet(verl), "lstm": lstm_beobachtet(z), "wm": lstm_beobachtet(z_wm)}
    gem = gemeinsame_tage(*beob.values())
    wahl = gem[(gem["datum"] >= WAHL_START) & (gem["datum"] < VAL_ENDE)]
    al_iv = ivelina_alarme(verl, H_IVELINA)
    w = {"mt": mt, "ref": ref, "mod": mod, "modtab": modtab, "verlauf": verl,
         "lstm": g, "abw": abw, "kal": kal, "faktor": fak, "z": z,
         "abw_wm": abw_wm, "kal_wm": kal_wm, "faktor_wm": fak_wm, "z_wm": z_wm,
         "beobachtet": beob, "gemeinsam": gem, "wahltage": wahl,
         "ziel_alarme": len(nur_tage(al_iv, wahl)),
         "einstellung": {"ivelina": ("cusum", H_IVELINA)}, "alarme": {"ivelina": al_iv}, "suche": []}
    for key in ("lstm_s", "lstm_c", "wm_s", "wm_c"):
        _einstellen(w, key)
    return w


def _einstellen(w: dict, key: str) -> None:
    """Wert aus dem Raster, der in der Einstellzeit so viele Alarme gibt wie Ivelinas Wächter."""
    quelle = _quelle(w, key)
    regel = _raster(key)[0][0]
    wert, tab = gleiche_alarmlast(lambda v: _alarme_fuer(quelle, regel, v),
                                  [v for _, v in _raster(key)], w["ziel_alarme"], w["wahltage"])
    w["einstellung"][key] = (regel, wert)
    w["alarme"][key] = _alarme_fuer(quelle, regel, wert)
    w["suche"] = pd.concat([w["suche"], tab.assign(waechter=key, regel=regel)], ignore_index=True) \
        if isinstance(w["suche"], pd.DataFrame) else tab.assign(waechter=key, regel=regel)


def nv_hinzufuegen(w: dict, e: dict, log=print) -> dict:
    """Dritter Wächter: LSTM mit fester Referenz, gebaut wie Ivelinas Wächter (siehe `nv_lernen`)."""
    w["nv"] = nv_lernen(w["mt"], w["ref"], e["temp"], log=log)
    _einstellen(w, "nv")
    return w


def nur_begangene_hinzufuegen(w: dict, e: dict, log=print) -> dict:
    """Variante: Prognose-LSTM nur auf den begangenen Stationen lernen (wie Notebook 20/21).

    Alles andere bleibt gleich: Zeitachse, Kalibrierung je Station (auch der
    nie begangenen, aus ihrer eigenen Probezeit), Regel CUSUM, gleiche Alarmlast.
    """
    beg = sorted(set(int(m) for m in e["labels"].index) & set(w["lstm"]["lern_stationen"]))
    g = lstm_lernen(e["stunden"], stationen=beg, log=log)
    abw = lstm_tage(g["modell"], g["skalierung"], feld=(g["werte"], g["tage"]))
    kal, fak = lstm_kalibrieren(abw)
    w["beg"] = {"lstm": g, "abw": abw, "kal": kal, "faktor": fak, "z": lstm_z(abw, kal, fak), "stationen": beg}
    _einstellen(w, "lstm_beg")
    return w


def arbeitslast(w: dict) -> pd.DataFrame:
    """Alarme je Station und Jahr in Probezeit (April/Mai) und Test, auf den gemeinsamen Tagen."""
    gem = w["gemeinsam"]
    teile = {"Einstellzeit (Apr–Mai 2024)": w["wahltage"],
             "Test (ab Juni 2024)": gem[gem["datum"] >= TEST_START]}
    zeilen = []
    for key, (regel, wert) in w["einstellung"].items():
        z = {"Wächter": WAECHTER[key], "Regel": regel, "Einstellung": wert}
        for teil, tage in teile.items():
            z[teil] = je_station_und_jahr(len(nur_tage(w["alarme"][key], tage)), tage)
        zeilen.append(z)
    return pd.DataFrame(zeilen)


def test_begehungen(w: dict, termine: Mapping[int, Sequence], fenster=(7, 60),
                    alarme: Optional[Mapping[str, pd.DataFrame]] = None,
                    tage: Optional[pd.DataFrame] = None) -> Tuple[pd.DataFrame, dict]:
    """Test A: Alarm um jede Begehung gegen Vergleichsstationen am selben Datum.

    Gezählt wird getrennt nach Richtung: Nach einer durchgeführten Maßnahme
    erwartet man eine Verbesserung (wie `alarmbewertung.richtungstest`).
    Rückgabe: Bilanz je Wächter und Richtung und die Einzelfälle.
    """
    from . import pruefstand as ps
    gem = w["gemeinsam"] if tage is None else tage
    gt = gem[gem["datum"] >= TEST_START]
    faelle = begehungsfaelle(termine)
    alarme = w["alarme"] if alarme is None else alarme
    zeilen, einzel = [], {}
    for key, a in alarme.items():
        a = nur_tage(a, gt)
        for richtung in ("besser", "alle", "schlechter"):
            aa = a if richtung == "alle" else a[a["bewertung"] == richtung]
            t = ps.trefferpruefung(aa, gt, faelle, termine, vor=fenster[0], nach=fenster[1])
            b = ps.bilanz(t, WAECHTER.get(key, key))
            zeilen.append({"Wächter": WAECHTER.get(key, key), "key": key, "Richtung": richtung,
                           "Fälle": b["Fälle"], "bemerkt": b["Treffer"], "Quote": b["Quote"],
                           "Kontrollquote": b["Kontrollquote"], "Hebel": b["Hebel"],
                           "p (einseitig)": b["p (einseitig)"], **konfusion_begehungen(t)})
            einzel[(key, richtung)] = t
    return pd.DataFrame(zeilen), einzel


def kurve_begehungen(w: dict, termine: Mapping[int, Sequence], richtung: str = "besser") -> pd.DataFrame:
    """Treffer gegen Arbeitslast für jeden Wert im Raster (Test A ohne gewählte Schwelle)."""
    from . import pruefstand as ps
    gem = w["gemeinsam"]
    gt = gem[gem["datum"] >= TEST_START]
    faelle = begehungsfaelle(termine)
    zeilen = []
    for key in w["einstellung"]:
        quelle = _quelle(w, key)
        for regel, v in _raster(key):
            a = nur_tage(_alarme_fuer(quelle, regel, v), gt)
            last = je_station_und_jahr(len(a), gt)
            aa = a if richtung == "alle" else a[a["bewertung"] == richtung]
            b = ps.bilanz(ps.trefferpruefung(aa, gt, faelle, termine))
            zeilen.append({"key": key, "Wächter": WAECHTER[key], "Wert": v, "Arbeitslast": last,
                           "Quote": b["Quote"], "Kontrollquote": b["Kontrollquote"],
                           "Vorsprung": b["Quote"] - b["Kontrollquote"],
                           "gewählt": w["einstellung"][key][1] == v})
    return pd.DataFrame(zeilen)


SAISONS = {"Winter": ("2024-12-02", "2025-01-31"), "Sommer": ("2024-06-15", "2024-07-20")}


def stoerungen_rechnen(w: dict, e: dict, saisons: Mapping[str, Tuple[str, str]] = SAISONS,
                       log=print) -> dict:
    """Test B: jede Störung an jeder Station einmal je Jahreszeit, alle Wächter.

    Gespeichert werden die z-Werte (nicht die Alarme), damit sich jede
    Schwelle nachträglich auswerten lässt. Kennlinien, Gewichte und
    Kalibrierung bleiben fest, so wie sie gelernt wurden.
    """
    ok = sorted(set(w["ref"].index[w["ref"]["status"] == "ok"]) & set(w["kal"].index))
    faelle = stoerfaelle(e["serien"], ok, e["termine"], saisons)
    g = w["lstm"]
    roh = []
    t0 = time.monotonic()
    spalten_z = ["zaehler", "tag", "heiztag", "z_rl", "z_fluss"]
    for i, f in enumerate(faelle.itertuples(index=False)):
        for art, (typ, staerke) in [("ohne Fehler", ("", None)), *STOERUNGEN.items()]:
            serie = e["serien"][f.zaehler]
            if typ:
                serie = stoerung_einrechnen(serie, f.beginn, typ, staerke)
            mt = ivelina_tage({f.zaehler: serie}, e["temp"])
            verl = ivelina_verlauf(mt, w["ref"].loc[[f.zaehler]], w["mod"])
            feld = pw.tagesfeld(stunden_aus_serien({f.zaehler: serie}, e["wetter"]))
            z = lstm_z(lstm_tage(g["modell"], g["skalierung"], feld=feld), w["kal"], w["faktor"])
            z_wm = lstm_z(lstm_tage(None, g["skalierung"], feld=feld, erwartung="wochenmittel"),
                          w["kal_wm"], w["faktor_wm"])
            r = {"zaehler": f.zaehler, "saison": f.saison, "beginn": f.beginn, "art": art,
                 "ivelina": verl[["meter", "kanal", "datum", "z"]],
                 "lstm": z[spalten_z], "wm": z_wm[spalten_z]}
            if "nv" in w:
                r["nv"] = nv_anwenden(w["nv"], mt, w["ref"], e["temp"])[["meter", "kanal", "datum", "z"]]
            if "beg" in w:
                gb = w["beg"]["lstm"]
                r["lstm_beg"] = lstm_z(lstm_tage(gb["modell"], gb["skalierung"], feld=feld),
                                       w["beg"]["kal"], w["beg"]["faktor"])[spalten_z]
            roh.append(r)
        if (i + 1) % 25 == 0:
            log(f"{i + 1}/{len(faelle)} Fälle, {time.monotonic() - t0:.0f} s")
    return {"faelle": faelle, "roh": roh}


def _fenster_tage(art: str) -> int:
    return RAMPE_TAGE if art.startswith("schleichend") else 14


def _quelle_fall(r: dict, w: dict, key: str):
    if key in ("ivelina", "nv"):
        return "verlauf", r[key], None
    if key == "lstm_beg":
        return "z", r["lstm_beg"], w["beg"]["kal"]
    if key.startswith("lstm"):
        return "z", r["lstm"], w["kal"]
    return "z", r["wm"], w["kal_wm"]


def stoerungen_auswerten(st: dict, w: dict, werte: Optional[Mapping[str, Tuple[str, float]]] = None
                         ) -> pd.DataFrame:
    """Je Fall, Störung und Wächter: bewertbar, Alarm im Fenster, Tage bis zum Alarm."""
    werte = w["einstellung"] if werte is None else werte
    zeilen = []
    for r in st["roh"]:
        fenster = _fenster_tage(r["art"])
        for key, (regel, v) in werte.items():
            quelle = _quelle_fall(r, w, key)
            beob = ivelina_beobachtet(quelle[1]) if quelle[0] == "verlauf" else lstm_beobachtet(quelle[1])
            erg = fensterergebnis(_alarme_fuer(quelle, regel, v), beob, r["beginn"], fenster)
            zeilen.append({"zaehler": r["zaehler"], "saison": r["saison"], "beginn": r["beginn"],
                           "art": r["art"], "key": key, "Wächter": WAECHTER[key], "Wert": v, **erg})
    return pd.DataFrame(zeilen)


def stoerungen_kurve(st: dict, w: dict) -> pd.DataFrame:
    """Trefferquote gegen Fehlalarmquote über das ganze Raster je Wächter (ROC-artig)."""
    teile = []
    for key in w["einstellung"]:
        for regel, v in _raster(key):
            t = stoerungen_auswerten(st, w, {key: (regel, v)})
            t = t[t["bewertbar"]]
            sauber = t[t["art"] == "ohne Fehler"].set_index(["zaehler", "saison"])["alarm"]
            for (saison, art), g in t[t["art"] != "ohne Fehler"].groupby(["saison", "art"]):
                fa = sauber.reindex(pd.MultiIndex.from_frame(g[["zaehler", "saison"]])).mean()
                teile.append({"key": key, "Wächter": WAECHTER[key], "Wert": v, "saison": saison,
                              "art": art, "Trefferquote": g["alarm"].mean(), "Fehlalarmquote": fa,
                              "Fälle": len(g), "gewählt": w["einstellung"][key][1] == v})
    return pd.DataFrame(teile)


# --- Zusatz: LSTM mit fester Referenz (gebaut wie Ivelinas Wächter) ------------------

NV_TAGE = 7


def nv_netz(n_stationen: int, versteckt: int = 32, emb: int = 8):
    """LSTM über die Tagesmitteltemperaturen der letzten 7 Tage plus Stationsvektor.

    Es sieht **keine** gemessenen Werte der Station, nur das Wetter. So kann
    es sich nicht an eine Veränderung gewöhnen, genau wie Ivelinas Kennlinie.
    """
    import torch
    nn = torch.nn

    class NormalLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(1, versteckt, batch_first=True)
            self.station = nn.Embedding(n_stationen, emb)
            self.kopf = nn.Sequential(nn.Linear(versteckt + emb, 32), nn.ReLU(), nn.Linear(32, 2))

        def forward(self, temp, station):
            _, (h, _) = self.lstm(temp)
            return self.kopf(torch.cat([h[-1], self.station(station)], dim=1))

    return NormalLSTM()


def _temp_folge(temp: pd.Series, daten) -> np.ndarray:
    t = temp.copy()
    t.index = pd.DatetimeIndex(t.index).normalize()
    t = t[~t.index.duplicated()].sort_index()
    d = pd.DatetimeIndex(pd.to_datetime(daten))
    #über den ganzen benötigten Zeitraum auffüllen, auch vor dem ersten Wettertag
    raster = pd.date_range(min(d.min(), t.index.min()) - pd.Timedelta(days=NV_TAGE), max(d.max(), t.index.max()))
    t = t.reindex(raster).interpolate(limit_direction="both")
    return np.stack([t.reindex(d - pd.Timedelta(days=k)).to_numpy(dtype=float)
                     for k in range(NV_TAGE - 1, -1, -1)], axis=1)


def _nv_eingang(d: pd.DataFrame, folge: np.ndarray, skal: dict):
    x = ((folge - skal["t_mittel"]) / skal["t_streu"]).astype(np.float32)[:, :, None]
    s = d["meter"].map(skal["nr"]).to_numpy(dtype=np.int64)
    y = np.stack([((d[k] - d["meter"].map(skal["lage"][k])) / d["meter"].map(skal["streu"][k])).to_numpy()
                  for k in tm.KANAELE], axis=1).astype(np.float32)
    return x, s, y


def _nv_vorhersage(nv: dict, d: pd.DataFrame, folge: np.ndarray) -> np.ndarray:
    import torch
    x, s, _ = _nv_eingang(d, folge, nv["skal"])
    netz = nv["netz"]
    geraet = next(netz.parameters()).device
    with torch.no_grad():
        p = np.concatenate([netz(torch.from_numpy(x[a:a + 8192]).to(geraet),
                                 torch.from_numpy(s[a:a + 8192]).to(geraet)).cpu().numpy()
                            for a in range(0, len(x), 8192)]) if len(x) else np.zeros((0, 2))
    lage = np.stack([d["meter"].map(nv["skal"]["lage"][k]).to_numpy() for k in tm.KANAELE], axis=1)
    streu = np.stack([d["meter"].map(nv["skal"]["streu"][k]).to_numpy() for k in tm.KANAELE], axis=1)
    return p * streu + lage


def nv_lernen(mt: pd.DataFrame, ref: pd.DataFrame, temp: pd.Series, seed: int = SEED, log=print) -> dict:
    """LSTM mit fester Referenz: gleiche Aufgabe, gleiche Tage, gleiche Regel wie Ivelinas Wächter.

    - Lernen auf genau den Referenztagen ihrer Kennlinien (Heiztage bis zum Lernende).
    - Vorhersage von Abkühlung (kWh/m³) und Tagesvolumen (log) nur aus dem
      Temperaturverlauf der letzten 7 Tage, ein Netz für alle Stationen mit
      Stationsvektor; Zielwerte je Station auf ihre Referenz skaliert.
    - Frühes Stoppen auf Februar/März 2024 (Kalibrierzeit), nie auf Einstellzeit oder Test.
    - Streuung wie bei Ivelina: robuste Streuung der Referenzreste, vergrößert
      für ähnliche Folgetage; danach dieselbe CUSUM-Regel.
    Unterschied zu Ivelina ist damit nur: Gerade bzw. Temperaturklassen gegen Netz.
    """
    import torch
    ok = [int(m) for m in ref.index[ref["status"] == "ok"]]
    d = mt[mt["meter"].isin(ok)].reset_index(drop=True)
    lern = ((d["datum"] >= d["meter"].map(ref["ref_start"]))
            & (d["datum"] < d["meter"].map(ref["ref_ende"]))).to_numpy()
    val = ((d["datum"] >= VAL_START) & (d["datum"] < WAHL_START)).to_numpy() & ~lern
    folge = _temp_folge(temp, d["datum"])
    g = d[lern].groupby("meter")
    skal = {"t_mittel": float(np.nanmean(folge[lern])), "t_streu": float(np.nanstd(folge[lern])),
            "nr": {m: i for i, m in enumerate(ok)},
            "lage": {k: g[k].mean() for k in tm.KANAELE},
            "streu": {k: g[k].std().clip(lower=1e-3).fillna(1.0) for k in tm.KANAELE}}
    x, s, y = _nv_eingang(d, folge, skal)

    def tens(maske):
        return (torch.from_numpy(x[maske]), torch.from_numpy(s[maske]), torch.from_numpy(y[maske]))

    netz, kurve = trainiere(lambda: nv_netz(len(ok)), tens(lern), tens(val), 300, 20, 0.003,
                            seed=seed, log=log, name="LSTM mit fester Referenz")
    nv = {"netz": netz, "skal": skal, "lernkurve": kurve, "lern_tage": int(lern.sum()),
          "pruef_tage": int(val.sum()), "stationen": len(ok)}
    erw = _nv_vorhersage(nv, d, folge)
    s_eff = {}
    for m, idx in d[lern].groupby("meter").groups.items():
        for j, k in enumerate(tm.KANAELE):
            rest = d.loc[idx, k].to_numpy(dtype=float) - erw[idx, j]
            s_ = max(tm.robuste_streuung(rest), 1e-6)
            phi = min(max(tm.autokorrelation(rest), 0.0), tm.PHI_MAX)
            s_eff[(int(m), k)] = s_ * float(np.sqrt((1 + phi) / (1 - phi)))
    nv["s_eff"] = s_eff
    nv["verlauf"] = nv_anwenden(nv, mt, ref, temp)
    return nv


def nv_anwenden(nv: dict, mt: pd.DataFrame, ref: pd.DataFrame, temp: pd.Series) -> pd.DataFrame:
    """Tagesverlauf nach der Referenz, Spalten wie `tagesmonitor.monitor` (ohne CUSUM-Konten)."""
    d = mt[mt["meter"].isin(list(nv["skal"]["nr"]))]
    d = d[d["datum"] >= d["meter"].map(ref["ref_ende"])].reset_index(drop=True)
    spalten = ["meter", "kanal", "datum", "t_mittel_c", "wert", "erwartung", "residuum", "z"]
    if d.empty:
        return pd.DataFrame(columns=spalten)
    erw = _nv_vorhersage(nv, d, _temp_folge(temp, d["datum"]))
    teile = []
    for j, k in enumerate(tm.KANAELE):
        wert = d[k].to_numpy(dtype=float)
        rest = wert - erw[:, j]
        se = np.array([nv["s_eff"][(int(m), k)] for m in d["meter"]])
        teile.append(pd.DataFrame({"meter": d["meter"].to_numpy(), "kanal": k, "datum": d["datum"].to_numpy(),
                                   "t_mittel_c": d["t_mittel_c"].to_numpy(), "wert": wert,
                                   "erwartung": erw[:, j], "residuum": rest, "z": rest / se}))
    return (pd.concat(teile, ignore_index=True).sort_values(["meter", "kanal", "datum"])
            .reset_index(drop=True)[spalten])


def klassifikation(e: dict, log=print, ziele: Sequence[str] = ZIELE, seed: int = 0,
                   kandidaten: Optional[Sequence[str]] = None, nur_begangene: bool = False) -> dict:
    """Test C: Fehlerart je Station mit äußerer Kreuzvalidierung über Stationsgruppen.

    Je Fold wird der LSTM-Encoder ohne die Teststationen neu gelernt; alle
    Kandidaten sehen dieselben Lern- und Teststationen. Rückgabe: Werte
    außerhalb des Folds je Station, Ziel und Kandidat, dazu die
    XGBoost-Beiträge und die endgültigen Modelle (auf allen 53 Stationen).
    ``seed`` ändert nur die Startgewichte der Encoder (Prüfung der
    Stabilität), die Folds bleiben gleich. ``nur_begangene`` lernt auch den
    Encoder nur auf begangenen Stationen (wie Notebook 20).
    """
    from sklearn.metrics import roc_curve
    st, labels, gruppen = e["stunden"], e["labels"], e["gruppen"]
    kz = kennzahlen_vor_begehung(st, labels)
    feld = fk._tagesfeld(st)
    aussen = ([int(m) for m in st["zaehler"].unique() if int(m) not in set(labels.index)]
              if nur_begangene else [])
    final = embedding_lernen(st, labels, ohne=aussen, feld=feld, log=log, seed=100 * seed)
    basis = basis_stationen(kz, labels, final["embedding"])
    kandidaten = list(MERKMALSSAETZE) if kandidaten is None else list(kandidaten)
    folds = aeussere_folds(basis, gruppen)
    g_all = gruppen.reindex(basis.index).to_numpy()
    zeilen, beitraege, fold_info = [], [], []
    for k, (tr, te) in enumerate(folds):
        test_ids = basis.index[te]
        enc = embedding_lernen(st, labels, ohne=list(test_ids) + aussen, seed=100 * seed + k, feld=feld,
                               log=log)
        X = kz.reindex(basis.index)[KENNZAHLEN].join(enc["embedding"].reindex(basis.index))
        fold_info.append({"fold": k, "Teststationen": len(te), "Lernstationen Encoder": enc["lern_stationen"],
                          "Lernpaare": enc["lern_paare"], "Prüfpaare": enc["val_paare"],
                          "Ventil im Test": int(basis["ventil"].iloc[te].sum())})
        for ziel in ziele:
            y_voll = basis[ziel]
            bekannt = y_voll.notna().to_numpy()
            tr_k, te_k = tr[bekannt[tr]], te[bekannt[te]]
            if len(te_k) == 0:
                continue
            y = y_voll.fillna(0).astype(int).to_numpy()
            for name in kandidaten:
                spalten = MERKMALSSAETZE[name]
                if name.startswith("XGBoost") and XGBAusgeglichen is None:
                    continue
                suche = innen_suchen(name, X.iloc[tr_k][spalten], y[tr_k], g_all[tr_k])
                p = suche.predict_proba(X.iloc[te_k][spalten])[:, 1]
                zeilen += [{"zaehler": int(basis.index[i]), "fold": k, "ziel": ziel, "kandidat": name,
                            "p": float(pi), "y": int(y[i]), "parameter": str(suche.best_params_)}
                           for i, pi in zip(te_k, p)]
                if name == "XGBoost Kennzahlen + LSTM" and ziel == "ventil":
                    b = xgb_beitraege(suche.best_estimator_, X.iloc[te_k][spalten])
                    beitraege.append(b.assign(fold=k))
            #Regeln ohne Lernen
            if ziel == "ventil":
                s = basis["sommer_durchlauf_anteil"].to_numpy()
                zeilen += [{"zaehler": int(basis.index[i]), "fold": k, "ziel": ziel,
                            "kandidat": "Regel Sommernacht-Anteil", "p": float(s[i]), "y": int(y[i]),
                            "parameter": "Grenze 0,5"} for i in te_k]
            if ziel == "ueberdimensioniert":
                s = -basis["auslastung_vertrag"].to_numpy()
                ok = tr_k[np.isfinite(s[tr_k])]
                fpr, tpr, schw = roc_curve(y[ok], s[ok])
                grenze = float(schw[np.argmax(tpr - fpr)])
                zeilen += [{"zaehler": int(basis.index[i]), "fold": k, "ziel": ziel,
                            "kandidat": "Regel Auslastung zum Vertrag", "p": float(s[i] >= grenze)
                            if np.isfinite(s[i]) else np.nan, "y": int(y[i]),
                            "parameter": f"Auslastung ≤ {-grenze:.3f} (im Lernteil gewählt)"} for i in te_k]
        log(f"Fold {k + 1}/{len(folds)} fertig")
    oof = pd.DataFrame(zeilen)
    #endgültige Modelle für das Paket: auf allen 53 Stationen, Raster innen gesucht
    X = kz.reindex(basis.index)[KENNZAHLEN].join(final["embedding"].reindex(basis.index))
    endmodelle = {}
    for ziel in ("ventil", "daemmung"):
        y = basis[ziel].astype(int).to_numpy()
        endmodelle[ziel] = innen_suchen("LR Kennzahlen + LSTM", X[KENNZAHLEN + EMB], y, g_all).best_estimator_
    km = fk.kmeans_lernen(kz)
    return {"kz": kz, "basis": basis, "folds": folds, "fold_info": pd.DataFrame(fold_info),
            "oof": oof, "beitraege": pd.concat(beitraege) if beitraege else pd.DataFrame(),
            "final": final, "endmodelle": endmodelle, "kmeans": km,
            "kmeans_klasse": fk.kmeans_einstufen(km, kz), "X": X}


def oof_breit(kl: dict, ziel: str) -> pd.DataFrame:
    """Werte außerhalb des Folds als Tabelle Station × Kandidat für ein Ziel."""
    o = kl["oof"][kl["oof"]["ziel"] == ziel]
    return o.pivot_table(index="zaehler", columns="kandidat", values="p").join(
        o.groupby("zaehler")["y"].first())


def bewertung_tabelle(kl: dict, iv: pd.DataFrame, gruppen: pd.Series, ziel: str) -> pd.DataFrame:
    """AUC mit Intervall, gepaarte Differenz zur Regel/zu Ivelina und Konfusion je Kandidat."""
    b = oof_breit(kl, ziel).join(iv[["netz_score", "fehlerbild", "auffaellig", "potenzial_score"]])
    g = gruppen.reindex(b.index).to_numpy()
    y = b["y"].to_numpy()
    zeilen = []
    kandidaten = [c for c in b.columns if c not in ("y", "fehlerbild", "auffaellig", "netz_score",
                                                    "potenzial_score")]
    bezug = "Regel Sommernacht-Anteil" if ziel == "ventil" else "LR Kennzahlen"
    for c in kandidaten + ["netz_score"]:
        s = b[c].to_numpy(dtype=float)
        if np.isfinite(s).sum() < 5 or len(np.unique(y[np.isfinite(s)])) < 2:
            continue
        auc, lo, hi = bootstrap_auc(y, s, g)
        d, dlo, dhi = (bootstrap_auc_differenz(y, s, b[bezug].to_numpy(dtype=float), g)
                       if c != bezug and bezug in b else (np.nan, np.nan, np.nan))
        if c == "netz_score":
            name, entscheidung = "Modell Ivelina (Netz-Score / Fehlerbild)", None
            treffer = FEHLERBILD_ZU_ZIEL.get(ziel)
            if treffer:
                entscheidung = b["fehlerbild"].isin(treffer).to_numpy()
        else:
            name = c
            entscheidung = (s >= GRENZE) if not c.startswith("Regel Auslastung") else (s >= 0.5)
        vf = vierfeld(y, entscheidung) if entscheidung is not None else {}
        zeilen.append({"Kandidat": name, "Stationen": int(np.isfinite(s).sum()),
                       "Befunde": int(y[np.isfinite(s)].sum()), "AUC": auc, "AUC unten": lo,
                       "AUC oben": hi, f"Differenz zu {bezug}": d, "Diff. unten": dlo,
                       "Diff. oben": dhi, **vf})
    return pd.DataFrame(zeilen)


def ab_wann_bewertbar(e: dict, w: dict) -> pd.DataFrame:
    """Wie viele Tage nach dem ersten Messwert jedes Modell eine Station bewerten kann.

    Ivelina (Tagesmonitor): 60 Heiztage mit 8 K Temperaturspanne in der
    Referenz. LSTM (Wächter): 7 volle Vortage, 10 Tage für die Skala und
    10 Tage für die Kalibrierung, also rund 27 volle Tage, in jeder
    Jahreszeit. Gerechnet auf den echten Daten jeder Station.
    """
    mt = w["mt"]
    werte, tage = w["lstm"]["werte"], w["lstm"]["tage"]
    zeilen = []
    for m, s in e["serien"].items():
        start = s["flow"].dropna().index.min()
        d = mt[mt["meter"] == m].sort_values("datum")
        iv = np.nan
        if len(d):
            t = d["t_mittel_c"].to_numpy()
            spanne = np.maximum.accumulate(t) - np.minimum.accumulate(t)
            ok = np.flatnonzero((np.arange(1, len(d) + 1) >= tm.MIN_REF_TAGE) & (spanne >= tm.MIN_REF_SPANNE_K))
            if len(ok):
                iv = (pd.Timestamp(d["datum"].iloc[ok[0]]) - start.normalize()).days
        tt = tage[tage["zaehler"] == m].sort_values("tag")
        ls = np.nan
        if len(tt) >= pw.VORGESCHICHTE + 2 * MIN_VAL_TAGE:
            ls = (tt["tag"].iloc[pw.VORGESCHICHTE + 2 * MIN_VAL_TAGE - 1] - start.normalize()).days
        zeilen.append({"zaehler": int(m), "erster Messwert": start.normalize(),
                       "Ivelina Tagesmonitor ab Tag": iv, "LSTM-Wächter ab Tag": ls})
    return pd.DataFrame(zeilen)


def stabilitaet(e: dict, seeds: Sequence[int] = (1, 2), log=print, nur_begangene: bool = True) -> pd.DataFrame:
    """Ventil und Dämmung mit anderen Startgewichten der Encoder (gleiche Folds)."""
    from sklearn.metrics import roc_auc_score
    namen = ("LR Kennzahlen + LSTM", "LR nur LSTM-Embedding", "XGBoost Kennzahlen + LSTM")
    zeilen = []
    for s in seeds:
        kl = klassifikation(e, log=log, ziele=("ventil", "daemmung"), seed=s, kandidaten=namen,
                            nur_begangene=nur_begangene)
        for ziel in ("ventil", "daemmung"):
            b = oof_breit(kl, ziel)
            for c in namen:
                vf = vierfeld(b["y"], b[c] >= GRENZE)
                zeilen.append({"Seed": s, "Ziel": ziel, "Kandidat": c,
                               "AUC": roc_auc_score(b["y"], b[c]), "gefunden": vf["gefunden"],
                               "Fehlalarm": vf["Fehlalarm"]})
    return pd.DataFrame(zeilen)


def fehlerklassen_teile(kl: dict) -> dict:
    """Endgültiges Modell LSTM für Fehlerarten im Format von `fehlerklassen.lade`.

    Ventil und Dämmung: LR auf Kennzahlen + Embedding, auf allen 53
    Stationen gelernt, Grenze 0,5. Überdimensionierung: Regel Auslastung zum
    Vertrag vor der Begehung, Grenze nach Youden auf den 35 Stationen mit
    bekanntem Vertrag (in der Kreuzvalidierung je Fold neu gewählt geprüft).
    """
    from sklearn.metrics import roc_curve
    basis = kl["basis"]
    d = basis.dropna(subset=["ueberdimensioniert"])
    median = float(basis["auslastung_vertrag"].median())
    s = -d["auslastung_vertrag"].fillna(median)
    fpr, tpr, schw = roc_curve(d["ueberdimensioniert"].astype(int), s)
    vertrag_grenze = -float(schw[np.argmax(tpr - fpr)])
    par = {"ventil_grenze": GRENZE, "daemmung_grenze": GRENZE, "vertrag_grenze": vertrag_grenze,
           "vertrag_median": median, "merkmale": KENNZAHLEN + EMB, "kennzahlen": KENNZAHLEN,
           "winter": list(WINTER), "sommer": list(SOMMER), "emb_min_tage": fk.EMB_MIN_TAGE,
           "stichtag": STICHTAG, "klassen": fk.KLASSEN, "handlung": fk.HANDLUNG}
    lernbereich = {"min": basis[fk.KENNZAHLEN].min().to_dict(), "max": basis[fk.KENNZAHLEN].max().to_dict()}
    oof = pd.DataFrame({"ventil": oof_breit(kl, "ventil")["LR Kennzahlen + LSTM"],
                        "daemmung": oof_breit(kl, "daemmung")["LR Kennzahlen + LSTM"]})
    oof["vertrag"] = (-basis["auslastung_vertrag"].fillna(median)).where(basis["ueberdimensioniert"].notna())
    return {"parameter": par, "netz": kl["final"]["netz"].cpu().eval(),
            "skalierung": kl["final"]["skalierung"], "ventil_modell": kl["endmodelle"]["ventil"],
            "daemmung_modell": kl["endmodelle"]["daemmung"], "kmeans": kl["kmeans"],
            "lernbereich": lernbereich, "kreuzvalidierung": oof}


WINTER_NACH = ("2024-10-01", "2025-04-01")
SOMMER_NACH = ("2025-06-01", "2025-09-01")


def gegenprobe_nach_reparatur(teile: dict, e: dict, kl: dict, netz: dict) -> pd.DataFrame:
    """Bekannte HAST später: beide Modelle unverändert auf Winter 24/25 (und Sommer 2025).

    Vorher: Modell LSTM mit den Werten außerhalb des Folds (begangene) bzw.
    dem Endmodell (nie begangene), Ivelina mit dem Netzvergleich 23/24.
    Nachher: dieselben Modelle auf den Daten nach den Begehungen.
    """
    nach = fk.saison_bewerten(teile, e["stunden"], WINTER_NACH, SOMMER_NACH)
    emb = kl["final"]["embedding"]
    vor = fk.bewerten(teile, kl["kz"], emb, oof=teile["kreuzvalidierung"])
    iv_vor = ivelina_je_station(netz, "23/24")
    iv_nach = ivelina_je_station(netz, "24/25")
    lab = e["labels"]
    idx = sorted(set(vor.index) | set(nach.index))
    t = pd.DataFrame(index=pd.Index(idx, name="zaehler"))
    t["gruppe"] = np.select([t.index.isin(lab.index[lab["ventil"].astype(bool)]), t.index.isin(lab.index)],
                            ["Ventil getauscht", "begangen, kein Ventil"], "nie begangen")
    t["p_ventil_vor"] = vor["p_ventil"].reindex(t.index)
    t["p_ventil_nach"] = nach["p_ventil"].reindex(t.index)
    t["stunden_sommer_nach"] = nach["stunden_sommer"].reindex(t.index)
    t["fehlerbild_vor"] = iv_vor["fehlerbild"].reindex(t.index)
    t["fehlerbild_nach"] = iv_nach["fehlerbild"].reindex(t.index)
    t["netz_score_vor"] = iv_vor["netz_score"].reindex(t.index)
    t["netz_score_nach"] = iv_nach["netz_score"].reindex(t.index)
    return t


def wirkung_und_potenzial(w: dict, netz: dict, kl: dict, termine: Mapping[int, Sequence]) -> pd.DataFrame:
    """Abkühlung bei 5 °C je Station im Winter 23/24 und 24/25 (`tagesmonitor.norm_winter`)
    neben Ivelinas Potenzial und der K-Means-Gruppe aus dem Winter 23/24."""
    norm = tm.norm_winter(w["mt"])
    a = norm[norm["winter"] == "23/24"].set_index("meter")["norm_kwh_m3"]
    b = norm[norm["winter"] == "24/25"].set_index("meter")["norm_kwh_m3"]
    iv = ivelina_je_station(netz, "23/24")
    t = pd.DataFrame({"kwh_m3_2324": a, "kwh_m3_2425": b}).dropna()
    t.index.name = "zaehler"
    t["delta_kwh_m3"] = t["kwh_m3_2425"] - t["kwh_m3_2324"]
    t["begangen"] = [any(pd.Timestamp("2024-03-01") <= pd.Timestamp(d) < pd.Timestamp("2024-12-01")
                         for d in termine.get(int(m), [])) for m in t.index]
    t["potenzial_score"] = iv["potenzial_score"].reindex(t.index)
    t["potenzial"] = iv["potenzial"].reindex(t.index)
    t["kmeans"] = kl["kmeans_klasse"].reindex(t.index)
    return t


def lstm_neue_stationen(e: dict, w: dict, anteil: float = 0.2, seed: int = SEED, log=print) -> dict:
    """Prognose-LSTM ohne ein Fünftel der Stationsgruppen lernen und dort prüfen.

    Gleiche Testtage, gleiche Stationen: bekanntes Modell (Station war im
    Lernen) gegen neues Modell (Station nie gesehen) gegen Wochenmittel.
    Die Skala des Durchflusses kommt bei neuen Stationen aus ihrer eigenen
    Vergangenheit vor dem Lernende.
    """
    gruppen = e["gruppen"]
    lern = w["lstm"]["lern_stationen"]
    g_einzeln = sorted(set(gruppen.reindex(lern)))
    raus = set(np.random.default_rng(seed).choice(g_einzeln, size=int(round(anteil * len(g_einzeln))),
                                                  replace=False))
    neu = [m for m in lern if gruppen[m] in raus]
    gb = lstm_lernen(e["stunden"], stationen=[m for m in lern if m not in neu], seed=seed, log=log)
    abw_b = lstm_tage(gb["modell"], gb["skalierung"], feld=(w["lstm"]["werte"], w["lstm"]["tage"]))
    teile = []
    for name, abw in (("bekannt (Station war im Lernen)", w["abw"]),
                      ("neu (Station nie gesehen)", abw_b), ("Wochenmittel (ohne Lernen)", w["abw_wm"])):
        a = abw[abw["zaehler"].isin(neu) & (abw["tag"] >= TEST_START)]
        teile.append(a[["zaehler", "tag", "heiztag", "mae_rl", "mae_fluss"]].assign(modell=name))
    t = pd.concat(teile)
    gemeinsam = t.groupby(["zaehler", "tag"])["modell"].transform("nunique") == 3
    return {"neu": neu, "tage": t[gemeinsam], "lernkurve": gb["lernkurve"]}


def fallbild(meter: int, w: dict, e: dict, von, bis, titel: str = ""):
    """Ein Fall mit echten Daten: Messwert, Erwartung, z-Werte, Schwelle und Alarme beider Modelle."""
    import matplotlib.pyplot as plt
    von, bis = pd.Timestamp(von), pd.Timestamp(bis)
    fig, ax = plt.subplots(4, 1, figsize=(13, 10), sharex=True)
    v = w["verlauf"]
    v = v[(v["meter"] == meter) & (v["datum"] >= von) & (v["datum"] <= bis)]
    k = v[v["kanal"] == "kwh_pro_m3"]
    ax[0].plot(k["datum"], k["wert"], ".", ms=4, color="black", label="gemessen")
    ax[0].plot(k["datum"], k["erwartung"], "-", color=FARBE_IVELINA, label="Erwartung Kennlinie (Ivelina)")
    ax[0].set_ylabel("Abkühlung\n[kWh/m³]")
    ax[0].set_title(titel or f"Station {meter}", fontsize=11)
    for kanal, farbe in (("kwh_pro_m3", FARBE_IVELINA), ("log_volumen", "#60A5FA")):
        g = v[v["kanal"] == kanal]
        ax[1].plot(g["datum"], np.maximum(g["s_plus"], g["s_minus"]), color=farbe,
                   label=f"CUSUM-Konto {tm.KANAELE[kanal]}")
    ax[1].axhline(H_IVELINA, color=FARBE_IVELINA, ls="--", lw=1, label=f"Grenze h = {H_IVELINA:g}")
    ax[1].set_ylabel("Konto Ivelina")
    z = w["z"]
    z = z[(z["zaehler"] == meter) & (z["tag"] >= von) & (z["tag"] <= bis)]
    ax[2].plot(z["tag"], z["rl_gemessen"], ".", ms=4, color="black", label="Rücklauf gemessen")
    ax[2].plot(z["tag"], z["rl_erwartet"], "-", color=FARBE_LSTM, label="Erwartung LSTM")
    ax[2].set_ylabel("Rücklauf\nTagesmittel [°C]")
    ax[3].plot(z["tag"], z["z_rl"], color=FARBE_LSTM, label="z Rücklauf (LSTM)")
    ax[3].plot(z["tag"], z["z_fluss"], color="#F59E0B", label="z Nachtdurchfluss (LSTM)")
    ax[3].set_ylabel("z-Wert LSTM")
    for key, a_ax, farbe in (("ivelina", ax[1], FARBE_IVELINA), ("lstm_c", ax[3], FARBE_LSTM)):
        a = w["alarme"][key]
        a = a[(a["zaehler"] == meter) & (a["datum"] >= von) & (a["datum"] <= bis)]
        for d, b in zip(a["datum"], a["bewertung"]):
            a_ax.axvline(d, color=farbe, lw=2, alpha=0.6, ls="-" if b == "schlechter" else ":")
    for d in e["termine"].get(int(meter), []):
        if von <= pd.Timestamp(d) <= bis:
            for a_ax in ax:
                a_ax.axvline(pd.Timestamp(d), color="green", lw=2.5, alpha=0.5)
    ax[0].plot([], [], color="green", lw=2.5, alpha=0.5, label="Begehung")
    for a_ax in ax:
        a_ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=3)
        a_ax.spines[["top", "right"]].set_visible(False)
    ax[3].set_xlabel("Datum (senkrechte Linien: Alarm, durchgezogen = schlechter, gepunktet = besser)")
    fig.tight_layout()
    return fig


def sommer_lstm_pruefen(w: dict, e: dict, st: dict, log=print) -> dict:
    """Gegenprobe: ein Prognose-LSTM nur für warme Tage, gegen das ganzjährige LSTM.

    Gleiche Sommerfälle aus Test B, gleiche CUSUM-Regel, Vergleich über
    das ganze Raster (Trefferquote bei gleicher Fehlalarmquote). Die
    Kalibrierung des Sommer-LSTM kommt aus den warmen Tagen der Probezeit.
    """
    gs = lstm_lernen(e["stunden"], nur_warm=True, log=log)
    abw = lstm_tage(gs["modell"], gs["skalierung"], feld=(gs["werte"], gs["tage"]))
    kal, fak = pw.kalibrieren(abw[(abw["tag"] >= VAL_START) & (abw["tag"] < VAL_ENDE) & ~abw["heiztag"]])
    fall = {(r["zaehler"], r["art"]): r for r in st["roh"] if r["saison"] == "Sommer"}
    zeilen = []
    for f in st["faelle"][st["faelle"]["saison"] == "Sommer"].itertuples(index=False):
        if f.zaehler not in kal.index:
            continue
        for art, (typ, staerke) in [("ohne Fehler", ("", None)), *STOERUNGEN.items()]:
            serie = e["serien"][f.zaehler]
            if typ:
                serie = stoerung_einrechnen(serie, f.beginn, typ, staerke)
            feld = pw.tagesfeld(stunden_aus_serien({f.zaehler: serie}, e["wetter"]))
            z_s = lstm_z(lstm_tage(gs["modell"], gs["skalierung"], feld=feld), kal, fak)
            for name, z, k in (("ganzjährig gelernt", fall[(f.zaehler, art)]["lstm"], w["kal"]),
                               ("nur Sommertage gelernt", z_s, kal)):
                for h in RASTER_CUSUM_H:
                    erg = fensterergebnis(lstm_alarme(z, k, "cusum", h), lstm_beobachtet(z), f.beginn,
                                          _fenster_tage(art))
                    zeilen.append({"zaehler": f.zaehler, "art": art, "modell": name, "h": h, **erg})
    r = pd.DataFrame(zeilen)
    r = r[r["bewertbar"]]
    sauber = r[r["art"] == "ohne Fehler"].set_index(["zaehler", "modell", "h"])["alarm"]
    kurve = []
    for (art, modell, h), g in r[r["art"] != "ohne Fehler"].groupby(["art", "modell", "h"]):
        idx = pd.MultiIndex.from_arrays([g["zaehler"], [modell] * len(g), [h] * len(g)])
        kurve.append({"art": art, "modell": modell, "h": h, "Trefferquote": g["alarm"].mean(),
                      "Fehlalarmquote": sauber.reindex(idx).mean(), "Fälle": len(g)})
    return {"kurve": pd.DataFrame(kurve), "lernkurve": gs["lernkurve"], "lern_ziele": gs["lern_ziele"],
            "pruef_ziele": gs["val_ziele"], "kalibriert": int(len(kal))}
