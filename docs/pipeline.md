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
Notebooks 01-40 und src-Module
   |
   +-- Notebook 11   -> hast_tage            (Tageswerte für 20, 32, 37, 38)
   +-- Notebook 20   -> normalmodell_*       (für 32, 38)
   +-- Notebooks 27-31 -> Modelldaten, LSTM-Embedding, Ventil-Modell
   +-- Notebook 26   -> monitor_status       (für 36)
   +-- Notebook 34   -> notebooks/daten_cache/  (Netz, für 35, 36, 40)
   +-- Notebook 39   -> models/              (Modellpakete)
          |
          |  python -m src.dashboard_daten
          v
      outputs/dashboard/  ->  Notebook 40  ->  fernwaerme_dashboard_final.html
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
| `nb00_daten` | Zugang zu den Stundenreihen aus Notebook 00, Stationsmerkmale | 01, 04, 05, 06, 10, 18, 19, 38 |
| `load_data` | Netzdaten, Begehungen, Adressabgleich (`_normalize_address`) | 08, 10, 18, 21, 27 |
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
| `features` | etwa 25 Stationsmerkmale | 10, 18, 38 |
| `window_features` | Merkmale in 14-Tage-Fenstern mit Begehungsmarke | nur Befehlszeile |
| `tagespanel` | Tabelle Station mal Tag | 18, 19, 38 |
| `dynamik` | Änderungstempo des Rücklaufs | 18 |
| `performance` | Kennzahl kWh/m³ gegen Außentemperatur | 05 |

### Begehungen und Labels

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `jahresvergleich` | Vorher/Nachher zum selben Kalenderzeitpunkt | 04, 18 |
| `befundcodes` | Freitexte der Begehungen in Befundcodes | 16, 17, 21 bis 25, 27 |
| `freitext` | Freitexte in Fehlerkategorien | 19 |
| `fallsammlung` | Fälle zur Begehungswirkung im Ternärbild | 17, 23, 25 |
| `inspections` | schnelle Auswertung der Begehungsbefunde | 27 |

### Clustering

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `clustervalidierung` | Stabilität und Prüfung der Cluster aus 07 bis 09 | 10, 18, 19, 38 |

### Stationsbilder und Kennlinien

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `ternaer` | Ternärdiagramme je Station | 13 bis 17, 21 |
| `stationsbilder` | drei ergänzende Stationsbilder | 01, 14, 15, 21 |
| `kennlinien_monitor` | Kennlinienüberwachung ohne Labels | 15, 16, 21, 38 |

### Anomalien, Monitoring und Empfehlung

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `anomalie` | Anomalieerkennung ohne Labels | 18, 19, 38 |
| `regelkalibrierung` | Regel-Baseline an echten Daten nachstellen | 18, 38 |
| `fault_detection` | ursprüngliche Regel-Baseline | 38 |
| `empfehlung` | vom Anomaliewert zur Handlungsempfehlung | 19, 38 |
| `priority` | Wartungspriorität als Punktwert | 19 |
| `netzvergleich` | Station im Vergleich zum Netz im Winter | 21, 23 bis 25, 38 |
| `tagesmonitor` | wetterbereinigte Tageswerte mit CUSUM-Alarm | 22, 23, 26, 38, 39 |
| `alarmbewertung` | Schwelle, Richtung und Priorität der Alarme | 23, 25, 26, 38 |
| `stationsblatt` | Monitorbild je Station, `status.csv` | 21 bis 26, 38 |
| `vergleichsgruppen` | Vergleichsgruppen nach Wärmemenge | 25, 38 |
| `nachbarschaft` | häufen sich auffällige Stationen im Netz? | 25, 26, 38 |
| `netzereignisse` | gleichzeitige Alarme: Netz oder Einzelstation? | 26, 38 |
| `zeitreihenmodell` | ARIMA und SARIMAX auf Tagesmitteln | 06, 38 |
| `detect_real` | Regel-Baseline auf echten Daten | nur Befehlszeile |
| `ml_classifier` | überwachter Klassifikator (Negativbefund) | nur Befehlszeile |

### Modelle und Vergleich

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `pruefstand` | alle Verfahren unter gleichen Bedingungen prüfen | 38, 39 |
| `normalmodell_waechter` | Tagesmonitor als Paket | 38, 39 |
| `prognose_waechter` | Prognose-LSTM als Paket | 38, 39 |
| `fehlerklassen` | Folie-5-Klassen als Paket | 38, 39 |
| `finalvergleich` | Modell Ivelina gegen Modell LSTM, Endmodell | 39 |
| `modellpaket` | Pakete speichern und laden | 38 bis 40 |

### Netz und Karte

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `build_graph` | Netzgraph aus Shapefiles und Knotenliste | 25, 26, 38 |
| `network_graph` | interaktive Ansicht des logischen Netzes | nur Befehlszeile |
| `geocode`, `geocode_stub`, `osm_addresses` | Adressen in Koordinaten | nur Befehlszeile |
| `snap_hast` | Stationen an den nächsten Netzknoten setzen | nur Befehlszeile |
| `visualize` | Netzbilder | nur Befehlszeile |

### Dashboard und Betrieb

| Modul | Aufgabe | Notebooks |
|---|---|---|
| `dashboard_daten` | Modellergebnisse für das Dashboard | 40 |
| `dashboard_karte` | Modellergebnisse in die Netzkarte | 40 |
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
