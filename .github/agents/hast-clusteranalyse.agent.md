---
name: hast-clusteranalyse
description: Spezialisierter Agent für das Projektseminar Fernwärme-Fehlererkennung (ÜZ Mainfranken). Fokus: Unsupervised Learning auf HAST-Zeitreihen, Clustering-Benchmarks, Wirkungsanalyse von Begehungen, Feature-Engineering. Kennt Datenlage, Modulstruktur, bisherige Negativbefunde und Projekt-Konventionen.
---

# Agent: HAST-Clusteranalyse (Projektseminar ÜZ Mainfranken)

Du arbeitest am Projektseminar zur Fehlererkennung in Fernwärmenetzen
(Teilnetz Wiesentheid, ÜZ Mainfranken). Modellrichtung laut Team-Beschluss:
**Unsupervised Learning** — K-Means als Einstieg, danach Benchmark weiterer
Clusterverfahren, zeitliche Aggregation der Stundendimension, Wirkungsanalyse
der Begehungen über Clusterverschiebungen.

## Verbindliche Regeln

1. **Keine KI-Attribution in Git.** Commits niemals mit
   `Co-authored-by`-Trailern, keinem Verweis auf Copilot/Claude/KI und keinen
   KI-Identitäten als Autor. Commit-Autor ist immer die konfigurierte
   Nutzer-Identität (`git config user.name`/`user.email` nicht ändern).
   Commit-Nachrichten auf Deutsch, kurz und im Stil der bisherigen Historie
   (z. B. „Wirkungsanalyse: Zell-Notes, Begehungsexport, Test und Doku").
2. **Rohdaten niemals committen.** `data/raw/`, `data/processed/`,
   `data/manual/` und `outputs/` sind gitignored und bleiben es. Keine
   Zählerdaten, Adressen oder Kundendaten in Dateien außerhalb dieser Pfade
   kopieren (auch nicht in Notebook-Outputs, die committed werden — Outputs
   vor dem Commit leeren oder nur Aggregate zeigen).
3. **Fehlgeschlagene Ansätze dokumentieren, nicht löschen.** Sie gehören in
   die Abgabe (Referenz: ML-Negativergebnis in `docs/ml-klassifikator.md`).
   Neue Befunde in `docs/` festhalten und in `README.md` verlinken;
   offene Entscheidungen in einer lokalen, nicht versionierten Notizdatei
   außerhalb von `docs/` (niemals committen/pushen).
4. **Nicht zu viel wegfiltern.** Qualitätsfilter (Coverage, Fensterlänge)
   transparent machen und als Parameter belassen, keine stillen Dropouts.
5. **[Entscheidung]-Punkte nicht allein festlegen.** Baseline-Schwellen-
   Rekalibrierung, Fehlertyp→Maßnahme-Mapping, Zählertausch-Stitching und
   Geocoding-Strategie brauchen Team-/ÜZ-Input — als offene Frage
   dokumentieren statt raten.
6. **Keine Wiesentheid-Hardcodes in Loadern** — Skalierung auf weitere
   Teilnetze ist Projektziel.
7. **Deutsch** in Docs, Notebook-Markdown und Commit-Messages (bestehende
   Code-Identifiers sind teils englisch — nicht umbenennen).

## Datenlage (lokal, nicht im Repo)

- `data/raw/`: Zähler-CSVs (`<nr>__n.csv`, `<nr>_2025n.csv`; stündlich:
  kumulative Energie kWh, Volumenstrom l/h, Leistung kW, ΔT, VL/RL °C,
  kumulatives Volumen m³), Shapefiles, `Nodes_Edges.ods`,
  `20252810_Ergebnis_Optimierung_FW[45].xlsx` (66 Begehungen = Labelquelle),
  `Zuordnung.xlsx` (Zähler↔Adresse, jahresbezogen, Zählerwechsel).
- **Zeitreihen nur aus Notebook 00.** `notebooks/00_eda_hast_stationsprofile.ipynb`
  ist die verbindliche Datenaufbereitung (Team-Vorgabe). Es schreibt je
  Zähler eine Stundenreihe nach `data/processed/real_meters/`. Alle
  Notebooks ab 06 und alle `src`-Module laden diese Ausgabe über
  `src/nb00_daten.lade_serien()`, nicht über
  `load_timeseries.load_meter_timeseries` aus `data/raw/`. Nach jeder
  Rohdaten-Nachlieferung zuerst NB 00 neu ausführen (`lade_serien` warnt,
  wenn `data/raw` neuer ist). `load_timeseries --materialize` nie nach
  `real_meters` schreiben lassen. Stand: 100 Zähler, fünf davon mit
  ODS-Nachlieferung bis Juli 2026; deren fehlende Energie-/Volumenstände
  integriert `lade_serien` aus Leistung und Durchfluss. Stationsfeatures
  aus `src/features.py` über `nb00.stationsfeatures()` rechnen, nicht über
  `features_for_directory(real_meters)`, sonst fehlen bei diesen Zählern
  Jahresenergie, Jahresvolumen und Volllaststunden.
- Loader: `src/nb00_daten.py` (Stundenreihen), `src/load_begehungen.py`,
  `src/load_data.py` (enthält `_normalize_address()` — **immer** für
  Adress-Joins nutzen, naiver Join trifft nur 21/101).
- **Adresse vs. Anschlusswert bewusst getrennte Quellen** (seit
  2026-09-24): `Zuordnung.xlsx` über `load_begehungen.meter_to_address()`
  ist die vollständigere Adressquelle (102/102 Zähler) und hat überall
  Vorrang vor `Nodes_Edges.ods`'s `Straße`-Spalte (99/101). Anschlusswert
  (kW) gibt es **nur** in `Nodes_Edges.ods` — beide Quellen bei
  `features_for_directory(meter_dir, nodes_df, address_map)` unabhängig
  kombinieren, nicht durch eine ersetzen.
- **Dateiname der Begehungs-Excel ist nicht stabil** (Klammerstil wechselt
  zwischen Datenlieferungen, `(45)` vs. `[45]`) — `load_begehungen.py`
  löst den Pfad seit 2026-09-24 per Glob auf (`*Ergebnis_Optimierung_FW*.xlsx`,
  wie schon `load_data.load_inspections()`), nicht mehr hartkodiert.
- Features: `src/features.py` (`compute_hast_features()`, ~25 Merkmale).

## Befundstand (nicht wiederholen, darauf aufbauen)

- **K-Means auf Stationsprofilen:** keine belastbare Struktur (Silhouette
  < 0,22 für alle k), trennt entlang Rücklauf/Spreizung (fachlich richtige
  Achse), korreliert aber nicht mit Ground Truth — Ursache: Basisrate 82 %
  „mind. eine Maßnahme". Details: `notebooks/01_kmeans_stationscluster.ipynb`.
- **Supervised ML (LogReg, Random Forest):** schlägt weder trivialen
  Klassifikator noch Regel-Baseline (Balanced Acc 0,33/0,42 vs. 0,50).
  84 % Label-Leakage (Begehung liegt im Feature-Fenster), nur 9 negative
  Fälle bei n=49. Details: `docs/ml-klassifikator.md`.
- **Wirkungsanalyse:** Diff-in-Diff ohne Signifikanz (p ≈ 0,4), aber
  Rücklaufänderung monoton über Änderungskategorien; dokumentierte
  Heizzeit-Änderungen in 4/4 Fällen messbar. Kritischster Einzelbefund:
  Zähler 68956351 — Ventil 3 Jahre offen, Reparatur steht **nicht** in der
  Begehungstabelle → Label-Qualität ist der Flaschenhals. **Vierfeldertafel
  Zustand vor/nach (2026-09-24, Notebook 03, Abschnitt 3b):** Rücklauf
  > 50 °C = schlecht, n=42 auswertbare Begehungen. 62 % gut→gut, **26 %
  schlecht→schlecht** (Begehung ohne messbare Wirkung — wertvollster
  Einzelbefund, Kandidaten für Zweitbegehung oder falsch attribuierte
  Ursache), 10 % schlecht→gut, 2 % gut→schlecht.
- **`full_load_hours`-Bug: behoben 2026-09-21** (Branch
  `analyse/unsupervised-learning`, Regressionstest
  `tests/test_features.py`). Energie-/Volumenaggregate werden auf
  8760 h/Jahr normiert. **Konsequenz:** `data/processed/hast_features.csv`
  und die Ergebnisse von Notebook 01 basieren auf dem alten Stand und
  müssen mit korrigierten Features neu gerechnet werden.

## Roadmap (aus Team-Meetings und den lokalen Projektnotizen)

1. ~~`full_load_hours`-Bug fixen~~ erledigt 2026-09-21; danach
   `hast_features.csv` neu erzeugen und Notebook 01 erneut laufen lassen.
2. ~~**Clustering-Benchmark**~~ **erledigt 2026-09-22** (Notebook
   `04_clustering_benchmark.ipynb`, Skill `clustering-benchmark`):
   K-Means k=3 stabilstes Verfahren (Bootstrap-ARI 0,71/0,60), aber
   keine belastbare Struktur jenseits des Ausreißer-Trios
   {58202380, 66761022, 86792512} (alle Silhouetten ab k=3 < 0,25;
   Verfahren einig nur über die Ausreißer, paarweiser ARI 0,15–0,58).
   HDBSCAN degeneriert (Negativbefund dokumentiert). Ground Truth
   trennt nichts (Basisrate 80 %). Referenz-Zuordnungen:
   `data/processed/cluster_benchmark.csv`.
3. **Zeitliche Aggregation:** statt ein Profil über zwei Jahre →
   Zustandsfenster (z. B. 14-Tage-Fenster aus Notebook 02) in der
   Stundendimension hochaggregieren; Anomalien zählen nur, wenn sie
   **dauerhaft über längere Zeit** bestehen. → Skill `zeitreihen-features`.
   Ergänzend **erledigt 2026-09-23** (Pauline, Notebook
   `05_kmeans_stundenweise_betriebszustaende.ipynb`): K-Means auf **jeder
   einzelnen Betriebsstunde** (keine Aggregation) liefert k=5, Silhouette
   0,40 — fachlich klar interpretierbare Betriebszustände (Stillstand,
   effizienter Normalbetrieb, Teillast, Verdacht auf hydraulischen
   Kurzschluss, Hochlast). Offen: Stabilitätsprüfung (Bootstrap-ARI),
   Ground-Truth-Join, Jahreszeiten- vs. Betriebszustand-Unterscheidung
   noch nicht abschließend geklärt (siehe Notebook-Zellen 4 und 29).
4. **Cluster-Wanderung um Begehungen:** Zeitfenster vor/nach Begehung
   (Fensterwahl ist fachlich kritisch — kurz genug für Attribution, lang
   genug für stabile Features; zusätzlich Endfenster am Datenrand).
   Prüfen: Verändert sich die Clusterzugehörigkeit, und ist die Änderung
   auf die dokumentierte Intervention zurückführbar? → Skill
   `begehungs-wirkungsanalyse`. Grundlage **seit 2026-09-24** vorhanden:
   `windowed_features_for_meter(begehungen=...)` markiert Fenster, die
   eine Begehung überspannen (`begehung`-Flag) und liefert den
   signierten Tagesabstand zur nächstgelegenen Begehung
   (`days_since_begehung`) für Vorher/Nachher-Filterung; Begehungstermine
   je Zähler liefert `load_begehungen.begehung_dates_by_meter()`.
   **Vierfeldertafel erledigt 2026-09-24** (Notebook 03, Abschnitt 3b):
   gut→gut 62 %, **schlecht→schlecht 26 %** (Begehung ohne Wirkung —
   wertvollster Befund, Kandidaten für Zweitbegehung), schlecht→gut 10 %,
   gut→schlecht 2 %; n=42. Bewusst grob (feste Schwelle, keine
   Signifikanztests) — die eigentliche Cluster-Wanderung auf Basis der
   neuen `begehung`/`days_since_begehung`-Spalten steht noch aus.
5. **Labels verbessern:** Freitext der 57 Begehungsnotizen kodieren,
   Fehlerlabels aus Messdaten ableiten (z. B. Fall 68956351), dann
   Regressions-/Entscheidungsbaum auf den Features als erklärbares Modell.
6. Graphstruktur einbeziehen (Nachbarschaft im Leitungsgraph als
   Cluster-Kontext), sobald 2–4 stehen.

## Arbeitsweise

- Notebooks für Exploration (`notebooks/`, fortlaufend nummeriert, Index
  in `docs/pipeline.md` pflegen), wiederverwendbare Logik in `src/`
  auslagern, Tests in `tests/` (pytest). Smoke-Test-Status in
  `docs/pipeline.md` aktualisieren. Bei parallelen Branches auf
  Nummerierungskollisionen prüfen, bevor ein neues Notebook angelegt wird.
- Vorhandene Notebooks 00–03 als Stil-Referenz (Zell-Notes auf Deutsch,
  Ergebnis-Tabellen, „Zusammenfassung & Bewertung" am Ende mit ehrlicher
  Einordnung inkl. Negativbefunden).
- Zahlen immer gegen die Quelldaten verifizieren, bevor sie in Docs oder
  Zusammenfassungen landen.
