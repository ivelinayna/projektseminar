"""
Tests fuer src.empfehlung.

Geprueft werden die Eigenschaften, an denen das Modul scheitern wuerde,
ohne dass es auffaellt. Die Musterzuordnung muss eine gebaute
Kurzschlussstation beim Namen nennen und eine gesunde Station gar nicht
erst in die Liste nehmen. Der Schweregrad muss monoton in seinen
Komponenten sein, sonst ist die Reihenfolge der Liste nicht
begruendbar. Und der Export muss sich weigern, eine Adressspalte
mitzuschreiben.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_empfehlung.py
"""

import numpy as np
import pandas as pd
import pytest

from src import anomalie as an
from src import empfehlung as em

RNG = np.random.default_rng(11)

NETZ = f"score_{an.D_RESID_NETZ}"
STATION = f"score_{an.D_RESID_STATION}"


def _panel(tage: int = 240) -> pd.DataFrame:
    """Panel mit vier gebauten Stationen und einem bekannten Befund.

    Station 1 ist gesund, Station 2 faehrt viel Volumenstrom ohne
    Auskuehlung, Station 3 schwankt stark, Station 4 ist im Sommer
    waermer als im Winter.
    """
    datum = pd.date_range("2024-01-01", periods=tage, freq="D")
    t_out = 5.0 + 12.0 * np.sin(np.arange(tage) / 58.0)
    sommer = np.where(t_out > 12, "sommer", "kernwinter")
    zeilen = []
    for zid, art in ((1, "gesund"), (2, "kurzschluss"), (3, "unruhig"),
                     (4, "sommer")):
        basis = dict(
            meter=zid, datum=datum, t_out_tag=t_out, season=sommer,
            genug_stunden=True, heizgradstunden=np.clip(15 - t_out, 0, None) * 24,
            energie_kwh=100.0, power_mean=12.0, flow_median=60.0,
            last_anteil=0.4, dt_mean_loaded=30.0, rt_median=45.0,
            rt_spanne_k=12.0, rt_d1_abs_mean=2.0, rt_d2_abs_mean=3.0,
            rt_traege_anteil=0.3, rt_vl_kopplung=0.4, reaktionszeit_h=1.0,
            n_lastwechsel=4.0, anteil_c1=0.05, performance=0.8,
            spreizung_k=30.0,
        )
        basis[NETZ] = RNG.normal(0, 1.0, tage)
        basis[STATION] = RNG.normal(0, 1.0, tage)
        if art == "kurzschluss":
            basis.update(flow_median=900.0, dt_mean_loaded=7.0,
                         last_anteil=0.1, anteil_c1=0.8, rt_median=68.0,
                         spreizung_k=7.0, performance=0.2)
            basis[NETZ] = 20.0 + RNG.normal(0, 1.0, tage)
        elif art == "unruhig":
            basis.update(rt_d1_abs_mean=12.0, rt_d2_abs_mean=20.0,
                         rt_median=55.0, rt_traege_anteil=0.05)
            basis[NETZ] = 9.0 + RNG.normal(0, 1.0, tage)
        elif art == "sommer":
            warm = np.where(sommer == "sommer", 22.0, 0.0)
            basis.update(rt_median=42.0 + warm, last_anteil=0.08)
            basis[NETZ] = 8.0 + warm / 3.0 + RNG.normal(0, 1.0, tage)
        zeilen.append(pd.DataFrame(basis))
    panel = pd.concat(zeilen, ignore_index=True)
    for spalte in (NETZ, STATION):
        panel[f"auffaellig_{spalte}"] = panel[spalte] > 5.0
        panel[f"persistent_{spalte}"] = panel[f"auffaellig_{spalte}"]
    panel.attrs["kurzschlusscluster"] = 1
    return panel


@pytest.fixture(scope="module")
def profil() -> pd.DataFrame:
    return em.kennzahlen(_panel())


def test_kennzahlen_eine_zeile_je_station(profil):
    assert len(profil) == 4
    assert profil["meter"].is_unique


def test_normalscore_ist_robust_gegen_schiefe():
    werte = pd.Series([0.0] * 50 + [1.0] * 30 + [5000.0])
    z = em._normalscore(werte)
    #der eine Ausreisser darf die Skala nicht sprengen
    assert z.max() < 4.0
    assert z.is_monotonic_increasing


def test_kurzschlussstation_bekommt_das_passende_muster(profil):
    zuordnung = em.musterzuordnung(profil)
    muster = zuordnung.set_index("meter").loc[2, "muster"]
    assert "Kurzschluss" in muster


def test_gesunde_station_kommt_nicht_in_die_trefferliste(profil):
    treffer = em.trefferliste(profil)
    assert 1 not in set(treffer["meter"])
    assert 2 in set(treffer["meter"])


def test_unauffaellige_stationen_tragen_kein_fehlermuster(profil):
    bilanz = em.musterbilanz(profil)
    unauff = bilanz[~bilanz["auffaellig"]]
    assert set(unauff["muster"]) <= {em.UNAUFFAELLIG}


def test_schweregrad_waechst_mit_abweichung_und_persistenz():
    basis = pd.DataFrame({"meter": [1, 2, 3],
                          "score_netz": [2.0, 8.0, 8.0],
                          "pers_netz": [0.1, 0.1, 0.4]})
    grad = em.schweregrad(basis).set_index("meter")
    assert grad.loc[1, "punkte"] < grad.loc[2, "punkte"]
    assert grad.loc[2, "punkte"] < grad.loc[3, "punkte"]


def test_schweregrad_ist_gedeckelt():
    basis = pd.DataFrame({"meter": [1],
                          "score_netz": [500.0], "pers_netz": [1.0]})
    grad = em.schweregrad(basis)
    assert grad["punkte"].iloc[0] <= 100.0


def test_trefferliste_enthaelt_massnahme_und_begruendung(profil):
    treffer = em.trefferliste(profil)
    assert treffer["massnahme"].notna().all()
    assert treffer["begruendung_kurz"].str.len().min() > 10
    assert treffer["punkte"].is_monotonic_decreasing


def test_export_verweigert_adressspalten(tmp_path, profil):
    treffer = em.trefferliste(profil)
    treffer = treffer.assign(adresse="Musterweg 1")
    with pytest.raises(ValueError):
        em.exportiere(treffer, str(tmp_path / "liste.csv"))


def test_export_schreibt_nur_zaehlernummern(tmp_path, profil):
    pfad = em.exportiere(em.trefferliste(profil), str(tmp_path / "liste.csv"))
    wieder = pd.read_csv(pfad)
    assert "meter" in wieder.columns
    assert not any("adress" in s.lower() for s in wieder.columns)


def test_abdeckung_endet_bei_eins(profil):
    ab = em.abdeckung(em.trefferliste(profil))
    assert abs(ab["anteil_punkte"].iloc[-1] - 1.0) < 1e-9
    assert ab["anteil_punkte"].is_monotonic_increasing


def test_baum_bleibt_flach_und_nutzt_keine_spreizung():
    panel = _panel()
    X, y, g = em.baumdaten(panel)
    assert "dt_mean_loaded" not in X.columns
    assert "rt_spanne_k" not in X.columns
    baum = em.fitte_baum(X, y, tiefe=2, min_blatt=20)
    assert baum.get_depth() <= 2


def test_nutzenbilanz_zaehlt_die_begehungen_vollstaendig(profil):
    treffer = em.trefferliste(profil)
    winter = pd.DataFrame({
        "meter": [1, 2, 3, 4],
        "auswertbar": True,
        "zustand_vor": ["gut", "schlecht", "schlecht", "gut"],
        "zustand_nach": ["gut", "schlecht", "gut", "gut"],
    })
    bilanz = em.nutzenbilanz(treffer, winter)
    assert bilanz["n_begehungen"] == 4
    assert bilanz["n_ohne_wirkung"] == 1
    assert bilanz["ohne_wirkung_erkannt"] == 1
