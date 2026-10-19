"""
Regelbasierte Kodierung der Begehungs-Freitexte in Fehlerkategorien.

Warum ueberhaupt kodieren
-------------------------
In der Begehungstabelle steht neben der groben Kategorie ("keine",
"geringe", "mittlere", "viele" Optimierungsmoeglichkeiten) eine
Freitextspalte, in der die Monteure notiert haben, was sie vorgefunden
und was sie geaendert haben. Das ist die einzige Stelle im Datenbestand,
an der ein Fehler beim Namen genannt wird. Die Texte sind kurz,
ungegliedert und in einem Satz stehen oft Gebaeudebeschreibung und
Befund nebeneinander ("Baujahr 1978 Filter leicht verschmutzt").

Warum Regeln und kein Sprachmodell
----------------------------------
57 Texte sind zu wenig fuer ein gelerntes Modell und gerade richtig fuer
eine Regelliste, die das Team lesen und korrigieren kann. Die
Schluesselwoerter stehen deshalb offen in `KATEGORIEN`, jede Zuordnung
laesst sich ueber die Spalte ``treffer`` bis auf das ausloesende Wort
zurueckverfolgen. Wer eine Zuordnung fuer falsch haelt, aendert die
Liste und rechnet neu; es gibt keine verborgene Gewichtung.

Negationen
----------
Ein Schluesselwort allein reicht nicht. "Schmutzfaenger fast leer" ist
der Gegenbefund zu "Schmutzfaenger stark voll", beide enthalten das Wort
Schmutzfaenger. Jede Kategorie hat darum eine Ausschlussliste; trifft
eine Ausschlussphrase, zaehlt der Treffer dieser Kategorie nicht.

Grenzen
-------
Die Kodierung sagt, wovon ein Text handelt, nicht wie schwer der Fehler
war. Mehrfachnennungen sind der Normalfall und werden nicht aufgeloest -
ein Text, der Pumpe und Daemmung nennt, zaehlt in beiden Kategorien.
Texte ohne Fehlerhinweis sind kein Mangel der Regeln, sondern der haeufige
Fall, dass der Monteur nur die Anlage beschrieben hat.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

#Kategorie ohne jeden Fehlerhinweis. Steht hier namentlich, weil die
#Ranglisten sie als eigene Zeile fuehren und nicht stillschweigend
#unterschlagen sollen.
OHNE_BEFUND = "kein Fehlerhinweis im Text"

#Fehlerkategorien mit ihren Schluesselwoertern und Ausschlussphrasen.
#Die Woerter sind in normalisierter Form notiert: klein geschrieben,
#Umlaute aufgeloest (ae, oe, ue, ss). `normalisiere` bringt die Texte in
#dieselbe Form, bevor verglichen wird.
KATEGORIEN: Sequence[Tuple[str, Dict[str, Sequence[str]]]] = (
    ("Schmutzfaenger oder Filter verschmutzt", {
        "woerter": ("schmutzfaenger", "schmutzfilter", "filter", "sieb"),
        "ausschluss": ("schmutzfaenger fast leer", "filter sauber"),
    }),
    ("Regelung defekt oder falsch eingestellt", {
        "woerter": ("regler", "regelventil", "stellmotor", "stellantrieb",
                    "stellantireb", "stellventil", "ventile getauscht",
                    "ventil getauscht", "amv", "anlagenkennziffer",
                    "anlagenschema", "fahrweise", "verstellt", "uhr",
                    "zeit 17", "heizzeit", "error", "zirkulationspumpe "
                    "eingestellt"),
        "ausschluss": (),
    }),
    ("Pumpe oder Zirkulation fehlerhaft", {
        "woerter": ("pumpe", "zirk abgeklemmt", "zirkulation nicht "
                    "angeschlossen", "fehlzirkulation", "naturumlauf",
                    "naturzirkulation", "schwerkraft"),
        "ausschluss": (),
    }),
    ("Hydraulik oder Volumenstrom falsch eingeregelt", {
        "woerter": ("volumenstrom", "durchfluss", "hydraulisch",
                    "abgleich", "schieber gesperrt", "l/h", "spreizung",
                    "druck ist zu niedrig", "hoher sekundaerdruck",
                    "eingeregelt", "schlupf"),
        "ausschluss": (),
    }),
    ("Daemmung mangelhaft", {
        "woerter": ("daemmung fehlt", "ungedaemmt", "nicht so gut gedaemmt",
                    "originale fenster", "undaemmt"),
        "ausschluss": ("ist gedaemmt",),
    }),
    ("Messtechnik oder Zaehler", {
        "woerter": ("zaehler", "fuehler", "plomb", "verblombt", "m-bus",
                    "batterie", "blitz"),
        "ausschluss": ("fuehler passt", "fuehler passen",
                       "fuehler sitzen"),
    }),
    ("Vertragsleistung passt nicht zur Abnahme", {
        "woerter": ("vertraglich", "zu wenig leistun", "leistung teilweise "
                    "hoeher"),
        "ausschluss": (),
    }),
    ("Sonstiger Defekt oder Reparaturbedarf", {
        "woerter": ("nippel", "dichtung muss getauscht", "undicht",
                    "starke geraeusche", "laeuft nicht", "defekt "
                    "gekennzeichnet"),
        "ausschluss": (),
    }),
)

_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
            "Ä": "ae", "Ö": "oe", "Ü": "ue"}

#Verneinungen, die ein Schluesselwort entwerten, wenn sie unmittelbar
#davor im selben Teilsatz stehen. Die Monteure schreiben knapp, deshalb
#reicht ein kurzes Fenster; ueber ein Komma oder einen Punkt hinweg wird
#nicht mehr verneint, sonst schluckt ein "keine Maengel" am Satzanfang
#jeden spaeteren Befund.
NEGATIONEN = ("nicht", "kein", "keine", "keinen", "ohne")
NEGATIONSFENSTER = 22


def normalisiere(text: object) -> str:
    """Kleinschreibung, aufgeloeste Umlaute, einfache Leerzeichen."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    s = str(text)
    for alt, neu in _UMLAUTE.items():
        s = s.replace(alt, neu)
    return " ".join(s.lower().split())


def verneint(norm: str, wort: str,
             fenster: int = NEGATIONSFENSTER) -> bool:
    """Steht vor diesem Schluesselwort eine Verneinung im selben Teilsatz."""
    start = norm.find(wort)
    while start >= 0:
        davor = norm[max(0, start - fenster):start]
        schnitt = max(davor.rfind(","), davor.rfind(";"), davor.rfind("."))
        davor = davor[schnitt + 1:]
        if not any(n in davor.split() for n in NEGATIONEN):
            return False
        start = norm.find(wort, start + 1)
    return True


def kodiere_text(text: object,
                 kategorien: Sequence = KATEGORIEN) -> Dict[str, object]:
    """Einen Freitext in Kategorien einordnen.

    Zurueck kommen die getroffenen Kategorien, die ausloesenden Woerter
    und die Einstufung ``eindeutig`` (genau eine Kategorie),
    ``mehrdeutig`` (mehrere) oder ``ohne Befund`` (keine).
    """
    norm = normalisiere(text)
    treffer: List[str] = []
    woerter: List[str] = []
    for name, regel in kategorien:
        if any(a and a in norm for a in regel["ausschluss"]):
            continue
        gefunden = [w for w in regel["woerter"]
                    if w in norm and not verneint(norm, w)]
        if gefunden:
            treffer.append(name)
            woerter.extend(gefunden)
    if not norm:
        stufe = "leer"
    elif len(treffer) == 1:
        stufe = "eindeutig"
    elif len(treffer) > 1:
        stufe = "mehrdeutig"
    else:
        stufe = "ohne Befund"
    return {"text_norm": norm,
            "kategorien": treffer or [OHNE_BEFUND],
            "treffer": "; ".join(sorted(set(woerter))),
            "stufe": stufe,
            "n_kategorien": len(treffer)}


def kodiere_tabelle(begehungen: pd.DataFrame,
                    spalte: str = "sonstiges",
                    kategorien: Sequence = KATEGORIEN) -> pd.DataFrame:
    """Eine Zeile je Begehung mit kodierten Kategorien.

    Die uebergebene Tabelle kommt aus `load_begehungen.load_begehungen`
    oder `begehungen_mit_zaehler`. Mitgefuehrt werden nur Spalten ohne
    Personenbezug: laufende Nummer, Datum, grobe Kategorie und - falls
    vorhanden - die Zaehlernummer. Adresse und Freitext bleiben in der
    Rueckgabe, der Export in `rangliste_begehungen` laesst beide weg.
    """
    mit = [s for s in ("nr", "datum", "kategorie", "meter") if s in begehungen]
    zeilen = []
    for _, zeile in begehungen.iterrows():
        kod = kodiere_text(zeile.get(spalte), kategorien)
        satz = {s: zeile[s] for s in mit}
        satz.update({"text": zeile.get(spalte), **kod})
        zeilen.append(satz)
    return pd.DataFrame(zeilen)


def rangliste_begehungen(kodiert: pd.DataFrame) -> pd.DataFrame:
    """Haeufigkeit der Fehlerkategorien ueber die kodierten Texte.

    Gezaehlt wird je Kategorie die Zahl der Texte, die sie nennen. Weil
    ein Text mehrere Kategorien nennen darf, summieren sich die Zahlen
    nicht auf die Zahl der Texte. ``anteil_texte`` bezieht sich deshalb
    auf die Zahl der Texte und nicht auf die Summe der Nennungen.
    """
    n = len(kodiert)
    zaehler: Dict[str, int] = {}
    for liste in kodiert["kategorien"]:
        for k in liste:
            zaehler[k] = zaehler.get(k, 0) + 1
    out = pd.DataFrame({"kategorie": list(zaehler),
                        "n_texte": list(zaehler.values())})
    out["anteil_texte"] = out["n_texte"] / n if n else float("nan")
    return out.sort_values("n_texte", ascending=False).reset_index(drop=True)


def kodierbilanz(kodiert: pd.DataFrame) -> pd.DataFrame:
    """Wie viele Texte eindeutig, mehrdeutig, ohne Befund oder leer sind."""
    out = (kodiert["stufe"].value_counts(dropna=False)
           .rename_axis("stufe").reset_index(name="n_texte"))
    out["anteil"] = out["n_texte"] / len(kodiert) if len(kodiert) else float("nan")
    return out


def kategorien_je_zaehler(kodiert: pd.DataFrame) -> pd.DataFrame:
    """Lange Form Zaehler mal Kategorie, fuer den Abgleich mit den Mustern.

    Zeilen ohne aufgeloeste Zaehlernummer fallen heraus; sie koennen
    nicht gegen Messdaten gehalten werden. Wie viele das sind, steht in
    der Spalte ``n_begehungen`` der Rueckgabe nicht mehr drin, deshalb
    gibt der Aufrufer die Differenz selbst aus.
    """
    if "meter" not in kodiert.columns:
        return pd.DataFrame(columns=["meter", "kategorie", "n_begehungen"])
    zeilen = []
    for _, zeile in kodiert.iterrows():
        if pd.isna(zeile.get("meter")):
            continue
        for k in zeile["kategorien"]:
            zeilen.append({"meter": int(zeile["meter"]), "kategorie": k})
    if not zeilen:
        return pd.DataFrame(columns=["meter", "kategorie", "n_begehungen"])
    lang = pd.DataFrame(zeilen)
    return (lang.groupby(["meter", "kategorie"]).size()
            .reset_index(name="n_begehungen"))


def pruefblatt(kodiert: pd.DataFrame,
               kategorie: Optional[str] = None) -> pd.DataFrame:
    """Kurze Ansicht zum Nachpruefen der Zuordnung durch das Team.

    Gibt je Text die zugeordneten Kategorien und die ausloesenden Woerter
    aus. Der Text selbst wird auf 120 Zeichen gekuerzt, damit die Tabelle
    im Notebook lesbar bleibt.
    """
    teil = kodiert
    if kategorie is not None:
        teil = teil[teil["kategorien"].apply(lambda ks: kategorie in ks)]
    out = teil.copy()
    out["text_kurz"] = out["text"].astype(str).str.slice(0, 120)
    out["kategorien"] = out["kategorien"].apply(lambda ks: ", ".join(ks))
    spalten = [s for s in ("nr", "meter", "stufe", "kategorien", "treffer",
                           "text_kurz") if s in out.columns]
    return out[spalten].reset_index(drop=True)
