"""Feature Engineering, Zeitstruktur und Erklärbarkeit (Notebook 36).

Notebook 35 hat gezeigt: Bei Filter, Durchfluss und Sollwert findet weder eine Regel
noch die KI etwas. Bei der Dämmung findet die KI ein Muster, das wir nicht erklären
können. Liegt das an den Daten, an unseren Kennzahlen oder an den Labels?
Dieses Modul rechnet vier Bausteine dafür:

1. **Tagestabelle** je Station (`tage`) als gemeinsame Grundlage.
2. **Wirkung der Maßnahmen** (`wirkung_je_station`): Ändert sich nach der Begehung
   die Größe, die die Maßnahme ändern müsste? Wetterbereinigt über eine Zerlegung des
   Tagesverbrauchs in Grundlast und Wetteranteil (`wetter_fit`).
3. **Zeitstruktur**: gleitende Korrelation zwischen Durchfluss und Außentemperatur
   (`kopplung_verlauf`) und die Zerlegung im Zeitverlauf (`zerlegung_verlauf`).
4. **Neue Kennzahlen** je Befund (`neue_kennzahlen`), dazu lineares SHAP für die
   logistische Regression (`shap_linear`, `shap_folds`).

Was je Befund erwartet wird, steht in ``PLAN_WIRKUNG`` und ``PLAN_KENNZAHLEN``. Beides
wurde festgelegt, bevor ein Ergebnis gerechnet war (26.10.2026), und wird nicht nach
dem Ergebnis umgedreht.

Warum keine STL-Zerlegung nach Kalender: Die „Saison“ des Wärmeverbrauchs ist die
Außentemperatur, nicht das Datum. Eine Kalender-Saison würde einen warmen Winter als
Trend lesen. Deshalb wird der Tagesverbrauch in Grundlast + Wetteranteil zerlegt
(Heizgradtage mit fester Heizgrenze), der Rest ergibt geglättet den Trend.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import fehlerklassen as fk

HEIZGRENZE_C = 15.0               # Heizgradtage: max(0, 15 °C - Außentemperatur)
HEIZTAG_MAX_C = 12.0              # Heiztage: Tagesmittel bis 12 °C
WARMTAG_MIN_C = 15.0              # Tage ohne Heizung: Tagesmittel ab 15 °C
KALTTAG_MAX_C = 5.0               # kalte Tage für den Filter
FENSTER_VOR = pd.Timedelta(days=365)
ABSTAND_NACH = pd.Timedelta(days=14)   # Einstellungen nach der Begehung setzen sich erst
FENSTER_NACH = pd.Timedelta(days=365)
MIN_STUNDEN_TAG = 20
MIN_TAGE_FIT = 30
MIN_TAGE_WARM = 10
MIN_TAGE_KALT = 5
KOPPLUNG_FENSTER = 14             # Tage je Fenster der gleitenden Korrelation
KOPPLUNG_MIN = 10
TREND_TAGE = 28
RAUM_C = 20.0                     # Raumtemperatur im Technikraum
FLUSS_STILL_LH = 1.0              # bis hier gilt der Durchfluss als Stillstand
WINTER = fk.WINTER
SOMMER = fk.SOMMER
ZIELE = ["ventil", "daemmung", "temperatur", "filter", "durchfluss", "ueberdimensioniert"]

# Erwartete Wirkung der Maßnahme: (Spalte aus wirkung_je_station, Richtung, Satz).
# Richtung -1 = die Größe sinkt bei Stationen mit dieser Maßnahme stärker, +1 = steigt,
# 0 = keine Änderung erwartet (Placebo, beidseitig geprüft).
PLAN_WIRKUNG = {
    "ventil": ("d_nachtfluss_lph", -1,
               "Ventil getauscht: Der Durchfluss in Sommernächten (0 bis 5 Uhr, Tage ab 15 °C) sinkt."),
    "daemmung": ("d_grundlast_rel", -1,
                 "Leitungen gedämmt: Die Grundlast, also der wetterunabhängige Teil des Tagesverbrauchs, sinkt."),
    "temperatur": ("d_ruecklauf_tag_k", -1,
                   "Rücklauf-Sollwert gesenkt: Der Rücklauf tagsüber (8 bis 20 Uhr) an Heiztagen sinkt, wetterbereinigt."),
    "filter": ("d_fluss_kalt_rel", +1,
               "Filter gereinigt: An kalten Tagen (bis 5 °C) kommt mehr Durchfluss, wetterbereinigt."),
    "durchfluss": ("d_fluss_rel", -1,
                   "Durchfluss neu eingestellt: Der Durchfluss an Heiztagen sinkt, wetterbereinigt."),
    "ueberdimensioniert": ("d_energie_rel", 0,
                           "Vertrag verkleinert (Placebo): Am Verbrauch ändert sich nichts."),
}

# Neue Kennzahl je Befund, Zustand vor der Begehung: (Spalte, Richtung, Satz).
PLAN_KENNZAHLEN = {
    "ventil": ("kopplung_fluss_winter", -1,
               "Offenes Ventil: Der Durchfluss folgt der Außentemperatur schlechter (gleitende Korrelation)."),
    "daemmung": ("abkuehlrate_stillstand", +1,
                 "Ungedämmte Leitungen: Steht das Wasser, kühlt der Vorlauf schneller ab."),
    "temperatur": ("ruecklauf_schwachlast", +1,
                   "Rücklauf-Sollwert zu hoch: Bei Schwachlast ist der Rücklauf wärmer."),
    "filter": ("fluss_saettigung", -1,
               "Verschmutzter Filter: An kalten Tagen kommt der Durchfluss nicht mehr so hoch wie erwartet."),
    "durchfluss": ("fluss_plateau_anteil", -1,
                   "Durchfluss zu hoch eingestellt: Er stößt selten an einen Deckel, weil keiner wirkt."),
    "ueberdimensioniert": ("volllaststunden", -1,
                           "Vertrag zu groß: Die Station kommt auf wenige Volllaststunden."),
}
# Zusatzprüfung der Labels mit der gleitenden Korrelation (gleichzeitig festgelegt).
PLAN_ZUSATZ = {
    "ventil": ("d_kopplung", +1,
               "Ventil getauscht: Danach folgt der Durchfluss der Außentemperatur besser (gleitende Korrelation)."),
}
# Nachträglich ergänzt, nachdem die Abkühlrate in Notebook 36, Abschnitt 6b, bei der Dämmung in die
# erwartete Richtung ging (26.10.2026). Die Richtung folgt eindeutig aus der Physik, die Prüfung ist
# aber nicht vorab geplant und wird im Notebook so gekennzeichnet.
PLAN_NACHTRAG = {
    "daemmung": ("d_abkuehlrate", -1,
                 "Leitungen gedämmt: Danach kühlt stehendes Wasser langsamer ab (Sommer 2025 gegen Sommer 2024)."),
}
SOMMER_NACH = ("2025-06-01", "2025-09-01")
NEUE_KENNZAHLEN = [k for k, _, _ in PLAN_KENNZAHLEN.values()]
EXPLORATIV = ["grundlast_anteil", "kopplung_energie_winter"]

ZIEL_TEXT = {"ventil": "Ventil", "daemmung": "Dämmung", "temperatur": "Sollwert",
             "filter": "Filter", "durchfluss": "Durchfluss", "ueberdimensioniert": "Vertrag"}


# --- Grundlage ------------------------------------------------------------------

def stunden_bereinigen(stunden: pd.DataFrame) -> pd.DataFrame:
    """Negative Durchflüsse und Leistungen (Fehlwerte wie -999) als fehlend."""
    s = stunden.copy()
    s["timestamp"] = s["timestamp"].astype("datetime64[ns]")
    for spalte in ("durchfluss", "leistung"):
        s.loc[s[spalte] < 0, spalte] = np.nan
    return s


def tage(stunden: pd.DataFrame) -> pd.DataFrame:
    """Tageswerte je Station, nur Tage mit mindestens 20 Stunden Leistung."""
    s = stunden_bereinigen(stunden)
    s["tag"] = s["timestamp"].dt.floor("D")
    stunde = s["timestamp"].dt.hour
    g = s.groupby(["zaehler", "tag"])
    t = pd.DataFrame({"aussen": g["aussen"].mean(),
                      "n_stunden": g["leistung"].count(),
                      "energie_kwh": g["leistung"].mean() * 24,
                      "fluss_mittel": g["durchfluss"].mean(),
                      "fluss_p95": g["durchfluss"].quantile(0.95),
                      "ruecklauf_mittel": g["ruecklauf"].mean(),
                      "vorlauf_mittel": g["vorlauf"].mean()})
    t["ruecklauf_tag"] = s[stunde.between(8, 19)].groupby(["zaehler", "tag"])["ruecklauf"].mean()
    t["nachtfluss"] = s[stunde <= 5].groupby(["zaehler", "tag"])["durchfluss"].median()
    t = t[t["n_stunden"] >= MIN_STUNDEN_TAG]
    return t.reset_index()


def heizgrad(aussen) -> np.ndarray:
    return np.clip(HEIZGRENZE_C - np.asarray(aussen, dtype=float), 0, None)


def wetter_fit(t: pd.DataFrame, spalte: str, min_tage: int = MIN_TAGE_FIT) -> Optional[np.ndarray]:
    """Zerlegung y = Grundlast + Steigung · Heizgrad (kleinste Quadrate), sonst None."""
    d = t[[spalte, "aussen"]].dropna()
    if len(d) < min_tage or np.ptp(heizgrad(d["aussen"])) == 0:
        return None
    X = np.column_stack([np.ones(len(d)), heizgrad(d["aussen"])])
    koef, *_ = np.linalg.lstsq(X, d[spalte].to_numpy(dtype=float), rcond=None)
    return koef


def wetter_rest(t: pd.DataFrame, spalte: str, koef: np.ndarray) -> pd.Series:
    """Messwert minus Erwartung aus der Zerlegung (wetterbereinigte Abweichung)."""
    return t[spalte] - (koef[0] + koef[1] * heizgrad(t["aussen"]))


# --- Wirkung der Maßnahmen -----------------------------------------------------

def fenster(t: pd.DataFrame, datum: pd.Timestamp) -> Tuple[pd.DataFrame, pd.DataFrame]:
    vor = t[(t["tag"] >= datum - FENSTER_VOR) & (t["tag"] < datum)]
    nach = t[(t["tag"] >= datum + ABSTAND_NACH) & (t["tag"] < datum + FENSTER_NACH)]
    return vor, nach


def wirkung_je_station(t: pd.DataFrame, datum: pd.Timestamp) -> Dict[str, float]:
    """Änderung nach der Begehung für eine Station (Tagestabelle einer Station).

    Vorher: 365 Tage vor der Begehung. Nachher: ab 14 Tage danach, höchstens 365 Tage.
    Wetterbereinigt heißt: Die Zerlegung wird vorher gelernt und nachher abgezogen.
    """
    vor, nach = fenster(t, pd.Timestamp(datum))
    w = {"tage_vor": len(vor), "tage_nach": len(nach)}
    # Ventil: Durchfluss in Sommernächten, an Tagen ohne Heizung
    wv, wn = vor[vor["aussen"] >= WARMTAG_MIN_C], nach[nach["aussen"] >= WARMTAG_MIN_C]
    ok = wv["nachtfluss"].notna().sum() >= MIN_TAGE_WARM and wn["nachtfluss"].notna().sum() >= MIN_TAGE_WARM
    w["d_nachtfluss_lph"] = wn["nachtfluss"].median() - wv["nachtfluss"].median() if ok else np.nan
    # Dämmung: Grundlast aus der Zerlegung vorher und nachher
    kv, kn = wetter_fit(vor, "energie_kwh"), wetter_fit(nach, "energie_kwh")
    basis = vor["energie_kwh"].mean()
    w["grundlast_vor_kwh"] = kv[0] if kv is not None else np.nan
    w["grundlast_nach_kwh"] = kn[0] if kn is not None else np.nan
    w["steigung_vor_kwh_k"] = kv[1] if kv is not None else np.nan
    w["steigung_nach_kwh_k"] = kn[1] if kn is not None else np.nan
    ok = kv is not None and kn is not None and basis > 0
    w["d_grundlast_rel"] = (kn[0] - kv[0]) / basis if ok else np.nan
    w["d_steigung_rel"] = (kn[1] - kv[1]) / kv[1] if ok and kv[1] > 0 else np.nan
    # gesamter Verbrauch, wetterbereinigt (Placebo Vertrag)
    ok = kv is not None and basis > 0 and nach["energie_kwh"].notna().sum() >= MIN_TAGE_FIT
    w["d_energie_rel"] = wetter_rest(nach, "energie_kwh", kv).mean() / basis if ok else np.nan
    # Heiztage: Rücklauf tagsüber und Durchfluss
    hv, hn = vor[vor["aussen"] <= HEIZTAG_MAX_C], nach[nach["aussen"] <= HEIZTAG_MAX_C]
    k = wetter_fit(hv, "ruecklauf_tag")
    ok = k is not None and hn["ruecklauf_tag"].notna().sum() >= MIN_TAGE_FIT
    w["d_ruecklauf_tag_k"] = wetter_rest(hn, "ruecklauf_tag", k).mean() if ok else np.nan
    k = wetter_fit(hv, "fluss_mittel")
    bezug = hv["fluss_mittel"].mean()
    ok = k is not None and hn["fluss_mittel"].notna().sum() >= MIN_TAGE_FIT and bezug > 0
    w["d_fluss_rel"] = wetter_rest(hn, "fluss_mittel", k).mean() / bezug if ok else np.nan
    # Filter: Durchfluss-Spitze an kalten Tagen
    k = wetter_fit(hv, "fluss_p95")
    kv_t, kn_t = vor[vor["aussen"] <= KALTTAG_MAX_C], nach[nach["aussen"] <= KALTTAG_MAX_C]
    bezug = kv_t["fluss_p95"].mean()
    ok = (k is not None and kv_t["fluss_p95"].notna().sum() >= MIN_TAGE_KALT
          and kn_t["fluss_p95"].notna().sum() >= MIN_TAGE_KALT and bezug > 0)
    w["d_fluss_kalt_rel"] = wetter_rest(kn_t, "fluss_p95", k).mean() / bezug if ok else np.nan
    # Kopplung des Durchflusses an die Außentemperatur, Winter vorher gegen nachher
    kp = kopplung_verlauf(t)
    kp_v = kp[(kp.index >= pd.Timestamp(datum) - FENSTER_VOR) & (kp.index < pd.Timestamp(datum))].dropna()
    kp_n = kp[(kp.index >= pd.Timestamp(datum) + ABSTAND_NACH)
              & (kp.index < pd.Timestamp(datum) + FENSTER_NACH)].dropna()
    ok = len(kp_v) >= MIN_TAGE_FIT and len(kp_n) >= MIN_TAGE_FIT
    w["d_kopplung"] = kp_n.median() - kp_v.median() if ok else np.nan
    return w


def wirkung(tage_tab: pd.DataFrame, termine: pd.Series) -> pd.DataFrame:
    """`wirkung_je_station` für alle Stationen mit Datum (Index Zähler)."""
    zeilen = {}
    for z, t in tage_tab.groupby("zaehler"):
        if z in termine.index and pd.notna(termine[z]):
            zeilen[int(z)] = wirkung_je_station(t.sort_values("tag"), termine[z])
    return pd.DataFrame.from_dict(zeilen, orient="index").rename_axis("zaehler")


# --- Zeitstruktur ---------------------------------------------------------------

def kopplung_verlauf(t: pd.DataFrame, spalte: str = "fluss_mittel",
                     fenster: int = KOPPLUNG_FENSTER) -> pd.Series:
    """Gleitende Korrelation (14 Tage) mit der Außentemperatur, mal -1.

    1 heißt: je kälter, desto mehr, wie es sein soll. Nur Fenster in der Heizzeit
    (Median der Außentemperatur bis 12 °C), sonst ist die Korrelation bedeutungslos.
    """
    d = t.set_index("tag")[[spalte, "aussen"]].sort_index()
    d = d[~d.index.duplicated()].asfreq("D")
    r = d[spalte].rolling(fenster, min_periods=KOPPLUNG_MIN).corr(d["aussen"])
    heizzeit = d["aussen"].rolling(fenster, min_periods=KOPPLUNG_MIN).median() <= HEIZTAG_MAX_C
    return (-r).where(heizzeit).replace([np.inf, -np.inf], np.nan)


def zerlegung_verlauf(t: pd.DataFrame, datum: pd.Timestamp) -> pd.DataFrame:
    """Tagesverbrauch einer Station zerlegt: Grundlast, Wetteranteil, Rest und Trend.

    Gelernt wird die Zerlegung in den 365 Tagen vor ``datum``. Der Trend ist der
    gleitende Median des Rests über 28 Tage. Sinkt er nach der Begehung, braucht die
    Station bei gleichem Wetter weniger.
    """
    vor, _ = fenster(t, pd.Timestamp(datum))
    koef = wetter_fit(vor, "energie_kwh")
    d = t.set_index("tag").sort_index()
    if koef is None:
        return pd.DataFrame(index=d.index)
    d = d[~d.index.duplicated()].asfreq("D")
    aus = pd.DataFrame(index=d.index)
    aus["energie_kwh"] = d["energie_kwh"]
    aus["grundlast"] = koef[0]
    aus["wetteranteil"] = koef[1] * heizgrad(d["aussen"])
    aus["rest"] = d["energie_kwh"] - aus["grundlast"] - aus["wetteranteil"]
    aus["trend"] = aus["rest"].rolling(TREND_TAGE, center=True, min_periods=TREND_TAGE // 2).median()
    aus["trend_rel"] = aus["trend"] / vor["energie_kwh"].mean()
    return aus


def ereignisverlauf(tage_tab: pd.DataFrame, termine: pd.Series, von: int = -300, bis: int = 300
                    ) -> pd.DataFrame:
    """Trend (relativ zum Verbrauch vorher) je Station und Tag relativ zur Begehung."""
    teile = []
    for z, t in tage_tab.groupby("zaehler"):
        if z not in termine.index or pd.isna(termine[z]):
            continue
        datum = pd.Timestamp(termine[z])
        v = zerlegung_verlauf(t, datum)
        if "trend_rel" not in v:
            continue
        rel = (v.index - datum).days
        m = (rel >= von) & (rel <= bis)
        teile.append(pd.DataFrame({"zaehler": int(z), "tag_rel": rel[m],
                                   "trend_rel": v["trend_rel"].to_numpy()[m]}))
    return pd.concat(teile, ignore_index=True) if teile else pd.DataFrame(
        columns=["zaehler", "tag_rel", "trend_rel"])


# --- Neue Kennzahlen (Zustand vor der Begehung) ----------------------------------

def abkuehlrate(h: pd.DataFrame, min_stunden: int = 50) -> float:
    """Abkühlrate k (1/h) im Stillstand nach Newton: ΔT = -k · (T - 20 °C).

    Gezählt werden Stundenpaare ohne Durchfluss mit Vorlauf über 30 °C.
    """
    d = h.sort_values("timestamp")
    t0, t1 = d["vorlauf"].to_numpy()[:-1], d["vorlauf"].to_numpy()[1:]
    f0, f1 = d["durchfluss"].to_numpy()[:-1], d["durchfluss"].to_numpy()[1:]
    dt = np.diff(d["timestamp"].to_numpy()).astype("timedelta64[m]").astype(float)
    ok = ((dt == 60) & (f0 <= FLUSS_STILL_LH) & (f1 <= FLUSS_STILL_LH)
          & (t0 > RAUM_C + 10) & np.isfinite(t0) & np.isfinite(t1))
    if ok.sum() < min_stunden:
        return np.nan
    return float(np.median((t0[ok] - t1[ok]) / (t0[ok] - RAUM_C)))



def abkuehlrate_vorher_nachher(stunden: pd.DataFrame, termine: pd.Series, sommer_vor=SOMMER,
                               sommer_nach=SOMMER_NACH, min_stunden: int = 30) -> pd.DataFrame:
    """Abkühlrate im Sommer vor der Begehung und im Sommer danach.

    Nur Stationen mit Begehung bis Ende April 2025, damit der Sommer danach ganz nach der Begehung liegt.
    Der Sommer davor endet spätestens an der Begehung. Weil die Daten meist im Juli 2025 enden, reichen
    hier 30 Stundenpaare im Stillstand.
    """
    s = stunden_bereinigen(stunden)
    letzte = pd.Timestamp(sommer_nach[0]) - pd.Timedelta(days=31)
    zeilen = {}
    for z, h in s.groupby("zaehler"):
        datum = termine.get(z, pd.NaT)
        if pd.isna(datum) or datum >= letzte:
            continue
        vor = h[(h["timestamp"] >= sommer_vor[0]) & (h["timestamp"] < min(pd.Timestamp(sommer_vor[1]), datum))]
        nach = h[(h["timestamp"] >= sommer_nach[0]) & (h["timestamp"] < sommer_nach[1])]
        zeilen[int(z)] = {"abkuehlrate_vor": abkuehlrate(vor, min_stunden),
                          "abkuehlrate_nach": abkuehlrate(nach, min_stunden)}
    t = pd.DataFrame.from_dict(zeilen, orient="index", columns=["abkuehlrate_vor", "abkuehlrate_nach"],
                               dtype=float).rename_axis("zaehler")
    t["d_abkuehlrate"] = t["abkuehlrate_nach"] - t["abkuehlrate_vor"]
    return t

def fluss_saettigung(tw: pd.DataFrame, min_mild: int = 20, min_kalt: int = MIN_TAGE_KALT) -> float:
    """Durchfluss-Spitze an kalten Tagen (bis 1 °C) geteilt durch die Fortschreibung
    der Geraden aus milden Tagen (3 bis 12 °C). Unter 1 heißt: Der Durchfluss bleibt
    zurück, als stieße er an eine Grenze."""
    d = tw.dropna(subset=["fluss_p95", "aussen"])
    mild = d[d["aussen"].between(3, HEIZTAG_MAX_C)]
    kalt = d[d["aussen"] <= 1]
    if len(mild) < min_mild or len(kalt) < min_kalt:
        return np.nan
    b, a = np.polyfit(mild["aussen"], mild["fluss_p95"], 1)
    erwartet = np.median(a + b * kalt["aussen"])
    return float(np.median(kalt["fluss_p95"]) / erwartet) if erwartet > 0 else np.nan


def fluss_plateau(hw: pd.DataFrame, min_stunden: int = 500) -> float:
    """Anteil der Stunden mit Durchfluss, die bei mindestens 95 % des 99-%-Werts liegen."""
    f = hw["durchfluss"].dropna()
    f = f[f > FLUSS_STILL_LH]
    if len(f) < min_stunden:
        return np.nan
    return float((f >= 0.95 * f.quantile(0.99)).mean())


def ruecklauf_schwachlast(hw: pd.DataFrame, min_stunden: int = 100) -> float:
    """Median-Rücklauf in Stunden mit Durchfluss und weniger als 20 % der Spitzenleistung."""
    d = hw.dropna(subset=["leistung", "ruecklauf", "durchfluss"])
    d = d[(d["durchfluss"] > FLUSS_STILL_LH) & (d["leistung"] > 0)]
    if len(d) < min_stunden:
        return np.nan
    schwach = d[d["leistung"] < 0.2 * d["leistung"].quantile(0.99)]
    return float(schwach["ruecklauf"].median()) if len(schwach) >= min_stunden else np.nan


def neue_kennzahlen(stunden: pd.DataFrame, tage_tab: pd.DataFrame, grenze: pd.Series,
                    vertrag: Optional[pd.Series] = None, winter=WINTER, sommer=SOMMER) -> pd.DataFrame:
    """Die neuen Kennzahlen je Station, nur aus Daten vor ``grenze`` (wie Notebook 25)."""
    s = stunden_bereinigen(stunden)
    s = s[s["timestamp"] < s["zaehler"].map(grenze)]
    t = tage_tab[tage_tab["tag"] < tage_tab["zaehler"].map(grenze)]
    w0, w1, s0, s1 = map(pd.Timestamp, (*winter, *sommer))
    zeilen = {}
    for z, h in s.groupby("zaehler"):
        tz = t[t["zaehler"] == z].sort_values("tag")
        hw = h[(h["timestamp"] >= w0) & (h["timestamp"] < w1)]
        hs = h[(h["timestamp"] >= s0) & (h["timestamp"] < s1)]
        tw = tz[(tz["tag"] >= w0) & (tz["tag"] < w1)]
        k = {}
        kp = kopplung_verlauf(tz) if len(tz) else pd.Series(dtype=float)
        kp = kp[(kp.index >= w0) & (kp.index < w1)].dropna()
        k["kopplung_fluss_winter"] = kp.median() if len(kp) >= MIN_TAGE_FIT else np.nan
        ke = kopplung_verlauf(tz, "energie_kwh") if len(tz) else pd.Series(dtype=float)
        ke = ke[(ke.index >= w0) & (ke.index < w1)].dropna()
        k["kopplung_energie_winter"] = ke.median() if len(ke) >= MIN_TAGE_FIT else np.nan
        k["abkuehlrate_stillstand"] = abkuehlrate(hs)
        k["fluss_saettigung"] = fluss_saettigung(tw)
        k["fluss_plateau_anteil"] = fluss_plateau(hw)
        k["ruecklauf_schwachlast"] = ruecklauf_schwachlast(hw)
        ende = pd.Timestamp(grenze[z])
        jahr = h[h["timestamp"] >= ende - FENSTER_VOR]
        v = vertrag.get(z, np.nan) if vertrag is not None else np.nan
        genug = jahr["leistung"].notna().sum() >= 0.8 * 8760
        k["volllaststunden"] = (jahr["leistung"].mean() * 8760 / v
                                if genug and pd.notna(v) and v > 0 else np.nan)
        tj = tz[tz["tag"] >= ende - FENSTER_VOR]
        koef = wetter_fit(tj, "energie_kwh")
        mittel = tj["energie_kwh"].mean()
        k["grundlast_anteil"] = koef[0] / mittel if koef is not None and mittel > 0 else np.nan
        zeilen[int(z)] = k
    return pd.DataFrame.from_dict(zeilen, orient="index").rename_axis("zaehler")


# --- Prüfen -----------------------------------------------------------------------

def plan_pruefen(werte: pd.Series, y: pd.Series, gruppen: pd.Series, richtung: int,
                 n_perm: int = 5000, seed: int = 0) -> Dict[str, float]:
    """AUC einer Größe mit vorher festgelegter Richtung, 95-%-Intervall und Zufallstest.

    Richtung 0 (Placebo): beidseitiger Zufallstest auf Abstand von 0,5.
    """
    from sklearn.metrics import roc_auc_score
    from . import finalvergleich as fv
    d = pd.DataFrame({"x": werte, "y": y}).dropna()
    d = d[np.isfinite(d["x"])]
    yy = d["y"].astype(int).to_numpy()
    aus = {"Stationen": len(d), "mit Befund": int(yy.sum()),
           "Median mit": float(d.loc[d["y"] == 1, "x"].median()),
           "Median ohne": float(d.loc[d["y"] == 0, "x"].median())}
    if len(np.unique(yy)) < 2 or yy.sum() < 3:
        return {**aus, "AUC": np.nan, "unten": np.nan, "oben": np.nan, "p": np.nan}
    score = d["x"].to_numpy() * (richtung if richtung != 0 else 1)
    auc, lo, hi = fv.bootstrap_auc(yy, score, gruppen.reindex(d.index).to_numpy())
    rng = np.random.default_rng(seed)
    zufall = np.array([roc_auc_score(rng.permutation(yy), score) for _ in range(n_perm)])
    if richtung == 0:
        p = (np.sum(np.abs(zufall - 0.5) >= abs(auc - 0.5)) + 1) / (n_perm + 1)
    else:
        p = (np.sum(zufall >= auc) + 1) / (n_perm + 1)
    return {**aus, "AUC": auc, "unten": lo, "oben": hi, "p": float(p)}



def effekt_bei_gleichem_start(d: pd.DataFrame, aenderung: str, start: str, gruppe: str,
                              n: int = 4000, seed: int = 0) -> Dict[str, float]:
    """Unterschied der Änderung zwischen Gruppe 1 und 0 bei gleichem Ausgangswert.

    Lineare Regression Änderung = a + b · Ausgangswert + c · Gruppe. Das nimmt die Rückkehr zur Mitte
    heraus: Wer vorher hoch lag, sinkt oft auch ohne Maßnahme. 95-%-Intervall von c durch Ziehen
    ganzer Stationen.
    """
    t = d[[aenderung, start, gruppe]].dropna()
    X = np.column_stack([np.ones(len(t)), t[start].to_numpy(float), t[gruppe].to_numpy(float)])
    y = t[aenderung].to_numpy(float)
    c = float(np.linalg.lstsq(X, y, rcond=None)[0][2])
    rng = np.random.default_rng(seed)
    werte = []
    for _ in range(n):
        i = rng.integers(0, len(t), len(t))
        if 0 < X[i, 2].sum() < len(i):
            werte.append(np.linalg.lstsq(X[i], y[i], rcond=None)[0][2])
    werte = np.asarray(werte)
    return {"Stationen": len(t), "Effekt": c, "unten": float(np.quantile(werte, 0.025)),
            "oben": float(np.quantile(werte, 0.975)), "unter 0 in": float(np.mean(werte < 0))}

def holm(p: Sequence[float]) -> np.ndarray:
    """Holm-Korrektur: angepasste p-Werte in der ursprünglichen Reihenfolge."""
    p = np.asarray(p, dtype=float)
    reihe = np.argsort(p)
    m = len(p)
    angepasst = np.empty(m)
    laufend = 0.0
    for rang, i in enumerate(reihe):
        laufend = max(laufend, min(1.0, (m - rang) * p[i]))
        angepasst[i] = laufend
    return angepasst


def folds_aus_oof(oof: pd.DataFrame, ziel: str) -> Tuple[pd.Series, np.ndarray]:
    """Folds und Labels je Station für ein Ziel aus den Test-C-Vorhersagen (Notebook 35)."""
    o = oof[oof["ziel"] == ziel]
    folds = o.groupby("zaehler")["fold"].first()
    y = o.groupby("zaehler")["y"].first().reindex(folds.index).to_numpy().astype(int)
    return folds, y


def lr_oof(X: pd.DataFrame, oof: pd.DataFrame, gruppen: pd.Series, ziel: str,
           name: str, spalten: Sequence[str]) -> pd.Series:
    """Dieselbe logistische Regression wie Notebook 35 (Raster innen), Werte außerhalb des Folds."""
    from . import finalvergleich as fv
    folds, y = folds_aus_oof(oof, ziel)
    g = gruppen.reindex(folds.index).to_numpy()
    Xs = X.reindex(folds.index)[list(spalten)]
    p = np.full(len(y), np.nan)
    for k in sorted(folds.unique()):
        tr, te = np.flatnonzero(folds.to_numpy() != k), np.flatnonzero(folds.to_numpy() == k)
        suche = fv.innen_suchen(name, Xs.iloc[tr], y[tr], g[tr])
        p[te] = suche.predict_proba(Xs.iloc[te])[:, 1]
    return pd.Series(p, index=folds.index, name=name)



# --- Äußere Faktoren (Abschnitt 8) ------------------------------------------------

def stationstyp_gruppe(typ) -> str:
    """Stationstyp aus dem Protokoll grob zusammengefasst (Schreibweisen vereinheitlicht)."""
    t = str(typ).upper().replace("'", "").replace(" ", "")
    if t in ("", "NAN", "NONE"):
        return "keine Angabe"
    if "COMFORT" in t:
        return "Comfort"
    if "0H" in t:
        return "GIRO 0H"
    if "1H" in t:
        return "GIRO 1H"
    return "GIRO ohne Typ"


def daemmung_und_gebaeude(zaehler_mit_reihe) -> pd.DataFrame:
    """Je begangenem Zähler: Dämmungs-Kästchen (ja, ausdrücklich nein, leer) und Gebäudeangaben.

    Quelle ist das Begehungsprotokoll, verbunden wie in Notebook 25. Die Adresse wird nur zum
    Verbinden gebraucht und nicht zurückgegeben. Je Zähler gilt „ja“, wenn bei einer Begehung das
    Kästchen angekreuzt oder im Freitext ein Dämmungsbefund steht, sonst „nein“, wenn ausdrücklich
    nein eingetragen ist, sonst „leer“.
    """
    from . import befundcodes, inspections, load_begehungen
    from . import load_data as ld
    roh = ld.load_inspections()
    tidy = inspections.tidy_inspections(roh)
    kodiert = befundcodes.kodiere_begehungen(
        load_begehungen.begehungen_mit_zaehler(available=set(int(z) for z in zaehler_mit_reihe)))
    if not (len(tidy) == len(kodiert) and (tidy["address_norm"].values == kodiert["key"].values).all()):
        raise ValueError("Protokoll und Zählerzuordnung haben nicht dieselbe Reihenfolge")
    kaestchen = roh["Leitungen\nneu gedämmt"].astype(str).str.strip().str.lower().to_numpy()
    zeilen = pd.DataFrame({
        "zaehler": kodiert["meter"].astype(int).to_numpy(),
        "kaestchen": np.where(kaestchen == "ja", "ja", np.where(kaestchen == "nein", "nein", "leer")),
        "freitext": kodiert["daemmung"].astype(bool).to_numpy(),
        "anlagenkennziffer": tidy["anlagen_konfig"].astype(str).str.split("->").str[0].str.strip().to_numpy(),
        "stationstyp": [stationstyp_gruppe(t) for t in tidy["station_typ"]],
        "zusatzheizung": tidy["zusatzheizung"].notna().to_numpy(),
        "personen": pd.to_numeric(tidy["personen"], errors="coerce").to_numpy(),
        "wohnflaeche": pd.to_numeric(tidy["wohnflaeche"], errors="coerce").to_numpy(),
        "baujahr": pd.to_numeric(tidy["bj"], errors="coerce").to_numpy(),
    })
    zeilen = zeilen[zeilen["zaehler"].isin(set(int(z) for z in zaehler_mit_reihe))]

    def status(g):
        if (g["kaestchen"] == "ja").any() or g["freitext"].any():
            return "ja"
        return "ausdrücklich nein" if (g["kaestchen"] == "nein").any() else "leer"

    aus = pd.DataFrame({"daemmung_eintrag": zeilen.groupby("zaehler").apply(status)})
    for spalte in ("anlagenkennziffer", "stationstyp", "personen", "wohnflaeche", "baujahr"):
        aus[spalte] = zeilen.groupby("zaehler")[spalte].first()
    aus["zusatzheizung"] = zeilen.groupby("zaehler")["zusatzheizung"].any()
    return aus.rename_axis("zaehler")


def auc_innerhalb(y, score, gruppe) -> Tuple[float, int]:
    """AUC nur aus Paaren innerhalb derselben Gruppe (mit Befund gegen ohne Befund).

    Erklärt die Gruppe den Score, fällt dieser Wert auf 0,5. Rückgabe: AUC und Zahl der Paare.
    """
    d = pd.DataFrame({"y": np.asarray(y, dtype=float), "s": np.asarray(score, dtype=float),
                      "g": np.asarray(gruppe, dtype=object)}).dropna()
    besser, paare = 0.0, 0
    for _, t in d.groupby("g"):
        pos, neg = t.loc[t["y"] == 1, "s"].to_numpy(), t.loc[t["y"] == 0, "s"].to_numpy()
        if len(pos) == 0 or len(neg) == 0:
            continue
        vergleich = pos[:, None] - neg[None, :]
        besser += (vergleich > 0).sum() + 0.5 * (vergleich == 0).sum()
        paare += vergleich.size
    return (besser / paare if paare else np.nan), int(paare)


def gruppen_zufallstest(gruppe, y, n: int = 5000, seed: int = 0) -> float:
    """Unterscheidet sich der Anteil mit Befund zwischen den Gruppen? Zufallstest auf der Chi-Quadrat-Größe.

    Bei wenigen Stationen je Gruppe ist der übliche Chi-Quadrat-Test ungenau, deshalb werden die Labels
    n-mal vertauscht. Rückgabe: Anteil der Durchläufe mit mindestens so großem Unterschied.
    """
    d = pd.DataFrame({"g": np.asarray(gruppe, dtype=object), "y": np.asarray(y, dtype=float)}).dropna()
    g = pd.factorize(d["g"])[0]
    y = d["y"].to_numpy().astype(int)
    n_g = np.bincount(g)
    gesamt = y.mean()
    if gesamt in (0, 1) or len(n_g) < 2:
        return np.nan

    def chi(yy):
        erwartet = n_g * gesamt
        beobachtet = np.bincount(g, weights=yy, minlength=len(n_g))
        return float(np.sum((beobachtet - erwartet) ** 2 / (erwartet * (1 - gesamt))))

    echt = chi(y)
    rng = np.random.default_rng(seed)
    zufall = np.array([chi(rng.permutation(y)) for _ in range(n)])
    return float((np.sum(zufall >= echt - 1e-12) + 1) / (n + 1))

# --- Erklärbarkeit -----------------------------------------------------------------

def shap_linear(pipe, X: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    """SHAP-Werte (Log-Odds) einer Pipeline Imputer → StandardScaler → LogisticRegression.

    Für ein lineares Modell ist SHAP exakt Gewicht · (Wert - Mittelwert im Lernteil).
    Nach dem StandardScaler ist der Mittelwert 0, also Gewicht · standardisierter Wert.
    Summe der Beiträge + Grundwert = Log-Odds der Vorhersage.
    """
    schritte = list(pipe.named_steps.values())
    lr = schritte[-1]
    z = X.to_numpy(dtype=float)
    for schritt in schritte[:-1]:
        z = schritt.transform(z if not hasattr(schritt, "feature_names_in_") else
                              pd.DataFrame(z, columns=X.columns, index=X.index))
    werte = np.asarray(z) * lr.coef_[0]
    return pd.DataFrame(werte, index=X.index, columns=X.columns), float(lr.intercept_[0])


def shap_folds(X: pd.DataFrame, oof: pd.DataFrame, gruppen: pd.Series, ziel: str,
               name: str, spalten: Sequence[str]) -> Dict[str, pd.DataFrame]:
    """SHAP je Teststation aus dem Modell des jeweiligen Folds, dazu die Gewichte je Fold."""
    from . import finalvergleich as fv
    folds, y = folds_aus_oof(oof, ziel)
    g = gruppen.reindex(folds.index).to_numpy()
    Xs = X.reindex(folds.index)[list(spalten)]
    teile, gewichte, p = [], [], pd.Series(np.nan, index=folds.index)
    for k in sorted(folds.unique()):
        tr, te = np.flatnonzero(folds.to_numpy() != k), np.flatnonzero(folds.to_numpy() == k)
        modell = fv.innen_suchen(name, Xs.iloc[tr], y[tr], g[tr]).best_estimator_
        sh, basis = shap_linear(modell, Xs.iloc[te])
        teile.append(sh.assign(fold=k, basiswert=basis))
        gewichte.append(pd.Series(list(modell.named_steps.values())[-1].coef_[0], index=spalten, name=k))
        p.iloc[te] = modell.predict_proba(Xs.iloc[te])[:, 1]
    return {"shap": pd.concat(teile).reindex(folds.index), "gewichte": pd.DataFrame(gewichte),
            "p": p, "y": pd.Series(y, index=folds.index)}
