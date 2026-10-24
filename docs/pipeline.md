# Pipeline

Ein-Befehl-Pipeline ab Projektwurzel (conda-Umgebung `heating-network`):

```bash
python -m src.main                                          # Graphen + Karten + Begehungs-Summary
python -m src.main --synth --detect --plot                  # + synthetische Daten + Fault Detection
python -m src.main --geocode --dashboard                    # + Geocoding + Dashboard-Karte
python -m src.main --synth --detect --plot --geocode --dashboard  # alles
```

Zusätzlich, unabhängig von `main.py`:

```bash
python -m src.load_timeseries                               # Inventur der echten CSV-Exporte
python -m src.load_timeseries --materialize data/processed/real_meters
python -m src.weather                                       # DWD-Aussentemperatur -> data/raw/weather/ (einmalig, danach offline)
python -m src.profile_timeseries                            # Daten-Profiling -> docs/datensichtung.md
python -m src.meter_quality                                 # Qualitätsklassen -> meter_quality.csv
python -m src.detect_real                                   # Baseline auf echten Daten -> docs/echte-daten-integration.md
python -m src.snap_hast                                     # Station -> naechster Rohrknoten (hast_snapped.csv)
python -m src.priority                                      # Wartungspriorisierung (priority_scores.csv)
python -m src.ml_classifier                                 # ML-Evaluation vs. Baseline -> docs/ml-klassifikator.md
python -m tests.test_load_timeseries                        # Loader-Tests (ohne Rohdaten lauffähig)
python -m pytest tests/test_load_timeseries_ods.py          # ODS-Nachlieferung (ohne Rohdaten)
python -m pytest tests/test_weather.py                      # Wetter-/Saison-Tests (ohne Netz und ohne Rohdaten)
python -m pytest tests/test_performance.py                  # Performance-Kennzahl und Regression (ohne Netz und ohne Rohdaten)
python -m pytest tests/test_befundcodes.py                  # Freitextkodierung (zwei Tests brauchen die Begehungstabelle)
```

## Datenfluss

```
data/raw/                          src/                     Artefakte
─────────                          ────                     ─────────
Nodes_Edges.ods ────────────────► load_data ──► build_graph ──► logical_topology.png
Leitungsverlauf_*.shp ──────────► load_data ──► build_graph ──► network_map_main.html
                                                               network_map_full.html
Optimierung_FW[45].xlsx ────────► load_data ──► inspections ──► inspections_tidy.csv
                                                               fault_summary.csv
(synthetisch) synth_data ───────► features ──► fault_detection ──► features.csv
                                                                  predictions.csv
<Zähler>_*.csv (echt) ──────────► load_timeseries ──► [noch nicht angeschlossen]
<Zähler>.ods (Nachlieferung) ──► load_timeseries ──► nur mit mit_ods=True
DWD Open Data (CDC) ────────────► weather ──► data/raw/weather/dwd_tu_*.csv ──► season
<Zähler>_*.csv + weather ───────► performance ──► outputs/performance_variante_*.png
Adressen ───────────────────────► geocode/osm_addresses ──► hast_geocoded.csv
alles zusammen ─────────────────► dashboard_map ──► dashboard_map.html
```

## Module

| Modul | Aufgabe |
|---|---|
| `load_data.py` | Rohdaten-I/O + deterministische deutsche Adressnormalisierung (`_normalize_address`) |
| `build_graph.py` | Logischer Graph (Adressen) und räumlicher Graph (Rohrgeometrie, Endpunkt-Snapping 5 cm) |
| `visualize.py` | Statische Topologie-PNG, Folium-Karten, DBSCAN-Cropping auf das Wiesentheid-Cluster |
| `inspections.py` | Begehungs-Excel → tidy Tabelle + Fehlerhäufigkeiten |
| `load_begehungen.py` | Begehungs-Excel mit Änderungs-Kategorie, Begehungszeiten, Heiz-/TWW-Zeiten und Sollwerten alt/neu; Adresse → Zählernummer aus `Zuordnung.xlsx` inkl. Zählerwechsel. Grundlage von `notebooks/03_wirkungsanalyse_begehungen.ipynb` |
| `synth_data.py` | Synthetische Stundendaten, 5 injizierte Fehlerbilder, `faults_truth.csv` als Label-Manifest |
| `load_timeseries.py` | Echte CSV-Exporte: Discovery, Merge der Export-Generationen, Dedupe, Materialisierung pro Zähler. Zusätzlich die ODS-Nachlieferung (`mit_ods=True`) mit Gegenprobe CSV gegen ODS |
| `weather.py` | Stündliche Außentemperatur aus DWD Open Data (Station 2600 Kitzingen), Cache unter `data/raw/weather/`, Umrechnung UTC nach Lokalzeit |
| `season.py` | Saisonsegmente (Kernwinter, Übergang spät/früh, Sommer) und die zwei kältesten Februarwochen je Jahr |
| `performance.py` | Performance in kWh/m³ auf Tagesebene je Station, Filterbilanz, Regression gegen die Außentemperatur vor/nach Begehung |
| `profile_timeseries.py` | Read-only-Datenprofiling der echten Exporte, generiert `docs/datensichtung.md` |
| `meter_quality.py` | Qualitätsklassen je Zähler (auswertbar/inaktiv/netzseitig/geringe Abdeckung/Schema), Schwellen als Konstanten |
| `detect_real.py` | Features + Baseline auf auswertbaren zugeordneten Zählern, Ground-Truth-Join, generiert `docs/echte-daten-integration.md` |
| `snap_hast.py` | Snapping geocodeter Stationen an den nächsten Rohrknoten des räumlichen Graphen, Distanz als Ehrlichkeits-Maß |
| `priority.py` | Transparenter Wartungsprioritäts-Score (Rücklauf/Anschlusswert/Begehungsalter), keine Vorhersage |
| `ml_classifier.py` | ML-Zustandsklassifikation vs. trivialer/Regel-Baseline, stratifizierte CV, Leakage-Analyse, Feature-Importances |
| `dashboard_app.py` | Streamlit-Dashboard: Ampel nach Winter-Rücklauf, Rohrnetz-Overlay, Detailpanel, Prioritätenliste |
| `features.py` | ~25 numerische Features pro HAST aus einem Jahr Stundendaten |
| `fault_detection.py` | Regelbasierte Baseline mit lesbaren Begründungen pro Flag |
| `ternaer.py` | Ternärdiagramme je Station (Leistung, Volumenstrom, Spreizung), sechs Zeitabschnitte, Kennzahlen je Panel |
| `stationsbilder.py` | Kennlinie (log-log), Carpet-Plot und Dauerlinie je Station, mit Kennzahlen |
| `kennlinien_monitor.py` | Kennlinie als Modell je Station: rollierender Fit, Residuen, Alarme über einen Sprungscore, Gegenprobe gegen Begehungstermine |
| `befundcodes.py` | Regelbasierte Kodierung der Begehungs-Freitexte in Mehrfachlabels, Fehlerrangliste, Labels je Zähler |
| `geocode.py` / `osm_addresses.py` | Nominatim/Overpass-Geocoding mit Cache und Overrides |
| `dashboard_map.py` | Kombinierte Folium-Karte: Rohre + HAST + Begehungen + Vorhersagen |
| `modellpaket.py` | Modellpakete unter `models/<name>/<version>/`: Dateien, Parameter, Datenstand, Code-Stand, SHA-256; Betriebsversion in `AKTUELL` |
| `pruefstand.py` | Gemeinsame Prüfungen für alle Kandidaten: Begehungs-Treffertest mit Kontrollgruppe, gemeinsame Tage, gleiches Alarmbudget, eingerechnete Fehler, AUC mit Intervall (auch paarweise), Zufallstest, Holm, McNemar, Vierfeldertafel |
| `prognose_waechter.py` | Prognose-LSTM aus NB 21 als Paket: Skalierung und Kalibrierung nachgerechnet, Anwenden ohne neues Lernen, Schwellen- und CUSUM-Regel, Wochenmittel als Vergleich, Gegenprobe gegen `prognose_tage.csv` |
| `normalmodell_waechter.py` | Tagesmonitor (Normalverhaltensmodell) als Paket: Referenz und Kennlinien je Station, Anwenden auf neue Tage |
| `fehlerklassen.py` | Folie 5 als Paket: Kennzahlen (NB 18), LSTM-Embedding (NB 20), Ventil- und Dämmungsmodell, Vertragsregel (NB 22), K-Means (NB 19); Klassen für jede Heizperiode |

## Schnittstellen-Vertrag

`features.features_for_directory(meter_dir, nodes_df)` erwartet ein
Verzeichnis mit einer CSV pro Zähler, Dateiname `<Zählernummer>.csv`
(int-parsebar), im 8-Spalten-Schema. Sowohl `synth_data.generate_dataset`
als auch `load_timeseries.materialize_meters` bedienen genau dieses
Layout — die Feature- und Detection-Schicht bleibt dadurch unverändert,
egal ob synthetische oder echte Daten anliegen.

## Notebooks des Unsupervised-Strangs

| Notebook | Ansatz | Kernbefund |
|---|---|---|
| `08_performance.ipynb` | Nachrechnung der ÜZ-Folie zur Gesamteffizienz: Performance in kWh/m³ gegen Außentemperatur, vor/nach Begehung | Prozentwert der Folie reproduziert (12,8 bis 13,6 % gegen 13,4 %); Höhenunterschied belastbar, Steigungsunterschied nicht |
| `12_ternaer.ipynb` | Ternärdiagramme für alle Stationen, Kennzahlen je Panel | Teilnetz überwiegend durchflussgeregelt (74 von 94); Spreizungsmodulation hängt mit schlechter Performance zusammen |
| `13_stationsbilder.ipynb` | Kennlinie, Carpet-Plot und Dauerlinie als Gegenprobe zum Ternärdiagramm | Kennliniensteigung = Durchflussanteil; Dauerlinie misst die Begehungswirkung, Kennlinie nicht |
| `14_monitor.ipynb` | Kennlinie als Modell je Station, Alarme, Gegenprobe gegen 53 Begehungsfälle | Bekannter Defekt (68956351) wird klar gefunden; über alle Begehungen nur ca. 30 % über Zufall |
| `15_befunde.ipynb` | Kodierung der 57 Begehungs-Freitexte, Fehlerrangliste, Monitor neu ausgewertet | Mit den Freitext-Labels trifft der Residuenkanal 10 von 19 mechanischen Eingriffen (p = 0,024) |

## Notebooks des Modell-Strangs

Aufbauend auf `00_eda` (`real_meters/`, `hast_features.csv`). Jedes Notebook
schreibt seine Zwischenergebnisse nach `data/processed/`, das nächste liest sie.
Modellgewichte liegen in `notebooks/models/` (gitignored) und werden beim
nächsten Lauf geladen statt neu trainiert. Ändert sich die Datenbasis in
`00_eda`, müssen die Gewichte von `20` und `21` gelöscht werden: Die
Validierungswochen werden aus allen Wochen gezogen und verschieben sich dann,
alte Gewichte hätten einen Teil der neuen Validierungstage schon im Training
gesehen. Neu trainieren dauert auf der Grafikkarte wenige Minuten. Benötigt zusätzlich `torch` und
`xgboost` (siehe `requirements.txt`); ohne Grafikkarte läuft alles auf der CPU.
`23_vergleich_waechter` liest außerdem die Ausgaben von `06` (`hast_tage.csv`)
und `17` (`normalmodell_*.csv`); diese beiden müssen vorher gelaufen sein.

| Notebook | Ansatz | Kernbefund |
|---|---|---|
| `18_modelldaten_labels.ipynb` | Stundenwerte mit DWD-Außentemperatur, 13 Kennzahlen je Zähler nur aus Daten vor der ersten Begehung, Auslastung zum Vertrag vor der Begehung, 6 Labels aus Kästchen (`inspections`) und Freitext (`befundcodes`) | 93 Zähler aus `00`, Kennzahlen für 91; 56 begangene Zähler mit Zeitreihe; Ventil 11, Dämmung 23; bei Filter, Durchfluss und Dämmung kaum ausdrückliche „nein“ (4–8); der Anschlusswert in `Nodes_Edges.ods` ist bei 7 von 9 verkleinerten Verträgen schon der neue Wert |
| `19_kmeans_einstufung_folie5.ipynb` | K-Means auf drei Regelungs-Kennzahlen (Winter 23/24): Optimum oder schlechter (Folie 5) | k = 2, Silhouette 0,44; Gruppe „schlechter“ (18 Zähler) hat 50 % Ventilbefunde gegen 14 % im Optimum (p = 0,021, nach Holm-Korrektur nicht abgesichert) |
| `20_lstm_fehlererkennung.ipynb` | LSTM (PyTorch) sagt aus einem Tag den nächsten vorher, gelernt nur auf den begangenen HAST; 8-Zahlen-Embedding je Station, logistische Regression verschachtelt geprüft; Vergleich mit Netz auf allen HAST und Autoencoder | Wiedererkennung über zwei Winter 83 %, bei nie gesehenen Stationen 78 %; Ventil mit allen Daten 0,89; nur Winter LSTM 0,83 gegen Kennzahlen 0,68 (knapp belegt, +0,15 [0,02; 0,32], in der vorigen Fassung nicht; hängt auch an einem fraglichen Label) |
| `21_prognose_lstm_waechter.ipynb` | Encoder–Decoder-LSTM sagt jeden Tag Rücklauf und Durchfluss vorher, gelernt nur auf den begangenen HAST; Warnung bei z ≥ 4 an zwei Tagen, ein Alarm je Veränderung | Bypass 150 l/h zu 84 % erkannt bei 8 % Fehlalarmen; 2,9 Alarme je Station und Jahr; Winterwarnungen kommen von Stationen, die sich nach der Begehung verändert haben, und von vier nie begangenen mit zu wenigen Validierungstagen |
| `22_xgboost_fehlerklassen.ipynb` | Logistische Regression, Random Forest, XGBoost mit/ohne Wechselwirkungen, SHAP; drei Klassen der Folie 5 für alle 91 Zähler mit Kennzahlen, Ventil-Grenze fest 0,5 | Ventil AUC 0,89 (LR auf Kennzahlen + LSTM), Dämmung 0,75; Folie 5: 24 × Ventil tauschen, 5 × Regelparameter optimieren, 61 × kein Handlungsbedarf; Überdimensionierung 0,78 mit der Auslastung zum Vertrag vor der Begehung (mit dem Anschlusswert 0,66); Bäume und Wechselwirkungen nicht besser; Filter, Durchfluss, Temperatur nicht erkennbar |
| `23_vergleich_waechter.ipynb` | Sebs Begehungsprüfung aus `17` nachgebaut (Fall für Fall identisch) und auf beide Wächter angewendet: gleiche Stationen, Heiztage, Fälle, Kontrollgruppe und gleiches Alarmbudget | Normalverhaltensmodell 30 von 43 Begehungen gegen 50 % Kontrolle (p = 0,008), schon in 14 Tagen; Prognose-LSTM 16 von 43 gegen 32 % (p = 0,26); Fall für Fall McNemar p = 0,001. Begehungen verschieben den Betrieb nur um etwa eine halbe Streuung: CUSUM sammelt das auf, eine Schwellenregel nicht |

## Modellvergleich

`32_modellvergleich.ipynb` stellt alle Modelle des Projekts auf denselben Prüfstand (`src/pruefstand.py`): 15 Wächter
und 27 Erkenner, Regeln eingeschlossen, mit gleichen Fällen, Stationen, Tagen und gleicher Alarmmenge. Es liest die
Ausgaben von 06, 17, 18, 20, 21 und 22 und die Modellpakete (baut sie, wenn sie fehlen) und schreibt
`outputs/pruefstand/`. Laufzeit etwa 11 Minuten mit Grafikkarte. Einzelheiten in [modellvergleich.md](modellvergleich.md).

| Notebook | Ansatz | Kernbefund |
|---|---|---|
| `32_modellvergleich.ipynb` | Gleiche Fälle, Stationen, Tage und Alarmmenge für alle; Erwartung und Alarmregel getrennt getauscht; Regeln als Kandidaten; GNN und Bayes nicht lauffähig ohne ihre Eingaben | Alarm: von 15 Wächtern bleibt nach Holm nur Kennlinie + CUSUM belegt (Tagesmonitor 33/43, p = 0,017); LSTM + Schwelle am besten bei plötzlichen Fehlern (Bypass 150 l/h 84 %, Fühler 43 % gegen 17 % ohne Lernen); Kennlinienmonitor (NB 14) und die Detektoren aus NB 10 taugen nicht als Alarm. Ventil: 15 von 27 Erkennern über Raten, LR Kennzahlen + LSTM 0,89 vorn, keiner belegt besser als die Sommernacht-Regel (0,85); Bäume nicht besser; nach dem Ventiltausch sinkt der Verdacht (p = 0,016). Dämmung: nur das Paket-Modell über Raten, Flottenmaße zeigen die umgekehrte Richtung. Monitoring-Modell gegen LSTM: Monitoring gewinnt den Alarm (33 gegen 16, McNemar 17 zu 0), LSTM-Kette das Erkennen (+0,16 Ventil, +0,37 Dämmung). Netz (logischer Graph): Nachbarn und Lage verbessern nichts |

Modellpakete bauen und gegen die Notebooks prüfen:

```bash
python -m src.prognose_waechter --bauen --gegenprobe
python -m src.normalmodell_waechter --bauen
python -m src.fehlerklassen --bauen --gegenprobe
python -m src.modellpaket                               # Übersicht der Versionen
```

## Smoke-Tests (zuletzt grün am 2026-07-08)

- `python -m src.main` — Graphen, Karten, Begehungs-Summary
- `python -m src.main --synth --detect` — 99 synthetische Zähler,
  100 % Accuracy der Baseline auf injizierten Fehlern
- `python -m tests.test_load_timeseries` — 7 Loader-Tests
- `python -m src.load_timeseries` — Inventur: 154 Dateien / 101 Zähler
