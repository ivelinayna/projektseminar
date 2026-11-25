# Aufteilung im Team

## Dominik

**Bereich:** lernende Modelle und Modellvergleich (*Vorgehen → Lernende Modelle*; *Modelle vergleichen* mit
Prüfdesign und Modellvergleich; Teile von *Verworfene Ansätze*).

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
Tagesmonitor; Teile von *Verworfene Ansätze*), dazu Projektaufbau, Abgabestand und *Installation und Ausführung*.

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
  Read-the-Docs-Konfiguration, *Installation und Ausführung* und `python -m src.aktualisieren` für neue Zählerdaten. Dazu das
  Dashboard als Streamlit-App (`dashboard_app.py`, `dashboard_app_logik.py`) als Ausblick
  ([Dashboard als Streamlit-App](../ausblick/streamlit.md)).
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

## Pauline

**Bereich:** Netz und Zuordnung (*Vorgehen → Netz einbeziehen* mit Rohrbaum, Haus oder Netz und Fehlererkennung mit
Netz-Merkmalen; *Datengrundlage → Netz und Zuordnung*), dazu die Handtabelle der Koordinaten und die Docker-Ausführung.

- **Notebooks:** 31 (Netzmodell aus Kantendatei, Leitungsplan und Zuordnung), 32 (Einspeisung, Rohrbaum,
  Nachbarvergleich, Basislinie mit Netz-Merkmalen, gelernter Graph). Notebook 32 schreibt den Export
  `gnn_daten.npz`, auf dem Notebook 39 aufbaut. Notebook 33 und Notebook 37 bauen auf dem Netz aus Notebook 31
  und dem Rohrbaum aus Notebook 32 auf.
- **Dashboard:** `dashboard_export.py` ist die erste Fassung des Dashboards auf dem Netz. Daraus sind
  `dashboard_final.py` (Notebook 37, in der Rohrbaum-Fassung) und die Streamlit-App `dashboard_app.py` entstanden.
- **Vorarbeit:** HAST-Analyse im August(nicht mehr im Abgabestand), stundenweises k-Means (k = 5) für Betriebszustände im September (heute
  Notebook 09), Netz-Notebook mit ersten Karten und Experimenten auch im September (Vorläufer von 31 und 32).
- **Handtabellen:** Koordinatentabelle `data/manual/adressen_koordinaten.ods`, eine Koordinate je Adresse aus
  Google Maps, mit Korrekturen und Ergänzungen.
- **Docker:** Der Ablauf mit Docker wurde auf Windows ausführlich getestet: Image bauen, Wetter und Modellpakete,
  `dashboard_daten`, Notebooks im Container, Dashboard auf Port 8000.

## Sebastian

**Bereich:** Datenbasis und Begehungen (*Datengrundlage*; *Vorgehen → Daten aufbereiten*; Wirkung und Labels unter
*Begehungen auswerten*; Stations- und Tagescluster unter *Merkmale und Clustering*), Normalverhaltensmodell und
Mitarbeit am Monitoring, die *Weiteren Versuche* Bayes-Diagnose und GNN, dazu Gliederung und Texte der Doku.

- **Notebooks:** 00 (Daten aufbereiten), 02 (Wirkung im 21-Tage-Fenster), 03 (Label aus Messdaten),
  07 (Stationscluster), 10 (Tagescluster), 18 (Normalverhaltensmodell), 38 (Bayes-Diagnose), 39 (GNN). Notebook 00
  ist die Datenbasis aller anderen Notebooks. Notebook 10 liefert die Tageswerte für die Notebooks 18, 30, 34 und 39.
  Aus Notebook 18 stammt die Idee des Tagesmonitors, eine Kennlinie je Station mit CUSUM.
- **Mitarbeit am Monitoring:** Netzvergleich (Notebook 19) und Tagesmonitor (Notebook 20) größtenteils dokumentiert
  und erklärt, mit Erklärnotizen zu den Abschnitten beider Notebooks und den Seiten
  [Netzvergleich und Wintervergleich](../monitoring/netzvergleich.md) und [Tagesmonitor](../monitoring/tagesmonitor.md).
- **Weitere Mitarbeit:** Notebook 05, Abschnitt 10 (Performance vor und nach der Begehung auf der Datenbasis von
  Notebook 00).
- **Handtabellen:** Prüfliste der Begehungsnotizen (alle 65 Begehungen von Hand gelesen und kodiert),
  Fehler-Symptom-Matrix (Entwurf) und Kodierbogen der Freitexte (siehe
  [Ergänzende Daten](../datengrundlage/ergaenzend.md#handtabellen)).
- **Doku:** Gliederung der Read-the-Docs-Doku in Kapitel mit Unterseiten und Abgleich der Seiten mit den Notebooks.
  Texte der Kapitel Einleitung, Datengrundlage, Daten aufbereiten, Begehungen auswerten, Merkmale und Clustering,
  Ergebnisse (Überblick und Datenanalyse), Grenzen und Erkenntnisse, Ausblick und Anhang.
- **Code in `src/`:** `load_begehungen.py` (Begehungstabelle laden und über die Zählernummer zuordnen), genutzt von den
  Notebooks 00, 02 und 03. Die übrigen eigenen Notebooks rechnen ohne `src/`, ihr Code steht im Notebook.

