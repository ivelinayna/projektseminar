"""
Tests fuer src.fallsammlung.

Geprueft werden die Stellen, an denen die Fallsammlung kippen kann: die
Zusammensetzung der Kontrollgruppe, der saisongleiche Schnitt und die
Kennzahlen, die spaeter in der Doku stehen. Cliffs delta und das
Screening sind reine Rechenfunktionen und werden gegen von Hand
nachrechenbare Beispiele gestellt.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_fallsammlung.py
"""

import numpy as np
import pandas as pd
import pytest

from src import fallsammlung as fs
from src import ternaer as tn


def _serie(start="2023-01-01", stunden=24 * 400, dt_vorher=5.0,
           dt_nachher=5.0, wechsel=None):
    """Kunstreihe mit konstanter Leistung und optionalem Sprung in der Spreizung."""
    idx = pd.date_range(start, periods=stunden, freq="h")
    dt = np.full(len(idx), float(dt_vorher))
    if wechsel is not None:
        dt[idx >= pd.Timestamp(wechsel)] = float(dt_nachher)
    #Leistung klar ueber der Lastschwelle, damit keine Stunde wegfaellt
    power = np.full(len(idx), 20.0)
    flow = power / (dt * 1.163) * 1000.0
    return pd.DataFrame({"power": power, "flow": flow, "dt": dt}, index=idx)


class TestKontrollgruppe:
    def test_zieht_nur_aus_echten_terminen(self):
        datum = {1: pd.Timestamp("2024-09-10"), 2: pd.Timestamp("2024-11-05")}
        k = fs.kontrollgruppe([1, 2, 3, 4, 5], datum)
        assert set(k) == {3, 4, 5}
        assert set(k.values()) <= set(datum.values())

    def test_ausschluss_bleibt_draussen(self):
        datum = {1: pd.Timestamp("2024-09-10")}
        k = fs.kontrollgruppe([1, 2, 3], datum, ausschluss=[2])
        assert set(k) == {3}

    def test_gleicher_seed_gleiches_ergebnis(self):
        datum = {1: pd.Timestamp("2024-09-10"), 2: pd.Timestamp("2024-10-01")}
        a = fs.kontrollgruppe(range(1, 20), datum, seed=7)
        b = fs.kontrollgruppe(range(1, 20), datum, seed=7)
        assert a == b

    def test_ohne_termine_leer(self):
        assert fs.kontrollgruppe([1, 2, 3], {}) == {}


class TestEffektJeStation:
    def test_sprung_wird_als_steigerung_gemessen(self):
        wechsel = "2023-06-01"
        serien = {11: _serie(dt_vorher=3.0, dt_nachher=9.0, wechsel=wechsel)}
        tab = fs.effekt_je_station(serien, {11: pd.Timestamp(wechsel)},
                                   begangen=[11], saison=None)
        zeile = tab.iloc[0]
        assert zeile["begehung"]
        assert zeile["genug"]
        assert zeile["d_perf"] > 5

    def test_saisonfilter_laesst_nur_winterstunden_uebrig(self):
        serien = {11: _serie(stunden=24 * 400)}
        datum = {11: pd.Timestamp("2023-06-01")}
        alle = fs.effekt_je_station(serien, datum, [11], saison=None)
        winter = fs.effekt_je_station(serien, datum, [11],
                                      saison=tn.GRUPPE_WINTER)
        punkte_alle = alle.iloc[0]["n_vorher"] + alle.iloc[0]["n_nachher"]
        punkte_winter = (winter.iloc[0]["n_vorher"]
                         + winter.iloc[0]["n_nachher"])
        assert 0 < punkte_winter < punkte_alle

    def test_station_ohne_datum_faellt_raus(self):
        serien = {11: _serie(), 12: _serie()}
        tab = fs.effekt_je_station(serien, {11: pd.Timestamp("2023-06-01")},
                                   begangen=[11], saison=None)
        assert tab["meter"].tolist() == [11]

    def test_leere_reihe_bleibt_mit_null_punkten_stehen(self):
        leer = pd.DataFrame({"power": [], "flow": [], "dt": []},
                            index=pd.DatetimeIndex([]))
        tab = fs.effekt_je_station({11: leer},
                                   {11: pd.Timestamp("2023-06-01")}, [])
        assert len(tab) == 1
        assert tab.iloc[0]["n_vorher"] == 0
        assert not tab.iloc[0]["genug"]

    def test_zu_wenig_punkte_wird_als_nicht_genug_markiert(self):
        serien = {11: _serie(stunden=40)}
        tab = fs.effekt_je_station(serien,
                                   {11: pd.Timestamp("2023-01-01 12:00")},
                                   begangen=[11], saison=None, min_punkte=30)
        assert not tab.iloc[0]["genug"]


class TestCliffsDelta:
    def test_vollstaendig_groesser_ergibt_eins(self):
        assert fs.cliffs_delta([5, 6, 7], [1, 2, 3]) == pytest.approx(1.0)

    def test_vollstaendig_kleiner_ergibt_minus_eins(self):
        assert fs.cliffs_delta([1, 2], [5, 6]) == pytest.approx(-1.0)

    def test_identische_stichproben_ergeben_null(self):
        assert fs.cliffs_delta([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)

    def test_nan_wird_ignoriert(self):
        assert fs.cliffs_delta([5, np.nan, 6], [1, 2]) == pytest.approx(1.0)

    def test_leere_stichprobe_ergibt_nan(self):
        assert np.isnan(fs.cliffs_delta([], [1, 2]))


class TestGruppenvergleich:
    def test_median_und_anteil_stimmen(self):
        tab = pd.DataFrame({"gruppe": ["a", "a", "a", "b", "b"],
                            "d_perf": [1.0, 3.0, 5.0, -2.0, -4.0]})
        out = fs.gruppenvergleich(tab, "gruppe").set_index("gruppe")
        assert out.loc["a", "n"] == 3
        assert out.loc["a", "median"] == pytest.approx(3.0)
        assert out.loc["a", "anteil_positiv"] == pytest.approx(1.0)
        assert out.loc["b", "anteil_positiv"] == pytest.approx(0.0)

    def test_nan_zaehlt_nicht_mit(self):
        tab = pd.DataFrame({"gruppe": ["a", "a"], "d_perf": [2.0, np.nan]})
        out = fs.gruppenvergleich(tab, "gruppe")
        assert out.loc[0, "n"] == 1


class TestMarkiereMechanisch:
    def test_nur_mechanische_kategorien_zaehlen(self):
        tab = pd.DataFrame({"meter": [1, 2, 3]})
        labels = pd.DataFrame({
            "meter": [1, 2],
            "ventil_stellantrieb": [1, 0],
            "daemmung": [0, 1],
            "n_befunde": [1, 1],
        })
        out = fs.markiere_mechanisch(tab, labels)
        assert out.set_index("meter")["mechanisch"].tolist() == [True, False,
                                                                 False]

    def test_station_ohne_notiz_gilt_als_nicht_mechanisch(self):
        tab = pd.DataFrame({"meter": [9]})
        labels = pd.DataFrame({"meter": [1], "pumpe": [1]})
        out = fs.markiere_mechanisch(tab, labels)
        assert not out.loc[0, "mechanisch"]


class TestScreening:
    def test_kennzahlen_gegen_handrechnung(self):
        #vier schwache Stationen, der Indikator trifft drei davon und
        #greift einmal daneben
        quer = pd.DataFrame({
            "anteil_mod_dt": [0.9, 0.8, 0.7, 0.1, 0.1, 0.1, 0.1, 0.9],
            "performance_median": [5, 6, 7, 30, 31, 32, 33, 34],
        })
        r = fs.screening(quer, schwelle=0.6, quantil=0.5)
        assert r["gewaehlt"] == 4
        assert r["treffer"] == 3
        assert r["genauigkeit"] == pytest.approx(0.75)
        assert r["trefferanteil"] == pytest.approx(0.75)
        assert r["basisrate"] == pytest.approx(0.5)

    def test_basisrate_wird_mitgeliefert(self):
        quer = pd.DataFrame({"anteil_mod_dt": [0.9, 0.1],
                             "performance_median": [5.0, 40.0]})
        r = fs.screening(quer, quantil=0.25)
        assert 0 < r["basisrate"] <= 1
        assert r["n"] == 2
