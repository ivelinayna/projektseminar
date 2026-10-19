"""
Gemeinsamer Zugang zu den Stundenreihen aus Notebook 00.

Notebook `00_eda_hast_stationsprofile.ipynb` ist die verbindliche
Datenaufbereitung des Projekts. Es führt CSV- und ODS-Exporte je Zähler
zusammen, rechnet die ODS-Werte um Faktor 1000 zurück, legt die
Zeitstempel auf die volle Stunde, entfernt Dubletten, setzt
physikalisch unmögliche Werte auf NaN und schreibt je Zähler eine Datei
auf einem lückenlosen Stundenraster nach `data/processed/real_meters/`.

Alle Auswertungen ab Notebook 06 lesen genau diese Dateien und nicht
`data/raw/` direkt. Dieses Modul ist der eine Ladeweg dafür:

    lade_serien         Dict Zählernummer -> Stundenreihe
    pruefe_ausgabe      bricht ab, wenn NB 00 fehlt, warnt, wenn
                        data/raw neuer ist als die NB-00-Ausgabe
    nicht_aufbereitet   Zähler aus data/raw, die NB 00 übersprungen hat
    lange_reihen        Zähler, die über das gemeinsame Exportende
                        hinausreichen (ODS-Nachlieferung)
    zaehlerstaende_integrieren
                        fehlende Energie- und Volumenstände aus
                        Leistung und Volumenstrom ergänzen
    stationsfeatures    Stationsfeatures aus `features` auf diesen Reihen

Zur ODS-Nachlieferung: NB 00 lässt bei Überlappung die neuere
Exportgeneration gewinnen. Bei den fünf Zählern mit Nachlieferung
stammen die Zeilen deshalb ab dem 26.05.2024 (Wechsel der ODS-Datei auf
Stundenabtastung) und davor täglich um 23 Uhr aus der ODS-Datei, und
dort fehlen Energie und Volumen. Leistung, Durchfluss und Temperaturen
sind mit der CSV identisch. `lade_serien` ergänzt die fehlenden
Zählerstände deshalb standardmäßig aus Leistung und Volumenstrom
(`zaehlerstaende_integrieren`), aber nur in Stunden, in denen Leistung
bzw. Durchfluss gemessen sind. Die Zahl der ergänzten Stunden steht in
``serie.attrs["zaehlerstand_integriert"]``. Die Integration trifft das
Niveau, einzelne Tage weichen ab (Notebook 08, Abschnitt 9).

Die Rasterzeilen, in denen NB 00 eine nicht gemessene Stunde markiert
(alle Messkanäle leer), entfernt `lade_serien` standardmäßig. Sie tragen
keine Information, würden aber in `performance.tagesdifferenzen` aus
einer einzelnen fehlenden Stunde zwei verworfene Intervalle machen.
Maskierte Einzelwerte bleiben als NaN in ihrer Zeile stehen.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
METER_DIR = REPO / "data" / "processed" / "real_meters"
NB00 = "notebooks/00_eda_hast_stationsprofile.ipynb"

#Spaltennamen in der NB-00-Ausgabe auf das Schema von features.features_for_meter
SPALTEN_MAP = {
    "Energy (kWh)": "energy",
    "Volume flow (l/h)": "flow",
    "Power (kW)": "power",
    "Temperature difference (°C)": "dt",
    "Flow temperature (°C)": "vl",
    "Return temperature (°C)": "rt",
    "Volume (m³)": "volume",
}
MESSSPALTEN = list(SPALTEN_MAP.values())

_ROH_RE = re.compile(r"^(\d+)(?:_.*\.csv|\.ods)$")


def _zaehler_dateien(meter_dir: Path) -> Dict[int, Path]:
    out = {}
    for csv in sorted(Path(meter_dir).glob("*.csv")):
        try:
            out[int(csv.stem)] = csv
        except ValueError:
            continue
    return out


def _roh_dateien(raw_dir: Path) -> Dict[int, list]:
    out: Dict[int, list] = {}
    for p in sorted(Path(raw_dir).glob("*")):
        m = _ROH_RE.match(p.name)
        if m:
            out.setdefault(int(m.group(1)), []).append(p)
    return out


def _raw_zu(meter_dir: Path) -> Path:
    #NB 00 schreibt nach data/processed/real_meters, die Rohdaten liegen in data/raw
    return Path(meter_dir).resolve().parent.parent / "raw"


def pruefe_ausgabe(meter_dir: Path = METER_DIR,
                   raw_dir: Optional[Path] = None) -> int:
    """Anzahl Zählerdateien in `meter_dir`, sonst ein klarer Abbruch.

    Liegt in `raw_dir` (Voreinstellung: ``data/raw`` neben
    ``data/processed``) eine Exportdatei, die jünger ist als die älteste
    Datei der NB-00-Ausgabe, kommt eine Warnung: dann ist nach einer
    Nachlieferung NB 00 nicht erneut gelaufen.
    """
    meter_dir = Path(meter_dir)
    if raw_dir is None:
        raw_dir = _raw_zu(meter_dir)
    dateien = _zaehler_dateien(meter_dir) if meter_dir.is_dir() else {}
    if not dateien:
        raise FileNotFoundError(
            f"keine Zählerdateien in {meter_dir} - zuerst {NB00} ausführen")
    if Path(raw_dir).is_dir():
        roh = [p for ps in _roh_dateien(raw_dir).values() for p in ps]
        if roh:
            neueste_roh = max(p.stat().st_mtime for p in roh)
            aelteste_aus = min(p.stat().st_mtime for p in dateien.values())
            if neueste_roh > aelteste_aus:
                warnings.warn(
                    f"data/raw enthält Exporte, die neuer sind als {meter_dir.name}; "
                    f"{NB00} erneut ausführen", stacklevel=2)
    return len(dateien)


def lade_serien(meter_dir: Path = METER_DIR,
                zaehler: Optional[Iterable[int]] = None,
                leere_stunden_entfernen: bool = True,
                raw_dir: Optional[Path] = None,
                zaehlerstaende_ergaenzen: bool = True
                ) -> Dict[int, pd.DataFrame]:
    """NB-00-Ausgabe als Dict Zählernummer -> Stundenreihe.

    Rückgabe auf einem DatetimeIndex mit den Spalten ``energy, flow,
    power, dt, vl, rt, volume``. Stunden, in denen alle Messkanäle leer
    sind, fallen mit `leere_stunden_entfernen` heraus. Mit
    `zaehlerstaende_ergaenzen` werden leere Energie- und Volumenstände
    aus Leistung und Volumenstrom integriert, siehe Modulbeschreibung.
    """
    pruefe_ausgabe(meter_dir, raw_dir)
    auswahl = None if zaehler is None else {int(z) for z in zaehler}
    serien: Dict[int, pd.DataFrame] = {}
    for zid, csv in _zaehler_dateien(meter_dir).items():
        if auswahl is not None and zid not in auswahl:
            continue
        df = pd.read_csv(csv, parse_dates=["Timestamp"]).rename(
            columns=SPALTEN_MAP)
        df = df.set_index("Timestamp").sort_index()
        df.index = pd.DatetimeIndex(df.index).floor("h")
        df = df[~df.index.duplicated(keep="last")]
        if leere_stunden_entfernen:
            vorhanden = [c for c in MESSSPALTEN if c in df.columns]
            df = df.dropna(subset=vorhanden, how="all")
        if zaehlerstaende_ergaenzen:
            df = _ergaenzen_wo_gemessen(df)
        serien[zid] = df
    return serien


def _ergaenzen_wo_gemessen(df: pd.DataFrame) -> pd.DataFrame:
    luecke_e = df["energy"].isna() & df["power"].notna()
    luecke_v = df["volume"].isna() & df["flow"].notna()
    n = int((luecke_e | luecke_v).sum())
    if n:
        voll = zaehlerstaende_integrieren(df)
        #nur dort fuellen, wo der Momentanwert gemessen ist, sonst bliebe
        #ueber einen Ausfall ein Nullzuwachs stehen
        df = df.copy()
        df.loc[luecke_e, "energy"] = voll.loc[luecke_e, "energy"]
        df.loc[luecke_v, "volume"] = voll.loc[luecke_v, "volume"]
    df.attrs["zaehlerstand_integriert"] = n
    return df


def stationsfeatures(meter_dir: Path = METER_DIR,
                     nodes_df: Optional[pd.DataFrame] = None,
                     address_map: Optional[Dict[int, str]] = None,
                     zaehler: Optional[Iterable[int]] = None) -> pd.DataFrame:
    """Stationsfeatures aus `features` auf den NB-00-Reihen.

    Wie ``features.features_for_directory(meter_dir)``, aber mit
    ergänzten Zählerständen. Ohne die Ergänzung wären Jahresenergie,
    Jahresvolumen und Volllaststunden bei den Zählern mit Nachlieferung
    leer, weil der letzte Stand aus der ODS-Datei kommt. Leere
    Rasterzeilen innerhalb der Reihe bleiben stehen, damit die übrigen
    Zähler dieselben Werte bekommen wie über `features_for_directory`.
    Leere Zeilen am Anfang und Ende fallen weg, sonst wäre der erste
    bzw. letzte Zählerstand NaN.
    """
    from . import features as ft

    serien = lade_serien(meter_dir, zaehler=zaehler,
                         leere_stunden_entfernen=False)
    for zid, df in serien.items():
        belegt = df[[c for c in MESSSPALTEN if c in df.columns]].notna().any(axis=1)
        if belegt.any():
            serien[zid] = df.loc[belegt.idxmax():belegt[::-1].idxmax()]
    return ft.features_for_frames(serien, nodes_df=nodes_df,
                                  address_map=address_map)


def nicht_aufbereitet(meter_dir: Path = METER_DIR,
                      raw_dir: Optional[Path] = None) -> pd.DataFrame:
    """Zähler mit Rohexport, aber ohne Datei in der NB-00-Ausgabe.

    NB 00 überspringt Zähler, deren Export eine Pflichtspalte fehlt, und
    nennt den Grund in seiner Ausgabe. Hier steht nur, welche es sind.
    """
    raw_dir = _raw_zu(meter_dir) if raw_dir is None else Path(raw_dir)
    roh = _roh_dateien(raw_dir) if raw_dir.is_dir() else {}
    aus = _zaehler_dateien(meter_dir) if Path(meter_dir).is_dir() else {}
    zeilen = [{"meter": zid,
               "dateien": ", ".join(p.name for p in roh[zid]),
               "grund": "von NB 00 übersprungen (siehe dort, Abschnitt 2)"}
              for zid in sorted(set(roh) - set(aus))]
    return pd.DataFrame(zeilen, columns=["meter", "dateien", "grund"])


def lange_reihen(serien: Dict[int, pd.DataFrame],
                 toleranz_tage: int = 30) -> list:
    """Zähler, deren Reihe deutlich nach dem typischen Exportende endet.

    Typisch heißt Median der Endzeitpunkte über alle Zähler. Das sind
    die Zähler mit ODS-Nachlieferung, ohne dass dafür `data/raw` gelesen
    werden muss.
    """
    enden = pd.Series({z: d.index[-1] for z, d in serien.items() if len(d)})
    if enden.empty:
        return []
    grenze = enden.median() + pd.Timedelta(days=toleranz_tage)
    return sorted(int(z) for z in enden[enden > grenze].index)


def zaehlerstaende_integrieren(serie: pd.DataFrame) -> pd.DataFrame:
    """Leere ``energy``/``volume`` aus ``power`` und ``flow`` aufsummieren.

    Reicht an `load_timeseries.ergaenze_zaehlerstaende` durch, nur im
    Spaltenschema von `lade_serien`. Die Spalte
    ``zaehlerstand_integriert`` markiert jede ergänzte Stunde.
    """
    from . import load_timeseries as lts

    zurueck = {v: k for k, v in SPALTEN_MAP.items()}
    df = serie.rename(columns=zurueck).rename_axis("Timestamp").reset_index()
    out = lts.ergaenze_zaehlerstaende(df)
    return out.rename(columns=SPALTEN_MAP).set_index("Timestamp")
