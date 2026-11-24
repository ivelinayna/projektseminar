# Aufteilung im Team

## Dominik

**Bereich:** lernende Modelle und Modellvergleich (*Vorgehen → Lernende Modelle*; *Modelle vergleichen* mit
Prüfdesign und Modellvergleich; Teile von *Was nicht getragen hat*).

- **Notebooks:** 25 (Daten, Labels und Messlatte), 26 (Einstufung mit K-Means), 27 (LSTM-Fingerabdruck),
  28 (Prognose-LSTM), 29 (XGBoost und Klassen), 30 (Wächtervergleich), 34 (Modellvergleich),
  35 (Endmodell), 36 (Merkmale und Erklärbarkeit), 37 (Dashboard). Notebook 35 vergleicht das Monitoring-Modell mit
  dem LSTM-Modell, Notebook 37 baut auf dem Rohrbaum aus Notebook 32 auf.
- **Vorarbeit:** die Gesamtpipeline aus dem August (nicht mehr im Abgabestand).
- **Code in `src/`:** `fehlerklassen.py`, `prognose_waechter.py`, `finalvergleich.py`, `pruefstand.py`,
  `modellpaket.py`, `merkmalsbau.py`, `normalmodell_waechter.py`, Mitarbeit an `dashboard_daten.py` und
  `dashboard_karte.py`.

## Ivelina

**Bereich:** Monitoring-Modell ohne Labels (*Vorgehen → Stationsbilder und Befunde*; Anomalien, Netzvergleich und
Tagesmonitor; Teile von *Was nicht getragen hat*), dazu Projektaufbau, Abgabestand und *Installation und Ausführung*.

- **Notebooks:** 01 (Lücken füllen), 04 (Wintervergleich), 05 (Performance), 06 (ARIMA und SARIMAX),
  08 (Clusterbenchmark), 09 (Clustervalidierung), 11 (Ternärdiagramme), 12 (Stationsbilder), 13 (Kennlinienmonitor),
  14 (Freitexte und Befunde), 15 (Fallsammlung), 16 (Anomalieerkennung), 17 (Handlungsempfehlung),
  19 (Netzvergleich), 20 (Tagesmonitor), 21 (Alarme), 22 (bestes Viertel als Maßstab), 23 (Vergleichsgruppen und
  Nachbarn), 24 (Netzereignisse), 33 (Netzkarte mit Monitorstatus). Netzvergleich und Tagesmonitor bilden zusammen das
  Monitoring-Modell, das Notebook 35 mit dem LSTM-Modell vergleicht. Notebook 33 baut auf dem Netz aus Notebook 31 auf.
- **Mitarbeit:** Überarbeitung der Notebooks 00 und 07 (Energie-Normierung, Clustering neu gerechnet), Mitarbeit an
  `dashboard_daten.py` und `dashboard_karte.py`.
- **Vorarbeit:** Projektaufbau im Mai (Grundgerüst von `src/` mit Datenladen, Netzgraph und ersten Karten) sowie die
  erste Fassung des Dashboards als Streamlit-App mit Rücklauf-Ampel und ersten ML-Modellen aus dem Juli (archiviert,
  nicht mehr im Abgabestand). Aus dieser Zeit stammen auch ältere Module für Geokodierung, synthetische Testdaten, eine
  erste Folium-Karte und einen überwachten Klassifikator (`geocode.py`, `geocode_stub.py`, `osm_addresses.py`,
  `synth_data.py`, `dashboard_map.py`, `ml_classifier.py`, `snap_hast.py`, `network_graph.py`, `window_features.py`).
  Sie werden im Abgabestand nicht mehr genutzt.
- **Abgabestand:** Zusammenführung der Stränge, Nummerierung der Notebooks 00 bis 39 in Teil-Ordnern, Docker,
  Read-the-Docs-Konfiguration, *Installation und Ausführung* und `python -m src.aktualisieren` für neue Zählerdaten.
- **Code in `src/`:**
    - Monitoring: `kennlinien_monitor.py`, `netzvergleich.py`, `tagesmonitor.py`, `alarmbewertung.py`,
      `stationsblatt.py`, `vergleichsgruppen.py`, `nachbarschaft.py`, `netzereignisse.py`
    - Stationsbilder und Befunde: `ternaer.py`, `stationsbilder.py`, `befundcodes.py`, `freitext.py`,
      `fallsammlung.py`, `jahresvergleich.py`, `performance.py`
    - Anomalien und Empfehlung: `anomalie.py`, `fault_detection.py`, `regelkalibrierung.py`, `empfehlung.py`,
      `priority.py`, `zeitreihenmodell.py`
    - Daten und Merkmale: `nb00_daten.py`, `luecken.py`, `weather.py`, `season.py`, `features.py`,
      `tagespanel.py`, `dynamik.py`, `clustervalidierung.py`, `load_timeseries.py`
    - Datenladen und Netz: `load_data.py`, `build_graph.py`, `inspections.py`
    - Vorbereitende Befehle: `main.py` mit `visualize.py` (Begehungstabelle für Notebook 08), `meter_quality.py`,
      `detect_real.py` und `profile_timeseries.py` (Tabellen für Notebook 17)
    - Betrieb: `aktualisieren.py`
