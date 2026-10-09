"""
Außentemperatur aus DWD Open Data (Climate Data Center).

Stündliche Lufttemperatur als Witterungskontext für Saisonsegmente und
für die Normierung der Zählerdaten.

Station
-------
- Standard: DWD-Station 2600 "Kitzingen" (193 m ü. NN), rund 13,3 km
  westlich von Wiesentheid, gleiches Maintal-Klima
- Alternative wäre 1107 "Ebrach" (346 m), gleich weit weg, aber rund
  150 m höher und damit kühler
- Wiesentheid liegt auf etwa 250 m, der Höhenversatz ist eine offene Frage
- `station_id` ist Parameter, für andere Teilnetze

Zeitzone
--------
- DWD liefert `MESS_DATUM` in UTC, die Zählerexporte stehen in Lokalzeit
  (Europe/Berlin mit Sommerzeit)
- umgerechnet wird hier: Raster in UTC, dann nach Europe/Berlin, dann
  Zeitzone entfernen
- dadurch gibt es wie in den Zählerexporten im Oktober eine doppelte und
  im März eine fehlende Stunde; die doppelte wird dedupliziert

Cache
-----
- `refresh_cache()` lädt die Archive einmalig nach ``data/raw/weather/``
  (gitignored)
- `load_outdoor_temperature()` liest danach nur noch den Cache, ohne
  Netzzugriff
- ohne Cache und mit ``allow_download=False`` gibt es einen Fehler

CLI:

    python -m src.weather                  # Cache anlegen/aktualisieren
    python -m src.weather --station 1107   # andere DWD-Station
    python -m src.weather --offline        # nur Cache-Status zeigen
"""

from __future__ import annotations

import argparse
import io
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd

DWD_BASE = ("https://opendata.dwd.de/climate_environment/CDC/"
            "observations_germany/climate/hourly/air_temperature")

#Kitzingen, 13,3 km vom Versorgungsgebiet; Begruendung siehe Modul-Docstring
DEFAULT_STATION_ID = 2600

CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "weather"

LOCAL_TZ = "Europe/Berlin"

#-999 ist der DWD-Fehlwert in allen Produktdateien
DWD_MISSING = -999.0

TimestampLike = Union[str, pd.Timestamp]


class WeatherDownloadError(RuntimeError):
    """DWD Open Data war nicht erreichbar oder lieferte kein Archiv."""


def cache_path(station_id: int = DEFAULT_STATION_ID,
               cache_dir: Path = CACHE_DIR) -> Path:
    """Pfad der Cache-CSV für eine Station."""
    return Path(cache_dir) / f"dwd_tu_{int(station_id):05d}.csv"


def _fetch(url: str, timeout: int = 60) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise WeatherDownloadError(
            f"DWD Open Data nicht erreichbar ({url}): {exc}. In Netzen mit "
            "Proxy oder Firewall das Archiv manuell herunterladen und mit "
            "refresh_cache(archives=[...]) einlesen.") from exc


def _archive_urls(station_id: int, timeout: int = 60) -> list[str]:
    """URLs des historischen und des aktuellen TU-Archivs einer Station.

    Der Dateiname des historischen Archivs enthält den Datenzeitraum und
    ändert sich mit jeder DWD-Aktualisierung, wird also aus dem
    Verzeichnislisting gelesen statt hartkodiert.
    """
    sid = f"{int(station_id):05d}"
    urls = []
    listing = _fetch(f"{DWD_BASE}/historical/", timeout=timeout).decode(
        "latin-1", errors="replace")
    hist = re.findall(rf"stundenwerte_TU_{sid}_\d+_\d+_hist\.zip", listing)
    urls.extend(f"{DWD_BASE}/historical/{name}" for name in sorted(set(hist)))
    urls.append(f"{DWD_BASE}/recent/stundenwerte_TU_{sid}_akt.zip")
    if not hist:
        #recent deckt nur rund 500 Tage ab - ohne historical fehlen die Altjahre
        pass
    return urls


def parse_tu_archive(raw: bytes) -> pd.DataFrame:
    """Ein TU-Archiv (ZIP) in ``timestamp_utc`` / ``t_out`` übersetzen.

    Erwartet die DWD-Produktdatei ``produkt_tu_stunde_*.txt`` mit den
    Spalten ``MESS_DATUM`` (YYYYMMDDHH, UTC) und ``TT_TU`` (Lufttemperatur
    2 m in °C). Fehlwerte (-999) werden zu NaN, nicht zu 0.
    """
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = [n for n in zf.namelist()
                 if n.lower().startswith("produkt_tu_stunde")]
        if not names:
            raise ValueError(
                "TU-Archiv enthält keine produkt_tu_stunde_*.txt - "
                f"gefunden: {zf.namelist()}")
        with zf.open(names[0]) as fh:
            df = pd.read_csv(fh, sep=";", encoding="latin-1")

    df.columns = [c.strip().upper() for c in df.columns]
    missing = [c for c in ("MESS_DATUM", "TT_TU") if c not in df.columns]
    if missing:
        raise ValueError(
            f"TU-Produktdatei ohne Spalten {missing} - got {list(df.columns)}")

    out = pd.DataFrame({
        "timestamp_utc": pd.to_datetime(df["MESS_DATUM"].astype(str),
                                        format="%Y%m%d%H", utc=True),
        "t_out": pd.to_numeric(df["TT_TU"], errors="coerce"),
    })
    out.loc[out["t_out"] <= DWD_MISSING, "t_out"] = np.nan
    out = out.dropna(subset=["timestamp_utc"])
    out = out.sort_values("timestamp_utc", kind="stable")
    out = out.drop_duplicates(subset="timestamp_utc", keep="last")
    return out.reset_index(drop=True)


def refresh_cache(station_id: int = DEFAULT_STATION_ID,
                  cache_dir: Path = CACHE_DIR,
                  archives: Optional[list[Path]] = None,
                  timeout: int = 60) -> Path:
    """Historisches und aktuelles TU-Archiv holen und als Cache-CSV ablegen.

    `archives` erlaubt lokal bereits heruntergeladene ZIP-Dateien statt
    eines Netzzugriffs - der Weg für Umgebungen, in denen opendata.dwd.de
    durch Proxy oder Firewall blockiert ist.

    Die Cache-CSV enthält die Rohmessung in UTC ohne Lückenfüllung;
    Zeitzonenumrechnung und Interpolation macht erst
    `load_outdoor_temperature`.
    """
    frames = []
    if archives:
        for path in archives:
            frames.append(parse_tu_archive(Path(path).read_bytes()))
    else:
        for url in _archive_urls(station_id, timeout=timeout):
            try:
                frames.append(parse_tu_archive(_fetch(url, timeout=timeout)))
            except WeatherDownloadError:
                #recent fehlt bei stillgelegten Stationen, historical bei neuen
                if url.endswith("_akt.zip") and frames:
                    continue
                raise

    if not frames:
        raise WeatherDownloadError(
            f"kein TU-Archiv für Station {station_id} gefunden")

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("timestamp_utc", kind="stable")
    df = df.drop_duplicates(subset="timestamp_utc", keep="last")

    target = cache_path(station_id, cache_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)
    return target


def load_outdoor_temperature(start: TimestampLike,
                             end: TimestampLike,
                             station_id: int = DEFAULT_STATION_ID,
                             cache_dir: Path = CACHE_DIR,
                             allow_download: bool = True,
                             max_gap_hours: int = 6,
                             tz: str = LOCAL_TZ) -> pd.DataFrame:
    """Stündliche Außentemperatur für [start, end] in Lokalzeit.

    `start` und `end` sind naive Lokalzeit-Zeitstempel (dieselbe Zeitbasis
    wie die Zählerexporte), inklusive beider Grenzen. Rückgabe ist ein
    DataFrame mit den Spalten

        timestamp       naive Lokalzeit, lückenloses Stundenraster
        t_out           Lufttemperatur 2 m in °C
        interpolated    True, wenn der Wert linear gefüllt wurde

    Lücken bis `max_gap_hours` Stunden werden linear interpoliert und
    über `interpolated` markiert. Längere Lücken bleiben NaN - eine
    mehrtägige Messlücke wird nicht erfunden. `max_gap_hours=0` schaltet
    die Interpolation ab.

    Netzzugriff findet nur statt, wenn der Cache fehlt und
    `allow_download` True ist. Existiert der Cache, läuft die Funktion
    vollständig offline.
    """
    path = cache_path(station_id, cache_dir)
    if not path.exists():
        if not allow_download:
            raise FileNotFoundError(
                f"kein Wetter-Cache unter {path} und allow_download=False - "
                f"einmalig 'python -m src.weather --station {station_id}' "
                "ausführen")
        refresh_cache(station_id, cache_dir)

    cached = pd.read_csv(path, parse_dates=["timestamp_utc"])
    if cached["timestamp_utc"].dt.tz is None:
        cached["timestamp_utc"] = cached["timestamp_utc"].dt.tz_localize("UTC")
    series = cached.set_index("timestamp_utc")["t_out"].sort_index()

    #Raster in UTC bilden und danach konvertieren: so entstehen genau die
    #Sommerzeit-Effekte der Zaehlerexporte statt kuenstlicher Luecken
    start_local = pd.Timestamp(start)
    end_local = pd.Timestamp(end)
    if end_local < start_local:
        raise ValueError(f"end ({end_local}) liegt vor start ({start_local})")
    start_utc = start_local.tz_localize(tz, nonexistent="shift_forward",
                                        ambiguous=True).tz_convert("UTC")
    end_utc = end_local.tz_localize(tz, nonexistent="shift_forward",
                                    ambiguous=True).tz_convert("UTC")
    grid_utc = pd.date_range(start_utc.floor("h"), end_utc.ceil("h"),
                             freq="h", tz="UTC")

    values = series.reindex(grid_utc)
    filled = values.copy()
    if max_gap_hours > 0:
        #interpolate(limit=...) fuellt die ersten n Stunden jeder Luecke; hier
        #soll dagegen eine zu lange Luecke komplett NaN bleiben, also erst die
        #Lauflaenge je NaN-Block bestimmen und lange Bloecke zurueckdrehen
        na = values.isna()
        blocks = (na != na.shift()).cumsum()
        run_len = na.groupby(blocks).transform("size")
        filled = values.interpolate(method="time", limit_area="inside")
        filled[na & (run_len > max_gap_hours)] = np.nan
    interpolated = values.isna() & filled.notna()

    local = grid_utc.tz_convert(tz).tz_localize(None)
    out = pd.DataFrame({
        "timestamp": local,
        "t_out": filled.to_numpy(),
        "interpolated": interpolated.to_numpy(),
    })
    #doppelte Lokalstunde bei der Zeitumstellung im Oktober
    out = out.drop_duplicates(subset="timestamp", keep="first")
    out = out[(out["timestamp"] >= start_local) &
              (out["timestamp"] <= end_local)]
    return out.sort_values("timestamp").reset_index(drop=True)


def heating_degree_hours(df: pd.DataFrame,
                         t_heiz: float = 15.0,
                         column: str = "t_out") -> pd.Series:
    """Heizgradstunden je Stunde: max(t_heiz - t_out, 0).

    `t_heiz` ist die Heizgrenztemperatur in °C. 15 °C ist der in VDI 2067
    und in der Fernwärmepraxis übliche Wert für Bestandsgebäude; für
    Neubauten liegt sie niedriger, deshalb ist sie Parameter und keine
    Konstante. Die Summe über einen Zeitraum ergibt die Heizgradstunden
    (Kh), geteilt durch 24 die Heizgradtage.

    Stunden ohne Messwert bleiben NaN, werden also nicht als 0 gezählt -
    sonst sähe eine Messlücke wie eine warme Phase aus.
    """
    if column not in df.columns:
        raise KeyError(f"Spalte '{column}' fehlt - vorhanden: {list(df.columns)}")
    t = pd.to_numeric(df[column], errors="coerce")
    hdh = (t_heiz - t).clip(lower=0.0)
    hdh.name = "heating_degree_hours"
    if "timestamp" in df.columns:
        hdh.index = pd.DatetimeIndex(df["timestamp"])
    return hdh


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--station", type=int, default=DEFAULT_STATION_ID,
                   help="DWD-Stations-ID (Voreinstellung 2600 Kitzingen)")
    p.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    p.add_argument("--offline", action="store_true",
                   help="nur Cache-Status zeigen, nicht herunterladen")
    p.add_argument("--archive", type=Path, action="append",
                   help="lokal vorliegendes TU-ZIP statt Download "
                        "(mehrfach angebbar)")
    args = p.parse_args()

    target = cache_path(args.station, args.cache_dir)
    if not args.offline and (args.archive or not target.exists()):
        try:
            target = refresh_cache(args.station, args.cache_dir,
                                   archives=args.archive)
            print(f"Cache geschrieben: {target}")
        except WeatherDownloadError as exc:
            raise SystemExit(f"Download fehlgeschlagen: {exc}")

    if not target.exists():
        raise SystemExit(f"kein Cache unter {target}")

    cached = pd.read_csv(target, parse_dates=["timestamp_utc"])
    print(f"Station {args.station}: {len(cached)} Stundenwerte, "
          f"{cached['timestamp_utc'].min()} .. {cached['timestamp_utc'].max()} (UTC)")
    print(f"  Fehlwerte: {int(cached['t_out'].isna().sum())}")
