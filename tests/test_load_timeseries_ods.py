"""
Tests fuer den ODS-Zweig von src.load_timeseries.

Die ODS-Dateien werden hier selbst gebaut, Zeile fuer Zeile und mit
``table:number-columns-repeated``, damit auch der Spaltenversatz getestet
ist, an dem ein naiver XML-Parser scheitert. Kein Netz, keine Rohdaten.

    python -m tests.test_load_timeseries_ods
    python -m pytest tests/test_load_timeseries_ods.py
"""

import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.load_timeseries import (
    KUMULATIVE_KANAELE,
    SCHEMA,
    discover_meter_ods,
    ergaenze_zaehlerstaende,
    load_meter_ods,
    load_meter_timeseries,
    pruefe_skalierung,
    vergleiche_ueberlappung,
    zeitraster,
)

KOPF = ["Timestamp", "Volume flow (l/h)", "Power (kW)",
        "Temperature difference (\u00b0C)", "Flow temperature (\u00b0C)",
        "Return temperature (\u00b0C)"]

#200 l/h bei 20 K sind 4,652 kW - die Pruefung der Skalierung haengt an
#genau dieser Identitaet, deshalb hier exakt gerechnet
FLOW_LAST = 200.0
DT_LAST = 20.0
POWER_LAST = round(FLOW_LAST * DT_LAST / 859.845, 3)
VL_LAST = 70.0
RT_LAST = VL_LAST - DT_LAST

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"')

MANIFEST = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:'
    'xmlns:manifest:1.0" manifest:version="1.2">'
    '<manifest:file-entry manifest:full-path="/" manifest:media-type='
    '"application/vnd.oasis.opendocument.spreadsheet"/>'
    '<manifest:file-entry manifest:full-path="content.xml" '
    'manifest:media-type="text/xml"/>'
    '</manifest:manifest>')


def _zelle(wert) -> str:
    if isinstance(wert, str):
        return ('<table:table-cell office:value-type="string">'
                f'<text:p>{wert}</text:p></table:table-cell>')
    return (f'<table:table-cell office:value-type="float" '
            f'office:value="{wert}"><text:p>{wert}</text:p>'
            '</table:table-cell>')


def _zeile(werte, zusammenfassen: bool = False) -> str:
    """Eine Tabellenzeile; mit `zusammenfassen` werden gleiche Nachbarn
    zu einer Zelle mit ``number-columns-repeated`` zusammengezogen - genau
    die Form, in der der ÜZ-Export Stillstandsstunden ablegt."""
    if not zusammenfassen:
        return "<table:table-row>" + "".join(
            _zelle(w) for w in werte) + "</table:table-row>"
    teile, i = [], 0
    while i < len(werte):
        j = i
        while j + 1 < len(werte) and werte[j + 1] == werte[i]:
            j += 1
        n = j - i + 1
        zelle = _zelle(werte[i])
        if n > 1:
            zelle = zelle.replace(
                "<table:table-cell ",
                f'<table:table-cell table:number-columns-repeated="{n}" ')
        teile.append(zelle)
        i = j + 1
    return "<table:table-row>" + "".join(teile) + "</table:table-row>"


def schreibe_ods(pfad: Path, zeilen, blattname: str | None = None,
                 kopf=None) -> Path:
    """Minimale, aber gueltige ODS-Datei mit genau einem Tabellenblatt."""
    blattname = blattname or pfad.stem
    kopf = kopf or KOPF
    xml = [f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<office:document-content {NS} office:version="1.2">'
           f'<office:body><office:spreadsheet>'
           f'<table:table table:name="{blattname}">',
           _zeile(kopf)]
    for werte, zusammenfassen in zeilen:
        xml.append(_zeile(werte, zusammenfassen))
    xml.append("</table:table></office:spreadsheet></office:body>"
               "</office:document-content>")
    with zipfile.ZipFile(pfad, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"),
                   "application/vnd.oasis.opendocument.spreadsheet",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", MANIFEST)
        z.writestr("content.xml", "".join(xml))
    return pfad


def _lastzeile(ts: pd.Timestamp, faktor: float):
    w = [str(ts), FLOW_LAST, POWER_LAST, DT_LAST, VL_LAST, RT_LAST]
    return [w[0]] + [round(x * faktor, 6) for x in w[1:]]


def _stillstandzeile(ts: pd.Timestamp, faktor: float):
    #Volumenstrom und Leistung sind beide null und stehen nebeneinander,
    #das ist der Fall, den der Export zusammenfasst
    return [str(ts), 0.0, 0.0, 0.0, 30.0 * faktor, 30.0 * faktor]


def _standardzeilen(faktor: float = 1000.0):
    """60 Tageszeilen, 10 Tage Luecke, 3 Tage stuendlich.

    Der mittlere der drei Stundentage ist Stillstand und wird mit
    zusammengefassten Spalten geschrieben.
    """
    zeilen = []
    for tag in pd.date_range("2024-01-01", periods=60, freq="D"):
        zeilen.append((_lastzeile(tag + pd.Timedelta(hours=23, minutes=59),
                                  faktor), False))
    for ts in pd.date_range("2024-03-11", periods=72, freq="h"):
        if ts.day == 12:
            zeilen.append((_stillstandzeile(ts, faktor), True))
        else:
            zeilen.append((_lastzeile(ts, faktor), False))
    #der Export liefert absteigend, der Loader muss selbst sortieren
    return zeilen[::-1]


def _dummy_csv(start: str, stunden: int, power: float) -> pd.DataFrame:
    ts = pd.date_range(start, periods=stunden, freq="h")
    return pd.DataFrame({
        "Timestamp": ts,
        "Energy (kWh)": np.arange(stunden, dtype=float) * power,
        "Volume flow (l/h)": FLOW_LAST,
        "Power (kW)": power,
        "Temperature difference (\u00b0C)": DT_LAST,
        "Flow temperature (\u00b0C)": VL_LAST,
        "Return temperature (\u00b0C)": RT_LAST,
        "Volume (m\u00b3)": np.arange(stunden, dtype=float) * 0.2,
    })[SCHEMA]


def test_discover_ignoriert_beiblaetter():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        (d / "Nodes_Edges.ods").write_bytes(b"kein Zaehlerexport")
        assert set(discover_meter_ods(d)) == {44444444}


def test_skalierung_wird_bestimmt_nicht_angenommen():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen(faktor=1000.0))
        schreibe_ods(d / "55555555.ods", _standardzeilen(faktor=1.0))
        from src.load_timeseries import _lies_ods_blatt
        assert pruefe_skalierung(
            _lies_ods_blatt(d / "44444444.ods"))["faktor"] == 1000.0
        #dieselbe Reihe in echten Einheiten darf nicht durch 1000 geteilt
        #werden, sonst waere der Faktor hartkodiert
        assert pruefe_skalierung(
            _lies_ods_blatt(d / "55555555.ods"))["faktor"] == 1.0


def test_unplausible_leistung_wird_abgelehnt():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        zeilen = [([w[0], w[1], 900000.0, w[3], w[4], w[5]], f)
                  for w, f in _standardzeilen()]
        schreibe_ods(d / "44444444.ods", zeilen)
        try:
            load_meter_ods(44444444, d)
        except ValueError as e:
            assert "Skalierung" in str(e)
        else:
            raise AssertionError("erwartet ValueError bei falscher Leistung")


def test_vertauschte_temperaturspalten_werden_abgelehnt():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        zeilen = [([w[0], w[1], w[2], w[3], w[5], w[4]], f)
                  for w, f in _standardzeilen()]
        schreibe_ods(d / "44444444.ods", zeilen)
        try:
            load_meter_ods(44444444, d)
        except ValueError as e:
            assert "Spaltenzuordnung" in str(e)
        else:
            raise AssertionError("erwartet ValueError bei Spaltentausch")


def test_csv_schema_in_ods_wird_abgelehnt():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        kopf = KOPF + ["Energy (kWh)"]
        zeilen = [(list(w) + [1.0], f) for w, f in _standardzeilen()]
        schreibe_ods(d / "44444444.ods", zeilen, kopf=kopf)
        try:
            load_meter_ods(44444444, d)
        except ValueError as e:
            assert "Energy (kWh)" in str(e)
        else:
            raise AssertionError("erwartet ValueError bei CSV-Schema")


def test_wiederholte_spalten_verschieben_nichts():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        df = load_meter_ods(44444444, d).set_index("Timestamp")
        still = df.loc["2024-03-12"]
        assert len(still) == 24
        #waere number-columns-repeated ignoriert worden, stuenden hier die
        #Temperaturen in den Durchflussspalten
        assert (still["Volume flow (l/h)"] == 0).all()
        assert (still["Power (kW)"] == 0).all()
        assert np.allclose(still["Flow temperature (\u00b0C)"], 30.0)
        assert np.allclose(still["Return temperature (\u00b0C)"], 30.0)


def test_kumulative_kanaele_bleiben_leer():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        df = load_meter_ods(44444444, d)
        assert list(df.columns) == SCHEMA
        assert df["Timestamp"].is_monotonic_increasing
        assert not df["Timestamp"].duplicated().any()
        for kanal in KUMULATIVE_KANAELE:
            assert df[kanal].isna().all()
        #die Messkanaele sind entskaliert
        last = df.dropna(subset=["Power (kW)"])
        assert np.isclose(last["Flow temperature (\u00b0C)"].max(), VL_LAST)


def test_zeitraster_trennt_taeglich_stuendlich_luecke():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        seg = zeitraster(load_meter_ods(44444444, d))
        assert list(seg["raster"]) == ["taeglich", "luecke", "stuendlich"]
        assert list(seg["n_tage"]) == [60, 10, 3]
        assert list(seg["n_zeilen"]) == [60, 0, 72]


def test_integration_ueberspringt_luecken():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        df = ergaenze_zaehlerstaende(load_meter_ods(44444444, d))
        assert df["zaehlerstand_integriert"].all()
        e = df.set_index("Timestamp")["Energy (kWh)"]
        assert e.is_monotonic_increasing
        #Tagesabstand und Luecke liegen ueber MAX_GAP_HOURS und duerfen
        #nichts beitragen
        assert np.isclose(e.loc["2024-03-11 00:00"], 0.0)
        #47 Stundenintervalle unter Last, der Stillstandstag traegt nichts
        assert np.isclose(e.iloc[-1], 47 * POWER_LAST, rtol=1e-6)
        v = df["Volume (m\u00b3)"]
        assert np.isclose(v.iloc[-1], 47 * FLOW_LAST / 1000.0, rtol=1e-6)


def test_merge_bevorzugt_csv_im_ueberlappungszeitraum():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        #die CSV deckt den ersten Stundentag ab und traegt eine andere
        #Leistung, damit sichtbar wird, welche Quelle gewinnt
        _dummy_csv("2024-03-11", 24, power=9.0).to_csv(
            d / "44444444__n.csv", index=False)

        ohne = load_meter_timeseries(44444444, d)
        assert ohne["Timestamp"].max() == pd.Timestamp("2024-03-11 23:00")

        mit = load_meter_timeseries(44444444, d, mit_ods=True).set_index(
            "Timestamp")
        assert mit.index.max() == pd.Timestamp("2024-03-13 23:00")
        assert np.isclose(mit.loc["2024-03-11 05:00", "Power (kW)"], 9.0)
        assert not np.isnan(mit.loc["2024-03-11 05:00", "Energy (kWh)"])
        #ausserhalb der CSV bleibt die ODS-Zeile stehen, ohne Zaehlerstand
        assert np.isclose(mit.loc["2024-03-13 05:00", "Power (kW)"],
                          POWER_LAST)
        assert np.isnan(mit.loc["2024-03-13 05:00", "Energy (kWh)"])

        gefuellt = load_meter_timeseries(
            44444444, d, mit_ods=True,
            zaehlerstaende_integrieren=True).set_index("Timestamp")
        assert gefuellt["Energy (kWh)"].notna().all()
        assert gefuellt.loc["2024-03-11 05:00", "zaehlerstand_integriert"] \
            == False  # noqa: E712 - gemessene Zeile bleibt unmarkiert
        assert gefuellt.loc["2024-03-13 05:00", "zaehlerstand_integriert"]


def test_ueberlappung_meldet_deckungsgleichheit():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        _dummy_csv("2024-03-11", 24, power=POWER_LAST).to_csv(
            d / "44444444__n.csv", index=False)
        tab = vergleiche_ueberlappung(44444444, d).set_index("kanal")
        assert tab.loc["Timestamp", "n_gemeinsam"] == 24
        for kanal in ["Volume flow (l/h)", "Power (kW)",
                      "Flow temperature (\u00b0C)"]:
            assert tab.loc[kanal, "anteil_in_toleranz"] == 1.0
            assert tab.loc[kanal, "max_abweichung"] < 0.051


def test_nur_ods_ohne_csv_ist_ladbar():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        schreibe_ods(d / "44444444.ods", _standardzeilen())
        df = load_meter_timeseries(44444444, d, mit_ods=True)
        assert len(df) == 132
        try:
            load_meter_timeseries(44444444, d)
        except FileNotFoundError as e:
            assert "44444444" in str(e)
        else:
            raise AssertionError("ohne mit_ods darf es keinen Treffer geben")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} Tests bestanden")
