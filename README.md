# Heating Network Fault Detection — ÜZ Mainfranken

Projektseminar in Zusammenarbeit mit **ÜZ Mainfranken** zur Fehlererkennung
und Leistungsoptimierung in Fernwärmenetzen.
Julius-Maximilians-Universität Würzburg, SS 2026 / WS 2026.

> **Status: Datenexploration & Graphaufbau (Schritt 1 von N).**
> Zeitreihen-Zählerdaten aus CSV-Dateien für 2024 / 2025 / 2026
> sowie Predictive-Maintenance-Modellierung folgen in späteren Iterationen.

## Inhalt

| Pfad | Zweck |
|---|---|
| `src/load_data.py` | Einlesen von Shapefiles, ODS-Topologie und Optimierungs-Excel, inklusive deutscher Adressnormalisierung |
| `src/build_graph.py` | Logischer Graph mit NetworkX aus der Adresstopologie + räumlicher Graph aus der Leitungsgeometrie |
| `src/visualize.py` | Statische PNG-Topologie + interaktive Folium-Karte des Leitungsnetzes |
| `src/inspections.py` | Aufbereitete Ansicht der Vor-Ort-Inspektions- und Optimierungsdaten |
| `src/synth_data.py` | Synthetische stündliche Zählerdaten mit eingebetteten Fehlern, 5 Fehlertypen, 1 Jahr |
| `src/features.py` | Feature Engineering für Zeitreihen, ca. 25 numerische Merkmale pro HAST |
| `src/fault_detection.py` | Regelbasierter Fehlerklassifikator — Baseline für das spätere ML-Modell |
| `src/geocode.py` | Geokodierung von HAST-Adressen über Nominatim, mit persistentem Cache |
| `src/geocode_stub.py` | Offline-Koordinaten-Stubs — nur für Sandbox-Tests, niemals lokal ausführen |
| `src/dashboard_map.py` | Kombinierte Karte: Leitungen + geokodierte HAST + Inspektionsbefunde + vorhergesagte Fehler |
| `src/main.py` | End-to-End-Pipeline mit einem Befehl |
| `data/raw/` | Quelldateien von ÜZ — **gitignored**, niemals committen |
| `data/processed/` | Abgeleitete CSV-Dateien — **gitignored** |
| `outputs/` | Generierte Visualisierungen — **gitignored** |
| `docs/` | Ausführliche Dokumentation, Ziel: Read the Docs / GitHub Pages |

## Schnellstart

```bash
git clone <repo-url>
cd heating-network
pip install -r requirements.txt
# ÜZ-Datendateien in data/raw/ ablegen  (NICHT committen - siehe .gitignore)
python -m src.main                                          # Graphen + Karten + Inspektionsübersicht
python -m src.main --synth --detect --plot                  # zusätzlich synthetische Daten + Fehlererkennung
python -m src.main --geocode --dashboard                    # Geokodierung der HAST + Dashboard-Karte
python -m src.main --synth --detect --plot --geocode --dashboard  # alles ausführen
```

**Hinweis zur Geokodierung.** Beim ersten lokalen Ausführen mit `--geocode`
wird Nominatim einmal pro eindeutiger Adresse abgefragt, also ca. 99 Anfragen.
Die Abfragen sind auf 1 Anfrage pro Sekunde begrenzt und dauern dadurch
ungefähr 100 Sekunden. Die Ergebnisse werden in
`data/processed/geocode_cache.json` zwischengespeichert, sodass spätere
Ausführungen sofort verfügbar sind.

## Datenquellen

Drei Datenquellen von ÜZ, roh und **niemals zu committen**:

1. **Shapefiles `Leitungsverlauf_*`** — physischer Leitungsverlauf für das
   gesamte Versorgungsgebiet von ÜZ Mainfranken. CRS: ETRS89 / UTM 32N
   (EPSG:25832). Enthalten sind 1.305 Liniensegmente mit Materialattributen
   wie Stahlrohr, ISOPEX PE-X und Uponor PE-X sowie 16 markierte Punkte
   (Abzweigungen / Stationen).

2. **`Nodes_Edges.ods`** — logische Topologie des Teilnetzes Prichsenstadt.
   Enthalten sind 99 Kundenanschlusspunkte (HAST), verknüpft über
   Zählernummer, Adresse und vertragliche Anschlussleistung (Anschlusswert),
   sowie 110 Kanten zwischen Adressen.

3. **`20252810_Ergebnis_Optimierung_FW_45_.xlsx`** — 67 Vor-Ort-
   Inspektionsdatensätze zu HAST mit alten und neuen Werten für
   Anlagenkonfiguration, Heizzeiten, Vertragsleistung und Regelparameter
   PA1.1–PA1.9. Zusätzlich enthält die Datei Ja/Nein-Markierungen dazu,
   was repariert wurde, z. B. Filter, Ventil, Stellantrieb, Dämmung oder
   Regler. **Diese Datei bildet den gelabelten Fehlerdatensatz.**

CSV-Zeitreihen pro Zähler mit Zeitstempel, Energie in kWh, Volumenstrom in l/h,
Leistung in kW, ΔT, Vorlauf in °C, Rücklauf in °C und Volumen in m³ für
2024 / 2025 / 2026 werden im nächsten Schritt ergänzt.

## Bisheriger Erkenntnisstand

Das Netz ist im Wesentlichen ein **Baum mit 110 Knoten und einem maximalen
Knotengrad von 4**, wobei zwei Verbraucher mit hoher Anschlussleistung
(ca. 250 kW und ca. 500 kW) als zentrale Knotenpunkte fungieren.
Die gesamte vertragliche Anschlussleistung beträgt ungefähr 2 MW über 94 HAST.

## Baseline für die Fehlererkennung

`src/fault_detection.py` ist ein regelbasierter Klassifikator, der das
Fachwissen aus der Inspektions-Excel-Datei über klare Schwellenwerte abbildet.
Er erfüllt drei Zwecke:

1. **Validierung der Pipeline.** Auf synthetischen Daten mit eingebetteten
   Fehlern erkennt das Regelwerk derzeit **100 % der eingefügten Fehler ohne
   False Positives** über 99 HAST hinweg. Das bestätigt, dass die Feature-
   Pipeline in sich konsistent ist.

2. **Benchmark.** Jedes spätere ML-Modell muss diese Baseline übertreffen,
   damit ein Einsatz sinnvoll ist.

3. **Erklärbarkeit.** Jede Markierung enthält eine verständliche Begründung
   (`"Sommer-Median des Volumenstroms 47 l/h (sollte ungefähr 0 sein)"`),
   die sich für ein Techniker-Dashboard eignet.

Derzeit sind fünf Fehlerfamilien umgesetzt:

| Fehler | Erkennungssignal |
|---|---|
| `fouled_filter` | 95. Perzentil des Volumenstroms sinkt von Monat zu Monat |
| `excess_rt` | Rücklauftemperatur im Winter > 48 °C oder Rücklauftemperatur > 50 °C in mehr als 30 % der belasteten Stunden |
| `continuous_flow` | Sommer-Median des Volumenstroms > 25 l/h, obwohl echtes Warmwasserverhalten stoßartig ist |
| `oversized_contract` | Spitzenleistung < 40 % der vertraglichen Anschlussleistung |
| `control_hysteresis` | Periodische Komponente von 4–12 Stunden erklärt mehr als 7 % der gesamten Varianz des Volumenstroms |

Diese Regeln werden später zu Klassifikatoren weiterentwickelt, sobald die
realen CSV-Daten vorliegen und die daraus erzeugten Features mit den
Inspektionslabels verknüpft werden können.

## Korrelationen zwischen Inspektionen und HAST-Eigenschaften

Eine erste Auswertung der 66 Inspektionsdatensätze, verknüpft mit Gebäudealter
und Anlagenkonfiguration, deutet auf drei praxisrelevante Muster hin:

* **Anlagenkonfiguration 2.1** kommt mit Abstand am häufigsten vor
  (32 / 66 HAST) und zeigt die höchste Filterreinigungsrate (53 %) sowie
  die höchste Rate für Volumenstrom-Nachregulierungen (47 %). Damit ist sie
  vermutlich das aussichtsreichste Ziel für eine gezielte Kampagne.

* **Von 11 Änderungen der Vertragsleistung waren 9 Reduzierungen**
  (Median −2 kW), was zu einer chronischen Überdimensionierung auf
  Kundenseite passt.

* **„Schmutzfänger“ erscheint zusätzlich 8-mal in Freitextnotizen**,
  neben der formalen Filter-Markierung. Die tatsächliche Verschmutzungsrate
  liegt daher wahrscheinlich höher als die 47 %, die sich aus den
  strukturierten Spalten ergeben.

## Bekannte Datenqualitätsprobleme

* `Nodes_Edges.ods` mischt unterschiedliche Schreibweisen von Straßennamen
  (`Blumenstr.`, `Blumenstraße`) — Adressen werden deshalb in
  `load_data._normalize_address` normalisiert.

* `Optimierung.xlsx` enthält den Tippfehler **Fleider**straße. Dieser wird in
  `load_inspections` behandelt.

* 8 HAST erscheinen im Tabellenblatt `Nodes`, werden aber von keiner Kante
  referenziert. Sie sind damit Waisen in der Topologie und sollten mit ÜZ
  rückgeklärt werden.

* Der `Point`-Layer der Shapefile enthält nur 16 markierte Punkte und keine
  Labels, die direkt zur Adresstopologie passen. Deshalb ist aktuell keine
  direkte Verknüpfung zwischen physischer Geometrie und logischen Adressen
  möglich. Die Geokodierung über Nominatim steht auf der To-do-Liste.

## Roadmap

- [x] Alle drei Datenquellen laden, Adressen normalisieren und erste Graphen erstellen
- [x] Pipeline mit einem Befehl; statische und interaktive Visualisierungen
- [x] Erste Häufigkeitstabelle der Fehler aus den Inspektionsdaten
- [x] Generator für synthetische Zeitreihen mit 5 eingebetteten Fehlertypen (`synth_data.py`)
- [x] Feature Engineering auf HAST-Ebene aus stündlichen Zählerdaten (`features.py`)
- [x] Regelbasierte Baseline zur Fehlererkennung — 100 % Genauigkeit auf synthetischen Daten
- [x] Korrelationsanalyse zwischen Inspektionen und Anlagenkonfiguration / Baujahr / Anschlusswert
- [x] Adressen geokodieren → logischen Graphen mit räumlicher Geometrie verbinden (`geocode.py`)
- [x] Kombinierte Dashboard-Karte mit Inspektionsbefunden und vorhergesagten Fehlern pro HAST
- [ ] Zeitreihen-CSV-Dateien pro Zähler für 2024 / 2025 / 2026 einlesen und synthetische Daten ersetzen
- [ ] Tree-Ensemble-Klassifikator mit Inspektionsdatensätzen als Labels trainieren
- [ ] Geokodierte HAST mit dem jeweils nächsten Knoten des räumlichen Graphen verbinden
- [ ] Predictive-Maintenance-Dashboard entwickeln, z. B. mit Streamlit oder einem ähnlichen Framework
- [ ] Vollständige Read-the-Docs-Dokumentation über GitHub Pages bereitstellen
