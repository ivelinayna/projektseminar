# Heating Network Fault Detection — ÜZ Mainfranken

Project seminar collaboration with **ÜZ Mainfranken** on fault detection
and performance optimisation in district heating networks.
Julius-Maximilians-Universität Würzburg, SS 2026 / WS 2026.

> **Status: data exploration & graph construction (Step 1 of N).**
> Time-series meter data (2024 / 2025 / 2026 CSVs) and predictive
> maintenance modelling will follow in later iterations.

## What's in here

| Path | Purpose |
|---|---|
| `src/load_data.py` | I/O for shapefiles, ODS topology, optimisation Excel, with German address normalisation |
| `src/build_graph.py` | Logical graph (NetworkX) from address topology + spatial graph from pipe geometry |
| `src/visualize.py` | Static PNG topology + interactive folium map of the pipe network |
| `src/inspections.py` | Tidy view of the on-site inspection / optimisation records |
| `src/synth_data.py` | Synthetic hourly meter data with embedded faults (5 fault types, 1 year) |
| `src/features.py` | Time-series feature engineering (~25 numeric features per HAST) |
| `src/fault_detection.py` | Rule-based fault classifier — baseline for the eventual ML model |
| `src/geocode.py` | Geocode HAST addresses via Nominatim (with persistent cache) |
| `src/geocode_stub.py` | Offline coordinate stubs — only for sandbox testing, never run locally |
| `src/dashboard_map.py` | Combined map: pipes + geocoded HAST + inspection findings + predicted faults |
| `src/main.py` | One-command end-to-end pipeline |
| `data/raw/` | Source files from ÜZ — **gitignored**, never committed |
| `data/processed/` | Derived CSVs — **gitignored** |
| `outputs/` | Generated visualisations — **gitignored** |
| `docs/` | Long-form docs (Read-the-Docs / GitHub Pages target) |

## Quick start

```bash
git clone <repo-url>
cd heating-network
pip install -r requirements.txt
# place ÜZ data files into data/raw/  (NOT committed - see .gitignore)
python -m src.main                                          # graphs + maps + inspection summary
python -m src.main --synth --detect --plot                  # also synth data + fault detection
python -m src.main --geocode --dashboard                    # geocode HAST + dashboard map
python -m src.main --synth --detect --plot --geocode --dashboard  # everything
```

**Note on geocoding.** The first time you run `--geocode` locally,
Nominatim is queried once per unique address (~99 requests, rate-limited
to 1/s ≈ 100 s). Results are cached in
`data/processed/geocode_cache.json` so subsequent runs are instant.

## Data sources

Three feeds from ÜZ (raw, **never** committed):

1. **Shapefiles `Leitungsverlauf_*`** — physical pipe layout for the
   whole ÜZ Mainfranken service area. CRS: ETRS89 / UTM 32N (EPSG:25832).
   1 305 line segments with material attributes
   (Stahlrohr, ISOPEX PE-X, Uponor PE-X), 16 marked points
   (junctions / stations).

2. **`Nodes_Edges.ods`** — logical topology of the Prichsenstadt
   sub-network. 99 customer connection points (HAST) keyed by meter
   number + address + contracted load (Anschlusswert), and 110 edges
   between addresses.

3. **`20252810_Ergebnis_Optimierung_FW_45_.xlsx`** — 67 on-site
   HAST inspection records with old / new values for Anlagenkonfig,
   Heizzeiten, Vertragsleistung, Regelparameter PA1.1–PA1.9, plus
   yes/no flags for what was repaired (filter, valve, actuator,
   insulation, controller). **This is the labelled fault corpus.**

CSV time-series per meter (timestamp, energy kWh, volume flow l/h, power
kW, ΔT, Vorlauf °C, Rücklauf °C, volume m³) for 2024 / 2025 / 2026
will be added next.

## What we know so far

Network is essentially a **tree, 110 nodes, max degree 4**, with two
high-load consumers (~250 kW and ~500 kW) acting as central hubs.
Total contracted load ≈ 2 MW across 94 HAST.

## Fault detection baseline

`src/fault_detection.py` is a rule-based classifier expressing the
domain knowledge from the inspection Excel as plain thresholds. It
serves three purposes:

1. **Pipeline validation.** On synthetic data with embedded faults,
   the rules currently recover **100 % of injected faults with no false
   positives** across 99 HAST. That confirms the feature pipeline is
   self-consistent.
2. **Benchmark.** Any future ML model has to beat this baseline to be
   worth deploying.
3. **Explainability.** Every flag carries a plain-language reason
   (`"summer median flow 47 l/h (should be ~0)"`) suitable for a
   technician dashboard.

Five fault families are currently encoded:

| Fault | Detection signal |
|---|---|
| `fouled_filter` | 95 th-percentile flow drifts down month-over-month |
| `excess_rt` | Winter return temperature > 48 °C, or RT > 50 °C in > 30 % of loaded hours |
| `continuous_flow` | Summer median flow > 25 l/h (real DHW is bursty) |
| `oversized_contract` | Peak power < 40 % of contracted load |
| `control_hysteresis` | 4–12 h periodic component carries > 7 % of total flow variance |

These will be retrained as classifiers once the real CSVs arrive and
features can be paired with the inspection labels.

## Inspection ↔ HAST property correlations

A first pass over the 66 inspection records, joined to building age and
plant configuration, suggests three actionable patterns:

* **Plant configuration 2.1** is by far the most common (32 / 66
  HAST) and shows the highest filter-cleaning rate (53 %) and
  flow-rebalancing rate (47 %) — likely the highest-yield target for
  any campaign.
* **Of 11 contract-load changes, 9 were *reductions*** (median −2 kW),
  consistent with chronic over-specification on the customer side.
* **"Schmutzfänger" appears 8× in free-text notes** in addition to the
  formal filter flag, so the real fouling rate is probably higher than
  the 47 % the structured columns show.

## Known data quality issues

* `Nodes_Edges.ods` mixes street-name styles (`Blumenstr.`, `Blumenstraße`)
  — addresses are normalised in `load_data._normalize_address`.
* `Optimierung.xlsx` has the typo **Fleider**straße → handled in
  `load_inspections`.
* 8 HAST appear in the `Nodes` sheet but are not referenced by any edge
  (orphans in the topology). Worth raising back to ÜZ.
* The shapefile `Point` layer has only 16 marked points and no labels
  matching the address topology — we cannot directly join physical
  geometry to logical addresses yet. Geocoding via Nominatim is on the
  to-do list.

## Roadmap

- [x] Load all three data feeds, normalise addresses, build first graphs
- [x] One-command pipeline; static + interactive visualisations
- [x] First fault frequency tabulation from inspection data
- [x] Synthetic time-series generator with 5 embedded fault types (`synth_data.py`)
- [x] HAST-level feature engineering from hourly meter data (`features.py`)
- [x] Rule-based fault detection baseline — 100 % accuracy on synthetic data
- [x] Inspection ↔ Anlagenkonfig / Baujahr / Anschlusswert correlation analysis
- [x] Geocode addresses → connect logical graph to spatial geometry (`geocode.py`)
- [x] Combined dashboard map showing inspection findings + predicted faults per HAST
- [ ] Ingest 2024/2025/2026 time-series CSVs per meter (replacing synthetic)
- [ ] Train a tree-ensemble classifier with the inspection records as labels
- [ ] Snap geocoded HAST to their nearest spatial-graph node (clean topology join)
- [ ] Predictive-maintenance dashboard (Streamlit / similar)
- [ ] Full Read-the-Docs site via GitHub Pages
