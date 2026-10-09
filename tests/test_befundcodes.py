"""Tests der regelbasierten Kodierung der Begehungs-Freitexte."""
import pandas as pd
import pytest

from src import befundcodes as bc


def labels(text):
    """Nur die gesetzten Fehlerlabels einer Notiz."""
    kod = bc.kodiere_text(text)
    return {name for name in bc.BEFUNDE if kod[name]}


def kontext(text):
    kod = bc.kodiere_text(text)
    return {name for name in bc.KONTEXT if kod[name]}


class TestNormalisiere:
    def test_umlaute_und_schreibweise(self):
        assert bc.normalisiere("Schmutzfänger VOLL") == "schmutzfaenger voll"

    def test_leerraum_zusammengezogen(self):
        assert bc.normalisiere("a\n  b\tc") == "a b c"

    def test_fehlender_text(self):
        assert bc.normalisiere(None) == ""
        assert bc.normalisiere(float("nan")) == ""

    def test_scharfes_s(self):
        assert bc.normalisiere("Fußbodenheizung") == "fussbodenheizung"


class TestVeto:
    def test_voller_schmutzfaenger_zaehlt(self):
        assert "schmutzfaenger" in labels("Schmutzfänger stark voll")

    def test_leerer_schmutzfaenger_zaehlt_nicht(self):
        assert "schmutzfaenger" not in labels("Schmutzfänger fast leer")

    def test_veto_wirkt_nur_direkt_hinter_dem_treffer(self):
        #in der Originalnotiz stehen Befund und das entfernte "passt" im
        #selben Satz; ein Veto mit grossem Fenster loescht sonst den Befund
        text = ("rw Pumpoe läuft nicht über Regler at Fühler passt "
                "Regler schliesst nicht ganz")
        gefunden = labels(text)
        assert "pumpe" in gefunden
        assert "ventil_stellantrieb" in gefunden

    def test_volumenstrom_passt_zaehlt_nicht(self):
        assert "hydraulik_volumenstrom" not in labels("Volumenstrom passt")

    def test_gedaemmt_ist_kein_befund(self):
        assert "daemmung" not in labels("ist gedämmt, 80 mm Dämmung")

    def test_fehlende_daemmung_zaehlt(self):
        assert "daemmung" in labels("Dämmung fehlt")


class TestZirkulation:
    def test_abgeklemmte_zirkulation_zaehlt(self):
        assert "zirkulation" in labels("Zirk abgeklemmt")

    def test_naturzirkulation_ist_bauart_kein_fehler(self):
        assert "zirkulation" not in labels("Naturzirkulation")
        assert "naturumlauf" in kontext("Naturzirkulation")

    def test_schwerkraftzirkulation_ist_bauart_kein_fehler(self):
        text = "Baujahr ca. 1970 Schwerkraft Zirkulation Gleiderheizkörper"
        assert "zirkulation" not in labels(text)
        assert "naturumlauf" in kontext(text)

    def test_defekte_zirkulationspumpe_laeuft_unter_zirkulation(self):
        #nicht zusaetzlich als Heizkreispumpe zaehlen
        gefunden = labels("Zirk Pumpe defekt geölt")
        assert gefunden == {"zirkulation"}


class TestMehrfachlabels:
    def test_eine_notiz_mehrere_befunde(self):
        text = ("Radiatoren überall Zähler von 2018 müsste abld getauscht "
                "werden Schmutzfänger hat Durchfluss um 200 l/h reduziert")
        assert labels(text) == {"schmutzfaenger", "hydraulik_volumenstrom",
                                "messtechnik"}

    def test_zaehlung_stimmt_mit_labels_ueberein(self):
        kod = bc.kodiere_text("Regelventil getauscht Dämmung fehlt")
        assert kod["n_befunde"] == 2

    def test_tippfehler_stellantrieb(self):
        assert "ventil_stellantrieb" in labels("Stellantireb gewechselt")

    def test_plombieren_ist_kein_befund(self):
        assert labels("Fühler 02 Zähler plombiert") == set()


class TestAnlageAus:
    def test_leerstand(self):
        assert "anlage_aus" in labels("2 Parteien Haus steht leer 3 Jahre")

    def test_heizung_laeuft_nicht(self):
        text = "Holzständer Heizung läuft allerding nicht"
        assert "anlage_aus" in labels(text)


class TestBaujahr:
    @pytest.mark.parametrize("text,jahr", [
        ("Baujahr 1978", 1978),
        ("BJ 2013 Beistellofen", 2013),
        ("1981 BJ", 1981),
        ("1960 Baujahr Fenster neu", 1960),
        ("Baujahr ca. 1970", 1970),
        ("Baujahr 2010/10", 2010),
    ])
    def test_schreibweisen(self, text, jahr):
        assert bc.kodiere_text(text)["baujahr"] == jahr

    def test_ohne_baujahr(self):
        assert bc.kodiere_text("Regelventil getauscht")["baujahr"] is None

    def test_unplausibles_jahr_wird_verworfen(self):
        assert bc.kodiere_text("Baujahr 9999")["baujahr"] is None


class TestLeererText:
    def test_kein_text_keine_labels(self):
        kod = bc.kodiere_text(None)
        assert kod["text_vorhanden"] is False
        assert kod["n_befunde"] == 0


def beispieltabelle():
    return pd.DataFrame({
        "nr": [1, 2, 3],
        "meter": [111, 111, 222],
        "sonstiges": ["Schmutzfänger stark voll", "Regelventil getauscht",
                      None],
        "heizzeit_alt_von": ["06:00", "06:00", None],
        "heizzeit_neu_von": ["05:00", "06:00", None],
    })


class TestTabellenfunktionen:
    def test_rangliste_hat_nenner_und_summiert_richtig(self):
        kod = bc.kodiere_begehungen(beispieltabelle())
        rang = bc.rangliste(kod)
        assert set(rang["nenner"]) == {2}
        n = dict(zip(rang["befund"], rang["n"]))
        assert n["schmutzfaenger"] == 1
        assert n["ventil_stellantrieb"] == 1
        assert rang["n"].is_monotonic_decreasing

    def test_rangliste_mit_eigenem_nenner(self):
        kod = bc.kodiere_begehungen(beispieltabelle())
        rang = bc.rangliste(kod, nenner=100)
        zeile = rang[rang["befund"] == "schmutzfaenger"].iloc[0]
        assert zeile["anteil"] == pytest.approx(0.01)

    def test_sollwert_geaendert(self):
        tab = beispieltabelle()
        assert bc.sollwert_geaendert(tab.iloc[0]) is True
        assert bc.sollwert_geaendert(tab.iloc[1]) is False

    def test_diskrepanzen_ist_vierfeldertafel(self):
        kod = bc.kodiere_begehungen(beispieltabelle())
        tafel = bc.diskrepanzen(kod)
        assert set(tafel.columns) == {"befund_im_text", "sollwert_geaendert",
                                      "n", "anteil"}
        assert tafel["n"].sum() == len(kod)

    def test_unkodiert_zeigt_nur_zeilen_mit_text_ohne_befund(self):
        tab = beispieltabelle()
        tab.loc[2, "sonstiges"] = "Nur Fußbodenheizung"
        kod = bc.kodiere_begehungen(tab)
        offen = bc.unkodiert(kod)
        assert list(offen["nr"]) == [3]

    def test_labels_je_zaehler_verodert(self):
        kod = bc.kodiere_begehungen(beispieltabelle())
        je = bc.labels_je_zaehler(kod).set_index("meter")
        assert bool(je.loc[111, "schmutzfaenger"]) is True
        assert bool(je.loc[111, "ventil_stellantrieb"]) is True
        assert int(je.loc[111, "n_befunde"]) == 2


class TestEchteDaten:
    def test_alle_begehungen_kodierbar(self):
        kod = bc.kodiere_begehungen()
        assert len(kod) == 66
        assert kod["text_vorhanden"].sum() == 57
        #jede Notiz mit Fehlerlabel soll auch einen Zaehler haben, sonst
        #ist das Label fuer die Zeitreihen wertlos
        mit_befund = kod[kod["n_befunde"] > 0]
        assert mit_befund["meter"].notna().all()

    def test_rangliste_auf_echten_daten(self):
        rang = bc.rangliste(bc.kodiere_begehungen())
        assert set(rang["nenner"]) == {57}
        assert rang["n"].sum() > 0
