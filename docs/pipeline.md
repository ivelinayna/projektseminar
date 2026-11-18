# Pipeline und Module

Der Code liegt in `src/`, die Auswertungen in `notebooks/`, die Tests in `tests/`. Wiederverwendbare Logik steht in
`src/`. Die Notebooks rufen sie auf und zeigen die Ergebnisse.

## Datenfluss

```text
data/raw/  (Zähler-CSV, ODS, Begehungen, Zuordnung, Netz)
   |
   |  Notebook 00  (einziger Ladeweg)
   v
data/processed/real_meters/   Stundenreihe je Zähler
   |
   |  nb00_daten.lade_serien()  +  weather (DWD-Außentemperatur)
   v
Notebooks 01-36 und src-Module
   |
   +-- Notebook 10   -> hast_tage            (Tageswerte für 18, 30, 34, 38)
   +-- Notebook 18   -> normalmodell_*       (für 30, 34)
   +-- Notebooks 25-29 -> Modelldaten, LSTM-Embedding, Ventil-Modell
   +-- Notebook 24   -> monitor_status       (für 33)
   +-- Notebook 31   -> notebooks/daten_cache/  (Netz, für 32, 33, 36)
   +-- Notebook 35   -> models/              (Modellpakete)
          |
          |  python -m src.dashboard_daten
          v
      outputs/dashboard/  ->  Notebook 36  ->  fernwaerme_dashboard_final.html
```

## Befehle

| Befehl | Zweck |
|---|---|
| `python -m src.weather` | Außentemperatur der DWD-Station Kitzingen holen, Cache in `data/raw/weather/` |
| `python -m src.main` | Graphen, Karten und Begehungstabelle `inspections_tidy.csv` (für Notebook 08) |
| `python -m src.main --dashboard` | zusätzlich eine einfache Folium-Karte |
| `python -m src.aktualisieren` | neue Zählerdaten einspielen: Notebook 00, Wetter, Netzvergleich, Tagesmonitor, Bericht |
| `python -m src.prognose_waechter --bauen --gegenprobe` | Paket Prognose-LSTM bauen |
| `python -m src.normalmodell_waechter --bauen` | Paket Tagesmonitor bauen |
| `python -m src.fehlerklassen --bauen --gegenprobe` | Paket Folie-5-Klassen bauen |
| `python -m src.modellpaket` | gespeicherte Pakete auflisten |
| `python -m src.dashboard_daten` | Pakete auf aktuelle Daten anwenden, Ergebnis nach `outputs/dashboard/` |
| `streamlit run src/dashboard_app.py` | ältere Streamlit-App |

## Module

Die Spalte „Notebooks“ nennt, wo das Modul benutzt wird.

### Daten laden und aufbereiten

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `nb00_daten` | Zugang zu den Stundenreihen aus Notebook 00, Stationsmerkmale | 01, 04, 05, 06, 09, 16, 17, 34 |
| `load_data` | Netzdaten, Begehungen, Adressabgleich (`_normalize_address`) | 08, 09, 16, 19, 25 |
| `load_begehungen` | Begehungen und Zuordnung Zählernummer zu Abnahmestelle | viele |
| `load_timeseries` | Rohdaten-Inventur und Prüfung der ODS-Nachlieferung | 05 |
| `luecken` | fehlende Stundenwerte auffüllen | 01 |
| `weather` | Außentemperatur vom DWD | viele |
| `season` | Saisonabschnitte (Kernwinter, Übergang, Sommer) | 04 |
| `meter_quality` | Zähler nach Datenqualität einteilen | nur Befehlszeile |
| `profile_timeseries` | erste Datensichtung der CSV | nur Befehlszeile |
| `synth_data` | künstliche Testreihen | nur Befehlszeile |

### Merkmale

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `features` | etwa 25 Stationsmerkmale | 09, 16, 34 |
| `window_features` | Merkmale in 14-Tage-Fenstern mit Begehungsmarke | nur Befehlszeile |
| `tagespanel` | Tabelle Station mal Tag | 16, 17, 34 |
| `dynamik` | Änderungstempo des Rücklaufs | 16 |
| `performance` | Kennzahl kWh/m³ gegen Außentemperatur | 05 |

### Begehungen und Labels

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `jahresvergleich` | Vorher/Nachher zum selben Kalenderzeitpunkt | 04, 16 |
| `befundcodes` | Freitexte der Begehungen in Befundcodes | 14, 15, 19 bis 23, 25 |
| `freitext` | Freitexte in Fehlerkategorien | 17 |
| `fallsammlung` | Fälle zur Begehungswirkung im Ternärbild | 15, 21, 23 |
| `inspections` | schnelle Auswertung der Begehungsbefunde | 25 |

### Clustering

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `clustervalidierung` | Stabilität und Prüfung der Cluster aus 07 bis 09 | 09, 16, 17, 34 |

### Stationsbilder und Kennlinien

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `ternaer` | Ternärdiagramme je Station | 11 bis 15, 19 |
| `stationsbilder` | drei ergänzende Stationsbilder | 01, 12, 13, 19 |
| `kennlinien_monitor` | Kennlinienüberwachung ohne Labels | 13, 14, 19, 34 |

### Anomalien, Monitoring und Empfehlung

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `anomalie` | Anomalieerkennung ohne Labels | 16, 17, 34 |
| `regelkalibrierung` | Regel-Baseline an echten Daten nachstellen | 16, 34 |
| `fault_detection` | ursprüngliche Regel-Baseline | 34 |
| `empfehlung` | vom Anomaliewert zur Handlungsempfehlung | 17, 34 |
| `priority` | Wartungspriorität als Punktwert | 17 |
| `netzvergleich` | Station im Vergleich zum Netz im Winter | 19, 21 bis 23, 34 |
| `tagesmonitor` | wetterbereinigte Tageswerte mit CUSUM-Alarm | 20, 21, 24, 34, 35 |
| `alarmbewertung` | Schwelle, Richtung und Priorität der Alarme | 21, 23, 24, 34 |
| `stationsblatt` | Monitorbild je Station, `status.csv` | 19 bis 24, 34 |
| `vergleichsgruppen` | Vergleichsgruppen nach Wärmemenge | 23, 34 |
| `nachbarschaft` | häufen sich auffällige Stationen im Netz? | 23, 24, 34 |
| `netzereignisse` | gleichzeitige Alarme: Netz oder Einzelstation? | 24, 34 |
| `zeitreihenmodell` | ARIMA und SARIMAX auf Tagesmitteln | 06, 34 |
| `detect_real` | Regel-Baseline auf echten Daten | nur Befehlszeile |
| `ml_classifier` | überwachter Klassifikator (Negativbefund) | nur Befehlszeile |

### Modelle und Vergleich

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `pruefstand` | alle Verfahren unter gleichen Bedingungen prüfen | 34, 35 |
| `normalmodell_waechter` | Tagesmonitor als Paket | 34, 35 |
| `prognose_waechter` | Prognose-LSTM als Paket | 34, 35 |
| `fehlerklassen` | Folie-5-Klassen als Paket | 34, 35 |
| `finalvergleich` | Monitoring-Modell gegen LSTM-Modell, Endmodell | 35 |
| `modellpaket` | Pakete speichern und laden | 34 bis 36 |

### Netz und Karte

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `build_graph` | Netzgraph aus Shapefiles und Knotenliste | 23, 24, 34 |
| `network_graph` | interaktive Ansicht des logischen Netzes | nur Befehlszeile |
| `geocode`, `geocode_stub`, `osm_addresses` | Adressen in Koordinaten | nur Befehlszeile |
| `snap_hast` | Stationen an den nächsten Netzknoten setzen | nur Befehlszeile |
| `visualize` | Netzbilder | nur Befehlszeile |

### Dashboard und Betrieb

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `dashboard_daten` | Modellergebnisse für das Dashboard | 36 |
| `dashboard_karte` | Modellergebnisse in die Netzkarte | 36 |
| `dashboard_map` | einfache Folium-Karte | nur Befehlszeile |
| `dashboard_app` | ältere Streamlit-App | nur Befehlszeile |
| `aktualisieren` | neue Daten in einem Schritt einspielen | nur Befehlszeile |
| `main` | Gesamtablauf Netz, Karten, Begehungstabelle | nur Befehlszeile |

## Modellpakete

- Ein Paket enthält das gelernte Modell und alles, was zum Anwenden gehört: Merkmalsliste, Schwellen, Zeiträume, Version.
- Pakete liegen in `models/` und sind gitignored.
- Es gibt drei Pakete: `normalmodell` (Tagesmonitor), `prognose_lstm` (Prognose-Wächter) und `fehlerklassen` (Folie 5).
- Das Dashboard wendet nur fertige Pakete an und lernt nichts neu.

## Tests

```bash
python -m pytest -q
```

- Eine Testdatei je Modul in `tests/`, insgesamt 40 Dateien.
- Die meisten Tests nutzen kleine künstliche Daten und laufen ohne Rohdaten.
- Tests, die Begehungen oder echte Reihen brauchen, werden ohne diese Daten übersprungen.

Letzter Lauf am 13.11.2026: 589 Tests bestanden, 1 übersprungen. `pytest.ini` beschränkt die Suche auf `tests/`.
