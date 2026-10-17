---
name: clustering-benchmark
description: Clusterverfahren auf HAST-Stationfeatures benchmarken (K-Means, Ward, GMM, DBSCAN/HDBSCAN) mit Stabilitäts- und Ground-Truth-Prüfung. Verwenden bei Aufgaben wie „Clustering vergleichen", „beste Methode finden", „k wählen", „Clusterprofile auswerten" im Fernwärme-Projekt.
---

# Clustering-Benchmark für HAST-Stationfeatures

Ziel: kleinen, ehrlichen Benchmark liefern, welches Clusterverfahren auf den
HAST-Features am besten funktioniert — inklusive Negativbefunden.

## Voraussetzungen

- Features aus `src/features.py` (`compute_hast_features()`); Ergebnis
  üblicherweise `data/processed/hast_features.csv`.
- **Vorher prüfen:** `full_load_hours`-Bug gefixt? (`src/features.py`:
  Normierung auf 8760 h/Jahr, nicht Gesamthistorie). Sonst blockiert.
- Ground Truth: `data/processed/inspections_tidy.csv` (aus
  `src/inspections.py`). Adress-Join **immer** über `_normalize_address()`
  aus `src/load_data.py` — naiver Join trifft nur 21/101, normalisiert 55+.

## Vorgehen

1. **Feature-Auswahl & Vorverarbeitung** wie in Notebook 01: numerische
   Merkmale, fehlende Werte explizit behandeln (Imputation kenntlich
   machen), StandardScaler. Nicht still wegfiltern — ausgeschlossene
   Stationen mit Grund tabellieren.
2. **Verfahren auf identischer Vorverarbeitung** fitten:
   - K-Means (Referenz, aus Notebook 01)
   - Agglomerativ/Ward
   - Gaussian Mixture Model
   - DBSCAN bzw. HDBSCAN (Dichte-basiert; Mindest-Clustergröße begründen)
3. **k fest setzen** (nicht automatisch nach Margin entscheiden — in
   Notebook 01 entschied 0,217 vs. 0,215, das ist Rauschen). Elbow- und
   Silhouette-Kurven zeigen, Entscheidung im Text begründen.
4. **Metriken je Verfahren:**
   - Silhouette (Schwelle „schwache Struktur": 0,25 — Notebook 01 lag bei
     allen k darunter; das ehrlich berichten)
   - Bootstrap-ARI als Stabilitätsmaß (Referenzwert K-Means: 0,90)
   - Clustergrößen (ein Verfahren, das 60/1/1 aufteilt, ist kein Befund)
5. **Fachliche Achsen prüfen:** Trennt das Verfahren entlang
   Rücklauf-/Spreizungs-Achse (`rt_mean_winter`, `dt_mean_loaded`,
   `summer_flow_baseline`)? Das ist die fernwärmetechnisch relevante
   Richtung. PCA-Plot zur Visualisierung.
6. **Ground-Truth-Join:** Clusterzugehörigkeit vs. Maßnahmen aus den
   Begehungen (Anteil mit Maßnahme, Ø Anzahl, Einzelmaßnahmen wie Filter).
   Signifikanztests (Chi²/Fisher, Mann-Whitney) mit p-Werten angeben.
   **Basisrate beachten:** „mind. eine Maßnahme" ist bei ~82 % wahr — ein
   fast konstantes Label kann nichts trennen; das als methodischen Befund
   benennen, nicht als Modellfehler.
7. **Ergebnis speichern** nach `data/processed/` (gitignored) und
   Zusammenfassung mit Bewertung ins Notebook; neue Erkenntnisse in
   `docs/` festhalten.

## Bekannte Fallstricke

- Silhouette < 0,25 = „Grenze durch ein Kontinuum", keine Typen — Formulierung
  aus Notebook 01 übernehmen, nicht überinterpretieren.
- Bei k = 3 fanden K-Means, Ward und GMM unabhängig denselben Dreier-Cluster
  (Winterrücklauf 59–62 °C, Sommerdurchfluss bis 16 640 l/h, idle_share ≈ 0)
  — belastbarster bisheriger Einzelbefund, als Konsistenz-Anker nutzen.
- `coverage` (16,7–98,7 %) als Qualitätsdimension berichten, nicht als
  implizites Feature.
- Keine Wiesentheid-Hardcodes; Stationen über normalisierte Adresse
  referenzieren.
