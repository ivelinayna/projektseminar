# Changelog

Alle nennenswerten Änderungen am Projekt. Aufbau angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
versioniert wird nicht — Einträge sind datumsbasiert.

## [Unreleased]

### Hinzugefügt

- `.github/agents/hast-clusteranalyse.agent.md` — projektspezifischer
  Agent für die Unsupervised-Learning-Analyse (Datenlage, Befundstand,
  Roadmap, Konventionen).
- `.github/skills/` — vier Skills: `clustering-benchmark`,
  `zeitreihen-features`, `begehungs-wirkungsanalyse`,
  `projektkonventionen`.
- `src/window_features.py` — zeitlich aufgelöste Zustandsfeatures
  (14-Tage-Fenster, Coverage- und Zählerwechsel-Flags), Grundlage für
  Cluster-Wanderung um Begehungen. *(in Arbeit)*
- `tests/test_features.py` — Regressionstest für die
  Jahresnormierung der Energieaggregate.

### Behoben

- `src/features.py`: `energy_kwh_year`, `volume_m3_year` und
  `full_load_hours` wurden über die gesamte Historie (0,88–4,72 Jahre)
  summiert statt auf ein Jahr normiert. Jetzt Normierung auf 8760 h/Jahr
  anhand der tatsächlichen Zeitspanne. Behebt Punkt 1 aus „Zu beheben"
  in Notebook `01_kmeans_stationscluster.ipynb`; Blocker für den
  Clustering-Benchmark.

## Frühere Stände

Siehe Git-Historie auf `main` (EDA, K-Means-Notebook, Gesamtpipeline,
Wirkungsanalyse der Begehungen, ML-Klassifikator-Negativergebnis).
