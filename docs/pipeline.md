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
python -m src.profile_timeseries                            # Daten-Profiling -> docs/datensichtung.md
python -m src.meter_quality                                 # Qualitätsklassen -> meter_quality.csv
python -m src.detect_real                                   # Baseline auf echten Daten -> docs/echte-daten-integration.md
python -m src.snap_hast                                     # Station -> naechster Rohrknoten (hast_snapped.csv)
python -m src.priority                                      # Wartungspriorisierung (priority_scores.csv)
python -m src.ml_classifier                                 # ML-Evaluation vs. Baseline -> docs/ml-klassifikator.md
python -m tests.test_load_timeseries                        # Loader-Tests (ohne Rohdaten lauffähig)
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
| `synth_data.py` | Synthetische Stundendaten, 5 injizierte Fehlerbilder, `faults_truth.csv` als Label-Manifest |
| `load_timeseries.py` | Echte CSV-Exporte: Discovery, Merge der Export-Generationen, Dedupe, Materialisierung pro Zähler |
| `profile_timeseries.py` | Read-only-Datenprofiling der echten Exporte, generiert `docs/datensichtung.md` |
| `meter_quality.py` | Qualitätsklassen je Zähler (auswertbar/inaktiv/netzseitig/geringe Abdeckung/Schema), Schwellen als Konstanten |
| `detect_real.py` | Features + Baseline auf auswertbaren zugeordneten Zählern, Ground-Truth-Join, generiert `docs/echte-daten-integration.md` |
| `snap_hast.py` | Snapping geocodeter Stationen an den nächsten Rohrknoten des räumlichen Graphen, Distanz als Ehrlichkeits-Maß |
| `priority.py` | Transparenter Wartungsprioritäts-Score (Rücklauf/Anschlusswert/Begehungsalter), keine Vorhersage |
| `ml_classifier.py` | ML-Zustandsklassifikation vs. trivialer/Regel-Baseline, stratifizierte CV, Leakage-Analyse, Feature-Importances |
| `dashboard_app.py` | Streamlit-Dashboard: Ampel nach Winter-Rücklauf, Rohrnetz-Overlay, Detailpanel, Prioritätenliste |
| `features.py` | ~25 numerische Features pro HAST aus einem Jahr Stundendaten |
| `fault_detection.py` | Regelbasierte Baseline mit lesbaren Begründungen pro Flag |
| `geocode.py` / `osm_addresses.py` | Nominatim/Overpass-Geocoding mit Cache und Overrides |
| `dashboard_map.py` | Kombinierte Folium-Karte: Rohre + HAST + Begehungen + Vorhersagen |

## Schnittstellen-Vertrag

`features.features_for_directory(meter_dir, nodes_df)` erwartet ein
Verzeichnis mit einer CSV pro Zähler, Dateiname `<Zählernummer>.csv`
(int-parsebar), im 8-Spalten-Schema. Sowohl `synth_data.generate_dataset`
als auch `load_timeseries.materialize_meters` bedienen genau dieses
Layout — die Feature- und Detection-Schicht bleibt dadurch unverändert,
egal ob synthetische oder echte Daten anliegen.

## Smoke-Tests (zuletzt grün am 2026-07-08)

- `python -m src.main` — Graphen, Karten, Begehungs-Summary
- `python -m src.main --synth --detect` — 99 synthetische Zähler,
  100 % Accuracy der Baseline auf injizierten Fehlern
- `python -m tests.test_load_timeseries` — 7 Loader-Tests
- `python -m src.load_timeseries` — Inventur: 154 Dateien / 101 Zähler
