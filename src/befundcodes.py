"""Regelbasierte Kodierung der Begehungs-Freitexte.

Die Begehungstabelle hat strukturierte Alt/Neu-Sollwerte und eine
Freitextspalte "Sonstiges". Was vor Ort gefunden wurde, steht oft nur im
Freitext (57 von 66 Begehungen haben einen Eintrag). Dieses Modul macht
daraus Mehrfachlabels.

- regelbasiert: 57 Notizen lassen sich von Hand pruefen, eine
  Stichwortliste ist reproduzierbar und korrigierbar
- eine Notiz darf mehrere Labels bekommen

Verneinungen
------------
- "fast leer", "passt", "ist gedaemmt" wuerden als reiner
  Stichworttreffer faelschlich zum Fehler
- jede Kategorie hat deshalb Vetomuster, gesucht in einem kurzen Fenster
  hinter dem Treffer
- nach links wird nicht gesucht: die Notizen haben keine Satzzeichen,
  ein Veto wuerde sonst Befunde zu anderen Bauteilen loeschen
- fuer vorangestellte Verneinungen ("schwerkraft zirkulation") gibt es
  eine eigene Liste, die nach links schaut

Kontextlabels
-------------
Fussbodenheizung, Heizkoerper, Holzfeuerung und Baujahr sind keine
Fehler, sondern beschreiben die Anlage. Sie werden getrennt ausgewiesen.

Grenzen
-------
Der Freitext ist ein Gedaechtnisprotokoll. Was nicht notiert wurde,
fehlt auch hier.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from . import load_begehungen as lb

#Fenster hinter einem Treffer, in dem nach einem Veto gesucht wird. 25
#Zeichen decken die beobachteten Faelle ab ("schmutzfaenger fast leer",
#"volumenstrom passt"), ohne in den naechsten Gedanken zu rutschen.
VETO_FENSTER = 25

#Fenster vor einem Treffer, nur fuer die Faelle, in denen die
#Einschraenkung vorangeht ("schwerkraft zirkulation").
VETO_FENSTER_DAVOR = 20

UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                         "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def normalisiere(text: object) -> str:
    """Kleinschreibung, Umlaute aufgeloest, Leerraum zusammengezogen."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    s = str(text).translate(UMLAUTE).lower()
    return re.sub(r"\s+", " ", s).strip()


#Fehlerkategorien. Je Kategorie die Treffermuster und die Vetomuster.
BEFUNDE: Dict[str, Dict[str, Sequence[str]]] = {
    "schmutzfaenger": {
        "treffer": [r"schmutzfaenger", r"schmutzfilter", r"\bfilter\b"],
        "veto_danach": [r"^ (fast )?leer", r"^ sauber", r"^ passt",
                        r"^ in ordnung"],
        "veto_davor": [],
    },
    "ventil_stellantrieb": {
        #"stellantireb" ist ein Tippfehler im Original und kommt genau
        #einmal vor; das Muster faengt beide Schreibweisen
        "treffer": [r"regelventil", r"stellventil", r"stellmot\w*",
                    r"stellant\w*", r"\bamv\s*\d", r"\bventile?\b",
                    r"regler schliesst nicht"],
        "veto_danach": [r"^ passt", r"^ in ordnung"],
        "veto_davor": [],
    },
    "regler_parameter": {
        "treffer": [r"anlagenkennziffer", r"anlagenschema",
                    r"anlagenkonfiguration", r"regler verstellt",
                    r"regler zeigt", r"\berror\b",
                    r"regler laesst sich schwer", r"fahrweise",
                    r"\buhr\b", r"verstellt", r"zu wenig leistung"],
        "veto_danach": [r"^ passt", r"^ in ordnung"],
        "veto_davor": [],
    },
    "zirkulation": {
        #"naturzirkulation" und "schwerkraft zirkulation" beschreiben die
        #Anlagenbauart, keinen Fehler; die Wortgrenze faengt den ersten
        #Fall, das Rueckwaertsveto den zweiten
        "treffer": [r"zirk\w* pumpe", r"zirkulationspumpe", r"\bzirk\b",
                    r"\bzirkulation", r"fehlzirkulation"],
        "veto_danach": [r"^ passt", r"^ in ordnung"],
        "veto_davor": [r"schwerkraft\s*$", r"natur\w*\s*$"],
    },
    "pumpe": {
        #Pumpe meint hier Heiz- und Ruecklaufkreis; die defekte
        #Zirkulationspumpe laeuft unter zirkulation
        "treffer": [r"heizkreispumpe", r"rw pumpoe", r"rw pumpe",
                    r"(?<!zirk )pumpe defekt", r"pumpe laeuft nicht"],
        "veto_danach": [r"^ passt", r"^ in ordnung"],
        "veto_davor": [],
    },
    "hydraulik_volumenstrom": {
        "treffer": [r"volumenstrom", r"durchfluss", r"hydraulisch\w* abgleich",
                    r"hydraulik nicht richtig", r"druck ist zu niedrig",
                    r"hoher sekundaerdruck", r"eingeregelt"],
        "veto_danach": [r"^ passt", r"^ in ordnung"],
        "veto_davor": [],
    },
    "daemmung": {
        "treffer": [r"daemmung fehlt", r"ungedaemmt", r"nicht so gut gedaemmt",
                    r"keine daemmung"],
        "veto_danach": [],
        "veto_davor": [],
    },
    "messtechnik": {
        #Plombieren ist Routine und kein Befund, deshalb nicht in der Liste
        "treffer": [r"zaehler\w*(?: von \d+)? muesste\w?.{0,20}getauscht",
                    r"batterie vom zaehler", r"\bm-?bus\b"],
        "veto_danach": [],
        "veto_davor": [],
    },
    "anlage_aus": {
        #Fuer die Zeitreihen der wichtigste Befund ueberhaupt: wo das
        #Gebaeude leer steht oder die Heizung abgeschaltet ist, ist
        #Stillstand kein Fehler, sondern erklaert
        "treffer": [r"haus steht leer", r"heizung laeuft .{0,12}nicht",
                    r"heizung wird im sommer ausgeschaltet"],
        "veto_danach": [],
        "veto_davor": [],
    },
}

#Kontextlabels. Keine Fehler, sondern Anlagenbeschreibung.
KONTEXT: Dict[str, Sequence[str]] = {
    "fussbodenheizung": [r"fussbodenheizung", r"fussbodenhiezung", r"\bfbh\b",
                         r"nur fussboden", r"\bfussboden\b"],
    "heizkoerper": [r"heizkoerper", r"radiator", r"\bhk\b", r"gliederheizkoerper",
                    r"gleiderheizkoerper"],
    "holzfeuerung": [r"beistellofen", r"holzofen", r"holzoefen", r"kaminofen",
                     r"holzkessel", r"mit holz geheizt", r"holz geheizt"],
    "naturumlauf": [r"naturumlauf", r"naturzirkulation", r"schwerkraft"],
}

BAUJAHR_MUSTER = [
    re.compile(r"baujahr\s*(?:ca\.?\s*)?(\d{4})"),
    re.compile(r"\bbj\s*(\d{4})"),
    re.compile(r"(\d{4})\s*\bbj\b"),
    re.compile(r"(\d{4})\s*baujahr"),
]


def _trifft(text: str, muster: str, danach: Iterable[str],
            davor: Iterable[str] = ()) -> bool:
    """Trifft ``muster``, ohne dass ein Veto den Treffer aufhebt?

    ``danach`` wird gegen das Stueck hinter dem Treffer geprueft, ``davor``
    gegen das Stueck davor. Die Muster in ``danach`` sind mit ``^``
    verankert gedacht, damit "passt" nur direkt hinter dem Stichwort
    zaehlt und nicht irgendwo im naechsten Gedanken.
    """
    danach = list(danach)
    davor = list(davor)
    for fund in re.finditer(muster, text):
        rechts = text[fund.end():fund.end() + VETO_FENSTER]
        links = text[max(0, fund.start() - VETO_FENSTER_DAVOR):fund.start()]
        if any(re.search(v, rechts) for v in danach):
            continue
        if any(re.search(v, links) for v in davor):
            continue
        return True
    return False


def kodiere_text(text: object) -> Dict[str, object]:
    """Labels einer einzelnen Notiz.

    Liefert je Fehler- und Kontextkategorie einen Wahrheitswert, dazu das
    Baujahr, sofern eines genannt ist, und die Zahl der Fehlerlabels.
    """
    s = normalisiere(text)
    out: Dict[str, object] = {}
    for name, regeln in BEFUNDE.items():
        out[name] = any(_trifft(s, m, regeln["veto_danach"],
                                regeln["veto_davor"])
                        for m in regeln["treffer"])
    for name, muster in KONTEXT.items():
        out[name] = any(re.search(m, s) for m in muster)

    jahr = None
    for muster in BAUJAHR_MUSTER:
        fund = muster.search(s)
        if fund:
            kandidat = int(fund.group(1))
            if 1800 <= kandidat <= 2030:
                jahr = kandidat
                break
    out["baujahr"] = jahr
    out["n_befunde"] = sum(bool(out[name]) for name in BEFUNDE)
    out["text_vorhanden"] = bool(s)
    return out


def kodiere_begehungen(beg: Optional[pd.DataFrame] = None,
                       spalte: str = "sonstiges") -> pd.DataFrame:
    """Kodiert alle Begehungen und haengt die Labels an.

    Ohne Argument wird :func:`load_begehungen.begehungen_mit_zaehler`
    geladen, damit die Zaehlernummer mitkommt.
    """
    if beg is None:
        beg = lb.begehungen_mit_zaehler()
    labels = pd.DataFrame([kodiere_text(t) for t in beg[spalte]],
                          index=beg.index)
    return pd.concat([beg, labels], axis=1)


def rangliste(kodiert: pd.DataFrame,
              nenner: Optional[int] = None) -> pd.DataFrame:
    """Haeufigkeit je Fehlerkategorie, absteigend.

    ``nenner`` ist die Bezugsgroesse des Anteils; ohne Angabe die Zahl der
    Begehungen mit Freitext. Ohne Nenner ist eine Haeufigkeit nicht
    interpretierbar, deshalb steht er in der Ausgabe.
    """
    mit_text = kodiert[kodiert["text_vorhanden"]]
    if nenner is None:
        nenner = len(mit_text)
    zeilen = []
    for name in BEFUNDE:
        n = int(mit_text[name].sum())
        zeilen.append({"befund": name, "n": n, "nenner": nenner,
                       "anteil": n / nenner if nenner else float("nan")})
    out = pd.DataFrame(zeilen).sort_values("n", ascending=False)
    return out.reset_index(drop=True)


#Welche strukturierte Spalte sollte zu welchem Freitextbefund passen?
#Nur dort, wo die Tabelle ueberhaupt etwas Vergleichbares fuehrt.
ABGLEICH: Mapping[str, Sequence[str]] = {
    "regler_parameter": ("rw_soll_tag", "rw_soll_nacht", "tww_soll",
                         "heizzeit", "tww"),
}

_ALT_NEU = [("heizzeit_alt_von", "heizzeit_neu_von"),
            ("heizzeit_alt_bis", "heizzeit_neu_bis"),
            ("tww_alt_von", "tww_neu_von"),
            ("tww_alt_bis", "tww_neu_bis"),
            ("rw_soll_tag_alt", "rw_soll_tag_neu"),
            ("rw_soll_nacht_alt", "rw_soll_nacht_neu"),
            ("tww_soll_alt", "tww_soll_neu")]


def sollwert_geaendert(zeile: Mapping) -> bool:
    """Weicht in der Zeile mindestens ein Neu- vom Alt-Wert ab?"""
    for alt, neu in _ALT_NEU:
        a, n = zeile.get(alt), zeile.get(neu)
        if pd.isna(a) or pd.isna(n):
            continue
        if str(a).strip() != str(n).strip():
            return True
    return False


def diskrepanzen(kodiert: pd.DataFrame) -> pd.DataFrame:
    """Vierfeldertafel Freitextbefund gegen dokumentierte Sollwertaenderung.

    Die Tabelle ist selbst ein Befund zur Labelqualitaet: wo der Freitext
    einen Eingriff nennt, die Alt/Neu-Spalten aber gleich bleiben, ist die
    strukturierte Spalte unvollstaendig, und umgekehrt.
    """
    k = kodiert.copy()
    k["sollwert_geaendert"] = k.apply(sollwert_geaendert, axis=1)
    k["befund_im_text"] = k["n_befunde"] > 0
    tafel = (k.groupby(["befund_im_text", "sollwert_geaendert"])
             .size().rename("n").reset_index())
    tafel["anteil"] = tafel["n"] / len(k)
    return tafel


def unkodiert(kodiert: pd.DataFrame, spalte: str = "sonstiges") -> pd.DataFrame:
    """Notizen mit Text, aber ohne Fehlerlabel.

    Zum Nachpruefen von Hand gedacht. Entweder beschreibt die Notiz nur
    den Gebaeudekontext, oder der Kodierer hat etwas uebersehen.
    """
    mask = kodiert["text_vorhanden"] & (kodiert["n_befunde"] == 0)
    spalten = ["nr", "datum", "meter", "kategorie", spalte]
    vorhanden = [s for s in spalten if s in kodiert.columns]
    vorhanden += [s for s in KONTEXT if s in kodiert.columns]
    return kodiert.loc[mask, vorhanden].reset_index(drop=True)


def labels_je_zaehler(kodiert: pd.DataFrame) -> pd.DataFrame:
    """Labels auf Zaehlerebene zusammengefasst.

    Eine Adresse kann mehrere Begehungen haben; die Labels werden dann
    verodert. Zeilen ohne Zaehlernummer fallen heraus.
    """
    k = kodiert[kodiert["meter"].notna()].copy()
    k["meter"] = k["meter"].astype(int)
    spalten: List[str] = list(BEFUNDE) + list(KONTEXT)
    gruppe = k.groupby("meter")[spalten].any()
    gruppe["n_befunde"] = gruppe[list(BEFUNDE)].sum(axis=1)
    jahr = k.groupby("meter")["baujahr"].min()
    gruppe["baujahr"] = jahr
    return gruppe.reset_index()
