# Changelog

Alle nennenswerten Änderungen am Projekt. Aufbau angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
versioniert wird nicht — Einträge sind datumsbasiert.

## [Unreleased]

### Entfernt (2026-09-22)

- `docs/naechste-schritte.md` aus der Git-Versionierung genommen
  (gitignored, bleibt lokal erhalten) — interne Arbeitsdatei, nicht für
  die öffentliche Doku. Verweise in `mkdocs.yml`, `docs/README.md`,
  `docs/datensichtung.md` und `src/profile_timeseries.py` entfernt.
  Hinweis: ältere Commits enthalten die Datei weiterhin (Historie).

### Hinzugefügt (Docs-Hosting 2026-09-22)

- Read-the-Docs-Setup: `mkdocs.yml` (Material-Theme, deutsch, Nav über
  alle acht Docs-Seiten), `.readthedocs.yaml` (v2-Config, Ubuntu 22.04 /
  Python 3.11) und `docs/requirements.txt` (mkdocs + mkdocs-material,
  getrennt von den Projekt-Dependencies). Lokaler Build getestet
  (`mkdocs build` ohne Warnungen). Fehlt nur noch der Import auf
  readthedocs.org (erfordert Repo-Owner-Zugang).

### Hinzugefügt (Benchmark 2026-09-22)

- `notebooks/04_clustering_benchmark.ipynb` — Verfahrensvergleich
  K-Means / Ward / GMM / HDBSCAN auf den korrigierten Features, jeweils
  mit und ohne BHKW-Ausschluss (parametrisiert über
  `EXCLUDE_STATION_TYPES`, Team-Entscheidung offen). Ergebnisse:
  - **k = 3 fest gesetzt** (k = 2 isoliert nur Ausreißer — Ward-Falle;
    k ≥ 4 fragmentiert ohne Silhouette-Gewinn).
  - **Konsistenz-Anker bestätigt:** alle Verfahren separieren das
    Ausreißer-Trio {58202380, 66761022, 86792512} bei k = 3 als
    Kleinst-Cluster; paarweiser ARI der Gesamtaufteilung nur
    0,15–0,58 (Einigkeit nur über die Ausreißer, nicht über die Masse).
  - **K-Means k = 3 stabilstes Verfahren** (Bootstrap-ARI 0,71/0,60),
    aber unter altem Referenzwert 0,90.
  - **Negativbefund HDBSCAN:** ab `min_cluster_size` = 5 komplett
    Rauschen; mcs = 3 lässt ~20 % unzugeordnet.
  - **Ground Truth trennt nichts** (Fisher p ≥ 0,47, MWU p ≥ 0,19,
    Basisrate 80 %); Ausreißer-Cluster in Begehungsdaten nicht
    vertreten.
  - Konsequenz: statische Stationsprofile tragen keine Typenbildung →
    zeitliche Auflösung via `src/window_features.py` ist der nächste
    Hebel. Referenz-Zuordnungen in `data/processed/cluster_benchmark.csv`
    (+ `.json` Lauf-Kontext, beide gitignored).

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
