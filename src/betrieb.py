"""Betrieb bei der ÜZ: Listenverlauf, Begehungsprotokolle und Prüfung nach vorn.

Schließt den Kreislauf aus *Ausblick → Probebetrieb* und *Prüfung nach vorn*:
vorhersagen, begehen, zurückmelden, prüfen.

    python -m src.betrieb liste-sichern        # Handlungsliste mit Datum sichern
    python -m src.betrieb vorlage              # Excel-Vorlage für das Begehungsprotokoll
    python -m src.betrieb protokolle           # ausgefüllte Protokolle einlesen und prüfen
    python -m src.betrieb pruefung-planen      # Stichprobe für die Prüfung nach vorn festlegen
    python -m src.betrieb pruefung-auswerten   # Stichprobe mit dem exakten Test auswerten

1. **Listenverlauf** (`liste_sichern`): Jeder Lauf von `src.aktualisieren`
   legt die Handlungsliste mit Datum unter `outputs/betrieb/listen/` ab.
   Später lässt sich so für jede Begehung sagen, ob und mit welcher
   Dringlichkeit die Station vorher auf der Liste stand.
2. **Begehungsprotokoll** (`vorlage_schreiben`, `protokolle_einlesen`): Die
   Monteure füllen je Begehung eine Zeile aus, vor allem *ob* etwas kaputt
   war und nicht nur, was gemacht wurde. Die ausgefüllten Dateien liegen in
   `data/manual/begehungsprotokolle/`. Beim Einlesen werden sie geprüft, mit
   dem Listenstand vor der Begehung verknüpft und als
   `outputs/betrieb/rueckmeldungen.csv` gesammelt. Jede Zeile ist ein neues
   Label für spätere Prüfungen.
3. **Prüfung nach vorn** (`pruefung_planen`, `pruefung_auswerten`): Die nie
   begangenen Stationen mit dem höchsten Ventil-Score und gleich viele
   zufällig gewählte nie begangene Stationen werden gemischt und ohne
   Gruppe als Begehungsliste ausgegeben. Der Schlüssel, welche Station zu
   welcher Gruppe gehört, und die Erwartung werden vorher festgeschrieben.
   Die Auswertung vergleicht den Anteil der Ventilbefunde beider Gruppen
   mit einem einseitigen exakten Test nach Fisher.

Alle Dateien enthalten nur Zählernummern, keine Adressen. Die Modelle lernen
hier nichts neu (Regel 1 des Probebetriebs).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "outputs" / "dashboard"
BETRIEB = ROOT / "outputs" / "betrieb"
LISTEN = BETRIEB / "listen"
RUECKMELDUNGEN = BETRIEB / "rueckmeldungen.csv"
PROTOKOLLE = ROOT / "data" / "manual" / "begehungsprotokolle"
VORLAGE_NAME = "vorlage_begehungsprotokoll.xlsx"

#Spalten der Handlungsliste, die gesichert werden (aus outputs/dashboard/stationen.parquet)
LISTEN_SPALTEN = ["zaehler", "rang", "dringlichkeit", "handlung", "klasse", "p_ventil",
                  "hinweis_daemmung", "hinweis_vertrag", "letzte_begehung", "tm_status", "lstm_status"]

#Fehlerarten im Protokoll, abgestimmt auf die Kategorien in src/befundcodes.py.
#"anschluss_zu_gross" entspricht dem Hinweis auf Kapazitätsanpassung im Dashboard.
FEHLERARTEN: Dict[str, str] = {
    "Regelventil / Stellantrieb": "ventil_stellantrieb",
    "Schmutzfänger / Filter": "schmutzfaenger",
    "Regler / Parameter": "regler_parameter",
    "Hydraulik / Volumenstrom": "hydraulik_volumenstrom",
    "Zirkulation": "zirkulation",
    "Pumpe": "pumpe",
    "Dämmung": "daemmung",
    "Anschluss zu groß": "anschluss_zu_gross",
    "Messtechnik": "messtechnik",
    "Anlage aus": "anlage_aus",
    "Sonstiges": "sonstiges",
}
KAPUTT = ("ja", "nein", "unklar")
MASSNAHMEN = ("Bauteil getauscht", "neu eingestellt", "gereinigt", "keine", "Sonstiges")

#Spalten der Vorlage: Überschrift für die Monteure -> interner Name
PROTOKOLL_SPALTEN: Dict[str, str] = {
    "Zählernummer": "zaehler",
    "Datum der Begehung": "datum",
    "Etwas kaputt?": "kaputt",
    "Fehlerart": "fehlerart",
    "Zweite Fehlerart": "fehlerart_2",
    "Was war kaputt?": "was_kaputt",
    "Maßnahme": "massnahme",
    "Getauschtes Bauteil": "bauteil",
    "Fehler vermutlich seit": "fehler_seit",
    "Bemerkung": "bemerkung",
}

#Befunde, für die die Modelle eine Vorhersage machen: Spalte im Protokoll -> Spalte der Liste
BEFUNDE = {
    "ventil": ("ventil_stellantrieb", "p_ventil"),
    "daemmung": ("daemmung", "hinweis_daemmung"),
    "anschluss": ("anschluss_zu_gross", "hinweis_vertrag"),
}


def _zaehler(wert) -> Optional[int]:
    """Zählernummer aus Zahl oder Text, führende Nullen und Leerzeichen egal."""
    if wert is None or (isinstance(wert, float) and np.isnan(wert)):
        return None
    ziffern = re.sub(r"\D", "", str(wert).split(".")[0] if isinstance(wert, float) else str(wert))
    return int(ziffern) if ziffern else None


def _leer(wert) -> bool:
    return wert is None or (isinstance(wert, float) and np.isnan(wert)) or str(wert).strip() in ("", "nan", "NaT")


def _text(wert) -> str:
    return "" if _leer(wert) else str(wert).strip()


def _sha256(pfad: Path) -> str:
    return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()


# ------------------------------------------------------------------ A Listenverlauf

def liste_sichern(dashboard: Path = DASHBOARD, ziel: Path = LISTEN,
                  jetzt: Optional[datetime] = None) -> Path:
    """Aktuelle Handlungsliste mit Datum ablegen.

    Liest ``stationen.parquet`` und ``meta.json`` aus ``outputs/dashboard/``
    (geschrieben von `src.dashboard_daten`) und schreibt
    ``handlungsliste_<JJJJ-MM-TT_HHMM>.csv``. Spalten ``stand`` (Zeitpunkt der
    Sicherung), ``datenende`` und die Paketversionen stehen in jeder Zeile,
    damit eine Datei für sich allein verständlich ist.
    """
    dashboard, ziel = Path(dashboard), Path(ziel)
    pfad_st = dashboard / "stationen.parquet"
    if not pfad_st.exists():
        raise SystemExit(f"{pfad_st} fehlt. Erst 'python -m src.dashboard_daten' ausführen.")
    st = pd.read_parquet(pfad_st)
    meta = json.loads((dashboard / "meta.json").read_text(encoding="utf-8")) \
        if (dashboard / "meta.json").exists() else {}
    jetzt = jetzt or datetime.now()
    liste = st[[s for s in LISTEN_SPALTEN if s in st.columns]].copy()
    liste.insert(0, "stand", jetzt.isoformat(timespec="minutes"))
    liste["datenende"] = meta.get("datenende", "")
    for name, version in (meta.get("pakete") or {}).items():
        liste[f"paket_{name}"] = version
    ziel.mkdir(parents=True, exist_ok=True)
    pfad = ziel / f"handlungsliste_{jetzt:%Y-%m-%d_%H%M}.csv"
    liste.to_csv(pfad, index=False, encoding="utf-8")
    return pfad


def listen_laden(ordner: Path = LISTEN) -> pd.DataFrame:
    """Alle gesicherten Handlungslisten untereinander, Spalte ``stand`` als Zeitpunkt."""
    dateien = sorted(Path(ordner).glob("handlungsliste_*.csv"))
    if not dateien:
        return pd.DataFrame(columns=["stand", *LISTEN_SPALTEN])
    df = pd.concat([pd.read_csv(p) for p in dateien], ignore_index=True)
    df["stand"] = pd.to_datetime(df["stand"])
    df["zaehler"] = df["zaehler"].map(_zaehler)
    return df


def letzte_liste(ordner: Path = LISTEN) -> pd.DataFrame:
    """Die jüngste gesicherte Handlungsliste."""
    df = listen_laden(ordner)
    if df.empty:
        raise SystemExit(f"Keine Handlungsliste in {ordner}. Erst 'python -m src.aktualisieren' oder "
                         "'python -m src.betrieb liste-sichern' ausführen.")
    return df[df["stand"] == df["stand"].max()].reset_index(drop=True)


def listenstand_vor(listen: pd.DataFrame, zaehler: int, datum: pd.Timestamp) -> Optional[pd.Series]:
    """Zeile der jüngsten Liste, die spätestens am Tag der Begehung gesichert wurde."""
    if listen.empty:
        return None
    kandidaten = listen[(listen["zaehler"] == zaehler)
                        & (listen["stand"].dt.normalize() <= pd.Timestamp(datum).normalize())]
    if kandidaten.empty:
        return None
    return kandidaten.loc[kandidaten["stand"].idxmax()]


# ------------------------------------------------------------------ B Begehungsprotokoll

def vorlage_schreiben(pfad: Optional[Path] = None) -> Path:
    """Excel-Vorlage mit Auswahllisten und einem Blatt mit Hinweisen schreiben."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    pfad = Path(pfad) if pfad else PROTOKOLLE / VORLAGE_NAME
    wb = Workbook()
    ws = wb.active
    ws.title = "Protokoll"
    kopf = list(PROTOKOLL_SPALTEN)
    ws.append(kopf)
    for zelle in ws[1]:
        zelle.font = Font(bold=True, color="FFFFFF")
        zelle.fill = PatternFill("solid", fgColor="2F5597")
        zelle.alignment = Alignment(wrap_text=True, vertical="top")
    breiten = [14, 16, 12, 26, 26, 40, 18, 24, 18, 40]
    for i, b in enumerate(breiten, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = b
    ws.freeze_panes = "A2"

    #Auswahllisten stehen auf einem eigenen Blatt, damit sie nicht an der Länge einer Formel scheitern
    listen = wb.create_sheet("Auswahl")
    for i, werte in enumerate((KAPUTT, list(FEHLERARTEN), MASSNAHMEN), start=1):
        for j, w in enumerate(werte, start=1):
            listen.cell(j, i, w)
    listen.sheet_state = "hidden"
    n = 500
    for spalte, bereich in (("C", f"Auswahl!$A$1:$A${len(KAPUTT)}"),
                            ("D", f"Auswahl!$B$1:$B${len(FEHLERARTEN)}"),
                            ("E", f"Auswahl!$B$1:$B${len(FEHLERARTEN)}"),
                            ("G", f"Auswahl!$C$1:$C${len(MASSNAHMEN)}")):
        dv = DataValidation(type="list", formula1=f"={bereich}", allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{spalte}2:{spalte}{n}")
    dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(2020,1,1)", allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"B2:B{n}")
    for zeile in range(2, n + 1):
        ws.cell(zeile, 2).number_format = "DD.MM.YYYY"

    hinweise = wb.create_sheet("Hinweise")
    text = [
        ("Begehungsprotokoll", ""),
        ("", ""),
        ("Eine Zeile je Begehung.", ""),
        ("Zählernummer", "Pflicht. Nummer des Wärmezählers, wie auf dem Zähler oder im Dashboard."),
        ("Datum der Begehung", "Pflicht. Tag, an dem die Station vor Ort geprüft wurde."),
        ("Etwas kaputt?", "Pflicht. ja, nein oder unklar. Wichtig: ob etwas defekt war, nicht ob etwas getan wurde."),
        ("Fehlerart", "Pflicht, wenn 'ja'. Was war defekt oder falsch eingestellt?"),
        ("Zweite Fehlerart", "Optional, wenn mehr als ein Fehler vorlag."),
        ("Was war kaputt?", "Kurze Beschreibung in eigenen Worten."),
        ("Maßnahme", "Was wurde gemacht?"),
        ("Getauschtes Bauteil", "Optional, z. B. Stellantrieb, Ventil, Fühler."),
        ("Fehler vermutlich seit", "Optional. Schätzung, seit wann der Fehler besteht (Datum oder Text)."),
        ("Bemerkung", "Optional."),
        ("", ""),
        ("Nicht eintragen", "Ob die Station auf der Handlungsliste stand. Das ergänzt das Einlesen "
                            "automatisch aus dem Listenverlauf, damit die Begehung unvoreingenommen bleibt."),
        ("Ablage", "Ausgefüllte Datei in data/manual/begehungsprotokolle/ speichern, Dateiname frei, "
                   "z. B. protokoll_2026-12.xlsx. Danach: python -m src.betrieb protokolle"),
    ]
    for zeile in text:
        hinweise.append(zeile)
    hinweise["A1"].font = Font(bold=True, size=14)
    hinweise.column_dimensions["A"].width = 26
    hinweise.column_dimensions["B"].width = 100
    for zeile in hinweise.iter_rows(min_row=4):
        zeile[0].font = Font(bold=True)
        zeile[1].alignment = Alignment(wrap_text=True, vertical="top")

    pfad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pfad)
    return pfad


def _protokoll_lesen(pfad: Path) -> pd.DataFrame:
    df = pd.read_excel(pfad, sheet_name=0, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    fehlen = [k for k in PROTOKOLL_SPALTEN if k not in df.columns]
    if fehlen:
        raise ValueError(f"{pfad.name}: Spalten fehlen: {', '.join(fehlen)}")
    df = df[list(PROTOKOLL_SPALTEN)].rename(columns=PROTOKOLL_SPALTEN)
    df["quelle"] = pfad.name
    df["zeile"] = df.index + 2
    return df[~df.drop(columns=["quelle", "zeile"]).map(_leer).all(axis=1)]


def _befund(kaputt: str, codes: Sequence[str], code: str):
    """True: dieser Fehler lag vor. False: geprüft, lag nicht vor. NaN: unklar."""
    if kaputt == "ja":
        return code in codes
    if kaputt == "nein":
        return False
    return np.nan


def protokolle_einlesen(ordner: Path = PROTOKOLLE, listen_ordner: Path = LISTEN,
                        ziel: Optional[Path] = RUECKMELDUNGEN,
                        heute: Optional[pd.Timestamp] = None) -> Tuple[pd.DataFrame, List[str]]:
    """Alle ausgefüllten Protokolle einlesen, prüfen und mit dem Listenstand verknüpfen.

    Rückgabe: (gültige Rückmeldungen, Liste der Hinweise). Zeilen mit einem
    Fehler werden nicht übernommen, der Hinweis nennt Datei und Zeile.
    """
    ordner = Path(ordner)
    heute = pd.Timestamp(heute or pd.Timestamp.now()).normalize()
    dateien = sorted(p for p in ordner.glob("*.xlsx") if p.name != VORLAGE_NAME and not p.name.startswith("~$"))
    hinweise: List[str] = []
    teile = []
    for p in dateien:
        try:
            teile.append(_protokoll_lesen(p))
        except ValueError as exc:
            hinweise.append(str(exc))
    roh = pd.concat(teile, ignore_index=True) if teile else pd.DataFrame(
        columns=[*PROTOKOLL_SPALTEN.values(), "quelle", "zeile"])

    listen = listen_laden(listen_ordner)
    bekannt = set(listen["zaehler"].dropna().astype(int)) if not listen.empty else set()
    zeilen = []
    gesehen = set()
    for r in roh.itertuples(index=False):
        wo = f"{r.quelle}, Zeile {r.zeile}"
        z = _zaehler(r.zaehler)
        if z is None:
            hinweise.append(f"{wo}: Zählernummer fehlt")
            continue
        datum = pd.to_datetime(r.datum, errors="coerce", dayfirst=True)
        if pd.isna(datum):
            hinweise.append(f"{wo}: Datum der Begehung fehlt oder ist unlesbar")
            continue
        datum = datum.normalize()
        if datum > heute:
            hinweise.append(f"{wo}: Datum {datum:%d.%m.%Y} liegt in der Zukunft")
            continue
        kaputt = _text(r.kaputt).lower()
        if kaputt not in KAPUTT:
            hinweise.append(f"{wo}: 'Etwas kaputt?' muss ja, nein oder unklar sein")
            continue
        codes = []
        for feld in (r.fehlerart, r.fehlerart_2):
            t = _text(feld)
            if not t:
                continue
            if t not in FEHLERARTEN:
                hinweise.append(f"{wo}: unbekannte Fehlerart '{t}', als Sonstiges übernommen")
                t = "Sonstiges"
            codes.append(FEHLERARTEN[t])
        if kaputt == "ja" and not codes:
            hinweise.append(f"{wo}: 'Etwas kaputt?' ist ja, aber keine Fehlerart angegeben")
            continue
        if (z, datum) in gesehen:
            hinweise.append(f"{wo}: Begehung {z} am {datum:%d.%m.%Y} doppelt, nur der erste Eintrag zählt")
            continue
        gesehen.add((z, datum))
        if bekannt and z not in bekannt:
            hinweise.append(f"{wo}: Zählernummer {z} steht in keiner gesicherten Handlungsliste")

        zeile = {"zaehler": z, "datum": datum.date().isoformat(), "kaputt": kaputt,
                 "fehlerart": codes[0] if codes else "", "fehlerart_2": codes[1] if len(codes) > 1 else "",
                 "was_kaputt": _text(r.was_kaputt), "massnahme": _text(r.massnahme),
                 "bauteil": _text(r.bauteil), "fehler_seit": _text(r.fehler_seit),
                 "bemerkung": _text(r.bemerkung), "quelle": r.quelle, "zeile": r.zeile}
        for name, (code, _) in BEFUNDE.items():
            zeile[f"befund_{name}"] = _befund(kaputt, codes, code)
        vorher = listenstand_vor(listen, z, datum)
        zeile["liste_stand"] = "" if vorher is None else pd.Timestamp(vorher["stand"]).isoformat(timespec="minutes")
        for spalte in ("rang", "dringlichkeit", "handlung", "p_ventil", "hinweis_daemmung", "hinweis_vertrag"):
            zeile[f"liste_{spalte}"] = np.nan if vorher is None else vorher.get(spalte, np.nan)
        zeilen.append(zeile)

    spalten = ["zaehler", "datum", "kaputt", "fehlerart", "fehlerart_2", "was_kaputt", "massnahme", "bauteil",
               "fehler_seit", "bemerkung", "quelle", "zeile", *[f"befund_{n}" for n in BEFUNDE], "liste_stand",
               *[f"liste_{s}" for s in ("rang", "dringlichkeit", "handlung", "p_ventil", "hinweis_daemmung",
                                        "hinweis_vertrag")]]
    ergebnis = pd.DataFrame(zeilen, columns=spalten)
    if not ergebnis.empty:
        ergebnis = ergebnis.sort_values(["datum", "zaehler"]).reset_index(drop=True)
        ohne = int((ergebnis["liste_stand"] == "").sum())
        if ohne:
            hinweise.append(f"{ohne} Begehungen ohne gesicherte Handlungsliste davor")
    if ziel is not None:
        Path(ziel).parent.mkdir(parents=True, exist_ok=True)
        ergebnis.to_csv(ziel, index=False, encoding="utf-8")
    return ergebnis, hinweise


def rueckmeldungen_laden(pfad: Path = RUECKMELDUNGEN) -> pd.DataFrame:
    if not Path(pfad).exists():
        return pd.DataFrame(columns=["zaehler", "datum", *[f"befund_{n}" for n in BEFUNDE]])
    df = pd.read_csv(pfad)
    df["datum"] = pd.to_datetime(df["datum"])
    return df


# ------------------------------------------------------------------ C Prüfung nach vorn

def pruefung_planen(anzahl: int = 10, seed: Optional[int] = None, listen_ordner: Path = LISTEN,
                    rueckmeldungen: Path = RUECKMELDUNGEN, ziel: Path = BETRIEB,
                    jetzt: Optional[datetime] = None) -> Path:
    """Stichprobe für die Prüfung nach vorn festlegen und festschreiben.

    Gruppe ``hoch``: die ``anzahl`` nie begangenen Stationen mit dem höchsten
    Ventil-Score. Gruppe ``zufall``: ``anzahl`` zufällig gezogene aus den
    übrigen nie begangenen Stationen mit Ventil-Score. Nie begangen heißt: in
    der jüngsten Handlungsliste ohne letzte Begehung und ohne Rückmeldung.

    Schreibt in ``pruefung_<JJJJ-MM-TT_HHMM>/``:

    - ``begehungsliste.csv``: beide Gruppen gemischt, ohne Gruppe und Score,
      für das Team vor Ort
    - ``schluessel.csv``: Gruppe und Score je Station, nicht weitergeben
    - ``plan.json``: Zeitpunkt, Listenstand, Seed, Erwartung, Test und
      Prüfsummen beider Dateien
    """
    jetzt = jetzt or datetime.now()
    ordner = Path(ziel) / f"pruefung_{jetzt:%Y-%m-%d_%H%M}"
    if ordner.exists():
        raise SystemExit(f"{ordner} gibt es schon. Ein festgelegter Plan wird nicht überschrieben.")
    liste = letzte_liste(listen_ordner)
    begangen = set(rueckmeldungen_laden(rueckmeldungen)["zaehler"].dropna().astype(int))
    offen = liste[liste["letzte_begehung"].map(_leer) & ~liste["zaehler"].isin(begangen)
                  & liste["p_ventil"].notna()].copy()
    if len(offen) < 2 * anzahl:
        raise SystemExit(f"Nur {len(offen)} nie begangene Stationen mit Ventil-Score, für zwei Gruppen "
                         f"zu je {anzahl} braucht es {2 * anzahl}. Kleinere Anzahl wählen (--anzahl).")
    seed = int(seed if seed is not None else jetzt.strftime("%Y%m%d%H%M"))
    rng = np.random.default_rng(seed)
    offen = offen.sort_values(["p_ventil", "zaehler"], ascending=[False, True])
    hoch = offen.head(anzahl).assign(gruppe="hoch")
    rest = offen.iloc[anzahl:]
    zufall = rest.iloc[np.sort(rng.choice(len(rest), size=anzahl, replace=False))].assign(gruppe="zufall")
    schluessel = pd.concat([hoch, zufall])[["zaehler", "gruppe", "p_ventil", "rang", "dringlichkeit",
                                            "hinweis_daemmung", "hinweis_vertrag"]]
    schluessel = schluessel.iloc[rng.permutation(len(schluessel))].reset_index(drop=True)
    begehungsliste = pd.DataFrame({"nr": range(1, len(schluessel) + 1), "zaehler": schluessel["zaehler"]})

    ordner.mkdir(parents=True)
    begehungsliste.to_csv(ordner / "begehungsliste.csv", index=False, encoding="utf-8")
    schluessel.to_csv(ordner / "schluessel.csv", index=False, encoding="utf-8")
    plan = {
        "erstellt": jetzt.isoformat(timespec="minutes"),
        "listenstand": pd.Timestamp(liste["stand"].iloc[0]).isoformat(timespec="minutes"),
        "datenende": str(liste.get("datenende", pd.Series([""])).iloc[0]),
        "pakete": {c.removeprefix("paket_"): str(liste[c].iloc[0]) for c in liste.columns if c.startswith("paket_")},
        "anzahl_je_gruppe": anzahl,
        "seed": seed,
        "auswahl": {
            "hoch": "nie begangene Stationen mit dem höchsten Ventil-Score",
            "zufall": "zufällig aus den übrigen nie begangenen Stationen mit Ventil-Score",
        },
        "erwartung": "Der Anteil der Ventilbefunde ist in der Gruppe 'hoch' größer als in der Gruppe 'zufall'.",
        "test": "exakter Test nach Fisher, einseitig, Signifikanzniveau 0,05",
        "zaehlweise": "erste Rückmeldung je Station nach dem Erstellen des Plans; 'unklar' zählt nicht",
        "nebenfragen": "Dämmung und Anschluss zu groß: Anteil der Befunde mit und ohne Hinweis im Dashboard",
        "pruefsummen": {"begehungsliste.csv": _sha256(ordner / "begehungsliste.csv"),
                        "schluessel.csv": _sha256(ordner / "schluessel.csv")},
    }
    (ordner / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return ordner


def _fisher(a: int, b: int, c: int, d: int) -> float:
    """Einseitiger exakter Test: ist der Anteil a/(a+b) größer als c/(c+d)?"""
    from scipy.stats import fisher_exact
    if (a + b) == 0 or (c + d) == 0:
        return float("nan")
    return float(fisher_exact([[a, b], [c, d]], alternative="greater")[1])


def _anteil(n: int, k: int) -> str:
    return f"{k} von {n} ({round(100 * k / n)} %)" if n else "keine"


def pruefung_auswerten(ordner: Optional[Path] = None, rueckmeldungen: Path = RUECKMELDUNGEN,
                       ziel_name: str = "auswertung.txt") -> str:
    """Festgelegte Stichprobe mit den Rückmeldungen auswerten und den Bericht schreiben."""
    if ordner is None:
        plaene = sorted(BETRIEB.glob("pruefung_*"))
        if not plaene:
            raise SystemExit("Kein Plan gefunden. Erst 'python -m src.betrieb pruefung-planen' ausführen.")
        ordner = plaene[-1]
    ordner = Path(ordner)
    plan = json.loads((ordner / "plan.json").read_text(encoding="utf-8"))
    schluessel = pd.read_csv(ordner / "schluessel.csv")
    warnungen = [f"{n} wurde nach dem Festlegen verändert"
                 for n, h in plan["pruefsummen"].items() if _sha256(ordner / n) != h]

    rm = rueckmeldungen_laden(rueckmeldungen)
    start = pd.Timestamp(plan["erstellt"]).normalize()
    rm = rm[rm["datum"] >= start].sort_values("datum").drop_duplicates("zaehler")
    df = schluessel.merge(rm, on="zaehler", how="left")

    z = [f"Prüfung nach vorn, Plan vom {pd.Timestamp(plan['erstellt']):%d.%m.%Y %H:%M}",
         f"Listenstand {pd.Timestamp(plan['listenstand']):%d.%m.%Y}, je Gruppe {plan['anzahl_je_gruppe']} Stationen, "
         f"Seed {plan['seed']}",
         f"Erwartung: {plan['erwartung']}", f"Test: {plan['test']}", ""]
    z += [f"WARNUNG: {w}" for w in warnungen] + ([""] if warnungen else [])

    z.append("Ventil (Hauptfrage)")
    zahlen = {}
    for g in ("hoch", "zufall"):
        teil = df[df["gruppe"] == g]
        begangen = teil["datum"].notna().sum()
        gewertet = teil["befund_ventil"].dropna().astype(bool)
        zahlen[g] = (int(gewertet.sum()), int((~gewertet).sum()))
        z.append(f"  {g:7s} geplant {len(teil)}, begangen {begangen}, gewertet {len(gewertet)}, "
                 f"Ventilbefund {_anteil(len(gewertet), int(gewertet.sum()))}")
    p = _fisher(*zahlen["hoch"], *zahlen["zufall"])
    z.append(f"  p (einseitig) = {p:.3f}".replace(".", ",") if not np.isnan(p) else "  noch keine Rückmeldungen")
    offen = int(df["datum"].isna().sum())
    if offen:
        z.append(f"  noch nicht begangen: {offen} von {len(df)}")
    z.append("")

    z.append("Nebenfragen (alle begangenen Stationen der Stichprobe)")
    for name, (_, spalte) in BEFUNDE.items():
        if name == "ventil":
            continue
        teil = df[df[f"befund_{name}"].notna()]
        hinweis = teil[spalte].map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))
        befund = teil[f"befund_{name}"].astype(bool)
        mit, ohne = befund[hinweis], befund[~hinweis]
        p = _fisher(int(mit.sum()), int((~mit).sum()), int(ohne.sum()), int((~ohne).sum()))
        z.append(f"  {name:9s} mit Hinweis {_anteil(len(mit), int(mit.sum()))}, ohne Hinweis "
                 f"{_anteil(len(ohne), int(ohne.sum()))}"
                 + (f", p (einseitig) = {p:.3f}".replace(".", ",") if not np.isnan(p) else ""))
    z += ["", "Bei so kleinen Gruppen ist der Test grob. Ein p über 0,05 heißt nicht, dass das Modell nichts taugt,"
          " sondern dass die Fälle für eine Aussage nicht reichen."]
    text = "\n".join(z) + "\n"
    (ordner / ziel_name).write_text(text, encoding="utf-8")
    return text


# ------------------------------------------------------------------ Befehlszeile

def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="befehl", required=True)
    sub.add_parser("liste-sichern", help="aktuelle Handlungsliste mit Datum sichern")
    sub.add_parser("vorlage", help="Excel-Vorlage für das Begehungsprotokoll schreiben")
    sub.add_parser("protokolle", help="ausgefüllte Protokolle einlesen und prüfen")
    pp = sub.add_parser("pruefung-planen", help="Stichprobe für die Prüfung nach vorn festlegen")
    pp.add_argument("--anzahl", type=int, default=10, help="Stationen je Gruppe (Standard 10)")
    pp.add_argument("--seed", type=int, default=None, help="Startwert für die Zufallsauswahl")
    pa = sub.add_parser("pruefung-auswerten", help="festgelegte Stichprobe auswerten")
    pa.add_argument("ordner", nargs="?", type=Path, default=None,
                    help="Ordner des Plans, sonst der jüngste unter outputs/betrieb/")
    args = p.parse_args(argv)

    if args.befehl == "liste-sichern":
        print("Handlungsliste gesichert:", liste_sichern())
    elif args.befehl == "vorlage":
        print("Vorlage geschrieben:", vorlage_schreiben())
    elif args.befehl == "protokolle":
        df, hinweise = protokolle_einlesen()
        print(f"{len(df)} Begehungen übernommen nach {RUECKMELDUNGEN}")
        if len(df):
            print(f"  davon etwas kaputt: {int((df['kaputt'] == 'ja').sum())}, "
                  f"Ventilbefund: {int(df['befund_ventil'].fillna(False).astype(bool).sum())}")
        for h in hinweise:
            print("  Hinweis:", h)
    elif args.befehl == "pruefung-planen":
        ordner = pruefung_planen(anzahl=args.anzahl, seed=args.seed)
        print("Plan festgelegt:", ordner)
        print("  begehungsliste.csv an das Team vor Ort geben, schluessel.csv nicht.")
    elif args.befehl == "pruefung-auswerten":
        protokolle_einlesen()
        print(pruefung_auswerten(args.ordner))


if __name__ == "__main__":
    main()
