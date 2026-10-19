import numpy as np
import pandas as pd
import pytest

from src import netzvergleich as nv


def _punkte(start, ende, flow_fn, seed=0, rt=40.0):
    """Synthetische Punkttabelle im Format von sb.punkttabelle."""
    rng = np.random.default_rng(seed)
    zeit = pd.date_range(start, ende, freq="h")
    p = rng.uniform(2.0, 10.0, len(zeit))
    flow = flow_fn(p, rng)
    dt = p * 1000.0 / (1.163 * flow)
    return pd.DataFrame({"zeit": zeit, "power_kw": p, "flow_lh": flow,
                         "dt_k": dt, "rt_c": np.full(len(zeit), rt)})


def _proportional(faktor=50.0):
    return lambda p, rng: faktor * p * np.exp(rng.normal(0, 0.05, len(p)))


def _konstant(wert=400.0):
    return lambda p, rng: wert * np.exp(rng.normal(0, 0.05, len(p)))


def test_heizperiode_labels():
    zeit = pd.to_datetime(["2023-11-30", "2023-12-01", "2024-02-29",
                           "2024-03-01", "2024-12-31", "2025-01-01"])
    lab = nv.heizperiode(zeit)
    assert list(lab) == ["", "23/24", "23/24", "", "24/25", "24/25"]


def test_heizperiode_nat_ist_kein_winter():
    zeit = pd.to_datetime(["2024-01-15", None])
    assert list(nv.heizperiode(zeit)) == ["23/24", ""]


def test_winter_ende_jahr():
    assert nv.winter_ende_jahr("23/24") == 2024
    assert nv.winter_ende_jahr("99/00") == 2000


def test_kennzahlen_punkte_proportional():
    tab = _punkte("2023-12-01", "2024-02-29 23:00", _proportional(50.0))
    k = nv.kennzahlen_punkte(tab, anschlusswert_kw=10.0)
    assert k["status"] == "ok"
    assert k["steigung"] == pytest.approx(1.0, abs=0.05)
    #50 l/h je kW ergibt 1000/(1.163*50) = 17.2 K
    assert k["spreizung_ref_k"] == pytest.approx(17.2, abs=0.5)
    assert k["rl_ueber_50_anteil"] == 0.0
    assert k["flow_spez_lh_kw"] == pytest.approx(k["flow_median_lh"] / 10.0)


def test_kennzahlen_punkte_zu_wenig_stunden():
    tab = _punkte("2023-12-01", "2023-12-05", _proportional())
    k = nv.kennzahlen_punkte(tab, min_stunden=300)
    assert k["status"] == "zu_wenig_stunden"
    assert k["n_stunden"] == len(tab)


def test_kennzahlen_punkte_ohne_anschlusswert():
    tab = _punkte("2023-12-01", "2024-02-29 23:00", _proportional(), rt=55.0)
    k = nv.kennzahlen_punkte(tab, anschlusswert_kw=None)
    assert np.isnan(k["flow_spez_lh_kw"])
    assert k["rl_ueber_50_anteil"] == 1.0


def _zwei_winter(flow_a, flow_b, seed=0):
    a = _punkte("2023-12-01", "2024-02-29 23:00", flow_a, seed=seed)
    b = _punkte("2024-12-01", "2025-02-28 23:00", flow_b, seed=seed + 1)
    sommer = _punkte("2024-06-01", "2024-06-30 23:00", flow_a, seed=seed + 2)
    return pd.concat([a, sommer, b], ignore_index=True)


def test_winterkennzahlen_eine_zeile_je_winter():
    punkte = {1: _zwei_winter(_proportional(), _proportional())}
    tab, aus = nv.winterkennzahlen(punkte, anschlusswerte={1: 8.0})
    assert sorted(tab["winter"]) == ["23/24", "24/25"]
    assert (tab["anschlusswert_kw"] == 8.0).all()
    assert len(aus) == 0


def test_winterkennzahlen_begehung_puffer_entfernt_stunden():
    punkte = {1: _zwei_winter(_proportional(), _proportional())}
    ohne, _ = nv.winterkennzahlen(punkte)
    mit, _ = nv.winterkennzahlen(
        punkte, begehungen={"1": [pd.Timestamp("2024-01-15")]}, puffer_tage=7)
    n_ohne = ohne.set_index("winter").loc["23/24", "n_stunden"]
    n_mit = mit.set_index("winter").loc["23/24", "n_stunden"]
    assert n_ohne - n_mit == 15 * 24


def test_winterkennzahlen_ausschluss_mit_grund():
    kurz = _punkte("2023-12-01", "2023-12-05", _proportional())
    leer = kurz.iloc[0:0]
    tab, aus = nv.winterkennzahlen({1: kurz, 2: leer})
    assert len(tab) == 0
    gruende = dict(zip(aus["meter"], aus["grund"]))
    assert gruende == {1: "zu_wenig_stunden", 2: "keine_daten"}


def test_winterkennzahlen_leer_bricht_netzbezug_nicht():
    kurz = _punkte("2023-12-01", "2023-12-05", _proportional())
    tab, _ = nv.winterkennzahlen({1: kurz})
    assert len(tab) == 0
    assert {"meter", "winter", "anschlusswert_kw"} <= set(tab.columns)
    m = nv.markiere(nv.netzbezug(tab), kennzahlen=nv.KENNZAHLEN)
    assert len(m) == 0


def test_robust_z_vorzeichen_und_skala():
    ref = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    #Median 3, MAD 1, Skala 1.4826
    z = nv.robust_z(np.array([3.0, 4.4826]), ref, vorzeichen=-1)
    assert z[0] == pytest.approx(0.0)
    assert z[1] == pytest.approx(-1.0)


def test_robust_z_konstante_referenz_nan():
    z = nv.robust_z(np.array([1.0]), np.array([2.0, 2.0, 2.0]))
    assert np.isnan(z[0])


def _netztabelle(n=30, winter="23/24", seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "meter": np.arange(1, n + 1), "winter": winter,
        "anschlusswert_kw": np.where(np.arange(n) < n // 2, 8.0, 20.0),
        "spreizung_ref_k": rng.normal(30, 3, n),
        "steigung": rng.normal(0.8, 0.1, n),
        "residuum_sd": rng.normal(0.2, 0.03, n),
        "rl_ueber_50_anteil": rng.uniform(0, 0.3, n),
        "flow_spez_lh_kw": rng.normal(20, 3, n),
        "r2": 0.9, "flow_median_lh": 200.0})


def test_netzbezug_referenzausschluss_bekommt_z():
    tab = _netztabelle()
    tab.loc[0, "spreizung_ref_k"] = 5.0
    b = nv.netzbezug(tab, referenz_ausschluss=(1,))
    zeile = b.set_index("meter").loc[1]
    assert not zeile["in_referenz"]
    assert zeile["z_spreizung_ref_k"] > 5
    assert (b["bezug"] == "netz").all()


def test_netzbezug_zu_kleiner_winter():
    tab = _netztabelle(n=10)
    b = nv.netzbezug(tab, min_stationen=20)
    assert (b["bezug"] == "zu_klein").all()
    assert b["z_steigung"].isna().all()


def test_netzbezug_leistungsklasse_mit_rueckfall():
    tab = _netztabelle(n=30)
    tab.loc[:2, "anschlusswert_kw"] = 3.0
    b = nv.netzbezug(tab, gruppe="leistungsklasse", min_klasse=8)
    bezug = b.set_index("meter")["bezug"]
    assert bezug.loc[1] == "netz"
    assert bezug.loc[20] == "leistungsklasse"


def _mit_schlechten(tab):
    tab = tab.copy()
    #Station 1: zwei Kennzahlen klar im schlechtesten Dezil
    tab.loc[tab["meter"] == 1, ["spreizung_ref_k", "steigung"]] = [10.0, 0.2]
    #Station 2: nur eine Kennzahl schlecht, Rest am Median
    tab.loc[tab["meter"] == 2, ["spreizung_ref_k", "steigung", "residuum_sd",
                                "rl_ueber_50_anteil", "flow_spez_lh_kw"]] = [
        30.0, 0.8, 0.35, 0.15, 20.0]
    return tab


def test_markiere_mindestens_zwei_kennzahlen():
    b = nv.netzbezug(_mit_schlechten(_netztabelle(n=30)))
    m = nv.markiere(b, kennzahlen=nv.KENNZAHLEN).set_index("meter")
    assert m.loc[1, "auffaellig"]
    assert m.loc[1, "rang"] == 1
    assert m.loc[2, "n_schlecht"] == 1
    assert not m.loc[2, "auffaellig"]


def test_markiere_bindungen_am_median_nicht_schlecht():
    tab = _netztabelle(n=30)
    #28 Stationen nie über 50 °C, nur 29 und 30 deutlich
    tab["rl_ueber_50_anteil"] = 0.0
    tab.loc[tab["meter"] == 29, "rl_ueber_50_anteil"] = 0.6
    tab.loc[tab["meter"] == 30, "rl_ueber_50_anteil"] = 0.8
    m = nv.markiere(nv.netzbezug(tab), kennzahlen=nv.KENNZAHLEN)
    schlecht = set(m.loc[m["schlecht_rl_ueber_50_anteil"], "meter"])
    assert schlecht == {29, 30}


def test_score_kennzahlen_redundanz_wirft_flow_raus():
    tab = _netztabelle(n=30)
    tab["flow_spez_lh_kw"] = 600.0 / tab["spreizung_ref_k"]
    k, rho = nv.score_kennzahlen(nv.netzbezug(tab))
    assert "flow_spez_lh_kw" not in k
    assert rho["rho"].abs().max() > 0.99


def test_score_kennzahlen_ohne_redundanz_behaelt_flow():
    k, _ = nv.score_kennzahlen(nv.netzbezug(_netztabelle(n=30)))
    assert "flow_spez_lh_kw" in k


def test_stationsuebersicht_chronisch():
    a = _mit_schlechten(_netztabelle(n=30, winter="23/24", seed=1))
    b = _mit_schlechten(_netztabelle(n=30, winter="24/25", seed=2))
    m = nv.markiere(nv.netzbezug(pd.concat([a, b], ignore_index=True)),
                    kennzahlen=nv.KENNZAHLEN)
    u = nv.stationsuebersicht(m).set_index("meter")
    assert u.loc[1, "chronisch"]
    assert u.loc[1, "winter_auffaellig"] == "23/24,24/25"
    assert not u.loc[2, "chronisch"]


def test_kontext_tabelle():
    k = nv.kontext_tabelle([1, 2, 3], anschlusswerte={1: 8.0, "2": 20.0},
                           bhkw=[3], begehungen={1: ["2024-09-01"]})
    k = k.set_index("meter")
    assert k.loc[1, "leistungsklasse"] == "5-10 kW"
    assert k.loc[3, "leistungsklasse"] == "unbekannt"
    assert k.loc[3, "bhkw"] and not k.loc[1, "bhkw"]
    assert k.loc[1, "hat_begehung"] and k.loc[2, "n_begehungen"] == 0


def test_kontext_tabelle_begehung_ohne_datum_zaehlt_als_begangen():
    k = nv.kontext_tabelle([1, 2, 3], begehungen={1: ["2024-09-01"]},
                           begangen_ohne_datum=["2"]).set_index("meter")
    assert k.loc[2, "hat_begehung"]
    assert k.loc[2, "n_begehungen"] == 0
    assert not k.loc[3, "hat_begehung"]


def test_markiere_zaehlt_kennzahlen_je_score():
    tab = _netztabelle(n=30)
    tab.loc[tab["meter"] == 5, "flow_spez_lh_kw"] = np.nan
    m = nv.markiere(nv.netzbezug(tab), kennzahlen=nv.KENNZAHLEN)
    m = m.set_index("meter")
    assert m.loc[5, "n_kennzahlen"] == len(nv.KENNZAHLEN) - 1
    assert m.loc[6, "n_kennzahlen"] == len(nv.KENNZAHLEN)


def test_profil_bool_numerisch_kategorial():
    meter = list(range(1, 11))
    ueb = pd.DataFrame({"meter": meter, "chronisch": [m <= 4 for m in meter],
                        "in_referenz": True})
    kontext = pd.DataFrame({
        "meter": meter,
        "ventil": [m <= 4 for m in meter],
        "baujahr": [1970 + m if m <= 4 else 2000 + m for m in meter],
        "leistungsklasse": ["5-10 kW"] * 5 + ["über 10 kW"] * 5,
        "n_beg": [1 if m <= 4 else 0 for m in meter]})
    p = nv.profil(ueb, kontext)
    assert p.loc[p["merkmal"] == "n_beg", "test"].iloc[0] == "mannwhitney"
    ventil = p[p["merkmal"] == "ventil"].iloc[0]
    assert ventil["test"] == "fisher"
    assert ventil["wert_gruppe"] == 1.0 and ventil["wert_rest"] == 0.0
    assert ventil["p_wert"] < 0.05
    assert p.loc[p["merkmal"] == "baujahr", "test"].iloc[0] == "mannwhitney"
    assert set(p.loc[p["merkmal"] == "leistungsklasse", "auspraegung"]) == {
        "5-10 kW", "über 10 kW"}


def test_heizgradstunden_je_winter():
    zeit = pd.date_range("2023-12-01", "2023-12-31 23:00", freq="h")
    temp = pd.DataFrame({"timestamp": zeit, "t_out": 5.0})
    h = nv.heizgradstunden_je_winter(temp).set_index("winter")
    assert h.loc["23/24", "heizgradstunden"] == pytest.approx(10.0 * len(zeit))
    assert h.loc["23/24", "n_stunden"] == len(zeit)


def test_bestwert_richtung():
    x = np.arange(1.0, 9.0)
    #kleiner besser: Quantil 0,25 = 2,75, beste sind 1 und 2
    assert nv.bestwert(x, 1) == pytest.approx(1.5)
    assert nv.bestwert(x, -1) == pytest.approx(7.5)
    assert np.isnan(nv.bestwert([np.nan], 1))


def _wintertabelle(winter, spreizung, rl, start=1):
    n = len(spreizung)
    return pd.DataFrame({"meter": range(start, start + n), "winter": winter,
                         "spreizung_ref_k": spreizung,
                         "rl_ueber_50_anteil": rl})


KZ2 = {"spreizung_ref_k": -1, "rl_ueber_50_anteil": 1}


def test_grenzen_lernen_ohne_bhkw_und_nur_lernwinter():
    lern = _wintertabelle("23/24", np.linspace(10, 40, 21), np.linspace(0.6, 0, 21))
    bhkw = _wintertabelle("23/24", [5.0], [1.0], start=99)
    spaeter = _wintertabelle("24/25", np.full(21, 80.0), np.zeros(21))
    gr = nv.grenzen_lernen(pd.concat([lern, bhkw, spaeter]), KZ2,
                           referenz_ausschluss=[99], winter=["23/24"])
    assert gr.attrs["n_referenz"] == 21
    assert gr.loc["spreizung_ref_k", "median"] == pytest.approx(25.0)
    assert gr.loc["spreizung_ref_k", "ziel"] > 35
    assert gr.loc["rl_ueber_50_anteil", "ziel"] == pytest.approx(0.075)


def test_grenzen_anwenden_eingefroren():
    lern = _wintertabelle("23/24", np.linspace(10, 40, 21), np.linspace(0.6, 0, 21))
    gr = nv.grenzen_lernen(lern, KZ2, referenz_ausschluss=[])
    #im Testwinter sind alle besser geworden, nur Station 1 bleibt schlecht
    test = _wintertabelle("24/25", [10.0] + [45.0] * 20, [0.6] + [0.0] * 20)
    a = nv.grenzen_anwenden(test, gr).set_index("meter")
    assert bool(a.loc[1, "auffaellig"])
    assert not a.loc[2:, "auffaellig"].any()
    assert (a.loc[2:, "potenzial"] == "gering").all()
    assert a.loc[2, "abstand_spreizung_ref_k"] == 0.0
    assert a.loc[2, "groesste_luecke"] == ""
    assert a.loc[1, "potenzial"] == "hoch"
    assert a.loc[1, "abstand_spreizung_ref_k"] == pytest.approx(
        gr.loc["spreizung_ref_k", "ziel"] - 10.0)


def test_potenzial_lueckeneinheit_typische_station_ist_eins():
    tab = _wintertabelle("23/24", np.linspace(10, 40, 21), np.linspace(0.6, 0, 21))
    p = nv.potenzial_je_winter(tab, KZ2, referenz_ausschluss=[],
                               min_stationen=5).set_index("meter")
    #Station 11 liegt bei beiden Kennzahlen genau am Median
    assert p.loc[11, "potenzial_score"] == pytest.approx(1.0)
    assert p.loc[11, "potenzial"] == "mittel"
    assert p.loc[1, "groesste_luecke"] in KZ2


def test_potenzial_kleiner_winter_bleibt_leer():
    tab = _wintertabelle("25/26", [10.0, 20.0, 30.0], [0.1, 0.2, 0.3])
    p = nv.potenzial_je_winter(tab, KZ2, referenz_ausschluss=[], min_stationen=20)
    assert p["potenzial_score"].isna().all()
    assert (p["potenzial"] == "").all()
