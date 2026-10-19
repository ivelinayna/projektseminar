"""
Tests fuer src.freitext.

Die Kodierung ist Handarbeit in Regelform, deshalb pruefen die Tests
weniger die Mechanik als die Eigenschaften, auf die sich das Team
verlassen koennen muss: eine Verneinung darf keine Kategorie ausloesen,
ein Text mit mehreren Befunden darf nicht stillschweigend auf einen
reduziert werden, und ein Text, der nur das Gebaeude beschreibt, muss
als Text ohne Fehlerhinweis durchfallen statt irgendwo einsortiert zu
werden.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_freitext.py
"""

import pandas as pd

from src import freitext as ft


def test_normalisierung_zieht_umlaute_und_grossschreibung_zusammen():
    assert ft.normalisiere("Schmutzfänger VERSCHMUTZT") == \
        ft.normalisiere("schmutzfaenger verschmutzt")


def test_eindeutiger_text_bekommt_genau_eine_kategorie():
    treffer = ft.kodiere_text("Schmutzfänger stark verschmutzt, gereinigt")
    assert treffer["stufe"] == "eindeutig"
    assert treffer["kategorien"] == ["Schmutzfaenger oder Filter verschmutzt"]


def test_mehrere_befunde_bleiben_mehrdeutig():
    treffer = ft.kodiere_text(
        "Regler defekt und Zirkulationspumpe läuft dauerhaft")
    assert treffer["stufe"] == "mehrdeutig"
    assert len(treffer["kategorien"]) >= 2


def test_verneinung_vor_dem_schluesselwort_loest_nichts_aus():
    assert ft.kodiere_text("keine Pumpe vorhanden")["kategorien"] == \
        [ft.OHNE_BEFUND]
    #ueber das Komma hinweg wird nicht mehr verneint
    treffer = ft.kodiere_text("keine Mängel am Gebäude, Pumpe defekt")
    assert "Pumpe oder Zirkulation fehlerhaft" in treffer["kategorien"]


def test_reine_gebaeudebeschreibung_gilt_als_ohne_befund():
    treffer = ft.kodiere_text("Baujahr 1998, Fußbodenheizung im Erdgeschoss")
    assert treffer["stufe"] == "ohne Befund"


def test_leerer_text_wird_als_leer_gefuehrt():
    for leer in (None, "", "   ", float("nan")):
        assert ft.kodiere_text(leer)["stufe"] == "leer"


def _begehungen() -> pd.DataFrame:
    return pd.DataFrame({
        "meter": [1, 2, 3, 4],
        "sonstiges": ["Schmutzfänger verschmutzt",
                      "Regler defekt, Pumpe läuft dauerhaft",
                      "Baujahr 1998",
                      None],
    })


def test_bilanz_zaehlt_jede_zeile_genau_einmal():
    kodiert = ft.kodiere_tabelle(_begehungen())
    bilanz = ft.kodierbilanz(kodiert)
    assert bilanz["n_texte"].sum() == len(_begehungen())
    assert abs(bilanz["anteil"].sum() - 1.0) < 1e-9


def test_rangliste_zaehlt_mehrfachzuordnung_in_jeder_kategorie():
    kodiert = ft.kodiere_tabelle(_begehungen())
    rang = ft.rangliste_begehungen(kodiert)
    namen = set(rang["kategorie"])
    assert "Regelung defekt oder falsch eingestellt" in namen
    assert "Pumpe oder Zirkulation fehlerhaft" in namen
    #der Text ohne Fehlerhinweis darf nicht in einer Fehlerkategorie landen
    schmutz = rang.loc[rang["kategorie"] ==
                       "Schmutzfaenger oder Filter verschmutzt",
                       "n_texte"].iloc[0]
    assert schmutz == 1


def test_pruefblatt_macht_jede_zuordnung_nachvollziehbar():
    kodiert = ft.kodiere_tabelle(_begehungen())
    blatt = ft.pruefblatt(kodiert)
    assert {"kategorien", "treffer"} <= set(blatt.columns)
    zeile = blatt[blatt["meter"] == 1].iloc[0]
    assert "schmutzfaenger" in str(zeile["treffer"]).lower()
