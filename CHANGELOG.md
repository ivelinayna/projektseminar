# Changelog

Alle nennenswerten Änderungen am Projekt. Aufbau angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
versioniert wird nicht — Einträge sind datumsbasiert.

## [Unreleased]

### Geändert

- Notebook `00_eda_hast_stationsprofile.ipynb`: Inline-Feature-Funktion
  `compute_hast_features()` normiert `energy_kwh_year`/`full_load_hours`
  jetzt ebenfalls auf 8760 h/Jahr (gleicher Fix wie `src/features.py`) —
  zuvor hätte der src-Fix an den Notebook-Ergebnissen nichts geändert.
  Markdown-Zahlen an den neuen Lauf angepasst (u. a. Korrelation
  `summer_flow_baseline`↔`full_load_hours` 0,41 → 0,82).
- Notebook `01_kmeans_stationscluster.ipynb` mit korrigierten Features
  neu gerechnet (2026-09-22): **k = 2 trennt jetzt 97/3 statt 63/38,
  Silhouette 0,599 statt 0,217.** Die drei isolierten Stationen sind
  exakt der frühere Konsens-Dreier-Cluster (58202380, 66761022,
  86792512). Neubefund: 86792512 ist laut `Zuordnung.xlsx` ein **BHKW** —
  die Ausreißer-Achse ist mindestens teils Stationstyp-, nicht
  Fehlersignal. Silhouette-Sprung ehrlich eingeordnet (isoliert 3
  Ausreißer, Flotte bleibt Kontinuum: alle k ≥ 3 < 0,25). Ground-Truth-
  Vergleich entfällt: alle 58 gejointen Stationen liegen in Cluster 0.
  Lauf-Kontext liegt als `data/processed/hast_clusters.json` bei.

### Hinzugefügt

- `.github/agents/hast-clusteranalyse.agent.md` — projektspezifischer
  Agent für die Unsupervised-Learning-Analyse (Datenlage, Befundstand,
  Roadmap, Konventionen).
- `.github/skills/` — vier Skills: `clustering-benchmark`,
  `zeitreihen-features`, `begehungs-wirkungsanalyse`,
  `projektkonventionen`.
- `src/window_features.py` — zeitlich aufgelöste Zustandsfeatures
  (14-Tage-Fenster, Coverage- und Zählerwechsel-Flags), Grundlage für
  Cluster-Wanderung um Begehungen. Dazu `tests/test_window_features.py`
  (9 Tests, synthetische Stundendaten).
- `tests/test_features.py` — Regressionstest für die
  Jahresnormierung der Energieaggregate.

### Behoben

- `requirements.txt`: `pandas>=2.2` statt `>=2.0` — `features.py`
  nutzt `resample("ME")`, den Alias gibt es erst ab pandas 2.2.
- `src/features.py`: `energy_kwh_year`, `volume_m3_year` und
  `full_load_hours` wurden über die gesamte Historie (0,88–4,72 Jahre)
  summiert statt auf ein Jahr normiert. Jetzt Normierung auf 8760 h/Jahr
  anhand der tatsächlichen Zeitspanne. Behebt Punkt 1 aus „Zu beheben"
  in Notebook `01_kmeans_stationscluster.ipynb`; Blocker für den
  Clustering-Benchmark.

## Frühere Stände

Siehe Git-Historie auf `main` (EDA, K-Means-Notebook, Gesamtpipeline,
Wirkungsanalyse der Begehungen, ML-Klassifikator-Negativergebnis).
