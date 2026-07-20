# Datensichtung: echte Zähler-Zeitreihen

Generiert am 2026-07-09 von `src/profile_timeseries.py` (read-only, keine
Filterung). Datenbasis: CSV-Exporte in `data/raw/`, eingelesen über
`src.load_timeseries` (Export-Generationen gemergt, Duplikate entfernt).

> **Datenschutz:** Dieser Report enthält Zählernummern. Nicht in
> öffentliche Artefakte, Review-ZIPs oder Präsentationen übernehmen.
> Die vollständige Metrik-Tabelle liegt (gitignored) unter
> `data/processed/timeseries_profile.csv`.

## 0. Schema-Abweichungen

1 Zähler konnten nicht profiliert werden, weil
mindestens eine Exportdatei vom 8-Spalten-Schema abweicht:

- `81050517_2025n.csv: missing expected columns ['Temperature difference (°C)'] - got ['Timestamp', 'Energy (kWh)', 'Volume flow (l/h)', 'Power (kW)', 'Flow temperature (°C)', 'Return temperature (°C)', 'Volume (m³)']`

Diese Zähler fehlen in allen folgenden Zahlen.

## 1. Inventar und Abdeckung

- **100 Zähler** profiliert, gesamt 1,744,864 Datenpunkte.
- Gesamtzeitraum: 2021-05-31 23:59:00 bis 2025-07-11 13:01:00.
- Historie je Zähler: Median 924 Tage,
  Minimum 322, Maximum 1434 Tage.
- **1 Zähler haben weniger als 365 Tage
  Historie** (Feature-Berechnung erwartet ~1 Jahr).
- Abdeckung (Datenpunkte / erwartete Stunden im Zeitraum): Median
  71.6 %, Minimum 16.7 %.
- Lücken (> 1.5 h zwischen Punkten): Median 160
  Lücken je Zähler, größte Einzellücke im Bestand
  730.0 Tage.

### Zähler mit kurzer Historie (< 365 Tage)

| Zählernummer | ts_min | ts_max | span_days |
|---|---|---|---|
| 86792512 | 2024-08-23 11:09:00 | 2025-07-11 13:01:00 | 322.1 |


## 2. Kumulative Zähler (Energy kWh, Volume m³)

- Energy monoton steigend: **91 von 100** Zählern
  (9 mit Rücksprüngen).
- Volume monoton steigend: **71 von 100** Zählern.
- **60 Zähler** haben Phasen von ≥ 7 Tagen
  mit komplett konstantem Energy-Zählerstand. Hinweis zur Interpretation:
  Im Sommer kann ein konstanter Zähler legitim sein (kein Verbrauch);
  konstante Phasen über Wochen oder im Winter deuten eher auf
  eingefrorene Werte im Export hin.

### Zähler mit Rücksprüngen im kumulativen Zähler

| Zählernummer | energy_n_drops | energy_max_drop | volume_n_drops |
|---|---|---|---|
| 69513891 | 2 | -3 | 4 |
| 72135463 | 0 | 0 | 3 |
| 58202380 | 0 | 0 | 3 |
| 72135453 | 1 | -2 | 3 |
| 72167783 | 0 | 0 | 3 |
| 72167782 | 0 | 0 | 3 |
| 68956369 | 1 | -1 | 2 |
| 72135442 | 0 | 0 | 2 |
| 72135481 | 0 | 0 | 2 |
| 72135486 | 1 | -1 | 2 |
| 68956372 | 0 | 0 | 2 |
| 72167793 | 1 | -3 | 2 |
| 72167777 | 0 | 0 | 2 |
| 72135480 | 0 | 0 | 2 |
| 72167784 | 2 | -1 | 2 |
| 68956355 | 0 | 0 | 2 |
| 68956353 | 0 | 0 | 2 |
| 72167791 | 0 | 0 | 1 |
| 72167778 | 1 | -1 | 1 |
| 41566330 | 1 | -141 | 1 |
| 72135476 | 0 | 0 | 1 |
| 72135440 | 0 | 0 | 1 |
| 68956367 | 0 | 0 | 1 |
| 68956366 | 0 | 0 | 1 |
| 68956361 | 0 | 0 | 1 |
| 68956360 | 0 | 0 | 1 |
| 68956356 | 0 | 0 | 1 |
| 68956351 | 0 | 0 | 1 |
| 72135441 | 0 | 0 | 1 |
| 53198226 | 4 | -3 | 0 |


### Zähler mit ≥ 7 Tagen konstantem Energy-Stand (Top nach Dauer)

| Zählernummer | energy_longest_const_days | energy_zero_diff_share | span_days |
|---|---|---|---|
| 72167783.0 | 170.8 | 0.538 | 1347.6 |
| 41704231.0 | 1347.5 | 1.0 | 1347.5 |
| 41704232.0 | 1347.5 | 1.0 | 1347.5 |
| 41628863.0 | 251.5 | 0.981 | 1347.5 |
| 80912199.0 | 242.4 | 0.19 | 771.5 |
| 80912161.0 | 222.1 | 0.908 | 771.5 |
| 80912194.0 | 160.5 | 0.295 | 771.5 |
| 80912198.0 | 146.7 | 0.269 | 771.5 |
| 80912201.0 | 146.6 | 0.483 | 771.5 |
| 80912195.0 | 146.5 | 0.361 | 771.5 |
| 80912196.0 | 141.3 | 0.283 | 771.5 |
| 80912175.0 | 139.6 | 0.087 | 771.5 |
| 80912177.0 | 139.4 | 0.326 | 771.5 |
| 80956410.0 | 139.3 | 0.081 | 771.5 |
| 72167778.0 | 139.0 | 0.327 | 771.5 |


## 3. Negative Messwerte

- Anteil Stunden mit Volume flow < 0: Median 0.0 %,
  p90 0.0 %, Maximum 40.9 %.
- Anteil Stunden mit Power < 0: Median 0.2 %,
  p90 2.6 %, Maximum 44.1 %.
- **1 Zähler** liegen über der Auffälligkeitsschwelle
  (30% negative Fluss- oder Leistungswerte).
- **3 Zähler** haben ≥ 90% Stunden mit
  Power ≤ 0 (fast nur Null-/Negativwerte).

### Zähler mit hohem Negativanteil

| Zählernummer | flow_neg_pct | power_neg_pct |
|---|---|---|
| 48090145.0 | 40.9 | 44.1 |


### Zähler mit ≥ 90% Power ≤ 0

| Zählernummer | power_le0_pct | flow_zero_pct | power_median |
|---|---|---|---|
| 41628863.0 | 98.9 | 96.7 | 0.0 |
| 41704231.0 | 100.0 | 100.0 | 0.0 |
| 41704232.0 | 100.0 | 100.0 | 0.0 |


## 4. Robuste Verteilungen der Kerngrößen

### Gepoolt über alle 1,744,864 Stundenwerte

| Größe | p10 | Median | p90 |
|---|---|---|---|
| Power (kW) | 0.0 | 0.42 | 7.32 |
| ΔT (K) | 0.3 | 14.0 | 36.5 |
| Vorlauf (°C) | 35.1 | 69.5 | 77.1 |
| Rücklauf (°C) | 26.9 | 46.6 | 69.2 |

### Streuung der Je-Zähler-Kennzahlen (p10 / Median / p90 über 100 Zähler)

| Kennzahl je Zähler | p10 | Median | p90 |
|---|---|---|---|
| Median Power (kW) | 0.0 | 0.75 | 3.47 |
| Median ΔT (K) | 1.95 | 16.4 | 28.0 |
| Median Vorlauf (°C) | 52.98 | 69.7 | 75.35 |
| Median Rücklauf (°C) | 31.57 | 44.6 | 65.01 |
| Zeitspanne (Tage) | 771.5 | 923.65 | 1347.5 |
| Abdeckung (%) | 51.07 | 71.6 | 73.82 |
| Anteil Fluss < 0 (%) | 0.0 | 0.0 | 0.0 |
| Anteil Power ≤ 0 (%) | 6.19 | 32.8 | 62.9 |

Die vollständige Tabelle pro Zähler (alle Metriken dieses Reports)
liegt unter `data/processed/timeseries_profile.csv`.

## 5. Zuordnung zur logischen Topologie

- **85 von 100 Zählern** stehen mit ihrer Zählernummer in
  `Nodes_Edges.ods` (Sheet `Nodes`).
- 15 Zähler fehlen dort - mutmaßlich Zählertausch; Kandidat
  für die Auflösung ist `Zuordnung.xlsx` (siehe
  [naechste-schritte.md](naechste-schritte.md)).

### CSV-Zähler ohne Topologie-Eintrag

| Zählernummer | ts_min | ts_max | span_days |
|---|---|---|---|
| 41566330 | 2021-11-01 23:01:00 | 2025-07-11 12:00:00 | 1347.5 |
| 41566331 | 2021-11-01 23:01:00 | 2025-07-11 12:00:00 | 1347.5 |
| 41566332 | 2021-11-01 23:01:00 | 2025-07-11 12:01:00 | 1347.5 |
| 41628863 | 2021-11-01 23:00:00 | 2025-07-11 12:01:00 | 1347.5 |
| 41704231 | 2021-11-01 23:00:00 | 2025-07-11 12:00:00 | 1347.5 |
| 41704232 | 2021-11-01 23:00:00 | 2025-07-11 12:00:00 | 1347.5 |
| 48090145 | 2021-11-01 23:01:00 | 2025-07-11 12:00:00 | 1347.5 |
| 58177363 | 2021-11-01 23:00:00 | 2024-05-13 13:00:00 | 923.6 |
| 58202380 | 2021-11-01 23:00:00 | 2024-05-13 13:00:00 | 923.6 |
| 61620222 | 2021-11-01 23:00:00 | 2024-05-13 14:00:00 | 923.6 |
| 72167784 | 2023-05-31 23:59:00 | 2025-07-11 13:01:00 | 771.5 |
| 80912166 | 2023-05-31 23:59:00 | 2025-07-11 13:01:00 | 771.5 |
| 58177384 | 2021-11-03 23:00:00 | 2023-11-08 11:00:00 | 734.5 |
| 81062289 | 2024-01-31 16:46:00 | 2025-07-11 13:01:00 | 526.8 |
| 86792512 | 2024-08-23 11:09:00 | 2025-07-11 13:01:00 | 322.1 |


## 6. Offene Fragen für die nächste Etappe

Keine Entscheidung getroffen - zu klären im Team / mit ÜZ:

1. Wie behandeln wir Zähler mit lang konstanten Zählerständen -
   Exportfehler bei ÜZ nachfragen oder betroffene Zeiträume maskieren?
2. Negative Flüsse/Leistungen: Messrauschen um Null (clippen?) oder
   systematisch (Zähler ausschließen)? Die Verteilung oben trennt
   beide Fälle.
3. Analysefenster: letztes volles Jahr je Zähler vs. fixes
   Kalenderjahr - 1 Zähler unterschreiten ein Jahr.
4. Zählertausch-Stitching über `Zuordnung.xlsx` für die
   15 Zähler ohne Topologie-Eintrag.
