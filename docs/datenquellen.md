# Datenquellen

Alle Rohdaten liegen lokal in `data/raw/` (vertraulich, gitignored).
Kennzahlen unten wurden am **2026-07-08 lokal verifiziert** (pandas-Checks,
Pipeline-Lauf), nicht aus Briefing-Dokumenten übernommen.

## 1. Leitungsverlauf-Shapefiles (`Leitungsverlauf_*`)

Physischer Rohrverlauf des gesamten ÜZ-Versorgungsgebiets.

- CRS: ETRS89 / UTM Zone 32N (EPSG:25832)
- 1 305 LineString-Segmente mit Materialattributen (Stahlrohr,
  ISOPEX PE-X, Uponor PE-X), 16 Punkt-Features (Knoten/Stationen)
- Räumlicher Graph daraus: 7 991 Knoten, 7 780 Kanten,
  281 Komponenten, größte Komponente 1 017 Knoten, 17,34 km Rohrlänge
- Die 16 Punkte tragen keine Labels, die zur Adresstopologie passen —
  ein direkter Join Geometrie ↔ Adresse ist damit nicht möglich.

## 2. Logische Topologie (`Nodes_Edges.ods`)

Drei Tabellenblätter (mit pandas/odfpy verifiziert):

| Blatt | Zeilen | Spalten |
|---|---|---|
| `Nodes` | 99 | Zählernummer, Kundennummer, Anschlusswert, Straße |
| `Edges` | 110 | Node From, Node To |
| `Straßen` | 99 | V-PIN, Abnahmestelle |

- 99 Zählerzeilen entsprechen **94 eindeutigen Adressen** (5 Gebäude
  haben zwei Zähler).
- `Straßen` ist ein Mapping Kundennummer (V-PIN) ↔ Adresse, redundant
  zu `Nodes`; die Loader nutzen nur `Nodes` und `Edges`.
- Logischer Graph: 118 Knoten (94 HAST + 24 Junctions), 110 Kanten,
  max. Grad 4, größte Komponente 110 Knoten, **8 Waisen-HAST ohne
  Kanten** (Datenqualitätsfrage an ÜZ).
- Gesamtanschlusswert: 2 133 kW; zwei 500-kW-Großabnehmer als Hubs.
- Straßennamen sind uneinheitlich (`Blumenstr.` vs. `Blumenstraße`) —
  deterministische Normalisierung in `load_data._normalize_address`.

## 3. Begehungsdaten (`20252810_Ergebnis_Optimierung_FW[45].xlsx`)

Wichtigste Ground Truth für bekannte Fehler.

- **66 Begehungszeilen** an **62 eindeutigen Adressen**; 59 der 94
  HAST-Adressen im Graph haben Begehungsdaten (63 % Abdeckung).
- Alt/Neu-Werte für Anlagenkonfiguration, Heizzeiten, Vertragsleistung,
  Regelparameter PA1.1–PA1.9 plus Ja/Nein-Flags für Maßnahmen
  (Filter, Ventil, Stellmotor, Dämmung, Regler).
- Bekannter Tippfehler „Fleiderstraße" → wird beim Laden zu
  „Fliederstraße" korrigiert.
- Häufigste Befunde (aus `fault_summary.csv`): Filter gereinigt 47 %,
  Durchfluss neu eingestellt 34,8 %, Dämmung erneuert 34,8 %.

## 4. Echte Zähler-Zeitreihen (CSV-Exporte)

**Stand 2026-07-08: vorhanden** (die CLAUDE.md-Annahme „fehlen noch" ist
überholt). Die Dateien liegen direkt in `data/raw/`.

- Schema pro Zeile: `Timestamp, Energy (kWh), Volume flow (l/h),
  Power (kW), Temperature difference (°C), Flow temperature (°C),
  Return temperature (°C), Volume (m³)` — **identisch zum synthetischen
  Schema** in `synth_data.py`. Energy/Volume sind kumulative Zähler.
- Zwei Export-Generationen mit überlappenden Zeiträumen:
  `<Zählernummer>__n.csv` (endet ~Mai 2024) und
  `<Zählernummer>_2025n.csv` (endet ~Juli 2025).
- **154 Dateien für 101 eindeutige Zählernummern**; Historie je Zähler
  unterschiedlich, insgesamt ca. Nov 2021 bis Jul 2025, Stundenraster
  mit Minuten-Versatz (z. B. `13:01`), Dateien absteigend sortiert.
- Abgleich mit der Topologie: 85 Zähler stehen in `Nodes_Edges.ods`,
  16 nicht (vermutlich Zählertausch), 14 Topologie-Zähler haben
  keine CSV.
- Bekannte Rohdaten-Eigenheiten: vereinzelt negative Durchfluss-/
  Leistungswerte (Messrauschen), Lücken, Zählerwechsel.
- Loader: `src/load_timeseries.py` (mergen, sortieren, deduplizieren;
  neuere Export-Generation gewinnt bei Zeitstempel-Duplikaten).

## 5. Zuordnung (`Zuordnung.xlsx`)

Blätter `2024`, `2025`, `2026`; 115 Zeilen (Blatt 2024).
Mapping Zählernummer → Kundennummer (V-PIN) → Abnahmestelle plus
Monatswerte. Wichtig, um Zählertausch aufzulösen: einige CSV-Zähler
fehlen in `Nodes_Edges.ods`, sind hier aber bekannten Adressen
zugeordnet (Beispielmuster: dieselbe Abnahmestelle mit alter Nummer in
`Nodes`, neuer Nummer in `Zuordnung`).

## Bekannte Datenprobleme (Kurzliste)

1. 8 Waisen-HAST ohne Kanten in der logischen Topologie → an ÜZ melden.
2. Geocoding-Lücke: OSM hat im Neubaugebiet Wiesentheid keine
   ausreichenden Hausnummern; mehrere HAST landen auf
   Straßenmittelpunkten. Lösung: GIS-Koordinaten von ÜZ oder
   BKG-Geocoder; Übergang: `data/manual/address_overrides.csv`.
3. Kein direkter Schlüssel zwischen Shapefile-Geometrie und
   Adresstopologie (Snapping wartet auf verlässliche Koordinaten).
4. Zählertausch: CSV-Bestand und `Nodes_Edges.ods` decken sich nur zu
   ~85 % — Stitching über `Zuordnung.xlsx` ist offen.
