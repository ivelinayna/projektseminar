"""Tagesmonitor: wetterbereinigte Tageswerte je Station mit CUSUM-Alarm.

Im finalen Modell ist das der einzige Alarm, der Fensteralarm aus NB 14
traf Begehungen kaum besser als Zufall und steht nicht mehr im
Stationsblatt. Die
Idee stammt aus NB 17 (Normalverhaltensmodell) und ist hier so umgebaut,
dass sie auf denselben Daten läuft wie der Rest des finalen Modells, also
auf den Stundenreihen aus NB 00 über ``nb00_daten.lade_serien``.

Je Station und Tag werden Energie und Volumen aus den Zählerständen um
Mitternacht gebildet. Daraus entstehen zwei Kanäle, die Abkühlung in
kWh/m³ und das logarithmierte Tagesvolumen. Im ersten Jahr einer Station
(spätestens 14 Tage vor ihrer ersten Begehung) wird je Kanal gelernt, wie
der Wert von der Tagesmitteltemperatur abhängt. Danach misst ein
zweiseitiger CUSUM, ob die Station über mehrere Heiztage hinweg von ihrer
eigenen Kennlinie wegläuft. Die Streuung wird für die Ähnlichkeit
aufeinanderfolgender Tage vergrößert, sonst alarmiert der CUSUM bei jeder
trägen Station.

Dazu kommen drei Auswertungen für das Notebook: ein Treffertest gegen
Kontrollstationen am selben Datum (für jede Alarmtabelle, also auch für
die Alarme aus NB 14), eine wetterbereinigte Differenz-in-Differenzen um
die Begehungen und die Abkühlung bei 5 °C je Kernwinter als Gegenprobe
zum Netzvergleich. Kein Tag wird gelöscht, jeder Ausschluss steht mit
Grund in der Tagestabelle.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from . import fallsammlung as fs
from . import netzvergleich as nv
from . import weather

#Tageswerte, Schwellen wie NB 06
MAX_ABSTAND_H = 2
AKTIV_FLUSS_LH = 20.0
MIN_STUNDEN = 12
MIN_ENERGIE_KWH = 5.0
MAX_KWH_PRO_M3 = 70.0
STEHT_LEISTUNG_KW = 1.0
MIN_WETTERSTUNDEN = 20
#frühe Jahre liegen teils nur als Tageswert vor, der Zählerstand reicht dann
IGNORIERT: Tuple[str, ...] = ("wenig_stunden",)
GRUENDE: Tuple[str, ...] = (
    "kein_zaehlerstand", "ruecksprung", "zaehler_steht", "nach_stillstand",
    "wenig_energie", "unplausibel", "wenig_stunden", "ohne_wetter")

T_HEIZGRENZE = 15.0
KANAELE: Dict[str, str] = {"kwh_pro_m3": "Abkühlung (kWh/m³)",
                           "log_volumen": "Wassermenge (Tagesvolumen)"}
FORM_JE_KANAL: Dict[str, str] = {"kwh_pro_m3": "gerade",
                                 "log_volumen": "klassen"}
KLASSENBREITE_K = 2.0
MIN_TAGE_JE_KLASSE = 8
PHI_MAX = 0.8

REF_KALENDERTAGE = 365
ABSTAND_BEGEHUNG = 14
MIN_REF_TAGE = 60
MIN_REF_SPANNE_K = 8.0

CUSUM_K = 0.5
CUSUM_H = 5.0
CUSUM_MAX = 10.0

PRUEF_TAGE = 120
MIN_PRUEF_TAGE = 20

FENSTER_VOR = 7
FENSTER_NACH = 60
KONTROLL_VORLAUF = 60
MIN_TAGE_IM_FENSTER = 5
MIN_KONTROLLEN = 5
PRUEFUNGEN: Dict[str, List[str]] = {
    "Abkühlung": ["kwh_pro_m3"], "Wassermenge": ["log_volumen"],
    "einer der beiden": list(KANAELE)}

WIRKUNG_TAGE = 30
WIRKUNG_ABSTAND = 7
WIRKUNG_MAX_TAGE = 365
MIN_WIRKUNG_TAGE = 10
MIN_WILCOXON = 6
#Richtung einer Verbesserung: mehr Abkühlung, weniger Wasser
ERWARTET: Dict[str, int] = {"kwh_pro_m3": 1, "log_volumen": -1}

RHO_C = 1.15
NORM_T_C = 5.0
MIN_NORM_TAGE = 30
MIN_NORM_SPANNE_K = 5.0

TAGES_SPALTEN = ["datum", "n_stunden", "fluss_mittel_lh",
                 "leistung_mittel_kw", "energie_kwh", "volumen_m3",
                 "zaehler_spanne_h", "kwh_pro_m3", "log_volumen"]


def prozent(x):
    """Differenz im Logarithmus als Prozent."""
    return 100.0 * (np.exp(x) - 1.0)


def _ns(werte) -> pd.Series:
    return pd.Series(pd.to_datetime(werte)).astype("datetime64[ns]")


def zaehler_differenz(serie: pd.DataFrame,
                      tage_idx: pd.DatetimeIndex,
                      max_abstand_h: float = MAX_ABSTAND_H) -> pd.DataFrame:
    """Energie und Volumen je Tag aus den Zählerständen um Mitternacht.

    Je Tagesgrenze wird der nächste Zählerstand innerhalb von
    ``max_abstand_h`` Stunden genommen und die Differenz auf 24 Stunden
    hochgerechnet. Liegt kein Stand nahe genug, bleibt der Tag leer.
    """
    leer = pd.DataFrame(index=tage_idx, dtype=float,
                        columns=["energie_kwh", "volumen_m3",
                                 "zaehler_spanne_h"])
    staende = serie.reindex(columns=["energy", "volume"]).dropna()
    if staende.empty or len(tage_idx) == 0:
        return leer
    staende = staende.rename_axis("ts").reset_index()
    staende["ts"] = _ns(staende["ts"]).to_numpy()
    staende = staende.sort_values("ts")
    grenzen = pd.DataFrame({"grenze": _ns(pd.date_range(
        tage_idx.min(), tage_idx.max() + pd.Timedelta(days=1), freq="D"))})
    nah = pd.merge_asof(grenzen, staende, left_on="grenze", right_on="ts",
                        direction="nearest",
                        tolerance=pd.Timedelta(hours=max_abstand_h))
    a = nah.iloc[:-1].reset_index(drop=True)
    b = nah.iloc[1:].reset_index(drop=True)
    spanne = (b["ts"] - a["ts"]).dt.total_seconds() / 3600
    spanne = spanne.where(spanne > 0)
    out = pd.DataFrame({
        "energie_kwh": (b["energy"] - a["energy"]) * 24 / spanne,
        "volumen_m3": (b["volume"] - a["volume"]) * 24 / spanne,
        "zaehler_spanne_h": spanne}).set_index(pd.DatetimeIndex(a["grenze"]))
    return out.reindex(tage_idx)


def tageswerte(serie: pd.DataFrame) -> pd.DataFrame:
    """Eine Zeile je Tag mit gemessenem Durchfluss."""
    serie = serie.reindex(columns=list(dict.fromkeys(
        [*serie.columns, "flow", "power", "energy", "volume"])))
    gem = serie[serie["flow"].notna()]
    if gem.empty:
        return pd.DataFrame(columns=TAGES_SPALTEN)
    tag = pd.DatetimeIndex(gem.index).normalize()
    tage_idx = pd.DatetimeIndex(np.unique(tag.to_numpy()),
                                name="datum").astype("datetime64[ns]")
    g = gem.groupby(tag)
    out = pd.DataFrame({"n_stunden": g.size(),
                        "fluss_mittel_lh": g["flow"].mean(),
                        "leistung_mittel_kw": g["power"].mean()})
    out.index = pd.DatetimeIndex(out.index).astype("datetime64[ns]")
    out = out.reindex(tage_idx).join(zaehler_differenz(serie, tage_idx))
    v = out["volumen_m3"].where(out["volumen_m3"] > 0)
    out["kwh_pro_m3"] = out["energie_kwh"] / v
    out["log_volumen"] = np.log(v)
    out.index.name = "datum"
    return out.reset_index()[TAGES_SPALTEN]


def tagestemperatur(wetter: pd.DataFrame,
                    min_stunden: int = MIN_WETTERSTUNDEN) -> pd.Series:
    """Tagesmittel der Außentemperatur, leer bei zu wenigen Stunden."""
    ts = pd.to_datetime(wetter["timestamp"])
    t = pd.to_numeric(wetter["t_out"], errors="coerce")
    g = t.groupby(ts.dt.normalize().to_numpy())
    mittel = g.mean().where(g.count() >= int(min_stunden))
    mittel.index = pd.DatetimeIndex(mittel.index, name="datum")
    return mittel.rename("t_mittel_c")


def lade_temperatur(start, ende, **kw) -> pd.Series:
    """Tagesmittel aus dem DWD-Cache (Station 2600)."""
    return tagestemperatur(weather.load_outdoor_temperature(start, ende, **kw))


def markiere(tage: pd.DataFrame,
             ignoriert: Sequence[str] = IGNORIERT,
             t_heizgrenze: float = T_HEIZGRENZE) -> pd.DataFrame:
    """Gründe je Tag, ``nutzbar`` und ``heiztag``; keine Zeile fällt weg."""
    d = tage.copy()
    e, v = d["energie_kwh"], d["volumen_m3"]
    if "kwh_pro_m3" not in d.columns:
        d["kwh_pro_m3"] = e / v.where(v > 0)
    gruende = {
        "kein_zaehlerstand": e.isna() | v.isna(),
        "ruecksprung": (e < 0) | (v < 0),
        "zaehler_steht": (((v == 0) & (d["fluss_mittel_lh"] >= AKTIV_FLUSS_LH))
                          | ((e == 0)
                             & (d["leistung_mittel_kw"] >= STEHT_LEISTUNG_KW))),
        "wenig_energie": e < MIN_ENERGIE_KWH,
        "unplausibel": d["kwh_pro_m3"] > MAX_KWH_PRO_M3,
        "wenig_stunden": d["n_stunden"] < MIN_STUNDEN,
        "ohne_wetter": d["t_mittel_c"].isna(),
    }
    #am Tag nach einem stehenden Zähler holt der Zähler meist auf
    steht = d.loc[gruende["zaehler_steht"], ["meter", "datum"]]
    folgetag = pd.MultiIndex.from_arrays(
        [steht["meter"], pd.to_datetime(steht["datum"]) + pd.Timedelta(days=1)])
    gruende["nach_stillstand"] = pd.Series(pd.MultiIndex.from_arrays(
        [d["meter"], pd.to_datetime(d["datum"])]).isin(folgetag), index=d.index)

    teile = pd.DataFrame({n: gruende[n].fillna(False).astype(bool)
                          for n in GRUENDE}, index=d.index)
    d["grund"] = [", ".join(n for n, x in zip(GRUENDE, zeile) if x)
                  for zeile in teile.to_numpy()]
    stoerend = [n for n in GRUENDE if n not in set(ignoriert)]
    d["nutzbar"] = ~teile[stoerend].any(axis=1)
    d["heiztag"] = (d["t_mittel_c"] < t_heizgrenze).fillna(False).astype(bool)
    return d


def ausschlusstabelle(tage: pd.DataFrame,
                      ignoriert: Sequence[str] = IGNORIERT) -> pd.DataFrame:
    """Tage und Stationen je Grund; ein Tag kann mehrere Gründe haben."""
    zeilen = []
    for name in GRUENDE:
        m = tage["grund"].str.split(", ").map(lambda g: name in g)
        zeilen.append({"grund": name, "tage": int(m.sum()),
                       "stationen": int(tage.loc[m, "meter"].nunique()),
                       "ignoriert": name in set(ignoriert)})
    return pd.DataFrame(zeilen)


def alle_tageswerte(serien: Mapping[int, pd.DataFrame],
                    temp: pd.Series) -> pd.DataFrame:
    """Tageswerte aller Zähler mit Temperatur und Markierungen."""
    stuecke = []
    for meter, serie in serien.items():
        t = tageswerte(serie)
        if len(t):
            t.insert(0, "meter", int(meter))
            stuecke.append(t)
    if not stuecke:
        tage = pd.DataFrame(columns=["meter", *TAGES_SPALTEN])
    else:
        tage = pd.concat(stuecke, ignore_index=True)
    temp = temp.copy()
    temp.index = pd.DatetimeIndex(temp.index).astype("datetime64[ns]")
    tage["datum"] = _ns(tage["datum"]).to_numpy()
    tage["t_mittel_c"] = tage["datum"].map(temp)
    return markiere(tage)


def modelltage(tage: pd.DataFrame) -> pd.DataFrame:
    """Nutzbare Heiztage mit beiden Kanälen und Temperatur."""
    m = (tage["nutzbar"] & tage["heiztag"] & (tage["volumen_m3"] > 0)
         & np.isfinite(tage["kwh_pro_m3"].astype(float))
         & np.isfinite(tage["t_mittel_c"].astype(float)))
    spalten = ["meter", "datum", "t_mittel_c", *KANAELE]
    return tage.loc[m, spalten].sort_values(["meter", "datum"]).reset_index(drop=True)


def referenz(mt: pd.DataFrame,
             termine: Mapping[int, Sequence],
             ref_kalendertage: int = REF_KALENDERTAGE,
             abstand_begehung: int = ABSTAND_BEGEHUNG,
             min_ref_tage: int = MIN_REF_TAGE,
             min_spanne_k: float = MIN_REF_SPANNE_K) -> pd.DataFrame:
    """Referenzzeitraum und Status je Station.

    Die Referenz beginnt am ersten nutzbaren Heiztag und dauert ein Jahr.
    Liegt vorher eine Begehung, endet sie ``abstand_begehung`` Tage davor.
    """
    zeilen = []
    for meter, d in mt.groupby("meter"):
        start = d["datum"].min()
        ende = start + pd.Timedelta(days=ref_kalendertage)
        grund = "ein Jahr"
        spaeter = sorted(pd.Timestamp(t) for t in termine.get(int(meter), [])
                         if pd.Timestamp(t) > start)
        if spaeter and spaeter[0] - pd.Timedelta(days=abstand_begehung) < ende:
            ende = spaeter[0] - pd.Timedelta(days=abstand_begehung)
            grund = "vor Begehung"
        ref = d[(d["datum"] >= start) & (d["datum"] < ende)]
        spanne = float(ref["t_mittel_c"].max() - ref["t_mittel_c"].min()) \
            if len(ref) else 0.0
        nachher = int((d["datum"] >= ende).sum())
        if len(ref) < min_ref_tage:
            status = "zu wenige Referenztage"
        elif spanne < min_spanne_k:
            status = "zu kleine Temperaturspanne"
        elif nachher == 0:
            status = "keine Tage nach der Referenz"
        else:
            status = "ok"
        zeilen.append({"meter": int(meter), "ref_start": start,
                       "ref_ende": ende, "ende_grund": grund,
                       "ref_tage": len(ref), "ref_spanne_k": spanne,
                       "ueberwachte_tage": nachher, "status": status,
                       "bhkw": int(meter) in nv.REFERENZ_AUSSCHLUSS})
    spalten = ["meter", "ref_start", "ref_ende", "ende_grund", "ref_tage",
               "ref_spanne_k", "ueberwachte_tage", "status", "bhkw"]
    return pd.DataFrame(zeilen, columns=spalten).set_index("meter")


def lerne_kennlinie(form: str, t, y) -> dict:
    """Kennlinie Temperatur -> erwarteter Wert.

    ``gerade`` ist eine Theil-Sen-Gerade, ``klassen`` der Median je
    2-K-Klasse an der mittleren Temperatur der Klasse. Hat die Referenz
    weniger als zwei brauchbare Klassen, wird die Gerade genommen.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if form == "klassen":
        tab = (pd.DataFrame({"klasse": np.floor(t / KLASSENBREITE_K),
                             "t": t, "y": y})
               .groupby("klasse")
               .agg(n=("y", "size"), t=("t", "median"), y=("y", "median")))
        tab = tab[tab["n"] >= MIN_TAGE_JE_KLASSE]
        if len(tab) >= 2:
            return {"form": "klassen", "stuetz_t": tab["t"].to_numpy(),
                    "stuetz_y": tab["y"].to_numpy()}
    b, a, _, _ = stats.theilslopes(y, t)
    return {"form": "gerade", "a": float(a), "b": float(b)}


def kennlinienwert(kennlinie: dict, t):
    """Erwarteter Wert bei Tagesmitteltemperatur ``t``."""
    t = np.asarray(t, dtype=float)
    if kennlinie["form"] == "gerade":
        return kennlinie["a"] + kennlinie["b"] * t
    return np.interp(t, kennlinie["stuetz_t"], kennlinie["stuetz_y"])


def robuste_streuung(r) -> float:
    """1,4826 * MAD, bei Normalverteilung gleich der Standardabweichung."""
    r = np.asarray(r, dtype=float)
    return float(1.4826 * np.median(np.abs(r - np.median(r))))


def autokorrelation(rest) -> float:
    """Korrelation der Residuen zweier aufeinanderfolgender Heiztage."""
    rest = np.asarray(rest, dtype=float)
    if len(rest) < 3 or np.std(rest) == 0:
        return 0.0
    return float(np.corrcoef(rest[:-1], rest[1:])[0, 1])


def _referenztage(mt: pd.DataFrame, ref: pd.DataFrame, meter: int) -> pd.DataFrame:
    d = mt[mt["meter"] == meter]
    return d[(d["datum"] >= ref.at[meter, "ref_start"])
             & (d["datum"] < ref.at[meter, "ref_ende"])]


def stationen_ok(ref: pd.DataFrame) -> List[int]:
    return [int(m) for m in ref.index[ref["status"] == "ok"]]


def modelle(mt: pd.DataFrame, ref: pd.DataFrame,
            phi_max: float = PHI_MAX) -> Tuple[dict, pd.DataFrame]:
    """Kennlinie und Streuung je überwachter Station und Kanal."""
    mod, zeilen = {}, []
    for meter in stationen_ok(ref):
        r = _referenztage(mt, ref, meter)
        t = r["t_mittel_c"].to_numpy(dtype=float)
        for kanal in KANAELE:
            y = r[kanal].to_numpy(dtype=float)
            k = lerne_kennlinie(FORM_JE_KANAL[kanal], t, y)
            rest = y - kennlinienwert(k, t)
            s = max(robuste_streuung(rest), 1e-6)
            phi = autokorrelation(rest)
            phi_k = min(max(phi, 0.0), phi_max)
            faktor = float(np.sqrt((1 + phi_k) / (1 - phi_k)))
            mod[(meter, kanal)] = {"kennlinie": k, "s": s, "s_eff": s * faktor}
            zeilen.append({"meter": meter, "kanal": kanal, "form": k["form"],
                           "a": k.get("a", np.nan), "b": k.get("b", np.nan),
                           "s": s, "phi": phi, "faktor": faktor,
                           "s_eff": s * faktor, "ref_tage": len(r)})
    return mod, pd.DataFrame(zeilen)


def cusum(z, k: float = CUSUM_K, h: float = CUSUM_H,
          deckel: float = CUSUM_MAX):
    """Zweiseitiger CUSUM (Page 1954) über eine Folge von z-Werten.

    Ein Alarm entsteht, wenn ein Konto ``h`` überschreitet; ein weiterer in
    dieselbe Richtung erst, wenn das Konto zwischendurch bei null war.
    Rückgabe S+, S- je Tag und Alarme als (Index, Richtung, Startindex),
    der Startindex schätzt den Beginn der Veränderung.
    """
    z = np.asarray(z, dtype=float)
    s_plus, s_minus = np.zeros(len(z)), np.zeros(len(z))
    sp = sm = 0.0
    an_plus = an_minus = False
    start_plus = start_minus = 0
    alarme = []
    for i, zi in enumerate(z):
        if sp == 0.0:
            start_plus = i
        if sm == 0.0:
            start_minus = i
        sp = min(max(0.0, sp + zi - k), deckel)
        sm = min(max(0.0, sm - zi - k), deckel)
        if sp == 0.0:
            an_plus = False
        if sm == 0.0:
            an_minus = False
        if sp > h and not an_plus:
            alarme.append((i, 1, start_plus))
            an_plus = True
        if sm > h and not an_minus:
            alarme.append((i, -1, start_minus))
            an_minus = True
        s_plus[i], s_minus[i] = sp, sm
    return s_plus, s_minus, alarme


VERLAUF_SPALTEN = ["meter", "kanal", "datum", "t_mittel_c", "wert",
                   "erwartung", "residuum", "z", "s_plus", "s_minus"]
ALARM_SPALTEN = ["meter", "kanal", "datum", "richtung", "beginn"]


def monitor(mt: pd.DataFrame, ref: pd.DataFrame,
            mod: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Residuen, z-Werte und CUSUM je Heiztag nach der Referenz."""
    stuecke, alarme = [], []
    for meter in stationen_ok(ref):
        d = mt[(mt["meter"] == meter)
               & (mt["datum"] >= ref.at[meter, "ref_ende"])].sort_values("datum")
        if d.empty:
            continue
        t = d["t_mittel_c"].to_numpy(dtype=float)
        datum = d["datum"].to_numpy()
        for kanal in KANAELE:
            m = mod[(meter, kanal)]
            wert = d[kanal].to_numpy(dtype=float)
            erw = kennlinienwert(m["kennlinie"], t)
            res = wert - erw
            z = res / m["s_eff"]
            sp, sm, al = cusum(z)
            stuecke.append(pd.DataFrame({
                "meter": meter, "kanal": kanal, "datum": datum,
                "t_mittel_c": t, "wert": wert, "erwartung": erw,
                "residuum": res, "z": z, "s_plus": sp, "s_minus": sm}))
            for i, richtung, start in al:
                alarme.append({"meter": meter, "kanal": kanal,
                               "datum": pd.Timestamp(datum[i]),
                               "richtung": int(richtung),
                               "beginn": pd.Timestamp(datum[start])})
    verlauf = (pd.concat(stuecke, ignore_index=True) if stuecke
               else pd.DataFrame(columns=VERLAUF_SPALTEN))
    return verlauf, pd.DataFrame(alarme, columns=ALARM_SPALTEN)


def guete(mt: pd.DataFrame, ref: pd.DataFrame, mod: dict,
          termine: Mapping[int, Sequence],
          pruef_tage: int = PRUEF_TAGE,
          min_pruef_tage: int = MIN_PRUEF_TAGE) -> pd.DataFrame:
    """Vorhersagegüte auf ungesehenen Heiztagen direkt nach der Referenz.

    Skill ist 1 - Fehler(Kennlinie) / Fehler(Referenzmedian); positiv
    heißt, die Temperatur hilft. Geprüft wird nur vor der nächsten
    Begehung.
    """
    zeilen = []
    for meter in stationen_ok(ref):
        d = mt[mt["meter"] == meter]
        ende = ref.at[meter, "ref_ende"]
        pruef = d[d["datum"] >= ende]
        spaeter = sorted(pd.Timestamp(t) for t in termine.get(meter, [])
                         if pd.Timestamp(t) >= ende)
        if spaeter:
            pruef = pruef[pruef["datum"]
                          < spaeter[0] - pd.Timedelta(days=FENSTER_VOR)]
        pruef = pruef.head(pruef_tage)
        if len(pruef) < min_pruef_tage:
            continue
        r = _referenztage(mt, ref, meter)
        for kanal in KANAELE:
            y = pruef[kanal].to_numpy(dtype=float)
            f_mod = float(np.mean(np.abs(
                y - kennlinienwert(mod[(meter, kanal)]["kennlinie"],
                                   pruef["t_mittel_c"]))))
            f_naiv = float(np.mean(np.abs(y - r[kanal].median())))
            zeilen.append({"meter": meter, "kanal": kanal, "tage": len(pruef),
                           "fehler_modell": f_mod, "fehler_naiv": f_naiv,
                           "skill": 1 - f_mod / f_naiv if f_naiv > 0 else np.nan})
    return pd.DataFrame(zeilen, columns=["meter", "kanal", "tage",
                                         "fehler_modell", "fehler_naiv",
                                         "skill"])


def beobachtete_tage(verlauf: pd.DataFrame,
                     kanal: str = "kwh_pro_m3") -> Dict[int, pd.DatetimeIndex]:
    """Überwachte Heiztage je Station, Grundlage für ``treffertest``."""
    v = verlauf[verlauf["kanal"] == kanal]
    return {int(m): pd.DatetimeIndex(g["datum"]) for m, g in v.groupby("meter")}


def faelle(kodiert: pd.DataFrame,
           kategorien: Sequence[str] = tuple(fs.MECHANISCH)) -> pd.DataFrame:
    """Eine Zeile je Zähler und Begehungstermin mit Flag ``mechanisch``.

    ``kodiert`` ist die Ausgabe von ``befundcodes.kodiere_begehungen``.
    Mechanisch heißt: der Freitext nennt einen Befund an Schmutzfänger,
    Ventil, Pumpe, Zirkulation oder Volumenstrom (wie NB 15/16).
    """
    k = kodiert.dropna(subset=["meter", "datum"]).copy()
    k["meter"] = k["meter"].astype(int)
    k["datum"] = pd.to_datetime(k["datum"]).dt.normalize()
    vorhanden = [c for c in kategorien if c in k.columns]
    k["mechanisch"] = (k[vorhanden].fillna(False).astype(bool).any(axis=1)
                       if vorhanden else False)
    if "kategorie" not in k.columns:
        k["kategorie"] = np.nan
    return (k.groupby(["meter", "datum"])
            .agg(kategorie=("kategorie", "first"),
                 mechanisch=("mechanisch", "any"))
            .reset_index())


def _begehung_zwischen(termine: Mapping[int, Sequence], meter: int,
                       von, bis) -> bool:
    return any(von <= pd.Timestamp(t) <= bis for t in termine.get(meter, []))


def treffertest(faelle: pd.DataFrame, alarme: pd.DataFrame,
                beobachtet: Mapping[int, pd.DatetimeIndex],
                termine: Mapping[int, Sequence],
                pruefungen: Mapping[str, Sequence[str]] = PRUEFUNGEN,
                fenster_vor: int = FENSTER_VOR,
                fenster_nach: int = FENSTER_NACH,
                kontroll_vorlauf: int = KONTROLL_VORLAUF,
                min_tage: int = MIN_TAGE_IM_FENSTER,
                min_kontrollen: int = MIN_KONTROLLEN) -> pd.DataFrame:
    """Alarm im Fenster um die Begehung gegen Kontrollstationen am selben Datum.

    Eine Station zählt nur, wenn sie im Fenster mindestens ``min_tage``
    beobachtete Tage hat. Kontrollen sind beobachtbare Stationen ohne
    eigene Begehung von ``kontroll_vorlauf`` Tagen vor dem Fenster bis zu
    seinem Ende. ``alarme`` braucht die Spalten meter, kanal, datum; so
    lassen sich Alarme aus beliebigen Monitoren gleich prüfen.
    """
    al = alarme.copy()
    al["datum"] = pd.to_datetime(al["datum"])
    je = {(int(m), k): pd.DatetimeIndex(g["datum"])
          for (m, k), g in al.groupby(["meter", "kanal"])}
    stationen = sorted(beobachtet)

    def alarm(meter, kanaele, von, bis):
        for kanal in kanaele:
            s = je.get((meter, kanal))
            if s is not None and ((s >= von) & (s <= bis)).any():
                return True
        return False

    def beob(meter, von, bis):
        s = beobachtet.get(meter)
        return s is not None and int(((s >= von) & (s <= bis)).sum()) >= min_tage

    zeilen = []
    for f in faelle.itertuples(index=False):
        meter, datum = int(f.meter), pd.Timestamp(f.datum)
        von = datum - pd.Timedelta(days=fenster_vor)
        bis = datum + pd.Timedelta(days=fenster_nach)
        if not beob(meter, von, bis):
            continue
        kontrollen = [z for z in stationen
                      if z != meter and beob(z, von, bis)
                      and not _begehung_zwischen(
                          termine, z, von - pd.Timedelta(days=kontroll_vorlauf),
                          bis)]
        if len(kontrollen) < min_kontrollen:
            continue
        for name, kanaele in pruefungen.items():
            zeilen.append({
                "meter": meter, "datum": datum,
                "mechanisch": bool(getattr(f, "mechanisch", False)),
                "kategorie": getattr(f, "kategorie", np.nan),
                "pruefung": name,
                "treffer": alarm(meter, kanaele, von, bis),
                "kontrollquote": float(np.mean(
                    [alarm(z, kanaele, von, bis) for z in kontrollen])),
                "n_kontrolle": len(kontrollen)})
    return pd.DataFrame(zeilen, columns=[
        "meter", "datum", "mechanisch", "kategorie", "pruefung", "treffer",
        "kontrollquote", "n_kontrolle"])


def bilanz(t: pd.DataFrame, gruppen: Sequence[str]) -> pd.DataFrame:
    """Trefferquote gegen Kontrollquote je Gruppe, einseitiger Binomialtest."""
    zeilen = []
    for schluessel, g in t.groupby(list(gruppen), sort=False):
        n, k = len(g), int(g["treffer"].sum())
        p0 = float(g["kontrollquote"].mean())
        p = (stats.binomtest(k, n, p0, alternative="greater").pvalue
             if 0 < p0 < 1 else np.nan)
        schluessel = schluessel if isinstance(schluessel, tuple) else (schluessel,)
        zeilen.append({**dict(zip(gruppen, schluessel)), "Faelle": n,
                       "Treffer": k, "Quote": k / n, "Kontrollquote": p0,
                       "Hebel": (k / n) / p0 if p0 > 0 else np.nan,
                       "p (einseitig)": p})
    return pd.DataFrame(zeilen)


def _vorher_nachher(v: pd.DataFrame, datum: pd.Timestamp,
                    tage: int, abstand: int, max_tage: int, min_tage: int):
    a = pd.Timedelta(days=abstand)
    w = pd.Timedelta(days=max_tage)
    vor = v[(v["datum"] < datum - a) & (v["datum"] >= datum - w)].tail(tage)
    nach = v[(v["datum"] > datum + a) & (v["datum"] <= datum + w)].head(tage)
    if len(vor) < min_tage or len(nach) < min_tage:
        return None
    return (float(nach["residuum"].median() - vor["residuum"].median()),
            vor["datum"].min(), nach["datum"].max())


def wirkung(verlauf: pd.DataFrame, faelle: pd.DataFrame,
            termine: Mapping[int, Sequence],
            tage: int = WIRKUNG_TAGE, abstand: int = WIRKUNG_ABSTAND,
            max_tage: int = WIRKUNG_MAX_TAGE, min_tage: int = MIN_WIRKUNG_TAGE,
            min_kontrollen: int = MIN_KONTROLLEN) -> pd.DataFrame:
    """Wetterbereinigte Differenz-in-Differenzen je Begehung und Kanal.

    Delta ist der Median der Residuen der ersten ``tage`` Heiztage nach
    der Begehung minus der letzten ``tage`` davor, mit ``abstand`` Tagen
    Luft um den Termin. Davon wird der Median der Deltas aller Stationen
    abgezogen, die im verwendeten Zeitraum keine Begehung hatten.
    """
    v = verlauf.copy()
    v["datum"] = pd.to_datetime(v["datum"])
    je = {(int(m), k): g.sort_values("datum")
          for (m, k), g in v.groupby(["meter", "kanal"])}
    stationen = sorted({m for m, _ in je})
    cache: Dict[tuple, Dict[int, float]] = {}
    pad = pd.Timedelta(days=abstand)

    def kontrolle(kanal, datum):
        if (kanal, datum) not in cache:
            werte = {}
            for z in stationen:
                if (z, kanal) not in je:
                    continue
                r = _vorher_nachher(je[(z, kanal)], datum, tage, abstand,
                                    max_tage, min_tage)
                if r is None or _begehung_zwischen(termine, z, r[1] - pad,
                                                   r[2] + pad):
                    continue
                werte[z] = r[0]
            cache[(kanal, datum)] = werte
        return cache[(kanal, datum)]

    zeilen = []
    for f in faelle.itertuples(index=False):
        meter, datum = int(f.meter), pd.Timestamp(f.datum)
        for kanal in KANAELE:
            if (meter, kanal) not in je:
                continue
            eigen = _vorher_nachher(je[(meter, kanal)], datum, tage, abstand,
                                    max_tage, min_tage)
            if eigen is None:
                continue
            k = [d for z, d in kontrolle(kanal, datum).items() if z != meter]
            if len(k) < min_kontrollen:
                continue
            zeilen.append({"meter": meter, "datum": datum,
                           "kategorie": getattr(f, "kategorie", np.nan),
                           "mechanisch": bool(getattr(f, "mechanisch", False)),
                           "kanal": kanal, "delta": eigen[0],
                           "delta_kontrolle": float(np.median(k)),
                           "n_kontrolle": len(k)})
    out = pd.DataFrame(zeilen, columns=[
        "meter", "datum", "kategorie", "mechanisch", "kanal", "delta",
        "delta_kontrolle", "n_kontrolle"])
    out["did"] = out["delta"] - out["delta_kontrolle"]
    return out


def wirkung_bilanz(w: pd.DataFrame,
                   gruppen: Sequence[str] = ("kanal",)) -> pd.DataFrame:
    """Median-DiD je Gruppe mit Wilcoxon-Test, Wassermenge in Prozent."""
    zeilen = []
    for schluessel, g in w.groupby(list(gruppen), sort=False):
        schluessel = schluessel if isinstance(schluessel, tuple) else (schluessel,)
        kanal = dict(zip(gruppen, schluessel)).get("kanal", g["kanal"].iloc[0])
        einheit = prozent if kanal == "log_volumen" else (lambda x: x)
        p = (float(stats.wilcoxon(g["did"]).pvalue)
             if len(g) >= MIN_WILCOXON else np.nan)
        richtung = ERWARTET.get(kanal, 1)
        zeilen.append({**dict(zip(gruppen, schluessel)), "Faelle": len(g),
                       "Median Δ begangen": einheit(g["delta"].median()),
                       "Median Δ Kontrolle": einheit(g["delta_kontrolle"].median()),
                       "Median DiD": einheit(g["did"].median()),
                       "Anteil in erwarteter Richtung": float(
                           (np.sign(g["did"]) == richtung).mean()),
                       "p (Wilcoxon)": p,
                       "Einheit": "%" if kanal == "log_volumen" else "kWh/m³"})
    return pd.DataFrame(zeilen)


NORM_SPALTEN = ["meter", "winter", "n_tage", "spanne_k", "steigung",
                "norm_kwh_m3", "bhkw", "n_stationen", "netz_median",
                "abstand_k", "z", "rang"]


def norm_winter(mt: pd.DataFrame, t_norm: float = NORM_T_C,
                min_tage: int = MIN_NORM_TAGE,
                min_spanne_k: float = MIN_NORM_SPANNE_K,
                ausschluss: Sequence[int] = nv.REFERENZ_AUSSCHLUSS,
                min_stationen: int = nv.MIN_STATIONEN_WINTER) -> pd.DataFrame:
    """Abkühlung bei ``t_norm`` je Station und Kernwinter gegen das Netz.

    Je Station und Winter (Dez. bis Feb.) eine Theil-Sen-Gerade kWh/m³
    über der Tagesmitteltemperatur, ausgewertet bei ``t_norm``. Der
    Abstand zum Netzmedian desselben Winters steht in Kelvin Spreizung,
    positiv heißt schlechter als das Netz. Das BHKW bekommt einen Wert,
    bestimmt den Median aber nicht mit. Gegenprobe, kein Teil des Scores.
    """
    d = mt.copy()
    d["winter"] = nv.heizperiode(d["datum"])
    d = d[d["winter"] != ""]
    aus = {int(m) for m in ausschluss}
    zeilen = []
    for (meter, winter), g in d.groupby(["meter", "winter"]):
        t = g["t_mittel_c"].to_numpy(dtype=float)
        y = g["kwh_pro_m3"].to_numpy(dtype=float)
        spanne = float(t.max() - t.min()) if len(t) else 0.0
        norm = steigung = np.nan
        if len(g) >= min_tage and spanne >= min_spanne_k:
            b, a, _, _ = stats.theilslopes(y, t)
            steigung, norm = float(b), float(a + b * t_norm)
        zeilen.append({"meter": int(meter), "winter": winter,
                       "n_tage": len(g), "spanne_k": spanne,
                       "steigung": steigung, "norm_kwh_m3": norm,
                       "bhkw": int(meter) in aus})
    out = pd.DataFrame(zeilen, columns=NORM_SPALTEN[:7])
    for spalte in NORM_SPALTEN[7:]:
        out[spalte] = np.nan
    for winter, g in out.groupby("winter"):
        ref = g.loc[~g["bhkw"] & g["norm_kwh_m3"].notna(), "norm_kwh_m3"]
        out.loc[g.index, "n_stationen"] = len(ref)
        if len(ref) < min_stationen:
            continue
        med = float(ref.median())
        out.loc[g.index, "netz_median"] = med
        out.loc[g.index, "abstand_k"] = (med - g["norm_kwh_m3"]) / RHO_C
        out.loc[g.index, "z"] = nv.robust_z(g["norm_kwh_m3"], ref, -1)
        bewertet = g[~g["bhkw"] & g["norm_kwh_m3"].notna()]
        out.loc[bewertet.index, "rang"] = (
            (med - bewertet["norm_kwh_m3"]).rank(ascending=False, method="min"))
    out["n_stationen"] = out["n_stationen"].astype(int)
    return out.sort_values(["winter", "meter"]).reset_index(drop=True)


def norm_aktuell(norm: pd.DataFrame) -> pd.DataFrame:
    """Je Station der jüngste Winter mit Netzabstand."""
    n = norm[norm["abstand_k"].notna()].copy()
    if n.empty:
        return n
    n["_ende"] = n["winter"].map(nv.winter_ende_jahr)
    n = n.sort_values(["meter", "_ende"]).groupby("meter").tail(1)
    return n.drop(columns="_ende").set_index("meter")


KEINE_HEIZTAGE = "keine nutzbaren Heiztage"


def stationsstand(meter: int, ref: pd.DataFrame,
                  alarme: pd.DataFrame) -> dict:
    """Kurzstand des Tagesmonitors für Statustabelle und Stationsblatt."""
    meter = int(meter)
    out = {"tm_status": KEINE_HEIZTAGE, "tm_alarme": 0,
           "tm_letzter_alarm": pd.NaT, "tm_letzter_kanal": "",
           "tm_letzte_richtung": np.nan}
    if meter not in ref.index:
        return out
    out["tm_status"] = str(ref.at[meter, "status"])
    a = alarme[alarme["meter"] == meter]
    if len(a):
        letzter = a.sort_values("datum").iloc[-1]
        out.update({"tm_alarme": int(len(a)),
                    "tm_letzter_alarm": pd.Timestamp(letzter["datum"]),
                    "tm_letzter_kanal": str(letzter["kanal"]),
                    "tm_letzte_richtung": int(letzter["richtung"])})
    return out


def rechne(serien: Mapping[int, pd.DataFrame],
           termine: Mapping[int, Sequence],
           temp: Optional[pd.Series] = None,
           min_stationen: int = nv.MIN_STATIONEN_WINTER) -> dict:
    """Ganze Kette von den NB-00-Stundenreihen bis zu Alarmen und Norm-5-°C."""
    if temp is None:
        starts = [s.index.min() for s in serien.values() if len(s)]
        enden = [s.index.max() for s in serien.values() if len(s)]
        temp = lade_temperatur(min(starts).normalize(),
                               max(enden).normalize() + pd.Timedelta(hours=23))
    tage = alle_tageswerte(serien, temp)
    mt = modelltage(tage)
    ref = referenz(mt, termine)
    mod, modtab = modelle(mt, ref)
    verlauf, alarme = monitor(mt, ref, mod)
    return {"tage": tage, "ausschluss": ausschlusstabelle(tage),
            "modelltage": mt, "referenz": ref, "modelle": mod,
            "modelltabelle": modtab, "verlauf": verlauf, "alarme": alarme,
            "norm": norm_winter(mt, min_stationen=min_stationen)}
