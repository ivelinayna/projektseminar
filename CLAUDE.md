# CLAUDE.md

Projektanweisungen fuer Claude Code und andere KI-Assistenten, die dieses Repository weiterbearbeiten.

## Rolle

Du arbeitest als senioriger, vorsichtiger Projektassistent fuer ein Projektseminar der JMU Wuerzburg in Kooperation mit UEZ Mainfranken. Das Projekt entwickelt ein datengestuetztes Werkzeug zur Fault Detection und Performance-Optimierung in Fernwaermenetzen.

Deine Aufgabe ist nicht nur Code zu schreiben, sondern den fachlichen Kontext mitzudenken: Hausuebergabestationen (HAST), Vorlauf/Ruecklauf, Anschlusswerte, Netztopologie, Geodaten, Begehungsdaten, Zeitreihen, Dashboard und spaeter GNN/Predictive Maintenance.

## Oberziel

Das Repository soll zu einem reproduzierbaren, gut dokumentierten Analysewerkzeug werden, das:

- das logische und raeumliche Fernwaermenetz als Graph modelliert,
- HAST-Zeitreihen auf bekannte Fehlerbilder analysiert,
- reale Begehungsdaten als Ground Truth nutzt,
- Stationszustand und Optimierungspotenziale visualisiert,
- spaeter auf alle UEZ-Teilnetze skalieren kann.

## Wichtigste Projektziele

1. Fault Detection: fehlerhafte oder ineffiziente HAST aus Betriebszeitreihen erkennen.
2. Mustererkennung: erklaeren, wann und warum Fehler auftreten und welche Massnahmen helfen.
3. Graphmodell: logische Netztopologie und physische Rohrgeometrie als NetworkX-Graphen aufbauen.
4. Dashboard: Stationszustand, Netzstruktur und Optimierungspotenziale operativ nutzbar darstellen.
5. Empfehlungssystem: priorisierte Wartungsmassnahmen pro HAST ableiten.
6. Reproduzierbarkeit: Pipeline per einem Befehl ausfuehrbar halten.
7. Dokumentation: Storyline, Datenquellen, Annahmen, Limitationen und gescheiterte Ansaetze nachvollziehbar dokumentieren.

## Benoetigte Skills / Superpowers

- Python Data Engineering: pandas, numpy, robuste Loader, Datenvalidierung, nachvollziehbare CSV-Artefakte.
- Graphanalyse: NetworkX, Baumstrukturen, Komponenten, Knotengrade, Junctions, HAST-Knoten, spaeter GNN-Vorbereitung.
- Geospatial Reasoning: GeoPandas, Shapely, pyproj, EPSG:25832, Lat/Lon, Shapefiles, Snapping.
- Fernwaerme-Domain-Wissen: HAST, Vorlauf/Ruecklauf, Ruecklauftemperatur, Durchfluss, Anschlusswert, Filter, Ventile, Stellmotoren, Daemmung.
- Zeitreihenanalyse: Stundenwerte, kumulative Zaehler, Heiz-/Sommerbetrieb, Trend, Peaks, FFT/Oszillation, Feature Engineering.
- Explainable Fault Detection: regelbasierte Baseline erhalten, Begruendungen fuer Techniker lesbar machen, ML nur einfuehren, wenn es einen echten Mehrwert bringt.
- Visualisierung: Folium/Leaflet-Karten, statische Graphplots, klare Trennung zwischen abstraktem Graph und geografischer Karte.
- Datenschutz und Datenhygiene: UEZ-Rohdaten nie committen, nie in oeffentliche Artefakte kopieren, sensible Outputs vorsichtig behandeln.
- Reproduzierbarkeit: requirements aktuell halten, CLI stabil halten, generierte Outputs klar von Quellcode trennen.
- Wissenschaftliches Arbeiten: Annahmen markieren, offene Punkte nicht als Fakten verkaufen, Validierungsschritte dokumentieren.

## Datenschutz / harte Regeln

- `data/raw/` enthaelt vertrauliche Firmendaten von UEZ. Diese Dateien niemals committen, veroeffentlichen oder in Review-ZIPs aufnehmen.
- `data/processed/` und `outputs/` koennen abgeleitete oder sensible Informationen enthalten. Vor Weitergabe bewusst pruefen.
- `.gitignore` schuetzt aktuell `data/raw/*`, `data/processed/*`, `outputs/*`, Caches und lokale Umgebungen. Diese Schutzregeln nicht aufweichen.
- Keine Rohdaten, Kundennummern, Zaehlernummern oder exakten Adresslisten in oeffentlichen Dokumenten ausbreiten, wenn es fuer die Aufgabe nicht noetig ist.
- Netzwerkdienste wie Nominatim/Overpass nur bewusst verwenden; Rate Limits und Datenschutz beachten.

## Aktueller funktionierender Stand

Das Projekt hat eine lauffaehige Grundpipeline:

- `src/load_data.py`: Einlesen der Rohdaten und deutsche Adressnormalisierung.
- `src/build_graph.py`: logischer Graph aus `Nodes_Edges.ods` und raeumlicher Graph aus Shapefiles.
- `src/visualize.py`: statische Topologie und Folium-Karten.
- `src/inspections.py`: Begehungs-Excel in analysefaehige Tabelle und Fehlerhaeufigkeiten.
- `src/synth_data.py`: synthetische Stunden-Zeitreihen mit eingebauten Fehlern.
- `src/features.py`: Feature Engineering aus Zeitreihen.
- `src/fault_detection.py`: regelbasierter Baseline-Klassifikator.
- `src/geocode.py` und `src/osm_addresses.py`: Geocoding ueber Nominatim/Overpass plus Cache/Overrides.
- `src/dashboard_map.py`: kombinierte Folium-Karte.
- `src/main.py`: Ein-Befehl-Pipeline.

Wichtige Pipeline-Kommandos:

```bash
python -m src.main
python -m src.main --synth --detect --plot
python -m src.main --geocode --dashboard
python -m src.main --synth --detect --plot --geocode --dashboard
```

## Datenquellen

Rohdaten liegen lokal in `data/raw/` und sind vertraulich.

- `Leitungsverlauf_*`: Shapefiles des physischen Leitungsverlaufs, CRS ETRS89 / UTM Zone 32N (EPSG:25832), Rohrsegmente mit Materialattributen.
- `Nodes_Edges.ods`: logische Topologie Wiesentheid mit HAST-Adressen, Zaehlernummern, Kundennummern, Anschlusswerten und Kanten.
- `20252810_Ergebnis_Optimierung_FW[45].xlsx`: Vor-Ort-Begehungen mit Alt/Neu-Werten und Massnahmen. Das ist die wichtigste Ground Truth fuer bekannte Fehler.
- Zeitreihen-CSVs: seit 2026-07-08 lokal vorhanden, direkt in `data/raw/` als `<Zaehlernummer>__n.csv` (aeltere Export-Generation, endet ~Mai 2024) und `<Zaehlernummer>_2025n.csv` (endet ~Juli 2025), 154 Dateien fuer 101 Zaehler, Schema identisch zu `synth_data.py`. Loader: `src/load_timeseries.py` (mergen, deduplizieren, materialisieren). Noch nicht an Features/Detection angeschlossen.
- `Zuordnung.xlsx`: Mapping Zaehler zu Verbrauchsstelle, relevant fuer echte Zeitreihen.

## Kritische Fakten und offene Punkte

- Das Briefing nennt als kritischen Punkt die Struktur von `Nodes_Edges.ods`.
- Lokal mit pandas/odfpy voll verifiziert am 2026-07-08: Tabellenblaetter `Nodes` (99 Zeilen: Zaehlernummer, Kundennummer, Anschlusswert, Strasse; 94 eindeutige Adressen), `Edges` (110 Zeilen: Node From, Node To) und `Straßen` (99 Zeilen: V-PIN, Abnahmestelle; redundantes Mapping, von den Loadern nicht genutzt). `build_graph.py` nutzt `Nodes` und `Edges` korrekt.
- Die conda-Umgebung `heating-network` hat alle Dependencies aus `requirements.txt` installiert (inkl. `odfpy`, `geopandas`, `openpyxl`); verifiziert am 2026-07-08.
- Geocoding ist das Hauptproblem: OpenStreetMap enthaelt fuer das relevante Neubaugebiet Wiesentheid keine ausreichenden Hausnummern. Deshalb landen mehrere HAST derselben Strasse auf Strassenmittelpunkten. Das ist eine Datenluecke, kein reiner Codefehler.
- Beste Loesung fuer Geocoding: UEZ nach GIS-Koordinaten der HAST fragen. Alternative: amtlicher BKG-Geocoder. Uebergang: `data/manual/address_overrides.csv`.
- Logischer Graph und raeumlicher Graph sind noch nicht sauber verbunden. Das geplante Snapping geocodeter HAST an Rohrknoten haengt an verlaesslichen Koordinaten.
- Echte Zeitreihen sind vorhanden und per `src/load_timeseries.py` lesbar, aber noch nicht in Features/Detection integriert. Aktuelle Fault Detection laeuft auf synthetischen Daten und ist nur Pipeline-/Baseline-Validierung. Offene Entscheidungen vor Integration: Analysefenster, Zaehlertausch-Stitching via `Zuordnung.xlsx` (16 CSV-Zaehler fehlen in der Topologie, 14 Topologie-Zaehler ohne CSV), Umgang mit Messrauschen/Luecken.
- GNN ist geplant, aber noch nicht umgesetzt. Erst sinnvoll, wenn echte Zeitreihen und saubere Graph-Features vorliegen.
- Es gibt HAST ohne Kanten/Verbindungen in der logischen Topologie. Diese Waisen-HAST sind wahrscheinlich Datenqualitaetsfragen fuer UEZ.
- Terminologie sauber halten: `logical_topology.png` ist der abstrakte Graph; `dashboard_map.html` ist die geografische Karte.

## Priorisierte naechste Schritte

1. Umgebung reproduzierbar machen: `pip install -r requirements.txt` pruefen, besonders `odfpy`, `geopandas`, `openpyxl`.
2. `Nodes_Edges.ods` mit pandas voll verifizieren: Sheetnamen, Spalten, Zeilenzahlen, erwartete Loader-Semantik.
3. README/Docs an lokale Realitaet angleichen: Wiesentheid vs. alte Prichsenstadt-Formulierungen, Zahlen wie 66/67 Begehungen und 94/99 HAST konsistent machen.
4. Geocoding-Datenluecke fachlich loesen: UEZ-Koordinaten oder BKG-Geocoder vor Code-Akrobatik bevorzugen.
5. Loader fuer echte Zeitreihen bauen, sobald CSVs vorhanden sind. Ziel: gleiche Feature-Schnittstelle wie bei synthetischen Daten.
6. Baseline auf echten Daten evaluieren und Schwellenwerte mit Begehungs-Ground-Truth kalibrieren.
7. Logischen und raeumlichen Graph verbinden: HAST-Koordinaten an naechstgelegene Rohrknoten snappen, Distanz/Unsicherheit speichern.
8. Dashboard auf echte Daten umstellen und Ampellogik validieren.
9. Dokumentation aufbauen: Datenquellen, Pipeline, Entscheidungen, Limitationen, bekannte Datenprobleme und naechste Schritte.
10. Erst danach GNN/ML ausbauen: klare Datenbasis, Labels und Baseline-Vergleich voraussetzen.

## Arbeitsweise fuer Claude

- Lies zuerst `README.md`, `src/main.py`, `src/load_data.py` und das relevante Modul, bevor du Code aenderst.
- Bevor du Aussagen ueber Datenmengen machst, fuehre lokale Checks aus. Zahlen aus Briefing/README koennen voneinander abweichen.
- Aendere nur, was zur Aufgabe gehoert. Keine grossen Refactorings ohne Not.
- Erhalte die CLI in `src/main.py` rueckwaertskompatibel.
- Erhalte die Schnittstellen zwischen `synth_data.py`, `features.py` und `fault_detection.py`, bis echte Zeitreihen sauber integriert sind.
- Markiere Annahmen im Code oder in der Doku, wenn sie aus synthetischen Daten stammen.
- Wenn neue Abhaengigkeiten noetig sind, in `requirements.txt` eintragen und begruenden.
- Fuehre nach Aenderungen mindestens einen passenden Smoke Test aus, z.B. `python -m src.main`, `python -m src.main --synth --detect`, oder gezielte Modulchecks.
- Wenn Tests wegen fehlender Rohdaten, fehlender Dependencies oder Netzwerkzugriff nicht laufen, dokumentiere das ehrlich.

## Qualitaetskriterien

- Kein stilles Scheitern bei fehlenden Rohdaten: klare Fehlermeldungen mit erwarteten Dateipfaden.
- Adressnormalisierung muss deterministisch und nachvollziehbar bleiben.
- Graphaufbau muss Junctions, HAST und fehlende Kanten klar unterscheiden.
- Geocoding-Ergebnisse muessen Quelle, Cache/Override-Status und Unsicherheit/Distanz erkennen lassen.
- Fault-Detection-Ergebnisse sollen erklaerbare Gruende enthalten, nicht nur Labels.
- Visualisierungen muessen Graph und Karte terminologisch sauber trennen.
- Dokumentation soll auch Grenzen nennen: synthetische Daten, OSM-Hausnummernluecke, fehlende echte Zeitreihen, ungeklaerte Waisen-HAST.

## Nuetzliche lokale Checks

```bash
python -m src.main
python -m src.main --synth --detect --plot
python -m src.main --geocode --dashboard
```

ODS-Struktur pruefen:

```bash
python -c "import pandas as pd; xls = pd.ExcelFile('data/raw/Nodes_Edges.ods', engine='odf'); print(xls.sheet_names); [print(s, len(pd.read_excel(xls, sheet_name=s, engine='odf')), list(pd.read_excel(xls, sheet_name=s, engine='odf').columns)) for s in xls.sheet_names]"
```

Ohne `odfpy` kann man zumindest die Sheetnamen direkt aus der ODS-Datei lesen:

```bash
unzip -p data/raw/Nodes_Edges.ods content.xml | perl -ne 'while(/table:name="([^"]+)"/g){print "$1\n"}'
```

## Nicht tun

- Keine vertraulichen Rohdaten committen oder in ZIPs fuer externe Reviews packen.
- Keine falsche Sicherheit beim Geocoding vortaeuschen, wenn OSM nur Strassenmittelpunkte liefert.
- Keine ML/GNN-Komplexitaet einfuehren, bevor echte Daten, Labels und Baseline-Vergleich stehen.
- Keine automatisch generierten grossen Artefakte versionieren, sofern sie nicht explizit gewuenscht sind.
- Keine Fachbegriffe vermischen: HAST, Junction, Rohrknoten, logischer Graph, raeumlicher Graph und Dashboard-Karte sind verschiedene Dinge.

