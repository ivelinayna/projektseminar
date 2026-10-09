"""
Loader for the real ÜZ meter time-series CSVs.

The exports live directly in ``data/raw/`` as one CSV per meter and
export generation:

    <Zählernummer>__n.csv       older export  (ends ~2024-05)
    <Zählernummer>_2025n.csv    newer export  (ends ~2025-07)

Both generations cover overlapping time ranges, so per meter we
concatenate all files, sort ascending and drop duplicate timestamps.
Column schema is identical to the synthetic data (`synth_data.py`):

    Timestamp, Energy (kWh), Volume flow (l/h), Power (kW),
    Temperature difference (°C), Flow temperature (°C),
    Return temperature (°C), Volume (m³)

Energy and Volume are cumulative counters; the rest are (roughly)
hourly instantaneous values. Known quirks of the raw exports, kept
as-is here so downstream code sees the real data:

  * timestamps are minute-offset (e.g. 13:01) and descending in file order
  * occasional negative flow / power readings (metering noise)
  * per-meter history starts/ends at different dates (2021-2025)
  * a few exports omit the spread column; it is derived from
    Vorlauf minus Rücklauf (see _derive_temperature_difference)

Seit dem 01.10.2026 liegt eine dritte Exportgeneration daneben:

    <Zählernummer>.ods         ÜZ-Nachlieferung, reicht bis 2026-07-20

Dieses Format hat nur sechs Spalten. Die beiden kumulativen Kanäle
Energie und Volumen fehlen, und alle Messwerte stehen als Ganzzahl mit
Faktor 1000 (5500 bedeutet 5,5 K). Der Faktor wird nicht angenommen,
sondern in ``pruefe_skalierung`` über zwei voneinander unabhängige
Bedingungen bestimmt: die Vorlauftemperatur muss in einem physikalisch
möglichen Band liegen, und die Leistung muss zu Volumenstrom und
Spreizung passen (P = V̇ · ΔT / 859,8). Beide Bedingungen sind nur bei
genau einem Faktor gleichzeitig erfüllt.

Die fehlenden Zählerstände werden nicht erfunden. ``load_meter_ods``
lässt ``Energy (kWh)`` und ``Volume (m³)`` leer; ``ergaenze_zaehlerstaende``
rekonstruiert sie auf Wunsch durch Integration von Leistung und
Volumenstrom über die Stundenabstände und markiert jede so entstandene
Zeile in der Spalte ``zaehlerstand_integriert``. Downstream wird von
diesen Kanälen ohnehin nur die Differenz zweier Zeitpunkte benutzt
(``performance.tagesdifferenzen``, ``jahresvergleich.fensterkennzahlen``),
der absolute Zählerstand ist also bedeutungslos - der Anschlusswert an
den letzten gemessenen Stand wird trotzdem gesetzt, damit die Reihe
monoton bleibt.

``materialize_meters`` writes one clean ``<Zählernummer>.csv`` per meter
into a target directory, which is exactly the layout that
``features.features_for_directory`` already consumes - the synthetic
pipeline interface stays untouched.

Deliberately NOT decided here (needs a project decision before the real
series feed fault detection): which analysis window to use (the feature
set assumes ~1 year), and how to stitch meter swaps (see Zuordnung.xlsx:
some CSV meter numbers are replacements not present in Nodes_Edges.ods).

CLI:

    python -m src.load_timeseries            # inventory summary
    python -m src.load_timeseries --materialize data/processed/real_meters
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

#canonical schema shared with synth_data.py
SCHEMA = [
    "Timestamp",
    "Energy (kWh)",
    "Volume flow (l/h)",
    "Power (kW)",
    "Temperature difference (°C)",
    "Flow temperature (°C)",
    "Return temperature (°C)",
    "Volume (m³)",
]

_FILE_RE = re.compile(r"^(\d+)_.*\.csv$")
_ODS_RE = re.compile(r"^(\d+)\.ods$")

#kumulative Kanaele; im ODS-Export fehlen genau diese beiden
KUMULATIVE_KANAELE = ["Energy (kWh)", "Volume (m³)"]

#Spalten des ODS-Exports, erkannt am Text vor der Einheitenklammer.
#Die Einheitenklammer traegt ein Gradzeichen, dessen Kodierung je nach
#Exportlauf wechselt - deshalb wird nur der Praefix verglichen.
ODS_KANAELE = {
    "volume flow": "Volume flow (l/h)",
    "power": "Power (kW)",
    "temperature difference": "Temperature difference (°C)",
    "flow temperature": "Flow temperature (°C)",
    "return temperature": "Return temperature (°C)",
    "timestamp": "Timestamp",
}

#geprueft werden nur Zehnerpotenzen; andere Faktoren waeren in einem
#Zaehlerexport ohne Beispiel
ODS_SKALEN = (1.0, 10.0, 100.0, 1000.0)

#physikalisch moegliches Band der Vorlauftemperatur einer Fernwaerme-HAST
VL_BAND_C = (5.0, 140.0)

#1 kW entspricht 859,8 l/h bei 1 K Spreizung:
#3600 s/h / 4,19 kJ/(kg K) = 859,2; mit 4,187 kJ/(kg K) sind es 859,8
L_K_JE_KWH = 859.845

#Toleranz der Leistungsprobe. Der Zaehler rundet Volumenstrom auf 0,1 m3/h
#und Spreizung auf 0,1 K, daraus entstehen einstellige Prozentabweichungen.
SKALEN_TOLERANZ = 0.10

#Maximaler Abstand zweier Messpunkte, der noch als ein Stundenintervall
#zaehlt; identisch zu performance.MAX_GAP_HOURS
MAX_GAP_HOURS = 2

#Ab so vielen Zeilen je Kalendertag gilt der Tag als stuendlich abgetastet
STUENDLICH_AB = 12



def discover_meter_files(data_dir: Path = DATA_DIR) -> dict[int, list[Path]]:
    """Map Zählernummer -> list of export CSVs found in `data_dir`.

    Only files matching ``<digits>_*.csv`` directly in `data_dir` count;
    subdirectories (e.g. data/raw/synthetic/) are not scanned.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(
            f"raw data directory not found: {data_dir} - place the ÜZ "
            "meter CSVs (e.g. 41566330__n.csv) into data/raw/")
    meters: dict[int, list[Path]] = {}
    for f in sorted(data_dir.glob("*.csv")):
        m = _FILE_RE.match(f.name)
        if m:
            meters.setdefault(int(m.group(1)), []).append(f)
    if not meters:
        raise FileNotFoundError(
            f"no meter CSVs matching '<Zählernummer>_*.csv' found in "
            f"{data_dir} - expected files like 41566330__n.csv or "
            "41566330_2025n.csv from the ÜZ export")
    return meters


_DT = "Temperature difference (°C)"
_VL = "Flow temperature (°C)"
_RL = "Return temperature (°C)"


def _derive_temperature_difference(df: pd.DataFrame) -> pd.DataFrame:
    """Add the spread column when an export omits it (e.g. 81050517).

    Most exports ship it, a few do not. It is Vorlauf minus Rücklauf by
    definition, so deriving it is exact - not an estimate - and keeps the
    meter in the pipeline instead of failing the whole run on one file.
    """
    if _DT in df.columns or not {_VL, _RL} <= set(df.columns):
        return df
    df = df.copy()
    df[_DT] = df[_VL] - df[_RL]
    return df


def discover_meter_ods(data_dir: Path = DATA_DIR) -> Dict[int, Path]:
    """Zählernummer -> ODS-Nachlieferung in `data_dir`.

    Nur Dateien, deren Name ausschliesslich aus Ziffern besteht, zaehlen.
    ``Nodes_Edges.ods`` und andere Beiblaetter fallen damit heraus. Im
    Gegensatz zu `discover_meter_files` ist ein leeres Ergebnis kein
    Fehler - der ODS-Export liegt bisher nur fuer einen Teil der Zaehler
    vor.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"raw data directory not found: {data_dir}")
    gefunden: Dict[int, Path] = {}
    for f in sorted(data_dir.glob("*.ods")):
        m = _ODS_RE.match(f.name)
        if m:
            gefunden[int(m.group(1))] = f
    return gefunden


def _lies_ods_blatt(path: Path) -> pd.DataFrame:
    """Das einzige Tabellenblatt einer ODS-Nachlieferung, roh und unskaliert.

    Spaltennamen werden ueber den Text vor der Einheitenklammer erkannt,
    weil das Gradzeichen je nach Exportlauf unterschiedlich kodiert ist.
    `pandas.read_excel` mit der odf-Engine loest dabei
    ``table:number-columns-repeated`` auf; ein selbstgebauter XML-Parser
    wuerde an dieser Stelle Spalten verschieben.
    """
    blaetter = pd.read_excel(path, engine="odf", sheet_name=None)
    if len(blaetter) != 1:
        raise ValueError(
            f"{path.name}: erwartet genau ein Tabellenblatt, "
            f"gefunden {list(blaetter)}")
    roh = next(iter(blaetter.values()))

    umbenennung = {}
    for spalte in roh.columns:
        praefix = str(spalte).split("(")[0].strip().lower()
        if praefix in ODS_KANAELE:
            umbenennung[spalte] = ODS_KANAELE[praefix]
    df = roh.rename(columns=umbenennung)

    fehlend = [c for c in ODS_KANAELE.values() if c not in df.columns]
    if fehlend:
        raise ValueError(
            f"{path.name}: Spalten {fehlend} nicht erkannt - "
            f"gefunden {list(roh.columns)}")
    vorhanden = [c for c in KUMULATIVE_KANAELE if c in df.columns]
    if vorhanden:
        raise ValueError(
            f"{path.name}: enthaelt die kumulativen Kanaele {vorhanden} - "
            "das ist das CSV-Schema, nicht die ODS-Nachlieferung")

    df = df[list(ODS_KANAELE.values())].copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    for spalte in df.columns:
        if spalte != "Timestamp":
            df[spalte] = pd.to_numeric(df[spalte], errors="coerce")
    return df.sort_values("Timestamp", kind="stable").reset_index(drop=True)


def pruefe_skalierung(roh: pd.DataFrame,
                      skalen: Sequence[float] = ODS_SKALEN,
                      toleranz: float = SKALEN_TOLERANZ) -> dict:
    """Den Skalenfaktor des ODS-Exports bestimmen statt ihn anzunehmen.

    Zwei Bedingungen muessen gleichzeitig gelten, und sie haengen nicht
    voneinander ab. Erstens muss die Vorlauftemperatur nach der Division
    im Band `VL_BAND_C` liegen. Zweitens muss die Leistung zu
    Volumenstrom und Spreizung passen: bei einem gemeinsamen Faktor s
    ist ``(flow/s) * (dt/s) / 859,8`` nur dann gleich ``power/s``, wenn s
    stimmt - ein um den Faktor 10 danebenliegendes s verfehlt die
    Leistung um denselben Faktor. Deshalb ist die Loesung eindeutig.

    Rueckgabe traegt ``faktor`` sowie die Diagnosewerte, die die
    Entscheidung belegen. Passt kein Kandidat, wird ``ValueError``
    geworfen - lieber ein Abbruch als eine stillschweigend um drei
    Groessenordnungen falsche Zeitreihe.
    """
    flow = pd.to_numeric(roh["Volume flow (l/h)"], errors="coerce")
    power = pd.to_numeric(roh["Power (kW)"], errors="coerce")
    dt = pd.to_numeric(roh["Temperature difference (°C)"], errors="coerce")
    vl = pd.to_numeric(roh["Flow temperature (°C)"], errors="coerce")
    rt = pd.to_numeric(roh["Return temperature (°C)"], errors="coerce")

    kandidaten = []
    for s in skalen:
        vl_med = float((vl / s).median())
        if not (VL_BAND_C[0] <= vl_med <= VL_BAND_C[1]):
            continue
        f, p, d = flow / s, power / s, dt / s
        #nur Stunden unter Last pruefen, im Stillstand teilt man Nullen
        unter_last = (f > 50) & (p > 0.2) & (d > 1.0)
        if int(unter_last.sum()) < 50:
            continue
        rel = ((f[unter_last] * d[unter_last] / L_K_JE_KWH - p[unter_last])
               / p[unter_last]).abs()
        kandidaten.append({
            "faktor": s,
            "n_pruefzeilen": int(unter_last.sum()),
            "rel_fehler_median": float(rel.median()),
            "vl_median_c": vl_med,
        })

    passend = [k for k in kandidaten
               if k["rel_fehler_median"] <= toleranz]
    if len(passend) != 1:
        raise ValueError(
            "Skalierung des ODS-Exports nicht eindeutig bestimmbar - "
            f"Kandidaten {kandidaten}, Toleranz {toleranz}")

    ergebnis = dict(passend[0])
    s = ergebnis["faktor"]
    #Gegenprobe der Spaltenzuordnung: die Spreizung muss die Differenz der
    #beiden Temperaturen sein. Skaleninvariant, deshalb keine zweite
    #Aussage ueber s, aber sie faengt vertauschte Spalten ab.
    abw = ((vl - rt - dt) / s).abs()
    ergebnis["identitaet_max_abw_k"] = float(abw.max(skipna=True))
    ergebnis["identitaet_anteil_ok"] = float((abw <= 0.2).mean())
    if ergebnis["identitaet_anteil_ok"] < 0.99:
        raise ValueError(
            "Spaltenzuordnung des ODS-Exports unplausibel: Vorlauf minus "
            "Ruecklauf ergibt nur in "
            f"{ergebnis['identitaet_anteil_ok']:.1%} der Zeilen die "
            "ausgewiesene Spreizung")
    return ergebnis


def load_meter_ods(zaehlernummer: int,
                   data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Eine ODS-Nachlieferung im kanonischen Achtspaltenschema.

    Die beiden kumulativen Kanaele bleiben leer, weil der Export sie
    nicht enthaelt; wer sie braucht, ruft `ergaenze_zaehlerstaende`.
    Zeitstempel aufsteigend, Dubletten entfernt (die letzte gewinnt, das
    ist der Umstellungszeitpunkt von Tages- auf Stundenabtastung).
    """
    dateien = discover_meter_ods(data_dir)
    if zaehlernummer not in dateien:
        raise FileNotFoundError(
            f"keine ODS-Nachlieferung fuer Zählernummer {zaehlernummer} in "
            f"{Path(data_dir)} - erwartet {zaehlernummer}.ods")
    path = dateien[zaehlernummer]
    roh = _lies_ods_blatt(path)
    faktor = pruefe_skalierung(roh)["faktor"]

    out = pd.DataFrame({"Timestamp": roh["Timestamp"]})
    for spalte in SCHEMA:
        if spalte == "Timestamp":
            continue
        if spalte in KUMULATIVE_KANAELE:
            out[spalte] = np.nan
        else:
            out[spalte] = roh[spalte] / faktor
    out = out[SCHEMA].sort_values("Timestamp", kind="stable")
    out = out.drop_duplicates(subset="Timestamp", keep="last")
    return out.reset_index(drop=True)


def zeitraster(df: pd.DataFrame,
               stuendlich_ab: int = STUENDLICH_AB) -> pd.DataFrame:
    """Abtastraster einer Reihe als Segmenttabelle, ohne etwas zu filtern.

    Der ÜZ-Export ist nicht durchgehend stuendlich: aeltere Abschnitte
    tragen genau eine Zeile je Kalendertag, davor liegen vollstaendige
    Luecken. Wer darueber Stundenkennzahlen mittelt, mischt zwei
    Messauflösungen. Die Rueckgabe hat eine Zeile je zusammenhaengendem
    Abschnitt mit ``raster`` aus ``stuendlich``, ``taeglich`` und
    ``luecke`` sowie ``von``, ``bis``, ``n_tage`` und ``n_zeilen``.
    """
    if len(df) == 0:
        return pd.DataFrame(columns=["raster", "von", "bis", "n_tage",
                                     "n_zeilen"])
    ts = pd.DatetimeIndex(pd.to_datetime(df["Timestamp"]
                                         if "Timestamp" in df.columns
                                         else df.index))
    je_tag = (pd.Series(1, index=ts).resample("D").sum()
              .reindex(pd.date_range(ts.min().normalize(),
                                     ts.max().normalize(), freq="D"),
                       fill_value=0))
    art = pd.Series(
        np.where(je_tag >= stuendlich_ab, "stuendlich",
                 np.where(je_tag > 0, "taeglich", "luecke")),
        index=je_tag.index)
    block = (art != art.shift()).cumsum()
    rows = []
    for _, g in art.groupby(block):
        tage = g.index
        rows.append({
            "raster": g.iloc[0],
            "von": tage[0],
            "bis": tage[-1],
            "n_tage": len(tage),
            "n_zeilen": int(je_tag.loc[tage].sum()),
        })
    return pd.DataFrame(rows)


def ergaenze_zaehlerstaende(df: pd.DataFrame,
                            max_gap_hours: int = MAX_GAP_HOURS
                            ) -> pd.DataFrame:
    """Fehlende Zaehlerstaende aus Leistung und Volumenstrom integrieren.

    Je Stundenintervall wird ``power * dt_h`` zur Energie und
    ``flow * dt_h / 1000`` zum Volumen addiert. Intervalle ueber eine
    Luecke hinweg (Abstand groesser `max_gap_hours`) tragen nichts bei -
    sonst wuerde eine Woche Ausfall als eine Woche Volllast gezaehlt.
    Negative Momentanwerte sind Messrauschen und werden auf null
    gekappt, damit die Reihe wie ein echter Zaehler monoton bleibt.

    Der Anschlusswert ist der letzte gemessene Zaehlerstand davor, bei
    einer reinen ODS-Reihe die Null. Das ist unkritisch, weil downstream
    nur Differenzen gebildet werden. Die neue Spalte
    ``zaehlerstand_integriert`` markiert jede rekonstruierte Zeile.
    """
    out = df.copy()
    ts = pd.DatetimeIndex(pd.to_datetime(out["Timestamp"]))
    schritt_h = (pd.Series(ts, index=range(len(ts))).diff()
                 .dt.total_seconds() / 3600.0)
    brauchbar = schritt_h.gt(0) & schritt_h.le(max_gap_hours)
    schritt = schritt_h.where(brauchbar, 0.0).fillna(0.0).to_numpy()

    power = pd.to_numeric(out["Power (kW)"], errors="coerce").fillna(0.0)
    flow = pd.to_numeric(out["Volume flow (l/h)"], errors="coerce").fillna(0.0)
    zuwachs = {
        "Energy (kWh)": np.clip(power.to_numpy(), 0.0, None) * schritt,
        "Volume (m³)": np.clip(flow.to_numpy(), 0.0, None) * schritt / 1000.0,
    }

    fehlt = out[KUMULATIVE_KANAELE].isna().any(axis=1).to_numpy()
    for kanal in KUMULATIVE_KANAELE:
        werte = pd.to_numeric(out[kanal], errors="coerce").to_numpy(
            dtype=float, copy=True)
        anker = 0.0
        for i in range(len(werte)):
            if np.isnan(werte[i]):
                anker = anker + zuwachs[kanal][i]
                werte[i] = anker
            else:
                anker = werte[i]
        out[kanal] = werte
    out["zaehlerstand_integriert"] = fehlt
    return out


def load_meter_timeseries(zaehlernummer: int,
                          data_dir: Path = DATA_DIR,
                          mit_ods: bool = False,
                          zaehlerstaende_integrieren: bool = False
                          ) -> pd.DataFrame:
    """Load, merge and clean all export files for one meter.

    Returns a DataFrame in the canonical 8-column schema, sorted by
    ascending Timestamp, duplicate timestamps dropped.

    ``mit_ods`` ist bewusst standardmaessig aus. Die Nachlieferung liegt
    nur fuer fuenf Zaehler vor; waere sie Standard, haetten diese fuenf
    eine um ein Jahr laengere Historie als die uebrigen 96, und jede
    Auswertung ueber alle Stationen wuerde unbemerkt ungleiche Zeitraeume
    mischen. Ausserdem bleiben die publizierten Zahlen der Notebooks 01
    bis 08 so reproduzierbar. Wer die Nachlieferung braucht, schaltet sie
    ausdruecklich zu.

    Zwischen den CSV-Generationen gewinnt die neuere. Gegenueber der
    ODS-Nachlieferung gewinnt dagegen die CSV, obwohl sie aelter ist:
    sie traegt die gemessenen Zaehlerstaende, die das ODS-Format gar
    nicht hat. Die ODS-Zeilen verlaengern die Reihe also nach hinten,
    ueberschreiben aber nichts. Ob die Werte im Ueberlappungszeitraum
    ueberhaupt zusammenpassen, prueft `vergleiche_ueberlappung`.

    Mit ``zaehlerstaende_integrieren=True`` werden die im ODS-Teil
    fehlenden kumulativen Kanaele rekonstruiert und die Zeilen in
    ``zaehlerstand_integriert`` markiert.
    """
    try:
        meters = discover_meter_files(data_dir)
    except FileNotFoundError:
        meters = {}
    ods = discover_meter_ods(data_dir) if mit_ods else {}
    if zaehlernummer not in meters and zaehlernummer not in ods:
        raise FileNotFoundError(
            f"no export for Zählernummer {zaehlernummer} in "
            f"{Path(data_dir)} - expected {zaehlernummer}__n.csv, "
            f"{zaehlernummer}_2025n.csv or {zaehlernummer}.ods")

    frames = []
    for path in meters.get(zaehlernummer, []):
        df = pd.read_csv(path, parse_dates=["Timestamp"])
        df = _derive_temperature_difference(df)
        missing = [c for c in SCHEMA if c not in df.columns]
        if missing:
            raise ValueError(
                f"{path.name}: missing expected columns {missing} - "
                f"got {list(df.columns)}")
        frames.append(df[SCHEMA])
    #concat oldest export first (by its last timestamp), so with
    #keep='last' the newer export generation wins on duplicate timestamps
    frames.sort(key=lambda f: f["Timestamp"].max())
    if zaehlernummer in ods:
        #die ODS-Reihe kommt nach vorne, damit keep='last' sie bei
        #gleichem Zeitstempel gegen die vollstaendigere CSV verliert
        frames.insert(0, load_meter_ods(zaehlernummer, data_dir))

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("Timestamp", kind="stable")
    out = out.drop_duplicates(subset="Timestamp", keep="last")
    out = out.reset_index(drop=True)
    if zaehlerstaende_integrieren:
        out = ergaenze_zaehlerstaende(out)
    return out


def vergleiche_ueberlappung(zaehlernummer: int,
                            data_dir: Path = DATA_DIR,
                            toleranz: float = 0.051) -> pd.DataFrame:
    """Gegenprobe CSV gegen ODS auf den gemeinsamen Zeitstempeln.

    Die wichtigste Validierung der Nachlieferung: decken sich die Werte
    im Ueberlappungszeitraum, ist das Zusammenfuehren zulaessig; tun sie
    es nicht, liegen zwei verschiedene Messreihen vor und der Anschluss
    waere ein Artefakt. `toleranz` ist etwas groesser als die halbe
    Rundungsstufe von 0,1, damit die Rundung des Exports nicht als
    Abweichung zaehlt.

    Rueckgabe: eine Zeile je Kanal mit Zahl der gemeinsamen Stunden,
    Anteil der Werte innerhalb der Toleranz, groesster Abweichung und
    Korrelation. Zusaetzlich eine Zeile ``Timestamp`` mit der
    Ueberdeckung der beiden Zeitstempelmengen.
    """
    ods = load_meter_ods(zaehlernummer, data_dir).set_index("Timestamp")
    csv_frames = [_derive_temperature_difference(
                      pd.read_csv(p, parse_dates=["Timestamp"]))[SCHEMA]
                  for p in discover_meter_files(data_dir)[zaehlernummer]]
    csv_frames.sort(key=lambda f: f["Timestamp"].max())
    csv = (pd.concat(csv_frames, ignore_index=True)
           .sort_values("Timestamp", kind="stable")
           .drop_duplicates(subset="Timestamp", keep="last")
           .set_index("Timestamp"))

    gemeinsam = ods.index.intersection(csv.index)
    rows = [{
        "kanal": "Timestamp",
        "n_gemeinsam": len(gemeinsam),
        "anteil_ods": len(gemeinsam) / len(ods) if len(ods) else np.nan,
        "anteil_csv": len(gemeinsam) / len(csv) if len(csv) else np.nan,
        "von": gemeinsam.min() if len(gemeinsam) else pd.NaT,
        "bis": gemeinsam.max() if len(gemeinsam) else pd.NaT,
    }]
    for kanal in SCHEMA:
        if kanal == "Timestamp" or kanal in KUMULATIVE_KANAELE:
            continue
        a = pd.to_numeric(ods.loc[gemeinsam, kanal], errors="coerce")
        b = pd.to_numeric(csv.loc[gemeinsam, kanal], errors="coerce")
        d = (a - b).abs()
        rows.append({
            "kanal": kanal,
            "n_gemeinsam": int(d.notna().sum()),
            "anteil_in_toleranz": float((d <= toleranz).mean()),
            "max_abweichung": float(d.max()) if d.notna().any() else np.nan,
            "korrelation": float(a.corr(b)),
        })
    return pd.DataFrame(rows)


def materialize_meters(out_dir: Path,
                       data_dir: Path = DATA_DIR,
                       mit_ods: bool = False,
                       zaehlerstaende_integrieren: bool = False
                       ) -> pd.DataFrame:
    """Write one merged ``<Zählernummer>.csv`` per meter into `out_dir`.

    The resulting directory has the same layout as the synthetic
    ``data/raw/synthetic/meters/`` and can be fed straight into
    ``features.features_for_directory``. Returns an inventory DataFrame
    (one row per meter: files merged, rows, time range). Mit
    ``mit_ods=True`` sind auch Zaehler enthalten, fuer die nur eine
    ODS-Nachlieferung vorliegt; zum Standard siehe
    `load_meter_timeseries`.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        csv_meters = discover_meter_files(data_dir)
    except FileNotFoundError:
        csv_meters = {}
    ods_meters = discover_meter_ods(data_dir) if mit_ods else {}
    if not csv_meters and not ods_meters:
        raise FileNotFoundError(
            f"weder CSV-Exporte noch ODS-Nachlieferungen in {data_dir}")

    inventory = []
    for zid in sorted(set(csv_meters) | set(ods_meters)):
        df = load_meter_timeseries(
            zid, data_dir, mit_ods=mit_ods,
            zaehlerstaende_integrieren=zaehlerstaende_integrieren)
        df.to_csv(out_dir / f"{zid}.csv", index=False)
        inventory.append({
            "Zählernummer": zid,
            "n_files": len(csv_meters.get(zid, [])) + (1 if zid in ods_meters
                                                       else 0),
            "hat_ods": zid in ods_meters,
            "n_rows": len(df),
            "ts_min": df["Timestamp"].min(),
            "ts_max": df["Timestamp"].max(),
        })
    return pd.DataFrame(inventory)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--materialize", type=Path, metavar="DIR",
                   help="write merged per-meter CSVs into DIR")
    p.add_argument("--mit-ods", action="store_true",
                   help="die ODS-Nachlieferung mit einmischen (verlaengert "
                        "die Historie, aber nur fuer die Zaehler, fuer die "
                        "sie vorliegt)")
    p.add_argument("--integriere-zaehlerstaende", action="store_true",
                   help="fehlende kumulative Kanaele der ODS-Nachlieferung "
                        "durch Integration rekonstruieren")
    p.add_argument("--ueberlappung", type=int, metavar="ZAEHLERNUMMER",
                   help="CSV gegen ODS auf den gemeinsamen Stunden pruefen")
    args = p.parse_args()

    meters = discover_meter_files()
    n_files = sum(len(v) for v in meters.values())
    print(f"found {n_files} export CSVs for {len(meters)} meters in {DATA_DIR}")
    ods_meters = discover_meter_ods()
    print(f"  dazu {len(ods_meters)} ODS-Nachlieferungen "
          f"({len(set(ods_meters) - set(meters))} davon ohne CSV)")

    try:
        from . import load_data as ld
        known = set(ld.load_logical_nodes()["Zählernummer"].astype(int))
        in_topo = len(set(meters) & known)
        print(f"  {in_topo} meters match Nodes_Edges.ods, "
              f"{len(meters) - in_topo} do not (meter swaps? see Zuordnung.xlsx), "
              f"{len(known - set(meters))} topology meters have no CSV")
    except Exception as e:  # topology file missing is fine for a pure inventory
        print(f"  (skipping topology cross-check: {e})")

    if args.ueberlappung:
        print(vergleiche_ueberlappung(args.ueberlappung).to_string(index=False))

    if args.materialize:
        inv = materialize_meters(
            args.materialize, mit_ods=args.mit_ods,
            zaehlerstaende_integrieren=args.integriere_zaehlerstaende)
        print(f"wrote {len(inv)} merged CSVs -> {args.materialize}")
        print(f"  time range: {inv['ts_min'].min()} .. {inv['ts_max'].max()}")
        print(f"  rows per meter: min {inv['n_rows'].min()}, "
              f"median {int(inv['n_rows'].median())}, max {inv['n_rows'].max()}")
