"""
Kalendergleicher Vorher/Nachher-Vergleich um eine Begehung.

Zwei Wege: der Jahresvergleich (Vorjahresversatz oder symmetrisches
Fenster fester Laenge) und der Wintervergleich (Heizperiode vor der
Begehung gegen Heizperiode danach). Der Wintervergleich ist der
spaetere, inzwischen bevorzugte Weg; der Jahresvergleich bleibt
vollstaendig erhalten, weil er die Vorstufe dokumentiert und von
Notebook 07 weiterhin gerechnet wird. Der Modulname stammt aus dem
Jahresvergleich und passt seitdem nicht mehr sauber; umbenannt wird er
nicht, weil Notebooks und Tests darauf importieren.

Warum ein eigenes Modul und keine Erweiterung von `window_features.py`:
dort laufen rollierende Fenster gleicher Laenge ueber die gesamte
Historie eines Zaehlers, der Bezugspunkt ist das Kalenderraster. Hier
ist der Bezugspunkt ein Ereignis, es gibt genau zwei Fenster je
Begehung, und die Witterungsnormierung ueber die Heizgradstunden aus
`src/weather.py` gehoert fest dazu. Die beiden Aufgaben teilen keine
Zwischenergebnisse, deshalb bleiben sie getrennt.

Zwei Fenstermodi
----------------
``kalendergleich`` legt das Nachher-Fenster auf [D+1, D+L] und das
Vorher-Fenster auf denselben Kalenderabschnitt ein Jahr frueher, also
[D+1-365, D+L-365]. Beide Fenster decken damit dieselben Kalendermonate
ab, die Saisonalitaet faellt aus der Differenz heraus. Das ist der
Vorjahresvergleich, den die Betreuung gefordert hat, und er funktioniert
fuer jede Fensterlaenge L, nicht nur fuer L=365.

``symmetrisch`` legt [D-L, D-1] gegen [D+1, D+L]. Nur bei L=365 sind
diese beiden Fenster kalendergleich; bei jedem kuerzeren L vergleichen
sie unterschiedliche Jahreszeiten. Der Modus bleibt als Referenz drin,
weil Notebook 03 so gerechnet hat (L=21) und die Ergebnisse
gegeneinander gestellt werden muessen.

Fensterlaenge
-------------
`window_days` ist Parameter, nicht Konstante. In der Datenlage vom
September 2026 reicht die Historie fuer *keine* Begehung ueber ein
volles Jahr danach (Exporte enden 2025-07-11, die erste Begehung ist
vom 2024-08-26, der groesste Abstand danach betraegt 319 Tage). Die
Fallzahl je Laenge gehoert deshalb in jede Auswertung; `abdeckung()`
liefert sie.

Qualitaet wird gekennzeichnet, nicht gefiltert
----------------------------------------------
Jede Zeile traegt die Abdeckung beider Fenster als eigene Spalte sowie
die Flags `meter_change` (im Vergleichszeitraum liegt ein dokumentierter
Zaehlertausch, es werden zwei Geraete verglichen) und
`weitere_begehung` (im Vorher- oder Nachher-Fenster liegt eine zweite
Begehung, die Zuordnung der Wirkung ist kontaminiert). Nichts davon
wirft Zeilen weg.

Witterungsnormierung
--------------------
Zwei aufeinanderfolgende Jahre sind unterschiedlich kalt. Ohne
Normierung waere ein milder Winter nicht von einer wirksamen Begehung zu
unterscheiden. `heizgradstunden` summiert die Heizgradstunden ueber das
volle Kalenderfenster (nicht nur ueber die gemessenen Stunden), weil die
Energie aus einem kumulativen Zaehler kommt und Messluecken mit
ueberbrueckt. `energie_je_kh` und `volumen_je_kh` sind die normierten
Kennzahlen. Das gilt fuer beide Wege gleichermassen: auch zwei
aufeinanderfolgende Winter sind unterschiedlich kalt, gleiche Jahreszeit
heisst nicht gleiche Witterung.

Wintervergleich
---------------
Notebook 06 hat gezeigt, dass der Sommer rund ein Drittel der
Kalenderstunden stellt, aber nur knapp fuenf Prozent der
Heizgradstunden, und dass der Ruecklauf unter Last im Sommer rund 4 K
ueber dem Kernwinterwert liegt. Ein Fenster ueber 270 oder 365 Tage
mittelt diesen Sommeranteil in jede Kennzahl hinein und verduennt damit
genau den Teil, der etwas aussagt. Der Wintervergleich stellt deshalb
die Heizperiode vor der Begehung gegen die Heizperiode danach.

Der Vorjahresversatz des Jahresvergleichs wird damit ueberfluessig. Er
hatte nur eine Aufgabe, naemlich beide Fenster auf dieselben
Kalendermonate zu legen. Beim Wintervergleich folgt die
Kalendergleichheit schon aus der Winterdefinition: beide Fenster sind
Heizperioden, decken also per Konstruktion dieselben Monate ab. Der
Versatz zwischen ihnen ergibt sich aus der Lage der Begehung und ist
kein Parameter mehr.

Die Monatsgrenzen kommen aus `src/season.py` und werden hier nicht neu
erfunden. `WINTER_KERN` ist der Kernwinter (Dezember bis Februar),
`WINTER_ERWEITERT` nimmt die beiden Uebergangssegmente dazu (September
bis April). Die Betreuervorgabe nennt den Uebergangsbereich ausdruecklich
getrennt vom Kernwinter, deshalb ist der Kernwinter die Voreinstellung
und die erweiterte Abgrenzung die Sensitivitaetsvariante.

Zuordnung Begehung zu Winter
----------------------------
Anker ist immer der Kernwinter, unabhaengig von der gewaehlten
Fenstervariante - nur so bleibt die Zuordnung zwischen beiden Varianten
vergleichbar. Liegt die Begehung zwischen zwei Kernwintern, ist der
Winter davor der zuletzt abgeschlossene und der Winter danach der
naechste beginnende. Eine Begehung im September 2024 bekommt damit
2023/24 als Vorher- und 2024/25 als Nachher-Winter.

Faellt die Begehung in einen Kernwinter, gilt dieser als angeschnitten:
er enthaelt Stunden vor und nach der Intervention und zaehlt deshalb
weder als Vorher noch als Nachher. Verglichen werden dann der
vorangegangene und der folgende Winter, die Begehung liegt also ein
ganzes Jahr statt eines halben zwischen den Fenstern. Das ist die
konservative Variante, und sie kostet Fallzahl: wie viel, weist
`winter_abdeckung` ueber die Spalte `angeschnitten` aus.

In der erweiterten Variante kann die Begehung in das Nachher-Fenster
oder das Vorher-Fenster hineinragen. Dann wird das betroffene Ende
abgeschnitten und derselbe Kalenderausschnitt im jeweils anderen Fenster
ebenfalls, damit die Kalendergleichheit erhalten bleibt.
`fensteranteil` meldet, wie viel der Heizperiode uebrig bleibt.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from . import season

MODUS_KALENDER = "kalendergleich"
MODUS_SYMMETRISCH = "symmetrisch"

#Winterabgrenzungen, aus src/season.py abgeleitet statt hier neu gesetzt.
#Der Kernwinter ist dort Dez/Jan/Feb, die erweiterte Abgrenzung nimmt die
#beiden Uebergangssegmente dazu (Sep/Okt/Nov und Maer/Apr) und laeuft
#damit von September bis April.
WINTER_KERN = "kernwinter"
WINTER_ERWEITERT = "erweitert"


def _monatsspanne(segmente: Sequence[str]) -> tuple:
    """(erster, letzter) Monat einer Heizperiode aus den Saisonsegmenten.

    Die Monate werden aus `season.SEASON_MONTHS` gelesen, damit es nur
    eine Quelle fuer die Winterdefinition gibt. Die Spanne laeuft ueber
    den Jahreswechsel; geprueft wird, dass die Monate dabei
    zusammenhaengen.
    """
    monate = {m for m, s in season.SEASON_MONTHS.items() if s in segmente}
    #Monate auf eine Achse legen, die im September beginnt, damit die
    #Heizperiode nicht am Jahreswechsel auseinanderfaellt
    versetzt = sorted(((m - 9) % 12, m) for m in monate)
    folge = [m for _, m in versetzt]
    if [p for p, _ in versetzt] != list(range(versetzt[0][0],
                                              versetzt[0][0] + len(folge))):
        raise ValueError(
            f"Segmente {segmente} ergeben keine zusammenhaengende "
            f"Heizperiode: Monate {sorted(monate)}")
    return folge[0], folge[-1]


WINTER_VARIANTEN = {
    WINTER_KERN: _monatsspanne([season.KERNWINTER]),
    WINTER_ERWEITERT: _monatsspanne([season.KERNWINTER,
                                     season.UEBERGANG_FRUEH,
                                     season.UEBERGANG_SPAET]),
}

#Versatz des Vorjahresfensters. 365 statt 365,25, damit Wochentage und
#Heizzeitprofile grob zusammenpassen; der Schalttagsversatz ist gegenueber
#einem 270-Tage-Fenster vernachlaessigbar.
JAHR_TAGE = 365

#Leistungsschwelle fuer "unter Last", identisch zu features.features_for_meter
LAST_SCHWELLE_KW = 0.5

#Rücklaufschwelle der Vierfeldertafel, identisch zu Notebook 03,
#src/dashboard_app.py (RT_YELLOW_MAX) und features.rt_above_50_share_loaded
RT_SCHWELLE = 50.0

#Kennzahlen, die je Fenster berechnet werden; Reihenfolge = Spaltenreihenfolge
KENNZAHLEN = [
    "rt_median",
    "rt_mean_loaded",
    "dt_mean_loaded",
    "flow_median",
    "energie_kwh",
    "volumen_m3",
    "vollaststunden",
    "betrieb_anteil",
    "spitzenleistung_kw",
    "sommer_flow_baseline",
    "heizgradstunden",
    "energie_je_kh",
    "volumen_je_kh",
]

TimestampLike = Union[str, pd.Timestamp]


def vergleichsfenster(datum: TimestampLike,
                      window_days: int,
                      modus: str = MODUS_KALENDER) -> Dict[str, pd.Timestamp]:
    """Die vier Zeitgrenzen zu einer Begehung, Begehungstag ausgeschlossen.

    Rueckgabe hat die Schluessel ``vor_start``, ``vor_end``,
    ``nach_start``, ``nach_end``; alle Grenzen sind inklusiv und auf
    Mitternacht normalisiert, das Nachher-Fenster endet auf 23:00.
    """
    if window_days <= 0:
        raise ValueError("window_days muss positiv sein")
    d = pd.Timestamp(datum).normalize()
    nach_start = d + pd.Timedelta(days=1)
    nach_end = d + pd.Timedelta(days=window_days) + pd.Timedelta(hours=23)

    if modus == MODUS_KALENDER:
        vor_start = nach_start - pd.Timedelta(days=JAHR_TAGE)
        vor_end = nach_end - pd.Timedelta(days=JAHR_TAGE)
    elif modus == MODUS_SYMMETRISCH:
        vor_start = d - pd.Timedelta(days=window_days)
        vor_end = d - pd.Timedelta(hours=1)
    else:
        raise ValueError(
            f"unbekannter Modus {modus!r} - erlaubt sind "
            f"{MODUS_KALENDER!r} und {MODUS_SYMMETRISCH!r}")

    return {"vor_start": vor_start, "vor_end": vor_end,
            "nach_start": nach_start, "nach_end": nach_end}


def abdeckung(begehungen: pd.DataFrame,
              historien: Dict[int, tuple],
              window_days: int,
              modus: str = MODUS_KALENDER) -> pd.DataFrame:
    """Machbarkeitstabelle: reicht die Historie je Begehung fuer beide Fenster?

    `begehungen` braucht die Spalten ``meter`` und ``datum``, `historien`
    bildet Zaehlernummer auf ``(erster, letzter)`` Zeitstempel ab.
    Gibt je Begehung die verfuegbaren Tage davor und danach, die
    Fenstergrenzen und ``vollstaendig`` aus. Es wird nichts verworfen,
    unvollstaendige Faelle bleiben mit ``vollstaendig=False`` stehen.
    """
    rows: List[dict] = []
    for _, r in begehungen.iterrows():
        if pd.isna(r.get("meter")) or pd.isna(r.get("datum")):
            continue
        zid = int(r["meter"])
        d = pd.Timestamp(r["datum"]).normalize()
        grenzen = vergleichsfenster(d, window_days, modus)
        lo, hi = historien.get(zid, (pd.NaT, pd.NaT))
        row = {
            "meter": zid,
            "datum": d,
            "historie_von": lo,
            "historie_bis": hi,
            "tage_davor": np.nan if pd.isna(lo) else (d - pd.Timestamp(lo)).days,
            "tage_danach": np.nan if pd.isna(hi) else (pd.Timestamp(hi) - d).days,
        }
        row.update(grenzen)
        row["vollstaendig"] = bool(
            pd.notna(lo) and pd.notna(hi)
            and pd.Timestamp(lo) <= grenzen["vor_start"]
            and pd.Timestamp(hi) >= grenzen["nach_end"].normalize()
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values(["datum", "meter"]).reset_index(drop=True)
    return out


def _heizgradstunden_summe(hdh: Optional[pd.Series],
                           start: pd.Timestamp,
                           end: pd.Timestamp) -> float:
    if hdh is None or len(hdh) == 0:
        return np.nan
    teil = hdh.loc[(hdh.index >= start) & (hdh.index <= end)]
    if teil.notna().sum() == 0:
        return np.nan
    return float(teil.sum(skipna=True))


def fensterkennzahlen(df: pd.DataFrame,
                      start: TimestampLike,
                      end: TimestampLike,
                      hdh: Optional[pd.Series] = None) -> dict:
    """Kennzahlen eines Zeitfensters aus einer stuendlichen Zaehlerreihe.

    `df` erwartet das Schema von `features.features_for_meter` (Spalten
    energy, flow, power, dt, vl, rt, volume auf einem stuendlichen
    DatetimeIndex). `hdh` ist die Heizgradstundenreihe aus
    `weather.heating_degree_hours`, indiziert auf denselben
    Zeitstempeln; ohne sie bleiben die normierten Kennzahlen NaN.

    `rt_median` ist bewusst der Median ueber *alle* Stunden des Fensters,
    also dieselbe Definition wie in Notebook 03 - nur so sind die
    Vierfeldertafeln vergleichbar. `rt_mean_loaded` ist der fachlich
    sauberere Rücklauf unter Last und steht daneben.
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    if end < start:
        raise ValueError(f"end ({end}) liegt vor start ({start})")

    w = df.loc[(df.index >= start) & (df.index <= end)]
    kalenderstunden = (end - start).total_seconds() / 3600 + 1

    f = {name: np.nan for name in KENNZAHLEN}
    f["n_hours"] = int(len(w))
    f["coverage"] = len(w) / kalenderstunden if kalenderstunden > 0 else np.nan
    kalendertage = max(1.0, kalenderstunden / 24.0)
    f["tagesabdeckung"] = (len(set(w.index.normalize())) / kalendertage
                           if kalendertage > 0 else np.nan)
    f["heizgradstunden"] = _heizgradstunden_summe(hdh, start, end)
    if len(w) == 0:
        return f

    last = w["power"] > LAST_SCHWELLE_KW
    f["rt_median"] = w["rt"].median()
    f["rt_mean_loaded"] = w.loc[last, "rt"].mean() if last.any() else np.nan
    f["dt_mean_loaded"] = w.loc[last, "dt"].mean() if last.any() else np.nan
    f["flow_median"] = w["flow"].median()
    f["betrieb_anteil"] = float(last.mean())
    f["spitzenleistung_kw"] = w["power"].max()

    sommer = w.index.month.isin([6, 7, 8])
    if sommer.any():
        f["sommer_flow_baseline"] = w.loc[sommer, "flow"].median()

    #kumulative Zaehler: Differenz ueberbrueckt Messluecken, deshalb wird
    #anschliessend auf die Kalenderlaenge des Fensters hochgerechnet
    if len(w) >= 2:
        f["energie_kwh"] = float(w["energy"].iloc[-1] - w["energy"].iloc[0])
        f["volumen_m3"] = float(w["volume"].iloc[-1] - w["volume"].iloc[0])
        peak = f["spitzenleistung_kw"]
        if pd.notna(peak):
            jahr_faktor = 8760.0 / kalenderstunden
            f["vollaststunden"] = (f["energie_kwh"] * jahr_faktor
                                   / max(float(peak), 0.1))

    kh = f["heizgradstunden"]
    if pd.notna(kh) and kh > 0:
        if pd.notna(f["energie_kwh"]):
            f["energie_je_kh"] = f["energie_kwh"] / kh
        if pd.notna(f["volumen_m3"]):
            f["volumen_je_kh"] = f["volumen_m3"] / kh
    return f


def vergleich_fuer_begehung(df: pd.DataFrame,
                            datum: TimestampLike,
                            window_days: int,
                            modus: str = MODUS_KALENDER,
                            hdh: Optional[pd.Series] = None,
                            meter_changes: Optional[Sequence[TimestampLike]] = None,
                            weitere_begehungen: Optional[Sequence[TimestampLike]] = None
                            ) -> dict:
    """Vorher- und Nachher-Kennzahlen einer Begehung plus Differenzen.

    Ausgabe traegt je Kennzahl die Suffixe ``_vor`` und ``_nach`` sowie
    die Differenz ``d_<kennzahl>`` (nachher minus vorher). Dazu die
    Abdeckung beider Fenster, `meter_change` und `weitere_begehung`.
    Beide Flags markieren nur, sie filtern nicht.
    """
    grenzen = vergleichsfenster(datum, window_days, modus)
    out: dict = {"window_days": int(window_days), "modus": modus}
    out.update(_vergleich_aus_grenzen(df, datum, grenzen, hdh,
                                      meter_changes, weitere_begehungen))
    return out


def _vergleich_aus_grenzen(df: pd.DataFrame,
                           datum: TimestampLike,
                           grenzen: Dict[str, pd.Timestamp],
                           hdh: Optional[pd.Series] = None,
                           meter_changes: Optional[Sequence[TimestampLike]] = None,
                           weitere_begehungen: Optional[Sequence[TimestampLike]] = None
                           ) -> dict:
    """Kennzahlen, Differenzen und Flags zu vier festen Zeitgrenzen.

    Gemeinsamer Kern von Jahres- und Wintervergleich; die beiden Wege
    unterscheiden sich nur darin, wie die vier Grenzen zustande kommen.
    """
    vor = fensterkennzahlen(df, grenzen["vor_start"], grenzen["vor_end"], hdh)
    nach = fensterkennzahlen(df, grenzen["nach_start"], grenzen["nach_end"], hdh)

    out: dict = {"datum": pd.Timestamp(datum).normalize()}
    out.update(grenzen)
    out["coverage_vor"] = vor["coverage"]
    out["coverage_nach"] = nach["coverage"]
    out["tagesabdeckung_vor"] = vor["tagesabdeckung"]
    out["tagesabdeckung_nach"] = nach["tagesabdeckung"]
    out["n_hours_vor"] = vor["n_hours"]
    out["n_hours_nach"] = nach["n_hours"]

    for name in KENNZAHLEN:
        out[f"{name}_vor"] = vor[name]
        out[f"{name}_nach"] = nach[name]
        out[f"d_{name}"] = nach[name] - vor[name]

    spanne = (grenzen["vor_start"], grenzen["nach_end"])

    def liegt_drin(werte: Optional[Iterable[TimestampLike]],
                   nur_fenster: bool) -> bool:
        if not werte:
            return False
        for t in werte:
            t = pd.Timestamp(t)
            if nur_fenster:
                im_vor = grenzen["vor_start"] <= t <= grenzen["vor_end"]
                im_nach = grenzen["nach_start"] <= t <= grenzen["nach_end"]
                if im_vor or im_nach:
                    return True
            elif spanne[0] <= t <= spanne[1]:
                return True
        return False

    out["meter_change"] = liegt_drin(meter_changes, nur_fenster=False)

    d = pd.Timestamp(datum).normalize()
    andere = [pd.Timestamp(t) for t in (weitere_begehungen or [])
              if pd.Timestamp(t).normalize() != d]
    out["weitere_begehung"] = liegt_drin(andere, nur_fenster=True)

    out["zustand_vor"] = _zustand(vor["rt_median"])
    out["zustand_nach"] = _zustand(nach["rt_median"])
    return out


def _zustand(rt: float, schwelle: float = RT_SCHWELLE) -> Optional[str]:
    if pd.isna(rt):
        return None
    return "schlecht" if rt > schwelle else "gut"


def jahresvergleich_tabelle(serien: Dict[int, pd.DataFrame],
                            begehungen: pd.DataFrame,
                            window_days: int,
                            modus: str = MODUS_KALENDER,
                            hdh: Optional[pd.Series] = None,
                            meter_changes: Optional[Dict[int, Sequence[TimestampLike]]] = None,
                            begehungen_je_meter: Optional[Dict[int, Sequence[TimestampLike]]] = None,
                            zusatzspalten: Sequence[str] = ("kategorie",)
                            ) -> pd.DataFrame:
    """Eine Zeile je Begehung mit Zeitreihe, ueber alle Zaehler.

    `serien` bildet Zaehlernummer auf die stuendliche Reihe ab,
    `begehungen` braucht ``meter`` und ``datum``. Begehungen ohne
    Zeitreihe werden uebersprungen (sie haben keine Messgrundlage);
    alles andere bleibt in der Tabelle und wird ueber `coverage_vor` /
    `coverage_nach` und die beiden Flags bewertet.
    """
    rows: List[dict] = []
    for _, r in begehungen.iterrows():
        if pd.isna(r.get("meter")) or pd.isna(r.get("datum")):
            continue
        zid = int(r["meter"])
        df = serien.get(zid)
        if df is None or len(df) == 0:
            continue
        row = vergleich_fuer_begehung(
            df, r["datum"], window_days, modus, hdh,
            meter_changes=(meter_changes or {}).get(zid),
            weitere_begehungen=(begehungen_je_meter or {}).get(zid),
        )
        row["meter"] = zid
        for col in zusatzspalten:
            if col in r.index:
                row[col] = r[col]
        rows.append(row)

    out = pd.DataFrame(rows)
    if len(out) == 0:
        return out
    vorne = ["meter", "datum", "modus", "window_days"]
    return out[vorne + [c for c in out.columns if c not in vorne]]


def kontrollgruppe_tabelle(serien: Dict[int, pd.DataFrame],
                           datum: TimestampLike,
                           window_days: int,
                           modus: str = MODUS_KALENDER,
                           hdh: Optional[pd.Series] = None) -> pd.DataFrame:
    """Dieselbe Fensterlogik fuer Stationen ohne Begehung.

    `serien` enthaelt nur die Kontrollstationen. Das Datum ist das
    Begehungsdatum der zugehoerigen behandelten Station, damit beide
    Gruppen denselben Kalenderabschnitt sehen - das ist die Grundlage
    des Diff-in-Diff.
    """
    rows = []
    for zid, df in serien.items():
        if df is None or len(df) == 0:
            continue
        row = vergleich_fuer_begehung(df, datum, window_days, modus, hdh)
        row["meter"] = int(zid)
        rows.append(row)
    return pd.DataFrame(rows)


def vierfeldertafel(tab: pd.DataFrame) -> pd.DataFrame:
    """Kreuztabelle Zustand vorher gegen Zustand nachher, feste Reihenfolge."""
    t = tab.dropna(subset=["zustand_vor", "zustand_nach"])
    kreuz = pd.crosstab(t["zustand_vor"], t["zustand_nach"])
    return kreuz.reindex(index=["gut", "schlecht"],
                         columns=["gut", "schlecht"], fill_value=0)


#--------------------------------------------------------------------------
#Wintervergleich: Heizperiode vor der Begehung gegen Heizperiode danach
#--------------------------------------------------------------------------

def heizperiode(start_jahr: int,
                variante: str = WINTER_KERN) -> Dict[str, pd.Timestamp]:
    """Anfang und Ende einer Heizperiode, benannt nach ihrem Startjahr.

    Der Winter 2024 ist die Periode, die im Dezember 2024 beginnt und im
    Februar 2025 endet; in der erweiterten Variante beginnt sie im
    September 2024 und endet im April 2025. `start` liegt auf
    Mitternacht des ersten Tages, `end` auf 23:00 des letzten.
    """
    if variante not in WINTER_VARIANTEN:
        raise ValueError(
            f"unbekannte Wintervariante {variante!r} - erlaubt sind "
            f"{sorted(WINTER_VARIANTEN)}")
    m_start, m_end = WINTER_VARIANTEN[variante]
    start = pd.Timestamp(year=int(start_jahr), month=m_start, day=1)
    letzter = (pd.Timestamp(year=int(start_jahr) + 1, month=m_end, day=1)
               + pd.offsets.MonthEnd(0))
    return {"start": start, "end": letzter + pd.Timedelta(hours=23)}


def winter_label(start_jahr: int) -> str:
    """Beschriftung einer Heizperiode, etwa ``2024/25``."""
    return f"{int(start_jahr)}/{(int(start_jahr) + 1) % 100:02d}"


def winterzuordnung(datum: TimestampLike) -> dict:
    """Welcher Winter zaehlt als vorher, welcher als nachher.

    Anker ist immer der Kernwinter, auch wenn die Fenster spaeter mit
    der erweiterten Abgrenzung gebildet werden - sonst haengt die
    Zuordnung an der Fensterwahl und die beiden Varianten liessen sich
    nicht gegeneinander stellen.

    Liegt das Datum zwischen zwei Kernwintern, sind Vorher- und
    Nachher-Winter die beiden benachbarten. Liegt es in einem
    Kernwinter, gilt dieser als angeschnitten und faellt heraus;
    verglichen werden dann der davorliegende und der darauffolgende
    Winter. Rueckgabe hat die Schluessel ``winter_vor``, ``winter_nach``
    (Startjahre), ``winter_vor_label``, ``winter_nach_label``,
    ``angeschnitten`` und ``winter_datum`` (Startjahr des angeschnittenen
    Winters, sonst None).
    """
    d = pd.Timestamp(datum).normalize()
    #Startjahr des Kernwinters, in dem das Datum liegen koennte
    jahr = d.year if d.month == 12 else d.year - 1
    kern = heizperiode(jahr, WINTER_KERN)
    angeschnitten = bool(kern["start"] <= d <= kern["end"])

    if angeschnitten:
        vor, nach = jahr - 1, jahr + 1
    else:
        vor, nach = jahr, jahr + 1

    return {"winter_vor": vor,
            "winter_nach": nach,
            "winter_vor_label": winter_label(vor),
            "winter_nach_label": winter_label(nach),
            "angeschnitten": angeschnitten,
            "winter_datum": jahr if angeschnitten else None}


def winterfenster(datum: TimestampLike,
                  variante: str = WINTER_KERN) -> dict:
    """Die vier Zeitgrenzen des Wintervergleichs zu einer Begehung.

    Beide Fenster sind Heizperioden und decken damit per Konstruktion
    dieselben Kalendermonate ab - ein Vorjahresversatz wie im
    Jahresvergleich wird dafuer nicht gebraucht.

    Ragt die Begehung in eines der beiden Fenster hinein (moeglich in der
    erweiterten Variante, weil September bis April den Begehungszeitraum
    ueberlappt), wird das betroffene Ende abgeschnitten und derselbe
    Kalenderausschnitt im anderen Fenster ebenfalls. `fensteranteil`
    meldet, welcher Teil der vollen Heizperiode uebrig bleibt.
    """
    z = winterzuordnung(datum)
    d = pd.Timestamp(datum).normalize()
    p_vor = heizperiode(z["winter_vor"], variante)
    p_nach = heizperiode(z["winter_nach"], variante)

    voll = p_nach["end"] - p_nach["start"]
    #Begehungstag selbst gehoert in kein Fenster
    versatz_anfang = max(pd.Timedelta(0),
                         (d + pd.Timedelta(days=1)) - p_nach["start"])
    versatz_ende = max(pd.Timedelta(0),
                       p_vor["end"] - (d - pd.Timedelta(hours=1)))
    #defensiv: ein vollstaendig weggeschnittenes Fenster bleibt leer statt
    #die Grenzen zu vertauschen
    rest = voll - versatz_anfang - versatz_ende
    if rest < pd.Timedelta(0):
        versatz_ende = max(pd.Timedelta(0), voll - versatz_anfang)
        rest = pd.Timedelta(0)

    grenzen = {
        "vor_start": p_vor["start"] + versatz_anfang,
        "vor_end": p_vor["end"] - versatz_ende,
        "nach_start": p_nach["start"] + versatz_anfang,
        "nach_end": p_nach["end"] - versatz_ende,
    }
    out = dict(grenzen)
    out.update(z)
    out["variante"] = variante
    out["fensteranteil"] = float(rest / voll) if voll else np.nan
    return out


def wintervergleich_fuer_begehung(df: pd.DataFrame,
                                  datum: TimestampLike,
                                  variante: str = WINTER_KERN,
                                  hdh: Optional[pd.Series] = None,
                                  meter_changes: Optional[Sequence[TimestampLike]] = None,
                                  weitere_begehungen: Optional[Sequence[TimestampLike]] = None
                                  ) -> dict:
    """Kennzahlen des Winters vor und des Winters nach der Begehung.

    Spaltenschema wie `vergleich_fuer_begehung`, zusaetzlich die
    Winterbeschriftungen, `angeschnitten` und `fensteranteil`.
    """
    fenster = winterfenster(datum, variante)
    grenzen = {k: fenster[k] for k in ("vor_start", "vor_end",
                                       "nach_start", "nach_end")}
    out: dict = {"variante": variante}
    out.update(_vergleich_aus_grenzen(df, datum, grenzen, hdh,
                                      meter_changes, weitere_begehungen))
    for k in ("winter_vor", "winter_nach", "winter_vor_label",
              "winter_nach_label", "angeschnitten", "fensteranteil"):
        out[k] = fenster[k]
    return out


def winter_abdeckung(begehungen: pd.DataFrame,
                     historien: Dict[int, tuple],
                     variante: str = WINTER_KERN) -> pd.DataFrame:
    """Machbarkeitstabelle des Wintervergleichs, eine Zeile je Begehung.

    Zeigt je Begehung die beiden zugeordneten Heizperioden, ob die
    Begehung in einen angeschnittenen Winter faellt und ob die Historie
    beide Fenster ueberhaupt abdeckt. Es wird nichts verworfen.
    """
    rows: List[dict] = []
    for _, r in begehungen.iterrows():
        if pd.isna(r.get("meter")) or pd.isna(r.get("datum")):
            continue
        zid = int(r["meter"])
        d = pd.Timestamp(r["datum"]).normalize()
        f = winterfenster(d, variante)
        lo, hi = historien.get(zid, (pd.NaT, pd.NaT))
        row = {"meter": zid, "datum": d, "variante": variante,
               "historie_von": lo, "historie_bis": hi}
        row.update({k: f[k] for k in
                    ("vor_start", "vor_end", "nach_start", "nach_end",
                     "winter_vor_label", "winter_nach_label",
                     "angeschnitten", "fensteranteil")})
        row["vollstaendig"] = bool(
            pd.notna(lo) and pd.notna(hi)
            and pd.Timestamp(lo) <= f["vor_start"]
            and pd.Timestamp(hi) >= f["nach_end"].normalize()
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values(["datum", "meter"]).reset_index(drop=True)
    return out


def wintervergleich_tabelle(serien: Dict[int, pd.DataFrame],
                            begehungen: pd.DataFrame,
                            variante: str = WINTER_KERN,
                            hdh: Optional[pd.Series] = None,
                            meter_changes: Optional[Dict[int, Sequence[TimestampLike]]] = None,
                            begehungen_je_meter: Optional[Dict[int, Sequence[TimestampLike]]] = None,
                            zusatzspalten: Sequence[str] = ("kategorie",)
                            ) -> pd.DataFrame:
    """Eine Zeile je Begehung mit Zeitreihe, Winter vorher gegen nachher."""
    rows: List[dict] = []
    for _, r in begehungen.iterrows():
        if pd.isna(r.get("meter")) or pd.isna(r.get("datum")):
            continue
        zid = int(r["meter"])
        df = serien.get(zid)
        if df is None or len(df) == 0:
            continue
        row = wintervergleich_fuer_begehung(
            df, r["datum"], variante, hdh,
            meter_changes=(meter_changes or {}).get(zid),
            weitere_begehungen=(begehungen_je_meter or {}).get(zid),
        )
        row["meter"] = zid
        for col in zusatzspalten:
            if col in r.index:
                row[col] = r[col]
        rows.append(row)

    out = pd.DataFrame(rows)
    if len(out) == 0:
        return out
    vorne = ["meter", "datum", "variante", "winter_vor_label",
             "winter_nach_label"]
    return out[vorne + [c for c in out.columns if c not in vorne]]


def winter_kontrollgruppe(serien: Dict[int, pd.DataFrame],
                          datum: TimestampLike,
                          variante: str = WINTER_KERN,
                          hdh: Optional[pd.Series] = None) -> pd.DataFrame:
    """Dieselben Winterfenster fuer Stationen ohne dokumentierte Begehung."""
    rows = []
    for zid, df in serien.items():
        if df is None or len(df) == 0:
            continue
        row = wintervergleich_fuer_begehung(df, datum, variante, hdh)
        row["meter"] = int(zid)
        rows.append(row)
    return pd.DataFrame(rows)


def winter_ausschlussbilanz(tab: pd.DataFrame,
                            min_tagesabdeckung: float = 0.6,
                            min_coverage: float = 0.0,
                            min_fensteranteil: float = 0.6
                            ) -> pd.DataFrame:
    """`tab` um `ausschlussgrund` und `auswertbar` ergaenzen.

    Die Gruende werden in fester Reihenfolge geprueft, damit jede Zeile
    genau einen traegt: zuerst die fehlende Historie, dann der zu stark
    beschnittene Kalenderausschnitt, dann die Abdeckung der beiden
    Fenster. Es wird nichts entfernt - `auswertbar` grenzt nur die
    Teilmenge ab, ueber die anschliessend getestet wird.

    Gemessen wird die Abdeckung in Tagen, nicht in Stunden. Der aeltere
    Teil der Exporte traegt bei einem Teil der Zaehler nur eine Zeile je
    Tag; auf dem Stundenraster sieht ein solcher Dezember nach 57 Prozent
    Abdeckung aus, obwohl kein einziger Tag fehlt. `min_coverage` prueft
    zusaetzlich die Stundenabdeckung und ist voreingestellt
    abgeschaltet; die Auswertung rechnet damit die strengere Variante als
    Gegenprobe, statt sie zur Voreinstellung zu machen.
    """
    out = tab.copy()

    def grund(r) -> str:
        if "vollstaendig" in r.index and not bool(r["vollstaendig"]):
            return "Historie deckt nicht beide Winter"
        if pd.notna(r.get("fensteranteil")) and \
                r["fensteranteil"] < min_fensteranteil:
            return f"Fensteranteil < {min_fensteranteil:.0%}"
        for seite, titel in (("vor", "Vorher-Winter"), ("nach", "Nachher-Winter")):
            tage = r.get(f"tagesabdeckung_{seite}")
            if pd.isna(tage) or tage < min_tagesabdeckung:
                return f"Tagesabdeckung {titel} < {min_tagesabdeckung:.0%}"
        if min_coverage > 0:
            for seite, titel in (("vor", "Vorher-Winter"),
                                 ("nach", "Nachher-Winter")):
                std = r.get(f"coverage_{seite}")
                if pd.isna(std) or std < min_coverage:
                    return f"Stundenabdeckung {titel} < {min_coverage:.0%}"
        return "auswertbar"

    out["ausschlussgrund"] = out.apply(grund, axis=1)
    out["auswertbar"] = out["ausschlussgrund"] == "auswertbar"
    return out
