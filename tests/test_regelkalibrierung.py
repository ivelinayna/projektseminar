"""
Tests fuer src.regelkalibrierung und die Parametrisierung von
src.fault_detection.

Der wichtigste Test ist der auf das unveraenderte Verhalten der alten
Regeln: der Umbau auf ein Schwellen-Dictionary darf die Klassifikation
ohne Argument nicht verschieben, sonst sind alle frueheren Befunde zur
Baseline nicht mehr vergleichbar.

    python -m pytest tests/test_regelkalibrierung.py
"""

import numpy as np
import pandas as pd

from src import fault_detection as fd
from src import regelkalibrierung as rk

RNG = np.random.default_rng(3)


def _features(n: int = 120) -> pd.DataFrame:
    """Stationstabelle mit den acht Features der Regel-Baseline."""
    return pd.DataFrame({
        "meter": np.arange(1, n + 1),
        "rt_mean_winter": RNG.normal(45, 5, n),
        "rt_above_50_share_loaded": RNG.uniform(0, 1, n),
        "summer_flow_baseline": RNG.uniform(0, 80, n),
        "summer_idle_flow_median": RNG.uniform(0, 40, n),
        "flow_ceiling_slope_per_month": RNG.normal(0, 3, n),
        "dt_mean_loaded": RNG.normal(25, 6, n),
        "peak_load_share": RNG.uniform(0, 1, n),
        "flow_short_cycle_power": RNG.uniform(0, 1, n),
    })


def test_standardschwellen_vollstaendig():
    assert set(rk.SPEZIFIKATION) <= set(fd.SCHWELLEN)


def test_klassifikation_ohne_argument_unveraendert():
    #Regressionsschutz fuer den Umbau auf parametrisierbare Schwellen
    df = _features()
    ohne = fd.classify_dataframe(df)["predicted_fault"]
    mit = fd.classify_dataframe(df, dict(fd.SCHWELLEN))["predicted_fault"]
    assert list(ohne) == list(mit)


def test_eigene_schwellen_wirken():
    df = _features()
    streng = dict(fd.SCHWELLEN)
    streng["rt_mean_winter"] = -999.0
    quoten = rk.trefferquoten(df, streng)
    zeile = quoten[quoten["schwelle"] == "rt_mean_winter"].iloc[0]
    assert zeile["anteil"] == 1.0


def test_trefferquoten_zaehlen_jede_bedingung_einzeln():
    df = _features()
    quoten = rk.trefferquoten(df)
    assert len(quoten) == len(rk.SPEZIFIKATION)
    assert (quoten["n_stationen"] == len(df)).all()
    assert quoten["anteil"].between(0, 1).all()


def test_fehlende_features_brechen_nicht_ab():
    df = _features().drop(columns=["peak_load_share"])
    quoten = rk.trefferquoten(df)
    zeile = quoten[quoten["schwelle"] == "peak_load_share"].iloc[0]
    assert zeile["n_stationen"] == 0
    assert zeile["treffer"] == 0


def test_kalibrierung_trifft_den_zielanteil():
    df = _features()
    neu, bilanz = rk.kalibriere(df, zielanteil=0.15)
    assert bool(bilanz["uebernommen"].all())
    quoten = rk.trefferquoten(df, neu)
    #Quantilschwelle setzt den Anteil per Konstruktion, kleine Abweichung
    #nur durch Bindungen in der Verteilung
    assert quoten["anteil"].between(0.10, 0.20).all()


def test_zielanteil_steuert_die_laenge_der_trefferliste():
    df = _features()
    eng, _ = rk.kalibriere(df, zielanteil=0.05)
    weit, _ = rk.kalibriere(df, zielanteil=0.30)
    a = rk.trefferquoten(df, eng)["treffer"].sum()
    b = rk.trefferquoten(df, weit)["treffer"].sum()
    assert a < b


def test_zu_wenige_stationen_behalten_die_alte_schwelle():
    df = _features(n=5)
    neu, bilanz = rk.kalibriere(df, min_stationen=20)
    assert not bilanz["uebernommen"].any()
    assert bilanz["grund"].str.contains("20").all()
    assert neu["rt_mean_winter"] == fd.SCHWELLEN["rt_mean_winter"]


def test_vorher_nachher_zeigt_beide_spalten():
    df = _features()
    neu, _ = rk.kalibriere(df)
    tab = rk.vorher_nachher(df, neu)
    assert {"anteil_alt", "anteil_neu", "schwelle_alt",
            "schwelle_neu"} <= set(tab.columns)
    assert len(tab) == len(rk.SPEZIFIKATION)


def test_labelverteilung_vergibt_je_station_ein_label():
    df = _features()
    verteilung = rk.labelverteilung(df)
    assert verteilung.sum() == len(df)


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
    print("alle Kalibrierungstests bestanden")
