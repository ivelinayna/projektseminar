# Daten (gitignored)

Hier liegen die Daten der ÜZ Mainfranken. Sie sind vertraulich und werden nie committet. Ausführliche Beschreibung:
`docs/daten.md`.

## `data/raw/`

Diese Dateien von der ÜZ hierher kopieren:

| Datei | Inhalt |
|---|---|
| `<Zählernummer>__n.csv`, `<Zählernummer>_2025n.csv` | Stundenwerte je Zähler |
| `<Zählernummer>.ods` | Nachlieferung für fünf Zähler bis Juli 2026 |
| `*Ergebnis_Optimierung_FW*.xlsx` | Begehungen |
| `Zuordnung.xlsx` | Zählernummer zu Abnahmestelle, je Jahr ein Blatt |
| `Nodes_Edges.ods` | logisches Netz mit Anschlusswert |
| `Leitungsverlauf_LineString.*`, `Leitungsverlauf_Point.*`, `Leitungsverlauf_MultiPoint.*` | Rohrverlauf als Shapefile (je `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`) |
| `Leitungsverlauf.kml` | Rohrverlauf als KML, optional für die Netz-Notebooks 31 und 33 |
| `zensus/.../Zensus2022_Baujahr_JZ_100m-Gitter.csv` | Zensus 2022, Gebäude nach Baujahr im 100-m-Gitter, optional (öffentlich, etwa 200 MB) |

- Die Außentemperatur holt `python -m src.weather` selbst: Stundenwerte als Cache in `data/raw/weather/`, Tageswerte
  für die Notebooks 10 und 38 in `data/raw/weather/tageswerte/`.
- Danach zuerst Notebook 00 ausführen.

## `data/processed/`

- Wird von Notebook 00 und den anderen Notebooks geschrieben.
- `real_meters/` enthält die Stundenreihe je Zähler. Alle Auswertungen lesen nur von dort.

## `data/manual/`

- Von Hand gepflegte Listen mit Adressen.
- Derzeit `adressen_koordinaten.ods` (Spalten `adresse`, `koordinate`, `quelle`).
- Wird von den Notebooks 24, 31 und 33 benutzt.
- Für Notebook 38 kommen zwei Handtabellen dazu: `fehler_symptom_matrix_entwurf.xlsx` und `pruefliste_begehungsnotizen.xlsx`. Sie liegen nicht im Repo. Ohne sie bricht Notebook 38 gleich am Anfang ab.