"""
Tests für src.weather (DWD-Außentemperatur) und src.season (Segmente).

Laufen ohne Netzzugriff und ohne Rohdaten: die DWD-Archive werden als
kleine ZIP-Dateien in tmp_path nachgebaut, der Cache liegt ebenfalls
dort. Wo geprüft werden soll, dass wirklich nichts heruntergeladen wird,
ersetzt ein Monkeypatch `weather._fetch` durch eine Funktion, die sofort
fehlschlägt.

Standalone lauffähig:

    python -m tests.test_weather
    python -m pytest tests/test_weather.py
"""

import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from src import season, weather


def _tu_archive(path, start_utc="2023-01-01 00:00", hours=48,
                values=None, station_id=2600):
    """Eine DWD-TU-Produktdatei als ZIP schreiben, wie sie CDC ausliefert."""
    ts = pd.date_range(start_utc, periods=hours, freq="h")
    if values is None:
        values = np.linspace(0.0, 10.0, hours)
    lines = ["STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor"]
    for t, v in zip(ts, values):
        lines.append(f"{station_id:>10};{t.strftime('%Y%m%d%H')};    3;"
                     f"{v:>8.1f};{80.0:>8.1f};eor")
    body = "\n".join(lines) + "\n"
    name = (f"produkt_tu_stunde_{ts[0]:%Y%m%d}_{ts[-1]:%Y%m%d}_"
            f"{station_id:05d}.txt")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(name, body.encode("latin-1"))
    return path


def _write_cache(cache_dir, start_utc, values, station_id=2600):
    """Cache-CSV direkt schreiben (UTC, ohne Lückenfüllung)."""
    ts = pd.date_range(start_utc, periods=len(values), freq="h", tz="UTC")
    df = pd.DataFrame({"timestamp_utc": ts, "t_out": values})
    target = weather.cache_path(station_id, cache_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)
    return target


def _no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("Netzzugriff, obwohl der Cache vorhanden ist")
    monkeypatch.setattr(weather, "_fetch", boom)


def test_parse_tu_archive_schema_and_missing_value(tmp_path):
    vals = [1.0, -999.0, 3.0, 4.0]
    zip_path = _tu_archive(tmp_path / "a.zip", hours=4, values=vals)
    df = weather.parse_tu_archive(zip_path.read_bytes())
    assert list(df.columns) == ["timestamp_utc", "t_out"]
    assert len(df) == 4
    assert str(df["timestamp_utc"].dt.tz) == "UTC"
    assert df["t_out"].iloc[0] == 1.0
    assert np.isnan(df["t_out"].iloc[1])  # -999 wird NaN, nicht 0
    assert df["timestamp_utc"].iloc[0] == pd.Timestamp("2023-01-01", tz="UTC")


def test_parse_tu_archive_rejects_foreign_zip(tmp_path):
    p = tmp_path / "b.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("irgendwas.txt", "kein TU-Produkt")
    with pytest.raises(ValueError, match="produkt_tu_stunde"):
        weather.parse_tu_archive(p.read_bytes())


def test_refresh_cache_from_local_archives_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(weather, "_fetch", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("kein Download erwartet")))
    hist = _tu_archive(tmp_path / "hist.zip", "2023-01-01 00:00", 24)
    akt = _tu_archive(tmp_path / "akt.zip", "2023-01-01 12:00", 24)
    out = weather.refresh_cache(cache_dir=tmp_path, archives=[hist, akt])
    assert out == weather.cache_path(2600, tmp_path)
    cached = pd.read_csv(out, parse_dates=["timestamp_utc"])
    #24 h + 24 h mit 12 h Ueberlappung -> 36 eindeutige Stunden
    assert len(cached) == 36
    assert cached["timestamp_utc"].is_monotonic_increasing


def test_missing_cache_without_download_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="allow_download"):
        weather.load_outdoor_temperature("2023-01-01", "2023-01-02",
                                         cache_dir=tmp_path,
                                         allow_download=False)


def test_load_uses_cache_offline(tmp_path, monkeypatch):
    _write_cache(tmp_path, "2023-01-01 00:00", np.full(72, 5.0))
    _no_network(monkeypatch)
    out = weather.load_outdoor_temperature("2023-01-01 06:00", "2023-01-02 06:00",
                                           cache_dir=tmp_path)
    assert list(out.columns) == ["timestamp", "t_out", "interpolated"]
    assert len(out) == 25
    assert out["timestamp"].iloc[0] == pd.Timestamp("2023-01-01 06:00")
    assert (out["t_out"] == 5.0).all()
    assert not out["interpolated"].any()
    assert out["timestamp"].dt.tz is None


def test_utc_to_local_shift_winter_and_summer(tmp_path, monkeypatch):
    #Winter: UTC+1, Sommer: UTC+2. Markerwert bei 12:00 UTC.
    vals = np.zeros(48)
    vals[12] = 7.5
    _write_cache(tmp_path, "2023-01-01 00:00", vals)
    _no_network(monkeypatch)
    winter = weather.load_outdoor_temperature("2023-01-01 00:00",
                                              "2023-01-01 23:00",
                                              cache_dir=tmp_path)
    hit = winter.loc[winter["t_out"] == 7.5, "timestamp"].iloc[0]
    assert hit == pd.Timestamp("2023-01-01 13:00")

    vals = np.zeros(48)
    vals[12] = 7.5
    _write_cache(tmp_path, "2023-07-01 00:00", vals)
    sommer = weather.load_outdoor_temperature("2023-07-01 00:00",
                                              "2023-07-01 23:00",
                                              cache_dir=tmp_path)
    hit = sommer.loc[sommer["t_out"] == 7.5, "timestamp"].iloc[0]
    assert hit == pd.Timestamp("2023-07-01 14:00")


def test_local_grid_has_no_fake_gap_at_dst_change(tmp_path, monkeypatch):
    #Umstellung auf Sommerzeit am 26.03.2023: lokal fehlt 02:00.
    _write_cache(tmp_path, "2023-03-25 00:00", np.full(96, 4.0))
    _no_network(monkeypatch)
    out = weather.load_outdoor_temperature("2023-03-26 00:00",
                                           "2023-03-26 23:00",
                                           cache_dir=tmp_path)
    assert out["t_out"].notna().all()
    assert not out["interpolated"].any()
    assert len(out) == 23  # der Tag hat lokal nur 23 Stunden
    assert pd.Timestamp("2023-03-26 02:00") not in set(out["timestamp"])


def test_gap_is_interpolated_and_flagged(tmp_path, monkeypatch):
    vals = np.full(96, 10.0)
    vals[30:33] = np.nan          # 3 h Luecke, innerhalb max_gap_hours
    vals[40] = 20.0               # Nachbar fuer eine erkennbare Interpolation
    _write_cache(tmp_path, "2023-01-01 00:00", vals)
    _no_network(monkeypatch)
    out = weather.load_outdoor_temperature("2023-01-01 02:00",
                                           "2023-01-04 20:00",
                                           cache_dir=tmp_path)
    assert int(out["interpolated"].sum()) == 3
    assert out["t_out"].notna().all()


def test_long_gap_stays_nan(tmp_path, monkeypatch):
    vals = np.full(96, 10.0)
    vals[30:54] = np.nan          # 24 h Luecke, laenger als max_gap_hours
    _write_cache(tmp_path, "2023-01-01 00:00", vals)
    _no_network(monkeypatch)
    out = weather.load_outdoor_temperature("2023-01-01 02:00",
                                           "2023-01-04 20:00",
                                           cache_dir=tmp_path,
                                           max_gap_hours=6)
    assert int(out["t_out"].isna().sum()) == 24
    assert not out["interpolated"].any()


def test_max_gap_hours_zero_disables_interpolation(tmp_path, monkeypatch):
    vals = np.full(48, 10.0)
    vals[10] = np.nan
    _write_cache(tmp_path, "2023-01-01 00:00", vals)
    _no_network(monkeypatch)
    out = weather.load_outdoor_temperature("2023-01-01 02:00",
                                           "2023-01-02 20:00",
                                           cache_dir=tmp_path,
                                           max_gap_hours=0)
    assert not out["interpolated"].any()
    assert int(out["t_out"].isna().sum()) == 1


def test_end_before_start_raises(tmp_path, monkeypatch):
    _write_cache(tmp_path, "2023-01-01 00:00", np.full(48, 5.0))
    _no_network(monkeypatch)
    with pytest.raises(ValueError, match="liegt vor"):
        weather.load_outdoor_temperature("2023-01-02", "2023-01-01",
                                         cache_dir=tmp_path)


def test_heating_degree_hours():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=4, freq="h"),
        "t_out": [0.0, 15.0, 20.0, np.nan],
    })
    hdh = weather.heating_degree_hours(df, t_heiz=15.0)
    assert hdh.iloc[0] == 15.0
    assert hdh.iloc[1] == 0.0
    assert hdh.iloc[2] == 0.0       # ueber der Heizgrenze, nicht negativ
    assert np.isnan(hdh.iloc[3])    # Messluecke zaehlt nicht als warm
    assert isinstance(hdh.index, pd.DatetimeIndex)
    #Schwelle ist Parameter
    assert weather.heating_degree_hours(df, t_heiz=12.0).iloc[0] == 12.0


def test_heating_degree_hours_missing_column():
    with pytest.raises(KeyError):
        weather.heating_degree_hours(pd.DataFrame({"x": [1]}))


def test_season_months_cover_the_whole_year():
    assert set(season.SEASON_MONTHS) == set(range(1, 13))
    assert season.season_of_month(1) == season.KERNWINTER
    assert season.season_of_month(12) == season.KERNWINTER
    assert season.season_of_month(3) == season.UEBERGANG_SPAET
    assert season.season_of_month(7) == season.SOMMER
    assert season.season_of_month(9) == season.UEBERGANG_FRUEH
    with pytest.raises(ValueError):
        season.season_of_month(13)


def test_add_season_segment_keeps_every_row():
    ts = pd.date_range("2023-01-01", "2023-12-31 23:00", freq="h")
    df = pd.DataFrame({"timestamp": ts, "rt": 40.0})
    out = season.add_season_segment(df, timestamp_col="timestamp")
    assert len(out) == len(df)
    assert out["season"].notna().all()
    assert (out.loc[out["timestamp"].dt.month == 7, "season"]
            == season.SOMMER).all()
    assert (out.loc[out["timestamp"].dt.month == 2, "season"]
            == season.KERNWINTER).all()
    #Sommer wird markiert, nicht entfernt
    assert (out["season"] == season.SOMMER).sum() == \
        ts[ts.month.isin([5, 6, 7, 8])].size


def test_add_season_segment_on_datetime_index():
    df = pd.DataFrame({"rt": [1.0, 2.0]},
                      index=pd.to_datetime(["2023-01-15", "2023-06-15"]))
    out = season.add_season_segment(df)
    assert out["season"].tolist() == [season.KERNWINTER, season.SOMMER]


def test_add_season_segment_custom_month_map():
    df = pd.DataFrame({"timestamp": pd.to_datetime(["2023-11-15"])})
    out = season.add_season_segment(
        df, timestamp_col="timestamp",
        month_map={**season.SEASON_MONTHS, 11: season.KERNWINTER})
    assert out["season"].iloc[0] == season.KERNWINTER


def _february_series(year, baseline, cold_start, cold_hours, cold_value):
    ts = pd.date_range(f"{year}-01-15", f"{year}-03-15 23:00", freq="h")
    vals = np.full(len(ts), float(baseline))
    mask = (ts >= pd.Timestamp(cold_start)) & \
           (ts < pd.Timestamp(cold_start) + pd.Timedelta(hours=cold_hours))
    vals[mask] = cold_value
    return pd.DataFrame({"timestamp": ts, "t_out": vals})


def test_coldest_february_weeks_finds_the_injected_cold_spell():
    df = _february_series(2023, baseline=6.0, cold_start="2023-02-10",
                          cold_hours=336, cold_value=-4.0)
    out = season.coldest_february_weeks(df)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["year"] == 2023
    assert row["start"] == pd.Timestamp("2023-02-10 00:00")
    assert row["end"] == pd.Timestamp("2023-02-23 23:00")
    assert np.isclose(row["t_out_mean"], -4.0)
    assert row["n_hours"] == 336
    assert row["coverage"] == 1.0


def test_coldest_february_weeks_is_data_driven_not_fixed_weeks():
    #Kaelteperiode ganz am Monatsanfang -> Fenster wandert mit
    df = _february_series(2024, baseline=8.0, cold_start="2024-02-01",
                          cold_hours=336, cold_value=-1.0)
    out = season.coldest_february_weeks(df)
    assert out.iloc[0]["start"] == pd.Timestamp("2024-02-01 00:00")


def test_coldest_february_weeks_one_row_per_year():
    frames = [
        _february_series(2022, 5.0, "2022-02-05", 336, 0.0),
        _february_series(2023, 5.0, "2023-02-10", 336, -3.0),
    ]
    out = season.coldest_february_weeks(pd.concat(frames, ignore_index=True))
    assert out["year"].tolist() == [2022, 2023]
    assert out["start"].dt.year.tolist() == [2022, 2023]


def test_coldest_february_weeks_window_length_is_a_parameter():
    df = _february_series(2023, 6.0, "2023-02-10", 168, -4.0)
    out = season.coldest_february_weeks(df, n_days=7)
    row = out.iloc[0]
    assert (row["end"] - row["start"]) == pd.Timedelta(hours=7 * 24 - 1)
    assert row["start"] == pd.Timestamp("2023-02-10 00:00")


def test_coldest_february_weeks_reports_low_coverage_instead_of_hiding_it():
    df = _february_series(2023, 6.0, "2023-02-10", 336, -4.0)
    #fast den ganzen Februar loeschen: kein Fenster erreicht min_coverage
    keep = (df["timestamp"] < pd.Timestamp("2023-02-01")) | \
           (df["timestamp"] >= pd.Timestamp("2023-02-25"))
    out = season.coldest_february_weeks(df[keep])
    assert len(out) == 1
    row = out.iloc[0]
    assert row["coverage"] < 0.8
    assert np.isnan(row["t_out_mean"])


def test_coldest_february_weeks_rejects_bad_arguments():
    df = _february_series(2023, 6.0, "2023-02-10", 24, -4.0)
    with pytest.raises(ValueError):
        season.coldest_february_weeks(df, n_days=0)
    with pytest.raises(KeyError):
        season.coldest_february_weeks(df, column="gibtsnicht")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
