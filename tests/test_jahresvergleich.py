"""
Tests fuer src.jahresvergleich (Jahres- und Wintervergleich um eine Begehung).

Nur synthetische Stundendaten, kein Netzzugriff, keine Rohdaten. Der
konstante Zaehler liefert exakte Erwartungswerte fuer Energie, Volumen
und Vollaststunden; der Sprungzaehler prueft, dass eine Verbesserung
nach der Begehung im Vorzeichen der Differenz ankommt. Der zweite Teil
deckt den Wintervergleich ab: Winterabgrenzung aus `src/season.py`,
Zuordnung der Begehung zu Vorher- und Nachher-Winter samt
angeschnittenem Winter, symmetrisches Beschneiden in der erweiterten
Variante und die Ausschlussbilanz.

Laeuft mit:

    python -m pytest tests/test_jahresvergleich.py
"""

import numpy as np
import pandas as pd
import pytest

from src import jahresvergleich as jv


def _meter(start: str = "2023-01-01", days: int = 800,
           rt: float = 45.0, power: float = 10.0) -> pd.DataFrame:
    """Konstanter Zaehler: jede Stunde dieselben Werte."""
    hours = days * 24
    ts = pd.date_range(start, periods=hours, freq="h")
    flow = power * 40.0
    return pd.DataFrame({
        "energy": np.arange(hours, dtype=float) * power,
        "flow": np.full(hours, flow),
        "power": np.full(hours, power),
        "dt": np.full(hours, 70.0 - rt),
        "vl": np.full(hours, 70.0),
        "rt": np.full(hours, rt),
        "volume": np.arange(hours, dtype=float) * flow / 1000.0,
    }, index=ts.rename("Timestamp"))


def _sprung_meter(datum: str, start: str = "2023-01-01", days: int = 800,
                  rt_vor: float = 55.0, rt_nach: float = 40.0) -> pd.DataFrame:
    df = _meter(start=start, days=days, rt=rt_vor)
    ab = df.index > pd.Timestamp(datum)
    df.loc[ab, "rt"] = rt_nach
    df.loc[ab, "dt"] = 70.0 - rt_nach
    return df


def _hdh(index: pd.DatetimeIndex, wert: float = 5.0) -> pd.Series:
    return pd.Series(np.full(len(index), wert), index=index,
                     name="heating_degree_hours")


#--------------------------------------------------------------------------
#Fenstergrenzen
#--------------------------------------------------------------------------

def test_kalendergleiche_fenster_liegen_genau_ein_jahr_auseinander():
    g = jv.vergleichsfenster("2024-09-15", window_days=270)
    assert g["nach_start"] == pd.Timestamp("2024-09-16")
    assert g["vor_start"] == g["nach_start"] - pd.Timedelta(days=365)
    assert g["vor_end"] == g["nach_end"] - pd.Timedelta(days=365)
    #beide Fenster decken dieselben Kalendermonate ab
    assert g["vor_start"].month == g["nach_start"].month
    assert g["vor_end"].month == g["nach_end"].month


def test_begehungstag_liegt_in_keinem_fenster():
    d = pd.Timestamp("2024-09-15")
    for modus in (jv.MODUS_KALENDER, jv.MODUS_SYMMETRISCH):
        g = jv.vergleichsfenster(d, window_days=180, modus=modus)
        assert g["nach_start"] > d
        assert not (g["vor_start"] <= d <= g["vor_end"])


def test_symmetrischer_modus_spiegelt_um_das_datum():
    g = jv.vergleichsfenster("2024-09-15", window_days=21,
                             modus=jv.MODUS_SYMMETRISCH)
    assert g["vor_start"] == pd.Timestamp("2024-08-25")
    assert g["vor_end"] == pd.Timestamp("2024-09-14 23:00")
    assert g["nach_start"] == pd.Timestamp("2024-09-16")


def test_fensterlaenge_ist_parameter_und_wird_geprueft():
    kurz = jv.vergleichsfenster("2024-09-15", window_days=90)
    lang = jv.vergleichsfenster("2024-09-15", window_days=270)
    assert lang["nach_end"] - kurz["nach_end"] == pd.Timedelta(days=180)
    with pytest.raises(ValueError):
        jv.vergleichsfenster("2024-09-15", window_days=0)
    with pytest.raises(ValueError):
        jv.vergleichsfenster("2024-09-15", window_days=90, modus="quatsch")


#--------------------------------------------------------------------------
#Kennzahlen je Fenster
#--------------------------------------------------------------------------

def test_energie_und_volumen_aus_kumulativem_zaehler():
    df = _meter(days=400, power=10.0)
    f = jv.fensterkennzahlen(df, "2023-02-01", "2023-02-10 23:00")
    stunden = 10 * 24
    #Differenz kumulativ ueber n Stunden: (n-1) Schritte a 10 kWh
    assert f["energie_kwh"] == pytest.approx((stunden - 1) * 10.0)
    assert f["n_hours"] == stunden
    assert f["coverage"] == pytest.approx(1.0)


def test_vollaststunden_auf_kalenderlaenge_normiert_nicht_auf_historie():
    df = _meter(days=400, power=10.0)
    kurz = jv.fensterkennzahlen(df, "2023-02-01", "2023-02-10 23:00")
    lang = jv.fensterkennzahlen(df, "2023-02-01", "2023-04-01 23:00")
    #konstante Last: die Jahres-Hochrechnung darf nicht von der
    #Fensterlaenge abhaengen (Regression zum full_load_hours-Bug)
    assert kurz["vollaststunden"] == pytest.approx(lang["vollaststunden"],
                                                   rel=0.02)
    assert kurz["vollaststunden"] == pytest.approx(8760.0, rel=0.02)


def test_ruecklauf_unter_last_ignoriert_stillstandsstunden():
    df = _meter(days=60, rt=40.0)
    #Stillstand mit hohem Ruecklauf: faellt aus rt_mean_loaded heraus,
    #verzieht aber den Median ueber alle Stunden
    aus = df.index < pd.Timestamp("2023-01-15")
    df.loc[aus, "power"] = 0.0
    df.loc[aus, "rt"] = 65.0
    f = jv.fensterkennzahlen(df, "2023-01-01", "2023-02-28 23:00")
    assert f["rt_mean_loaded"] == pytest.approx(40.0)
    assert f["rt_median"] == pytest.approx(40.0)
    assert f["betrieb_anteil"] < 1.0


def test_abdeckung_faellt_bei_messluecke_ohne_zeile_zu_verlieren():
    df = _meter(days=60)
    df = df[(df.index < "2023-01-10") | (df.index >= "2023-01-20")]
    f = jv.fensterkennzahlen(df, "2023-01-01", "2023-01-30 23:00")
    assert 0.6 < f["coverage"] < 0.7
    assert not np.isnan(f["energie_kwh"])


def test_leeres_fenster_liefert_nan_statt_fehler():
    df = _meter(days=30)
    f = jv.fensterkennzahlen(df, "2025-01-01", "2025-01-31 23:00")
    assert f["n_hours"] == 0
    assert f["coverage"] == pytest.approx(0.0)
    assert np.isnan(f["rt_median"])


def test_sommer_flow_baseline_nur_aus_sommermonaten():
    df = _meter(days=500)
    winter = jv.fensterkennzahlen(df, "2023-01-01", "2023-02-28 23:00")
    sommer = jv.fensterkennzahlen(df, "2023-06-01", "2023-08-31 23:00")
    assert np.isnan(winter["sommer_flow_baseline"])
    assert sommer["sommer_flow_baseline"] == pytest.approx(400.0)


#--------------------------------------------------------------------------
#Witterungsnormierung
#--------------------------------------------------------------------------

def test_witterungsnormierung_neutralisiert_das_kaeltere_jahr():
    df = _meter(days=800, power=10.0)
    d = "2024-03-01"
    g = jv.vergleichsfenster(d, window_days=180)
    hdh = _hdh(df.index, 4.0)
    #Vorjahr 25 % kaelter: roh sieht das Nachher-Jahr sparsamer aus,
    #normiert auf Heizgradstunden verschwindet der Unterschied
    kalt = (hdh.index >= g["vor_start"]) & (hdh.index <= g["vor_end"])
    hdh[kalt] = 5.0
    df_kalt = df.copy()
    ist_vor = (df.index >= g["vor_start"]) & (df.index <= g["vor_end"])
    df_kalt.loc[:, "power"] = np.where(ist_vor, 12.5, 10.0)
    df_kalt["energy"] = np.cumsum(df_kalt["power"].to_numpy())

    v = jv.vergleich_fuer_begehung(df_kalt, d, window_days=180, hdh=hdh)
    assert v["d_energie_kwh"] < 0
    assert v["d_energie_je_kh"] == pytest.approx(0.0, abs=1e-6)


def test_ohne_heizgradstunden_bleiben_normierte_kennzahlen_nan():
    df = _meter(days=800)
    v = jv.vergleich_fuer_begehung(df, "2024-03-01", window_days=180)
    assert np.isnan(v["energie_je_kh_vor"])
    assert np.isnan(v["d_energie_je_kh"])
    assert not np.isnan(v["d_energie_kwh"])


#--------------------------------------------------------------------------
#Vergleich je Begehung, Flags
#--------------------------------------------------------------------------

def test_ruecklaufsprung_nach_begehung_erscheint_in_der_differenz():
    d = "2024-03-01"
    df = _sprung_meter(d, days=900, rt_vor=55.0, rt_nach=40.0)
    v = jv.vergleich_fuer_begehung(df, d, window_days=180)
    assert v["rt_mean_loaded_vor"] == pytest.approx(55.0)
    assert v["rt_mean_loaded_nach"] == pytest.approx(40.0)
    assert v["d_rt_mean_loaded"] == pytest.approx(-15.0)
    assert v["zustand_vor"] == "schlecht"
    assert v["zustand_nach"] == "gut"


def test_zustand_nutzt_dieselbe_schwelle_wie_notebook_03():
    assert jv.RT_SCHWELLE == 50.0
    assert jv._zustand(50.1) == "schlecht"
    assert jv._zustand(49.9) == "gut"
    assert jv._zustand(float("nan")) is None


def test_zaehlerwechsel_im_vergleichszeitraum_wird_markiert():
    df = _meter(days=900)
    d = "2024-03-01"
    ohne = jv.vergleich_fuer_begehung(df, d, window_days=180)
    mit = jv.vergleich_fuer_begehung(df, d, window_days=180,
                                     meter_changes=["2024-01-15"])
    spaeter = jv.vergleich_fuer_begehung(df, d, window_days=180,
                                         meter_changes=["2022-01-15"])
    assert not ohne["meter_change"]
    assert mit["meter_change"]
    assert not spaeter["meter_change"]


def test_weitere_begehung_im_fenster_wird_markiert_eigene_nicht():
    df = _meter(days=900)
    d = "2024-03-01"
    nur_eigene = jv.vergleich_fuer_begehung(df, d, window_days=180,
                                            weitere_begehungen=[d])
    zweite = jv.vergleich_fuer_begehung(df, d, window_days=180,
                                        weitere_begehungen=[d, "2024-06-01"])
    assert not nur_eigene["weitere_begehung"]
    assert zweite["weitere_begehung"]


#--------------------------------------------------------------------------
#Machbarkeit und Tabellen
#--------------------------------------------------------------------------

def test_abdeckung_meldet_zu_kurze_historie_statt_sie_zu_verwerfen():
    beg = pd.DataFrame({"meter": [1, 2], "datum": pd.to_datetime(
        ["2024-09-15", "2024-09-15"])})
    historien = {
        1: (pd.Timestamp("2021-05-31"), pd.Timestamp("2025-07-11")),
        2: (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
    }
    t = jv.abdeckung(beg, historien, window_days=270)
    assert len(t) == 2
    assert bool(t.loc[t["meter"] == 1, "vollstaendig"].iloc[0])
    assert not bool(t.loc[t["meter"] == 2, "vollstaendig"].iloc[0])


def test_volles_jahr_scheitert_an_der_historie_kuerzeres_fenster_nicht():
    beg = pd.DataFrame({"meter": [1], "datum": [pd.Timestamp("2024-09-15")]})
    historien = {1: (pd.Timestamp("2021-05-31"), pd.Timestamp("2025-07-11"))}
    assert not bool(jv.abdeckung(beg, historien, 365)["vollstaendig"].iloc[0])
    assert bool(jv.abdeckung(beg, historien, 270)["vollstaendig"].iloc[0])


def test_tabelle_haelt_zusatzspalten_und_ueberspringt_zaehler_ohne_reihe():
    serien = {1: _meter(days=900), 2: _meter(days=900, rt=52.0)}
    beg = pd.DataFrame({
        "meter": [1, 2, 99],
        "datum": pd.to_datetime(["2024-03-01"] * 3),
        "kategorie": ["viele", "keine", "mittlere"],
    })
    t = jv.jahresvergleich_tabelle(serien, beg, window_days=180)
    assert list(t["meter"]) == [1, 2]
    assert list(t["kategorie"]) == ["viele", "keine"]
    assert set(t["modus"]) == {jv.MODUS_KALENDER}


def test_kontrollgruppe_nutzt_dieselben_fenstergrenzen():
    serien = {7: _meter(days=900), 8: _meter(days=900)}
    k = jv.kontrollgruppe_tabelle(serien, "2024-03-01", window_days=180)
    g = jv.vergleichsfenster("2024-03-01", 180)
    assert len(k) == 2
    assert set(k["vor_start"]) == {g["vor_start"]}
    assert set(k["nach_end"]) == {g["nach_end"]}


def test_vierfeldertafel_hat_immer_alle_vier_felder():
    tab = pd.DataFrame({"zustand_vor": ["gut", "gut", "schlecht"],
                        "zustand_nach": ["gut", "gut", "gut"]})
    v = jv.vierfeldertafel(tab)
    assert list(v.index) == ["gut", "schlecht"]
    assert list(v.columns) == ["gut", "schlecht"]
    assert v.loc["gut", "gut"] == 2
    assert v.loc["schlecht", "schlecht"] == 0


#--------------------------------------------------------------------------
#Wintervergleich: Winter vor der Begehung gegen Winter danach
#--------------------------------------------------------------------------

def test_winterabgrenzung_kommt_aus_season():
    from src import season
    kern = {m for m, s in season.SEASON_MONTHS.items()
            if s == season.KERNWINTER}
    assert kern == {12, 1, 2}
    #die Spanne laeuft ueber den Jahreswechsel, deshalb (erster, letzter)
    assert jv.WINTER_VARIANTEN[jv.WINTER_KERN] == (12, 2)
    assert jv.WINTER_VARIANTEN[jv.WINTER_ERWEITERT] == (9, 4)
    assert set(jv.WINTER_VARIANTEN) == {jv.WINTER_KERN, jv.WINTER_ERWEITERT}


def test_heizperiode_laeuft_ueber_den_jahreswechsel():
    p = jv.heizperiode(2024, jv.WINTER_KERN)
    assert p["start"] == pd.Timestamp("2024-12-01")
    assert p["end"] == pd.Timestamp("2025-02-28 23:00")
    #Schaltjahr: der Februar endet einen Tag spaeter
    assert jv.heizperiode(2023)["end"] == pd.Timestamp("2024-02-29 23:00")
    e = jv.heizperiode(2024, jv.WINTER_ERWEITERT)
    assert e["start"] == pd.Timestamp("2024-09-01")
    assert e["end"] == pd.Timestamp("2025-04-30 23:00")
    assert jv.winter_label(2024) == "2024/25"
    with pytest.raises(ValueError):
        jv.heizperiode(2024, "halbwinter")


def test_begehung_im_herbst_bekommt_den_winter_davor_und_danach():
    z = jv.winterzuordnung("2024-09-15")
    assert z["winter_vor_label"] == "2023/24"
    assert z["winter_nach_label"] == "2024/25"
    assert not z["angeschnitten"]


def test_angeschnittener_winter_zaehlt_weder_vorher_noch_nachher():
    z = jv.winterzuordnung("2025-01-20")
    assert z["angeschnitten"]
    assert z["winter_datum"] == 2024
    #der Winter 2024/25 faellt heraus, verglichen werden die Nachbarn
    assert z["winter_vor_label"] == "2023/24"
    assert z["winter_nach_label"] == "2025/26"


def test_winterfenster_sind_ohne_vorjahresversatz_kalendergleich():
    g = jv.winterfenster("2024-09-15")
    #beide Fenster sind Heizperioden, decken also dieselben Monate ab -
    #dafuer wird kein Versatz wie im Jahresvergleich gebraucht
    assert g["vor_start"].month == g["nach_start"].month == 12
    assert g["vor_end"].month == g["nach_end"].month == 2
    assert g["fensteranteil"] == pytest.approx(1.0)
    assert g["vor_end"] < pd.Timestamp("2024-09-15")
    assert g["nach_start"] > pd.Timestamp("2024-09-15")


def test_erweitertes_fenster_wird_beidseitig_gleich_beschnitten():
    #der 20.09. liegt im erweiterten Nachher-Winter; der abgeschnittene
    #Anfang muss im Vorher-Fenster genauso fehlen, sonst waeren die
    #Fenster nicht mehr kalendergleich
    g = jv.winterfenster("2024-09-20", jv.WINTER_ERWEITERT)
    assert g["nach_start"] == pd.Timestamp("2024-09-21")
    assert g["vor_start"] == pd.Timestamp("2023-09-21")
    assert g["vor_start"].strftime("%m-%d") == g["nach_start"].strftime("%m-%d")
    assert g["vor_end"].strftime("%m-%d") == g["nach_end"].strftime("%m-%d")
    assert 0.0 < g["fensteranteil"] < 1.0


def test_erweitertes_fenster_schneidet_auch_am_ende_symmetrisch():
    g = jv.winterfenster("2025-03-15", jv.WINTER_ERWEITERT)
    assert g["vor_end"] < pd.Timestamp("2025-03-15")
    assert g["vor_end"].strftime("%m-%d") == g["nach_end"].strftime("%m-%d")
    assert g["nach_start"] == pd.Timestamp("2025-09-01")


def test_wintervergleich_findet_den_ruecklaufsprung():
    d = "2024-09-15"
    df = _sprung_meter(d, start="2023-06-01", days=800,
                       rt_vor=55.0, rt_nach=40.0)
    v = jv.wintervergleich_fuer_begehung(df, d)
    assert v["winter_vor_label"] == "2023/24"
    assert v["winter_nach_label"] == "2024/25"
    assert v["rt_mean_loaded_vor"] == pytest.approx(55.0)
    assert v["rt_mean_loaded_nach"] == pytest.approx(40.0)
    assert v["d_rt_mean_loaded"] == pytest.approx(-15.0)
    assert v["zustand_vor"] == "schlecht"
    assert v["zustand_nach"] == "gut"


def test_wintervergleich_meldet_den_kaelteren_winter():
    df = _meter(start="2023-06-01", days=800)
    hdh = _hdh(df.index, 4.0)
    g = jv.winterfenster("2024-09-15")
    kalt = (hdh.index >= g["nach_start"]) & (hdh.index <= g["nach_end"])
    hdh[kalt] = 6.0
    v = jv.wintervergleich_fuer_begehung(df, "2024-09-15", hdh=hdh)
    assert v["heizgradstunden_nach"] > v["heizgradstunden_vor"]
    #gleiche Jahreszeit heisst nicht gleiche Witterung
    assert (v["heizgradstunden_nach"] / v["heizgradstunden_vor"]
            == pytest.approx(1.5, rel=0.05))


def test_tagesabdeckung_bewertet_tagesraster_nicht_als_luecke():
    df = _meter(start="2023-06-01", days=800)
    #aelterer Exportstand mit nur einer Zeile je Tag: auf dem
    #Stundenraster sieht das nach einer Luecke aus, es fehlt aber kein Tag
    g = jv.winterfenster("2024-09-15")
    taeglich = df[(df.index > g["vor_end"]) | (df.index.hour == 12)]
    f = jv.fensterkennzahlen(taeglich, g["vor_start"], g["vor_end"])
    assert f["coverage"] == pytest.approx(1 / 24, abs=0.01)
    assert f["tagesabdeckung"] == pytest.approx(1.0, abs=0.02)


def test_winter_abdeckung_meldet_angeschnitten_und_fehlende_historie():
    beg = pd.DataFrame({
        "meter": [1, 2, 3],
        "datum": pd.to_datetime(["2024-09-15", "2024-12-10", "2024-09-15"]),
    })
    historien = {
        1: (pd.Timestamp("2021-05-31"), pd.Timestamp("2025-07-11")),
        2: (pd.Timestamp("2021-05-31"), pd.Timestamp("2025-07-11")),
        3: (pd.Timestamp("2024-06-01"), pd.Timestamp("2025-07-11")),
    }
    t = jv.winter_abdeckung(beg, historien).set_index("meter")
    assert len(t) == 3
    assert bool(t.loc[1, "vollstaendig"])
    #angeschnitten: der Nachher-Winter rueckt auf 2025/26 und liegt
    #ausserhalb der Historie
    assert bool(t.loc[2, "angeschnitten"])
    assert not bool(t.loc[2, "vollstaendig"])
    #Historie beginnt nach dem Vorher-Winter
    assert not bool(t.loc[3, "vollstaendig"])


def test_ausschlussbilanz_vergibt_genau_einen_grund_und_filtert_nicht():
    tab = pd.DataFrame({
        "meter": [1, 2, 3, 4],
        "vollstaendig": [True, False, True, True],
        "fensteranteil": [1.0, 1.0, 0.3, 1.0],
        "tagesabdeckung_vor": [1.0, 1.0, 1.0, 0.2],
        "tagesabdeckung_nach": [1.0, 1.0, 1.0, 1.0],
        "coverage_vor": [1.0, 1.0, 1.0, 1.0],
        "coverage_nach": [1.0, 1.0, 1.0, 1.0],
    })
    b = jv.winter_ausschlussbilanz(tab)
    assert len(b) == len(tab)
    assert list(b["auswertbar"]) == [True, False, False, False]
    assert b.loc[1, "ausschlussgrund"].startswith("Historie")
    assert b.loc[2, "ausschlussgrund"].startswith("Fensteranteil")
    assert b.loc[3, "ausschlussgrund"].startswith("Tagesabdeckung")


def test_strenge_stundenabdeckung_ist_zuschaltbar():
    tab = pd.DataFrame({
        "meter": [1],
        "vollstaendig": [True], "fensteranteil": [1.0],
        "tagesabdeckung_vor": [1.0], "tagesabdeckung_nach": [1.0],
        "coverage_vor": [0.57], "coverage_nach": [1.0],
    })
    assert bool(jv.winter_ausschlussbilanz(tab)["auswertbar"].iloc[0])
    streng = jv.winter_ausschlussbilanz(tab, min_coverage=0.6)
    assert not bool(streng["auswertbar"].iloc[0])
    assert streng["ausschlussgrund"].iloc[0].startswith("Stundenabdeckung")


def test_wintertabelle_und_kontrollgruppe_nutzen_dieselben_grenzen():
    serien = {1: _meter(start="2023-06-01", days=800),
              2: _meter(start="2023-06-01", days=800, rt=52.0)}
    beg = pd.DataFrame({"meter": [1, 99],
                        "datum": pd.to_datetime(["2024-09-15"] * 2),
                        "kategorie": ["viele", "keine"]})
    t = jv.wintervergleich_tabelle(serien, beg)
    assert list(t["meter"]) == [1]
    assert list(t["kategorie"]) == ["viele"]
    k = jv.winter_kontrollgruppe(serien, "2024-09-15")
    g = jv.winterfenster("2024-09-15")
    assert len(k) == 2
    assert set(k["vor_start"]) == {g["vor_start"]}
    assert set(k["nach_end"]) == {g["nach_end"]}


def test_jahresvergleich_bleibt_unveraendert_lauffaehig():
    #der Wintervergleich kommt dazu, er ersetzt den Jahresweg nicht
    df = _meter(days=900)
    alt = jv.vergleich_fuer_begehung(df, "2024-03-01", window_days=180)
    assert alt["modus"] == jv.MODUS_KALENDER
    assert alt["window_days"] == 180
    assert alt["vor_start"] == alt["nach_start"] - pd.Timedelta(days=365)
