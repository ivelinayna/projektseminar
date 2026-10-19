# `data/raw/` — source files (gitignored)

This directory holds the raw data feeds from **ÜZ Mainfranken**. To run the pipeline, copy the following files here:

| File | From |
|---|---|
| `Leitungsverlauf_LineString.{shp,shx,dbf,prj,cpg}` | ÜZ shapefile bundle |
| `Leitungsverlauf_Point.{shp,shx,dbf,prj,cpg}` | ÜZ shapefile bundle |
| `Leitungsverlauf_MultiPoint.{shp,shx,dbf,prj,cpg}` | ÜZ shapefile bundle |
| `Nodes_Edges.ods` | ÜZ topology export |
| `*Ergebnis_Optimierung_FW*.xlsx` | ÜZ on-site inspection export |
| (later) `2024.zip`, `2025.zip`, `2026.zip` | meter time series, one CSV per Zählernummer |
| (later) `Zuordnung.xlsx` | meter-number ↔ Verbrauchsstelle mapping per year |

## `data/manual/` (gitignored)

Hand-maintained lists that contain addresses. Currently `adressen_koordinaten.ods` (columns `adresse`, `koordinate`, `quelle`), the coordinate list from notebook 16 of the team. Used by `notebooks/24_netzereignisse.ipynb` (part E) and `notebooks/25_netzkarte.ipynb`.
