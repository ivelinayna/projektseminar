# Heating Network Fault Detection - UEZ Mainfranken

Projektseminar in Zusammenarbeit mit **UEZ Mainfranken** zur Fehlererkennung
und Leistungsoptimierung in Fernwaermenetzen.
Julius-Maximilians-Universitaet Wuerzburg, SS 2026 / WS 2026.

> **Status: Datenexploration, Graphaufbau und erste echte Datenintegration.**
> Reale stundenweise Zaehler-Exporte liegen lokal in `data/raw/` und koennen
> ueber `src/load_timeseries.py` eingelesen werden. Die regelbasierte Fault
> Detection ist weiterhin die erklaerbare Baseline; die Schwellenwerte muessen
> auf echten Daten neu kalibriert werden.

## Inhalt

| Pfad | Zweck |
|---|---|
| `src/load_data.py` | Einlesen von Shapefiles, ODS-Topologie und Optimierungs-Excel, inklusive deutscher Adressnormalisierung |
| `src/build_graph.py` | Logischer Graph mit NetworkX aus der Adresstopologie + raeumlicher Graph aus der Leitungsgeometrie |
| `src/visualize.py` | Statische PNG-Topologie + interaktive Folium-Karte des Leitungsnetzes |
| `src/inspections.py` | Aufbereitete Ansicht der Vor-Ort-Inspektions- und Optimierungsdaten |
| `src/synth_data.py` | Synthetische stuendliche Zaehlerdaten mit eingebetteten Fehlern, 5 Fehlertypen, 1 Jahr |
| `src/load_timeseries.py` | Loader fuer reale UEZ-Zaehler-CSVs: Exportgenerationen zusammenfuehren, deduplizieren, Schema wie synthetische Daten |
| `src/features.py` | Feature Engineering fuer Zeitreihen, ca. 25 numerische Merkmale pro HAST |
| `src/fault_detection.py` | Regelbasierter Fehlerklassifikator - Baseline fuer das spaetere ML-Modell |
| `src/detect_real.py` | Defensive Auswertung echter Zeitreihen inkl. Qualitaetsklassen, 365-Tage-Fenster und Ground-Truth-Join |
| `src/meter_quality.py` | Qualitaetschecks fuer Zaehlerdaten |
| `src/ml_classifier.py` | ML-State-Classifier als ehrlicher Vergleich zur Baseline |
| `src/geocode.py` | Geokodierung von HAST-Adressen ueber Nominatim, mit persistentem Cache |
| `src/geocode_stub.py` | Offline-Koordinaten-Stubs - nur fuer Sandbox-Tests, niemals lokal ausfuehren |
| `src/snap_hast.py` | Snapping geokodierter HAST auf den naechsten Knoten des raeumlichen Graphen |
| `src/dashboard_map.py` | Kombinierte Karte: Leitungen + geokodierte HAST + Inspektionsbefunde + vorhergesagte Fehler |
| `src/dashboard_app.py` | Interaktives Streamlit-Dashboard mit Ampel, Karte, Stationsdetail und Wartungsprioritaet |
| `src/priority.py` | Transparenter Wartungsprioritaets-Score, noch keine echte Fehlerprognose |
| `src/main.py` | End-to-End-Pipeline mit einem Befehl |
| `data/raw/` | Quelldateien von UEZ - **gitignored**, nicht committen |
| `data/processed/` | Abgeleitete CSV-Dateien - **gitignored** |
| `outputs/` | Generierte Visualisierungen - **gitignored** |
| `docs/` | Ausfuehrliche Dokumentation, Ziel: Read the Docs / GitHub Pages |

## Schnellstart

```bash
git clone <repo-url>
cd heating-network
pip install -r requirements.txt

# UEZ-Datendateien in data/raw/ ablegen, nicht committen
python -m src.main
python -m src.main --synth --detect --plot
python -m src.main --geocode --dashboard
python -m src.main --synth --detect --plot --geocode --dashboard
```

Streamlit-Dashboard:

```bash
streamlit run src/dashboard_app.py
```

## Datenquellen

Rohdaten von UEZ liegen lokal in `data/raw/` und duerfen nicht oeffentlich
versioniert werden.

1. **Shapefiles `Leitungsverlauf_*`** - physischer Leitungsverlauf fuer das
   gesamte Versorgungsgebiet von UEZ Mainfranken. CRS: ETRS89 / UTM 32N
   (EPSG:25832). Enthalten sind ca. 1.305 Liniensegmente mit
   Materialattributen wie Stahlrohr, ISOPEX PE-X und Uponor PE-X sowie
   markierte Punkte.

2. **`Nodes_Edges.ods`** - logische Topologie des Teilnetzes Wiesentheid.
   Die Datei enthaelt die Tabellenblaetter `Nodes`, `Edges` und `Strassen`.
   Es gibt 99 Zaehlerzeilen bzw. 94 eindeutige HAST-Adressen; einige Gebaeude
   haben mehrere Zaehler. Die Kanten beschreiben die logischen Verbindungen
   zwischen Adressen. `Strassen` ist ein Mapping zwischen Kunden-ID und Adresse.

3. **`20252810_Ergebnis_Optimierung_FW[45].xlsx`** - 66 Vor-Ort-
   Inspektionsdatensaetze zu HAST mit alten und neuen Werten fuer
   Anlagenkonfiguration, Heizzeiten, Vertragsleistung und Regelparameter
   PA1.1-PA1.9. Zusaetzlich enthaelt die Datei Ja/Nein-Markierungen dazu,
   was repariert wurde, z. B. Filter, Ventil, Stellantrieb, Daemmung oder
   Regler. **Diese Datei bildet den gelabelten Fehlerdatensatz.**

4. **Zaehler-Zeitreihen-CSVs** - stuendliche Reihen pro Zaehler mit
   Zeitstempel, kumulativer Energie in kWh, Volumenstrom in l/h, Leistung in
   kW, Delta T, Vorlauf in Grad C, Ruecklauf in Grad C und kumulativem
   Volumen in m3. Es gibt zwei Exportgenerationen: `<Zaehlernummer>__n.csv`
   und `<Zaehlernummer>_2025n.csv`, teilweise mit Ueberlappungen.
   `src/load_timeseries.py` fuehrt sie zusammen und dedupliziert sie.

5. **`Zuordnung.xlsx`** - jahresbezogenes Mapping von Zaehlernummer zu
   Kunden-ID bzw. V-PIN und Adresse. Wichtig, weil Zaehler getauscht werden
   koennen und nicht jede CSV-Zaehlernummer direkt in `Nodes_Edges.ods` steht.

## Bisheriger Erkenntnisstand

Der logische Graph ist im Wesentlichen ein **Baum**: 118 Knoten
(94 HAST-Adressen + 24 Junctions), 110 Kanten und maximaler Knotengrad 4.
Die groesste zusammenhaengende Komponente umfasst 110 Knoten; 8 HAST sind
Waisen ohne Kanten und sollten mit UEZ geklaert werden. Zwei 500-kW-Verbraucher
wirken als zentrale Knotenpunkte. Die gesamte vertragliche Anschlussleistung
liegt bei ca. 2,1 MW ueber 94 HAST-Adressen bzw. 99 Zaehler.

## Baseline fuer die Fehlererkennung

`src/fault_detection.py` ist ein regelbasierter Klassifikator, der das
Fachwissen aus der Inspektions-Excel-Datei ueber klare Schwellenwerte abbildet.
Er erfuellt drei Zwecke:

1. **Validierung der Pipeline.** Auf synthetischen Daten mit eingebetteten
   Fehlern erkennt das Regelwerk derzeit 100 % der eingefuegten Fehler ohne
   False Positives. Das bestaetigt, dass die Feature-Pipeline in sich
   konsistent ist.

2. **Benchmark.** Jedes spaetere ML-Modell muss diese Baseline uebertreffen,
   damit ein Einsatz sinnvoll ist.

3. **Erklaerbarkeit.** Jede Markierung enthaelt eine verstaendliche
   Begruendung, die sich fuer ein Techniker-Dashboard eignet.

Derzeit sind fuenf Fehlerfamilien umgesetzt:

| Fehler | Erkennungssignal |
|---|---|
| `fouled_filter` | 95. Perzentil des Volumenstroms sinkt von Monat zu Monat |
| `excess_rt` | Ruecklauftemperatur im Winter > 48 Grad C oder Ruecklauftemperatur > 50 Grad C in mehr als 30 % der belasteten Stunden |
| `continuous_flow` | Sommer-Median des Volumenstroms > 25 l/h, obwohl echtes Warmwasserverhalten stossartig ist |
| `oversized_contract` | Spitzenleistung < 40 % der vertraglichen Anschlussleistung |
| `control_hysteresis` | Periodische Komponente von 4-12 Stunden erklaert mehr als 7 % der gesamten Varianz des Volumenstroms |

Wichtig: Auf echten Daten muessen diese Schwellen neu kalibriert werden. Die
synthetisch kalibrierte Regelbasis markiert reale Zaehler zu breit und ist
deshalb aktuell eher Diagnosewerkzeug als fertiges Produktivmodell.

## Korrelationen zwischen Inspektionen und HAST-Eigenschaften

Eine erste Auswertung der 66 Inspektionsdatensaetze, verknuepft mit
Gebaeudealter und Anlagenkonfiguration, deutet auf drei praxisrelevante Muster
hin:

* **Anlagenkonfiguration 2.1** kommt mit Abstand am haeufigsten vor
  (32 / 66 HAST) und zeigt die hoechste Filterreinigungsrate sowie eine hohe
  Rate fuer Volumenstrom-Nachregulierungen.

* **Von 11 Aenderungen der Vertragsleistung waren 9 Reduzierungen**, was zu
  einer chronischen Ueberdimensionierung auf Kundenseite passt.

* **"Schmutzfaenger" erscheint zusaetzlich mehrfach in Freitextnotizen**,
  neben der formalen Filter-Markierung. Die tatsaechliche Verschmutzungsrate
  liegt daher wahrscheinlich hoeher als die strukturierte Spalte zeigt.

## Bekannte Datenqualitaetsprobleme

* `Nodes_Edges.ods` mischt unterschiedliche Schreibweisen von Strassennamen
  (`Blumenstr.`, `Blumenstrasse`, `Blumenstraße`) - Adressen werden deshalb in
  `load_data._normalize_address` normalisiert.

* `Optimierung.xlsx` enthaelt den Tippfehler **Fleiderstrasse**. Dieser wird in
  `load_inspections` behandelt.

* 8 HAST erscheinen im Tabellenblatt `Nodes`, werden aber von keiner Kante
  referenziert. Sie sind damit Waisen in der Topologie und sollten mit UEZ
  rueckgeklaert werden.

* Der `Point`-Layer der Shapefile enthaelt nur wenige markierte Punkte und
  keine Labels, die direkt zur Adresstopologie passen.

* OpenStreetMap enthaelt fuer das relevante Neubaugebiet in Wiesentheid keine
  zuverlaessigen Hausnummern. Deshalb kann Nominatim mehrere HAST derselben
  Strasse auf denselben Strassenmittelpunkt legen. Beste Loesung: echte
  GIS-Koordinaten von UEZ oder ein amtlicher Geocoder.

## Roadmap

- [x] Alle drei Basis-Datenquellen laden, Adressen normalisieren und erste Graphen erstellen
- [x] Pipeline mit einem Befehl; statische und interaktive Visualisierungen
- [x] Erste Haeufigkeitstabelle der Fehler aus den Inspektionsdaten
- [x] Generator fuer synthetische Zeitreihen mit 5 eingebetteten Fehlertypen (`synth_data.py`)
- [x] Feature Engineering auf HAST-Ebene aus stuendlichen Zaehlerdaten (`features.py`)
- [x] Regelbasierte Baseline zur Fehlererkennung auf synthetischen Daten
- [x] Korrelationsanalyse zwischen Inspektionen und Anlagenkonfiguration / Baujahr / Anschlusswert
- [x] Adressen geokodieren und kombinierte Dashboard-Karte bauen
- [x] Loader fuer reale Zaehler-CSVs: Exportgenerationen zusammenfuehren, deduplizieren, pro Zaehler materialisieren (`load_timeseries.py`)
- [x] Echte Zeitreihen defensiv in Features + Fault Detection fuehren: Qualitaetsklassen, 365-Tage-Fenster, mindestens 60 % Abdeckung, Ground-Truth-Join (`detect_real.py`)
- [x] Geokodierte HAST an naechstgelegene Knoten des raeumlichen Graphen snappen, mit Distanz als Unsicherheitsmass (`snap_hast.py`)
- [x] ML-State-Classifier gegen Baseline evaluieren (`ml_classifier.py`) - ehrliches negatives Ergebnis, siehe `docs/ml-klassifikator.md`
- [x] Streamlit-Dashboard mit gemessener Ruecklauf-Ampel, klickbarer Karte, Stationsdetail und Wartungsprioritaet (`dashboard_app.py`)
- [x] Transparenter Wartungsprioritaets-Score (`priority.py`) - noch keine echte Fehlerprognose
- [ ] Regel-Schwellenwerte auf echten Daten neu kalibrieren
- [ ] Zaehlerwechsel ueber `Zuordnung.xlsx` sauber zusammensetzen
- [ ] Echte UEZ-GIS-Koordinaten oder belastbaren Geocoder fuer HAST beschaffen
- [ ] Vollstaendige Read-the-Docs-/GitHub-Pages-Dokumentation bereitstellen
