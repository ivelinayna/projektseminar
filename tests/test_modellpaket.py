"""Modellpakete (src/modellpaket.py): speichern, laden, Prüfsummen, Versionen."""

import json

import pandas as pd
import pytest

from src import modellpaket as mp


def test_paket_schreiben_und_laden(tmp_path):
    tab = pd.DataFrame({"zaehler": [1, 2], "wert": [0.5, 1.5]})
    p = mp.schreibe_paket("test", "Alarm", {"tab.csv": lambda pf: tab.to_csv(pf, index=False)},
                          parameter={"schwelle": 4.0, "stichtag": pd.Timestamp("2024-09-01")},
                          kennzahlen={"auc": 0.9}, datenstand=pd.Timestamp("2025-07-11"),
                          lernzeitraum=(pd.Timestamp("2023-01-01"), pd.Timestamp("2024-05-31")),
                          version="v1", wurzel=tmp_path)
    assert (tmp_path / "test" / "v1" / "paket.json").exists()
    assert mp.aktuelle_version("test", tmp_path) == "v1"
    geladen = mp.lade_paket("test", wurzel=tmp_path)
    assert geladen.parameter["schwelle"] == 4.0
    assert geladen.parameter["stichtag"].startswith("2024-09-01")
    assert geladen.tabelle("tab.csv")["wert"].sum() == pytest.approx(2.0)
    assert len(geladen.meta["dateien"]["tab.csv"]) == 64, "SHA-256 je Datei"
    assert json.loads((tmp_path / "test" / "v1" / "paket.json").read_text())["kennzahlen"]["auc"] == 0.9
    ue = mp.uebersicht(tmp_path)
    assert len(ue) == 1 and bool(ue["aktuell"].iloc[0])
    assert ue["lernzeitraum"].iloc[0] == "2023-01-01 bis 2024-05-31"


def test_veraenderte_datei_faellt_auf(tmp_path):
    mp.schreibe_paket("test", "x", {"a.txt": lambda pf: pf.write_text("eins")},
                      version="v1", wurzel=tmp_path)
    (tmp_path / "test" / "v1" / "a.txt").write_text("zwei")
    with pytest.raises(mp.PaketFehler):
        mp.lade_paket("test", wurzel=tmp_path)
    mp.lade_paket("test", wurzel=tmp_path, pruefen=False)


def test_versionen_und_zurueckschalten(tmp_path):
    for v in ("v1", "v2"):
        mp.schreibe_paket("test", "x", {"a.txt": lambda pf: pf.write_text(v)}, version=v, wurzel=tmp_path)
    assert mp.versionen("test", tmp_path) == ["v1", "v2"]
    assert mp.aktuelle_version("test", tmp_path) == "v2"
    mp.setze_aktuell("test", "v1", tmp_path)
    assert mp.lade_paket("test", wurzel=tmp_path).version == "v1"
    with pytest.raises(mp.PaketFehler):
        mp.setze_aktuell("test", "v9", tmp_path)
    with pytest.raises(mp.PaketFehler):
        mp.schreibe_paket("test", "x", {}, version="v1", wurzel=tmp_path)


def test_fehlendes_paket(tmp_path):
    with pytest.raises(mp.PaketFehler):
        mp.lade_paket("gibtsnicht", wurzel=tmp_path)
    assert mp.uebersicht(tmp_path).empty
