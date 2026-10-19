"""Netzvergleich des winterlichen Normalbetriebs.

Der Kennlinien-Monitor misst jede HAST an ihrer eigenen Geschichte. Eine
Station, die seit Jahren schlecht läuft, ist für ihn unauffällig. Dieses
Modul stellt den Normalbetrieb jeder Station im Kernwinter (Dez. bis
Feb.) neben den der übrigen Stationen desselben Winters.

Je Station und Winter werden fünf größenunabhängige Kennzahlen gerechnet,
robust gegen den Netzmedian standardisiert (positiv heißt schlechter) und
zu einem Score gemittelt. Auffällig ist eine Station, wenn mindestens
zwei Kennzahlen im schlechtesten Dezil des Winters liegen; chronisch,
wenn das in mindestens zwei Wintern zutrifft.

Die Stunden um Begehungen fallen heraus, damit der Normalbetrieb nicht
durch den Eingriff selbst verzerrt wird. Alle Schwellen sind Parameter,
weil sie Teamentscheidungen sind und kein Datenbefund.
"""
from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from . import clustervalidierung as cvl
from . import stationsbilder as sb
from . import ternaer as tn
from . import weather

WINTER_MONATE = (12, 1, 2)
MIN_STUNDEN_WINTER = 300
MIN_STATIONEN_WINTER = 20
MIN_KLASSE = 8
RL_SCHWELLE_C = 50.0
DEZIL = 0.10
MIN_KENNZAHLEN_AUFFAELLIG = 2
MIN_WINTER_CHRONISCH = 2
REFERENZ_AUSSCHLUSS: Tuple[int, ...] = (86792512,)
REDUNDANZ_RHO = 0.9
BESTWERT_ANTEIL = 0.25
#Potenzial in Vielfachen der Lücke typische Station -> bestes Viertel, Vorschlag, Team entscheidet
POTENZIAL_GRENZEN: Tuple[float, float] = (1.0, 2.0)

#Vorzeichen: +1 heißt größer ist schlechter
KENNZAHLEN: Dict[str, int] = {
    "spreizung_ref_k": -1,
    "steigung": -1,
    "residuum_sd": 1,
    "rl_ueber_50_anteil": 1,
    "flow_spez_lh_kw": 1,
}
BESCHREIBEND: Tuple[str, ...] = ("r2", "flow_median_lh")
#Felder, die kennzahlen_punkte neben dem Status liefert
PUNKT_SPALTEN: Tuple[str, ...] = (
    "n_stunden", "p_ref_kw", "achsenabschnitt", "steigung", "r2",
    "residuum_sd", "spreizung_ref_k", "rl_ueber_50_anteil", "flow_median_lh",
    "flow_spez_lh_kw")


def heizperiode(zeit) -> np.ndarray:
    """Winterlabel wie ``"23/24"`` für Dez. bis Feb., sonst ``""`` (auch NaT)."""
    z = pd.DatetimeIndex(pd.to_datetime(zeit))
    monat = z.month.fillna(0).astype(int).to_numpy()
    jahr = z.year.fillna(0).astype(int).to_numpy()
    ende = np.where(monat == 12, jahr + 1, jahr)
    namen = {e: f"{(e - 1) % 100:02d}/{e % 100:02d}" for e in np.unique(ende)}
    lab = pd.Series(ende).map(namen).to_numpy(dtype=object)
    return np.where(np.isin(monat, WINTER_MONATE), lab, "")


def winter_ende_jahr(label: str) -> int:
    """Kalenderjahr, in dem der Winter endet (``"23/24"`` -> 2024)."""
    return 2000 + int(str(label)[-2:])


def betriebsstunden(tab: pd.DataFrame) -> pd.DataFrame:
    """Nur Stunden mit Leistung, Durchfluss und Spreizung über null."""
    m = (tab["power_kw"] > 0) & (tab["flow_lh"] > 0) & (tab["dt_k"] > 0)
    return tab[m.fillna(False)]


def kennzahlen_punkte(tab: pd.DataFrame,
                      anschlusswert_kw: Optional[float] = None,
                      min_stunden: int = MIN_STUNDEN_WINTER,
                      rl_schwelle: float = RL_SCHWELLE_C) -> dict:
    """Kennzahlen des Normalbetriebs aus einer Menge von Stundenpunkten.

    Wird für ganze Winter (Netzvergleich) und für Teilwinter vor und nach
    einer Begehung (Wintervergleich) gleich gerechnet. ``spreizung_ref_k``
    ist die Spreizung, die die Kennlinie bei der Medianleistung der
    Punkte vorhersagt. Sie hängt damit nicht davon ab, wie viel Volllast
    der Winter hatte.
    """
    teil = betriebsstunden(tab)
    n = int(len(teil))
    out = {"status": "ok", **{s: np.nan for s in PUNKT_SPALTEN},
           "n_stunden": n}
    if n < int(min_stunden):
        out["status"] = "zu_wenig_stunden"
        return out
    fit = sb.kennlinienfit(teil, min_punkte=min_stunden)
    if not np.isfinite(fit["steigung"]):
        out["status"] = "kein_fit"
        return out

    p_ref = float(teil["power_kw"].median())
    flow_ref = float(np.exp(fit["achsenabschnitt"]
                            + fit["steigung"] * np.log(p_ref)))
    flow_med = float(teil["flow_lh"].median())
    out.update({"p_ref_kw": p_ref,
                "achsenabschnitt": fit["achsenabschnitt"],
                "steigung": fit["steigung"], "r2": fit["r2"],
                "residuum_sd": fit["residuum_sd"],
                "spreizung_ref_k": p_ref * 1000.0 / (tn.KWH_PRO_M3_K * flow_ref),
                "flow_median_lh": flow_med})
    if "rt_c" in teil.columns:
        rt = pd.to_numeric(teil["rt_c"], errors="coerce").to_numpy(dtype=float)
        rt = rt[np.isfinite(rt)]
        if len(rt):
            out["rl_ueber_50_anteil"] = float(np.mean(rt > rl_schwelle))
    try:
        aw = float(anschlusswert_kw)
    except (TypeError, ValueError):
        aw = np.nan
    if np.isfinite(aw) and aw > 0:
        out["flow_spez_lh_kw"] = flow_med / aw
    return out


def int_schluessel(d: Optional[Mapping]) -> dict:
    """Zählernummern als int, weil die Begehungsquellen teils Strings liefern."""
    if not d:
        return {}
    return {int(k): v for k, v in d.items()}


def begehungsmaske(zeit, daten: Iterable, puffer_tage: int = tn.PUFFER_TAGE
                   ) -> np.ndarray:
    """True für Stunden innerhalb von ±puffer_tage Kalendertagen um einen Termin."""
    z = pd.DatetimeIndex(pd.to_datetime(zeit))
    maske = np.zeros(len(z), dtype=bool)
    for d in daten or []:
        d = pd.Timestamp(d).normalize()
        lo = d - pd.Timedelta(days=puffer_tage)
        hi = d + pd.Timedelta(days=puffer_tage + 1)
        maske |= np.asarray((z >= lo) & (z < hi))
    return maske


def winterkennzahlen(punkte: Mapping[int, pd.DataFrame],
                     anschlusswerte: Optional[Mapping] = None,
                     begehungen: Optional[Mapping] = None,
                     min_stunden: int = MIN_STUNDEN_WINTER,
                     puffer_tage: int = tn.PUFFER_TAGE,
                     ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Kennzahlen je Station und Kernwinter plus Ausschlusstabelle.

    ``punkte`` ist ``meter -> sb.punkttabelle(df, meter, "stunde")``.
    Stunden im Puffer um eine Begehung fallen vorher heraus. Jede Station
    oder jeder Winter, der keine Zeile bekommt, steht mit Grund in der
    Ausschlusstabelle.
    """
    aw = int_schluessel(anschlusswerte)
    beg = int_schluessel(begehungen)
    zeilen, aus = [], []
    for meter, tab in punkte.items():
        meter = int(meter)
        if tab is None or len(tab) == 0:
            aus.append({"meter": meter, "winter": "", "grund": "keine_daten",
                        "n_stunden": 0})
            continue
        winter = heizperiode(tab["zeit"])
        behalten = (winter != "") & ~begehungsmaske(tab["zeit"],
                                                    beg.get(meter, []),
                                                    puffer_tage)
        teil = tab[behalten]
        if len(teil) == 0:
            aus.append({"meter": meter, "winter": "", "grund": "keine_daten",
                        "n_stunden": 0})
            continue
        for w, grp in teil.groupby(winter[behalten]):
            k = kennzahlen_punkte(grp, aw.get(meter), min_stunden=min_stunden)
            if k["status"] != "ok":
                aus.append({"meter": meter, "winter": w, "grund": k["status"],
                            "n_stunden": k["n_stunden"]})
                continue
            k.pop("status")
            zeilen.append({"meter": meter, "winter": w,
                           "anschlusswert_kw": aw.get(meter, np.nan), **k})
    spalten_aus = ["meter", "winter", "grund", "n_stunden"]
    tabelle = pd.DataFrame(zeilen, columns=["meter", "winter",
                                            "anschlusswert_kw", *PUNKT_SPALTEN])
    if len(tabelle):
        tabelle["_j"] = tabelle["winter"].map(winter_ende_jahr)
        tabelle = (tabelle.sort_values(["_j", "meter"]).drop(columns="_j")
                   .reset_index(drop=True))
    return tabelle, pd.DataFrame(aus, columns=spalten_aus)


def robust_z(werte, referenz, vorzeichen: int = 1) -> np.ndarray:
    """(x - Median) / (1.4826 * MAD) gegen die Referenz, positiv = schlechter.

    Ist der MAD null, wird die Standardabweichung genommen; ist auch sie
    null, gibt es keinen z-Wert statt einer Division durch null.
    """
    x = np.asarray(werte, dtype=float)
    med, skala = _lage_skala(referenz)
    if not np.isfinite(skala):
        return np.full(x.shape, np.nan)
    return vorzeichen * (x - med) / skala


def _lage_skala(referenz) -> Tuple[float, float]:
    """Median und 1.4826 * MAD, ersatzweise Standardabweichung, sonst NaN."""
    ref = np.asarray(referenz, dtype=float)
    ref = ref[np.isfinite(ref)]
    if len(ref) < 2:
        return np.nan, np.nan
    med = float(np.median(ref))
    skala = 1.4826 * float(np.median(np.abs(ref - med)))
    if not skala > 1e-12:
        skala = float(np.std(ref, ddof=1))
    if not skala > 1e-12:
        return med, np.nan
    return med, skala


def netzbezug(tabelle: pd.DataFrame,
              gruppe: Optional[str] = None,
              referenz_ausschluss: Sequence[int] = REFERENZ_AUSSCHLUSS,
              min_stationen: int = MIN_STATIONEN_WINTER,
              min_klasse: int = MIN_KLASSE,
              kennzahlen: Mapping[str, int] = KENNZAHLEN) -> pd.DataFrame:
    """z-Werte je Kennzahl gegen die Stationen desselben Winters.

    Stationen aus ``referenz_ausschluss`` (BHKW) bestimmen Median und
    Streuung nicht mit, bekommen aber selbst z-Werte. Mit
    ``gruppe="leistungsklasse"`` wird innerhalb der Klasse verglichen;
    Klassen mit weniger als ``min_klasse`` Referenzstationen und
    ``unbekannt`` fallen auf den Netzbezug zurück.
    """
    out = tabelle.reset_index(drop=True)
    ausschluss = {int(m) for m in referenz_ausschluss}
    out["in_referenz"] = ~out["meter"].astype(int).isin(ausschluss)
    if gruppe == "leistungsklasse" and "leistungsklasse" not in out.columns:
        out["leistungsklasse"] = out["anschlusswert_kw"].map(cvl.leistungsklasse)
    out["bezug"] = "netz"
    for k in kennzahlen:
        out[f"z_{k}"] = np.nan

    for _, idx in out.groupby("winter").groups.items():
        w = out.loc[idx]
        ref = w[w["in_referenz"]]
        if len(ref) < int(min_stationen):
            out.loc[idx, "bezug"] = "zu_klein"
            continue
        teile = [(w.index, ref)]
        if gruppe is not None:
            teile = []
            for klasse, sub in w.groupby(gruppe):
                ref_kl = ref[ref[gruppe] == klasse]
                if klasse != "unbekannt" and len(ref_kl) >= int(min_klasse):
                    teile.append((sub.index, ref_kl))
                    out.loc[sub.index, "bezug"] = gruppe
                else:
                    teile.append((sub.index, ref))
        for t_idx, r in teile:
            for k, vz in kennzahlen.items():
                out.loc[t_idx, f"z_{k}"] = robust_z(out.loc[t_idx, k], r[k], vz)
    return out


def score_kennzahlen(bezogen: pd.DataFrame,
                     kennzahlen: Mapping[str, int] = KENNZAHLEN,
                     schwelle: float = REDUNDANZ_RHO,
                     ) -> Tuple[Dict[str, int], pd.DataFrame]:
    """Kennzahlen für den Score nach Redundanzprüfung.

    Spezifischer Volumenstrom und Referenzspreizung messen bei gleicher
    Auslegung fast dasselbe. Liegt Spearmans |rho| zwischen beiden in
    irgendeinem Winter über ``schwelle``, fliegt der Volumenstrom aus dem
    Score, sonst zählte derselbe Befund doppelt. Die rho-Tabelle geht ins
    Notebook.
    """
    a, b = "flow_spez_lh_kw", "spreizung_ref_k"
    zeilen = []
    for w, g in bezogen[bezogen["in_referenz"]].groupby("winter"):
        teil = g[[a, b]].dropna()
        rho = np.nan
        if len(teil) >= 5:
            rho = float(stats.spearmanr(teil[a], teil[b])[0])
        zeilen.append({"winter": w, "rho": rho, "n": int(len(teil))})
    rho_tab = pd.DataFrame(zeilen, columns=["winter", "rho", "n"])
    gewaehlt = dict(kennzahlen)
    if a in gewaehlt and (rho_tab["rho"].abs() > schwelle).any():
        gewaehlt.pop(a)
    return gewaehlt, rho_tab


def markiere(bezogen: pd.DataFrame,
             kennzahlen: Optional[Mapping[str, int]] = None,
             dezil: float = DEZIL,
             min_kennzahlen: int = MIN_KENNZAHLEN_AUFFAELLIG) -> pd.DataFrame:
    """Score, Rang und Auffälligkeit je Station und Winter.

    ``score`` ist das Mittel der verfügbaren z-Werte, ``n_kennzahlen`` die
    Zahl der z-Werte dahinter. ``rang`` 1 ist die
    schlechteste Station des Winters. Eine Kennzahl gilt als schlecht,
    wenn ihr z-Wert mindestens das (1 - dezil)-Quantil der
    Referenzstationen desselben Winters erreicht und über null liegt.
    Ohne die zweite Bedingung wären bei vielen gleichen Werten, etwa
    einem RL-Anteil von null, alle Stationen am Median schlecht.
    """
    if kennzahlen is None:
        kennzahlen, _ = score_kennzahlen(bezogen)
    out = bezogen.reset_index(drop=True)
    z_spalten = [f"z_{k}" for k in kennzahlen]
    out["score"] = out[z_spalten].mean(axis=1, skipna=True)
    out["n_kennzahlen"] = out[z_spalten].notna().sum(axis=1).astype(int)
    out["rang"] = out.groupby("winter")["score"].rank(ascending=False,
                                                      method="min")
    schlecht = [f"schlecht_{k}" for k in kennzahlen]
    for s in schlecht:
        out[s] = False
    for _, idx in out.groupby("winter").groups.items():
        g = out.loc[idx]
        ref = g[g["in_referenz"]]
        for k in kennzahlen:
            werte = ref[f"z_{k}"].dropna()
            if len(werte) == 0:
                continue
            grenze = float(werte.quantile(1.0 - dezil))
            z = g[f"z_{k}"]
            out.loc[idx, f"schlecht_{k}"] = ((z >= grenze) & (z > 0)).to_numpy()
    out["n_schlecht"] = out[schlecht].sum(axis=1).astype(int)
    out["auffaellig"] = out["n_schlecht"] >= int(min_kennzahlen)
    return out


def bestwert(werte, vorzeichen: int, anteil: float = BESTWERT_ANTEIL) -> float:
    """Median des besten Anteils der Werte, ``vorzeichen`` wie in KENNZAHLEN."""
    x = np.asarray(werte, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan
    if vorzeichen > 0:
        beste = x[x <= np.quantile(x, anteil)]
    else:
        beste = x[x >= np.quantile(x, 1.0 - anteil)]
    return float(np.median(beste))


GRENZEN_SPALTEN = ["vorzeichen", "median", "skala", "grenze_z", "ziel",
                   "n_werte"]


def grenzen_lernen(tabelle: pd.DataFrame,
                   kennzahlen: Mapping[str, int] = KENNZAHLEN,
                   referenz_ausschluss: Sequence[int] = REFERENZ_AUSSCHLUSS,
                   winter: Optional[Iterable[str]] = None,
                   dezil: float = DEZIL,
                   anteil: float = BESTWERT_ANTEIL) -> pd.DataFrame:
    """Maßstab je Kennzahl aus einem festen Lernzeitraum.

    Alle Zeilen der Lernwinter (ohne BHKW) werden zusammengelegt. Je
    Kennzahl stehen Median und Streuung für den z-Wert, die Schlecht-Grenze
    als (1 - dezil)-Quantil der z-Werte wie in `markiere` und als ``ziel``
    der Median des besten Viertels. ``winter=None`` nimmt alle Winter der
    Tabelle. Index ist die Kennzahl, ``n_referenz`` steht in ``attrs``.
    """
    ausschluss = {int(m) for m in referenz_ausschluss}
    ref = tabelle[~tabelle["meter"].astype(int).isin(ausschluss)]
    if winter is not None:
        ref = ref[ref["winter"].isin(list(winter))]
    zeilen = {}
    for k, vz in kennzahlen.items():
        x = pd.to_numeric(ref[k], errors="coerce").to_numpy(dtype=float)
        med, skala = _lage_skala(x)
        grenze = np.nan
        if np.isfinite(skala):
            z = vz * (x[np.isfinite(x)] - med) / skala
            grenze = float(np.quantile(z, 1.0 - dezil))
        zeilen[k] = {"vorzeichen": int(vz), "median": med, "skala": skala,
                     "grenze_z": grenze, "ziel": bestwert(x, vz, anteil),
                     "n_werte": int(np.isfinite(x).sum())}
    out = pd.DataFrame.from_dict(zeilen, orient="index", columns=GRENZEN_SPALTEN)
    out.index.name = "kennzahl"
    out.attrs["n_referenz"] = int(len(ref))
    return out


def _potenzial_spalten(out: pd.DataFrame, grenzen: pd.DataFrame,
                       potenzial_grenzen: Tuple[float, float] = POTENZIAL_GRENZEN,
                       ) -> pd.DataFrame:
    """Abstand zum besten Viertel in Einheiten der Kennzahl und als Lücke.

    ``abstand_k`` ist 0, wenn die Station mindestens so gut ist wie das
    beste Viertel. ``luecke_k`` teilt den Abstand durch den Abstand der
    typischen Station (Median), 1 heißt also so weit weg wie die typische
    Station. ``potenzial_score`` mittelt die Lücken.
    """
    luecken = []
    for k, g in grenzen.iterrows():
        x = pd.to_numeric(out[k], errors="coerce").to_numpy(dtype=float)
        abstand = np.clip(g["vorzeichen"] * (x - g["ziel"]), 0.0, None)
        breite = abs(g["median"] - g["ziel"])
        out[f"abstand_{k}"] = abstand
        out[f"luecke_{k}"] = abstand / breite if breite > 1e-12 else np.nan
        luecken.append(f"luecke_{k}")
    werte = out[luecken].to_numpy(dtype=float)
    out["potenzial_score"] = out[luecken].mean(axis=1, skipna=True)
    groesste = []
    for zeile in werte:
        ok = np.isfinite(zeile)
        if not ok.any() or np.nanmax(zeile) <= 0:
            groesste.append("")
        else:
            groesste.append(luecken[int(np.nanargmax(zeile))][len("luecke_"):])
    out["groesste_luecke"] = groesste
    s = out["potenzial_score"]
    unten, oben = potenzial_grenzen
    out["potenzial"] = np.select([s >= oben, s >= unten, s.notna()],
                                 ["hoch", "mittel", "gering"], default="")
    return out


def grenzen_anwenden(tabelle: pd.DataFrame, grenzen: pd.DataFrame,
                     min_kennzahlen: int = MIN_KENNZAHLEN_AUFFAELLIG,
                     potenzial_grenzen: Tuple[float, float] = POTENZIAL_GRENZEN,
                     ) -> pd.DataFrame:
    """z-Werte, Auffälligkeit und Potenzial gegen einen eingefrorenen Maßstab.

    Gegenstück zu `netzbezug` und `markiere` für den Lern-/Testvergleich:
    Der Maßstab kommt aus `grenzen_lernen` auf früheren Wintern und
    bewegt sich nicht mit, wenn sich im Testwinter viele Stationen
    gleichzeitig ändern.
    """
    out = tabelle.reset_index(drop=True).copy()
    z_spalten, schlecht = [], []
    for k, g in grenzen.iterrows():
        x = pd.to_numeric(out[k], errors="coerce").to_numpy(dtype=float)
        z = g["vorzeichen"] * (x - g["median"]) / g["skala"]
        out[f"z_{k}"] = z
        out[f"schlecht_{k}"] = (z >= g["grenze_z"]) & (z > 0)
        z_spalten.append(f"z_{k}")
        schlecht.append(f"schlecht_{k}")
    out["score"] = out[z_spalten].mean(axis=1, skipna=True)
    out["n_schlecht"] = out[schlecht].sum(axis=1).astype(int)
    out["auffaellig"] = out["n_schlecht"] >= int(min_kennzahlen)
    return _potenzial_spalten(out, grenzen, potenzial_grenzen)


def potenzial_je_winter(tabelle: pd.DataFrame,
                        kennzahlen: Mapping[str, int] = KENNZAHLEN,
                        referenz_ausschluss: Sequence[int] = REFERENZ_AUSSCHLUSS,
                        min_stationen: int = MIN_STATIONEN_WINTER,
                        anteil: float = BESTWERT_ANTEIL) -> pd.DataFrame:
    """Abstand zum besten Viertel desselben Winters, je Station und Winter.

    Winter mit weniger als ``min_stationen`` Referenzstationen bekommen
    keine Werte, wie in `netzbezug`.
    """
    spalten = (["meter", "winter"]
               + [f"{p}_{k}" for p in ("abstand", "luecke") for k in kennzahlen]
               + ["potenzial_score", "potenzial", "groesste_luecke"])
    teile = []
    for _, g in tabelle.groupby("winter"):
        gr = grenzen_lernen(g, kennzahlen, referenz_ausschluss, anteil=anteil)
        if gr.attrs["n_referenz"] < int(min_stationen):
            gr["ziel"] = np.nan
        teile.append(_potenzial_spalten(g.reset_index(drop=True).copy(), gr))
    if not teile:
        return pd.DataFrame(columns=spalten)
    return pd.concat(teile, ignore_index=True)[spalten]


def stationsuebersicht(markiert: pd.DataFrame,
                       min_winter: int = MIN_WINTER_CHRONISCH) -> pd.DataFrame:
    """Eine Zeile je Station über alle Winter mit gültigem Score."""
    g = markiert[markiert["score"].notna()]
    agg = g.groupby("meter").agg(n_winter=("winter", "nunique"),
                                 n_auffaellig=("auffaellig", "sum"),
                                 score_median=("score", "median"),
                                 rang_median=("rang", "median"),
                                 in_referenz=("in_referenz", "first"))
    liste = (g[g["auffaellig"]].groupby("meter")["winter"]
             .apply(lambda s: ",".join(sorted(s, key=winter_ende_jahr))))
    agg["winter_auffaellig"] = liste.reindex(agg.index).fillna("")
    agg["n_auffaellig"] = agg["n_auffaellig"].astype(int)
    agg["chronisch"] = agg["n_auffaellig"] >= int(min_winter)
    return (agg.reset_index()
            .sort_values("score_median", ascending=False)
            .reset_index(drop=True))


def kontext_tabelle(meters: Iterable,
                    anschlusswerte: Optional[Mapping] = None,
                    bhkw: Iterable = (),
                    begehungen: Optional[Mapping] = None,
                    labels: Optional[pd.DataFrame] = None,
                    *,
                    begangen_ohne_datum: Iterable = ()) -> pd.DataFrame:
    """Kontextmerkmale je Station für das Profil der auffälligen Stationen.

    ``labels`` ist die Ausgabe von `befundcodes.labels_je_zaehler` mit
    Spalte ``meter``; Stationen ohne Begehung bekommen dort NaN, nicht
    False, weil über sie nichts bekannt ist. ``begangen_ohne_datum`` sind
    Zähler, deren Begehung ohne Datum in der Tabelle steht. Sie zählen bei
    ``hat_begehung`` als begangen. ``n_begehungen`` zählt weiter nur die
    datierten Termine und ist für sie 0.
    """
    aw = int_schluessel(anschlusswerte)
    beg = int_schluessel(begehungen)
    ohne_datum = {int(m) for m in begangen_ohne_datum}
    df = pd.DataFrame({"meter": sorted({int(m) for m in meters})})
    df["anschlusswert_kw"] = df["meter"].map(aw).astype(float)
    df["leistungsklasse"] = df["anschlusswert_kw"].map(cvl.leistungsklasse)
    df["bhkw"] = df["meter"].isin({int(m) for m in bhkw})
    df["n_begehungen"] = df["meter"].map(lambda m: len(beg.get(m, []))).astype(int)
    df["hat_begehung"] = (df["n_begehungen"] > 0) | df["meter"].isin(ohne_datum)
    if labels is not None:
        lab = labels.copy()
        lab["meter"] = lab["meter"].astype(int)
        df = df.merge(lab, on="meter", how="left")
    return df


def _vierfeld(merkmal: np.ndarray, flag: np.ndarray) -> dict:
    a = int((merkmal & flag).sum())
    b = int((~merkmal & flag).sum())
    c = int((merkmal & ~flag).sum())
    d = int((~merkmal & ~flag).sum())
    return {"test": "fisher", "n_gruppe": a + b, "n_rest": c + d,
            "wert_gruppe": a / (a + b) if a + b else np.nan,
            "wert_rest": c / (c + d) if c + d else np.nan,
            "p_wert": float(stats.fisher_exact([[a, b], [c, d]])[1])}


def profil(uebersicht: pd.DataFrame,
           kontext: pd.DataFrame,
           gruppe: str = "chronisch",
           nur_referenz: bool = True) -> pd.DataFrame:
    """Was haben die markierten Stationen gemeinsam?

    Bool-Merkmale und jede Ausprägung kategorialer Merkmale gehen über
    Fishers exakten Test (Anteil in der Gruppe gegen den Rest), numerische
    über Mann-Whitney (Mediane). Fehlende Werte zählen nicht mit. Ein
    kleiner p-Wert ist bei n um 85 und vielen Merkmalen nur ein Hinweis
    auf einen Zusammenhang, keine Ursache.
    """
    spalten = ["meter", gruppe] + (["in_referenz"] if nur_referenz else [])
    d = uebersicht[spalten].merge(kontext, on="meter", how="left")
    if nur_referenz:
        d = d[d["in_referenz"].astype(bool)]
    flag_alle = d[gruppe].astype(bool).to_numpy()
    zeilen = []
    for spalte in kontext.columns:
        if spalte == "meter":
            continue
        s = d[spalte]
        ok = s.notna().to_numpy()
        werte = set(s.dropna().unique())
        ist_bool = pd.api.types.is_bool_dtype(s) or (
            s.dtype == object and len(werte) > 0
            and all(isinstance(v, (bool, np.bool_)) for v in werte))
        if ist_bool:
            r = _vierfeld(s[ok].astype(bool).to_numpy(), flag_alle[ok])
            zeilen.append({"merkmal": spalte, "auspraegung": "", **r})
        elif pd.api.types.is_numeric_dtype(s):
            x = s.to_numpy(dtype=float)
            g, rest = x[ok & flag_alle], x[ok & ~flag_alle]
            p = np.nan
            if len(g) >= 2 and len(rest) >= 2:
                p = float(stats.mannwhitneyu(g, rest, alternative="two-sided")[1])
            zeilen.append({"merkmal": spalte, "auspraegung": "",
                           "test": "mannwhitney", "n_gruppe": len(g),
                           "n_rest": len(rest),
                           "wert_gruppe": float(np.median(g)) if len(g) else np.nan,
                           "wert_rest": float(np.median(rest)) if len(rest) else np.nan,
                           "p_wert": p})
        else:
            for wert in sorted(werte, key=str):
                m = (s[ok] == wert).to_numpy()
                r = _vierfeld(m, flag_alle[ok])
                zeilen.append({"merkmal": spalte, "auspraegung": str(wert), **r})
    spalten_out = ["merkmal", "auspraegung", "test", "n_gruppe", "n_rest",
                   "wert_gruppe", "wert_rest", "p_wert"]
    return (pd.DataFrame(zeilen, columns=spalten_out)
            .sort_values("p_wert", na_position="last").reset_index(drop=True))


def heizgradstunden_je_winter(temp: pd.DataFrame,
                              t_heiz: float = 15.0) -> pd.DataFrame:
    """Heizgradstunden je Kernwinter als Witterungskontext.

    ``temp`` ist die Ausgabe von `weather.load_outdoor_temperature`
    (Spalten ``timestamp``, ``t_out``). ``n_stunden`` zählt die Stunden
    mit Messwert, damit eine lückenhafte Temperaturreihe sichtbar bleibt.
    """
    hgs = weather.heating_degree_hours(temp, t_heiz=t_heiz)
    d = pd.DataFrame({"winter": heizperiode(hgs.index),
                      "hgs": hgs.to_numpy(dtype=float)})
    d = d[d["winter"] != ""]
    out = d.groupby("winter").agg(heizgradstunden=("hgs", "sum"),
                                  n_stunden=("hgs", "count")).reset_index()
    return out
