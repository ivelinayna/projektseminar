# Dashboard (Streamlit-App)

Interaktive Stationsübersicht für ÜZ Mainfranken. Das ist die
**geografische Dashboard-Karte** — nicht zu verwechseln mit dem
abstrakten logischen Netzgraphen (`outputs/logical_topology.png`).

## Starten

```bash
streamlit run src/dashboard_app.py
```

Voraussetzung: die Pipeline-Artefakte in `data/processed/` existieren.
Die App startet auch, wenn einzelne fehlen, und nennt dann das
Erzeugungskommando. Vollständig erzeugen:

```bash
python -m src.main --geocode      # inspections_tidy.csv, hast_geocoded.csv
python -m src.meter_quality       # meter_quality.csv
python -m src.detect_real         # features_real.csv, predictions_real.csv, real_meters_window/
python -m src.snap_hast           # hast_snapped.csv (Station -> Rohrknoten)
python -m src.priority            # priority_scores.csv (Wartungspriorisierung)
```

## Worauf die Ampel basiert

**Bewusst NICHT auf der Fehlererkennung.** Die regelbasierte Baseline
meldet auf echten Daten für praktisch jede Station einen Fehler (siehe
[echte-daten-integration.md](echte-daten-integration.md)) und ist damit
nicht entscheidungstauglich. Die Ampel nutzt stattdessen die direkt
gemessene **mittlere Winter-Rücklauftemperatur** aus den echten
Features — laut ÜZ-Problembeschreibung der zentrale
Effizienz-Indikator.

| Kategorie | Winter-Rücklauf |
|---|---|
| 🟢 Grün | < 45 °C |
| 🟡 Gelb | 45–50 °C |
| 🟠 Orange | 50–55 °C |
| 🔴 Rot | > 55 °C |
| ⚪ Keine verlässlichen Daten | Qualitätsklasse nicht `auswertbar`, keine Zeitreihen oder kein Winterwert |

**Die Schwellen sind Startwerte und fachlich mit ÜZ zu validieren**
(Konstanten `RT_*_MAX` oben in `src/dashboard_app.py`). Stationen ohne
verlässliche Daten werden nie grün gefärbt — grau ist eine eigene,
ehrliche Kategorie. Die Statusfarben sind gegen die
Farbfehlsichtigkeits-Checks validiert; Farbe steht nie allein
(Emoji + Textlabel überall).

## Datenquellen (nur vorhandene Artefakte, keine eigene Verarbeitung)

| Datei | Liefert |
|---|---|
| `data/processed/hast_geocoded.csv` | Stationen, Adressen, Koordinaten inkl. Unsicherheits-Notiz |
| `data/processed/meter_quality.csv` | Qualitätsklasse je Zähler |
| `data/processed/features_real.csv` | Winter-Rücklauf/-Vorlauf je Zähler (echte Daten) |
| `data/processed/inspections_tidy.csv` | Letzte Begehung + Maßnahmen je Adresse |
| `data/processed/real_meters_window/` | Zeitreihen fürs Detail-Diagramm |
| `data/processed/predictions_real.csv` | Nur Transparenz-Anzeige im Entwicklungs-Bereich |
| `data/processed/hast_snapped.csv` | Snapping-Distanz Station → nächster Rohrknoten |
| `data/processed/priority_scores.csv` | Prioritäts-Score inkl. Einzelkomponenten und Klartext-Begründung |
| `data/raw/Leitungsverlauf_*.shp` | Rohrgeometrie-Overlay (via bestehende Loader + `visualize.find_main_cluster`) |

## Rohrnetz-Overlay und Snapping

Die Karte zeigt die **geografische Rohrgeometrie** des
Wiesentheid-Clusters als dezente graue Linien unter den
Stationspunkten (das Overlay ist NICHT der abstrakte logische Graph).
`src/snap_hast.py` ordnet jeder Station den nächstgelegenen Knoten des
räumlichen Graphen zu und speichert die Distanz in Metern. Die
Distanzschwelle (`SNAP_MAX_DIST_M = 50 m`) ist ein Ehrlichkeits-Maß:
Stationen darüber gelten als nicht verlässlich am Netz verortet und
werden im Detailpanel entsprechend markiert. Wichtig zur
Interpretation: Da fast alle Koordinaten Straßenmittelpunkt-Fallbacks
sind, beweist eine *kleine* Distanz keine korrekte Zuordnung — aber
eine *große* Distanz beweist eine unverlässliche. Die optionalen
Zuordnungslinien auf der Karte werden nur für Stationen innerhalb der
Schwelle gezeichnet.

## Netz-Gesamtschau

Aggregierte Effizienz-Sicht auf Basis der gemessenen
Winter-Rücklauftemperatur (nicht der Fehlererkennung):

- **Histogramm** des Winter-Rücklaufs über alle bewerteten Stationen,
  Balken im jeweiligen Ampelband eingefärbt, Ampelschwellen (45/50/55
  °C) als gestrichelte Markierungen.
- **Straßenzüge im Vergleich:** Stationen, bewertete Stationen,
  Median- und Max-Rücklauf je Straße, sortierbar. **Warum das
  belastbarer ist als die Einzelposition:** Die *Straßenzuordnung*
  jeder Station stammt aus der Adresse und ist sicher; unsicher ist
  nur die genaue *Hausposition* (OSM-Hausnummernlücke). Aggregierte
  Straßenwerte sind davon unberührt. Gruppiert wird über die
  normalisierte Adresse, damit Schreibvarianten (Rosenstr. /
  Rosenstraße) nicht als zwei Straßen zählen.
- **Netz-Kennzahlen** ohne erfundene Prozente: Anzahl und Anteil je
  Ampelkategorie, Median-/Mittel-Rücklauf, Anzahl Stationen ohne
  verlässliche Daten (separat ausgewiesen, nicht bewertet).

## Kartendarstellung der Stationscluster

Wegen der OSM-Hausnummernlücke liegen mehrere HAST einer Straße auf
demselben Straßenmittelpunkt. Zur Lesbarkeit werden sie kompakt in
Sonnenblumen-Anordnung aufgefächert (deterministisch, ~4–13 m) — das
ist **keine echte Position** und rät keine Hausreihenfolge. Ein
dauerhafter Hinweis direkt auf der Karte (nicht nur im Hover) sagt:
„Stationspunkte straßenweise gruppiert — genaue Hausposition unbekannt
(ÜZ-Koordinaten ausstehend)".

## Wartungspriorisierung (`src/priority.py`)

**Priorisierte Handlungsempfehlung auf Basis aktueller Messwerte —
ausdrücklich KEINE Ausfallvorhersage und kein ML.** Der Score ist eine
transparente gewichtete Summe normalisierter Komponenten (0–100
Punkte); jede Komponente steht einzeln im Output und im Detailpanel:

| Komponente | Gewicht | Normalisierung |
|---|---|---|
| Rücklauf | 0,60 | (Winter-Rücklauf − 45 °C) / 15 K, gekappt auf 0–1 — zentraler Effizienz-Indikator laut ÜZ |
| Anschlusswert | 0,15 | log-skaliert auf den größten Anschlusswert — Ineffizienz großer Verbraucher wirkt stärker aufs Netz |
| Begehungsalter | 0,25 | keine dokumentierte Begehung = 1; sonst Tage seit Begehung / 730, gekappt — Informationslücke = Handlungsbedarf |

Alle Gewichte und Schwellen sind benannte Konstanten oben in
`src/priority.py` und **mit ÜZ fachlich zu validieren** (Startwerte).
Der Score ist bewusst zeitabhängig: das Begehungsalter wächst.

Stationen mit Datenqualitätsproblemen (Qualitätsklasse nicht
`auswertbar`, keine Zeitreihen, kein Winterwert) bekommen **keinen
Score**, sondern die separate Klasse **„erst Daten klären"** —
Datenlücken werden nicht mit Effizienz-Auffälligkeiten vermischt und
landen am Ende der Liste, nicht oben.

Im Dashboard: Top-Handlungsempfehlungen (8 Stationen) im Kopfbereich,
Score-Spalte + Prioritäts-Sortierung in der Stationsliste (die
Ampel-/Rücklauf-Sortierung bleibt als Option), Score-Aufschlüsselung
mit Klartext-Begründung im Detailpanel.

## Gestaltung (rein kosmetisch, Stand 2026-07-17)

Die Überarbeitung hat **keine Berechnung, Schwelle oder Kennzeichnung
verändert** — nur Darstellung und Anordnung:

- **Header-Banner** (Blau-Verlauf, minimales dokumentiertes CSS im
  Modulkopf): Projekttitel, Kontext (ÜZ Mainfranken · Projektseminar
  JMU Würzburg), plus die ehrlichen Dauerhinweise (geografische Karte
  vs. abstrakter Graph; Ampel = gemessener Rücklauf, Schwellen mit ÜZ
  zu validieren) direkt im Header.
- **Kennzahlen-Kacheln:** die vier bestehenden `st.metric`-Werte als
  umrandete Kacheln; die Ampelverteilung als Farbpunkt-Badges (Farben
  unverändert, immer mit Textlabel).
- **Tab-Navigation** statt langem Scrollen: 🗺️ Netzkarte &
  Stationsdetail · 🎯 Priorisierung & Stationsliste ·
  📊 Netz-Gesamtschau · 🚧 Fehlererkennung (in Entwicklung). Der
  „in Entwicklung"-Charakter steht sichtbar im Tab-Titel.
- CSS bewusst minimal (Theme-Variablen mit Fallbacks für Light/Dark);
  Ampelfarben bleiben ausschließlich dem Stationsstatus vorbehalten,
  das Rahmen-Farbschema ist Blau/Grau.

## Ehrlichkeits-Merkmale

- **Positionsunsicherheit sichtbar:** HAST, die wegen der bekannten
  OSM-Hausnummernlücke auf Straßenmittelpunkten liegen, werden
  halbtransparent gezeichnet, im Hover markiert und zur Sichtbarkeit
  leicht aufgefächert (~15 m, in der Karte als solches ausgewiesen).
  Die Snapping-Distanz ergänzt diese Kennzeichnung, sie ersetzt sie
  nicht.
- **Keine erfundenen Kennzahlen:** der Kopfbereich zeigt nur Zählungen
  und den Median-Rücklauf der bewerteten Stationen.
- **Fehlererkennung als Baustelle:** eigener Bereich erklärt, dass die
  Baseline auf echten Daten nicht trennscharf ist; der aktuelle Output
  ist nur in einem Transparenz-Expander sichtbar und ausdrücklich
  nicht für Entscheidungen gedacht.

## Bewusst noch nicht enthalten

- Funktionierende automatische Fehlererkennung (Baseline muss erst auf
  echten Daten rekalibriert werden; danach ML mit Begehungslabels).
- Simulation / Was-wäre-wenn-Szenarien.
- Ein belastbarer Join logischer ↔ räumlicher Graph: das Snapping
  liefert Kandidaten-Zuordnungen samt Distanz, aber solange die
  Koordinaten Straßenmittelpunkte sind, bleibt die Zuordnung
  näherungsweise (echte HAST-Koordinaten von ÜZ ausstehend).
- Zählertausch-Stitching (`Zuordnung.xlsx`).

## Test

```bash
python -m tests.test_dashboard_app   # rendert alle Bereiche headless (AppTest)
```

Hinweis Umgebung: `pyarrow` ist auf < 25 gepinnt — pyarrow 25
segfaultet bei Streamlit-Reruns (zweiter Script-Thread) in dieser
Umgebung; mit 21.x stabil. Zusätzlich erzwingt die App
Python-String-Storage in pandas (siehe Kommentar im Modulkopf).
