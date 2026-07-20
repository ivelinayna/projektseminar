# Integration der echten Zeitreihen

Generiert am 2026-07-09 von `src/detect_real.py`. Baut auf der
Datensichtung ([datensichtung.md](datensichtung.md)) und der
Qualitätsklassifikation (`src/meter_quality.py`) auf.

> **Datenschutz:** enthält Zählernummern - nicht in öffentliche
> Artefakte oder Review-ZIPs übernehmen.

## 1. Auswahltrichter

| Stufe | Zähler |
|---|---|
| CSV-Exporte vorhanden | 101 |
| davon `auswertbar` | 87 |
| davon zusätzlich topologie-zugeordnet → **ausgewertet** | 79 |

Qualitätsklassen (Schwellen als Konstanten in `src/meter_quality.py`;
Analysefenster = letzte 365 Tage je Zähler, Mindestabdeckung
60 %):

| Klasse | n | Zählernummern |
|---|---|---|
| auswertbar | 87 | (siehe `data/processed/meter_quality.csv`) |
| geringe_abdeckung | 6 | 72135441, 72135443, 80912156, 80912165, 80912191, 81019433 |
| verdaechtig_netzseitig | 4 | 41566330, 41566331, 41566332, 48090145 |
| inaktiv | 3 | 41628863, 41704231, 41704232 |
| schema_abweichend | 1 | 81050517 |

- 6 topologie-zugeordnete Zähler fallen wegen
  Qualität heraus (alle `geringe_abdeckung`).
- 8 auswertbare Zähler sind **nicht zugeordnet**
  (Zählertausch-Kandidaten, Stitching über `Zuordnung.xlsx` steht aus)
  und bleiben deshalb vorerst außen vor - nicht gelöscht.

## 2. Analysefenster

Je Zähler die letzten 365 Tage vor seinem jüngsten
Datenpunkt; materialisiert unter `data/processed/real_meters_window/`.
Fenster über alle ausgewerteten Zähler: 2023-05-14 bis 2025-07-11.
Rohwerte bleiben unverändert (keine Clipping-/Filterentscheidung);
`features.py` wurde minimal robustifiziert (Monats-Trend ignoriert
Monate ohne Daten, statt sie als Durchfluss 0 zu werten).

## 3. Baseline-Ergebnis auf echten Daten

Vorhersageverteilung über die 79 ausgewerteten Zähler:

| predicted_fault | n |
|---|---|
| control_hysteresis | 44 |
| excess_rt | 26 |
| continuous_flow | 6 |
| fouled_filter | 3 |

### Binäre Bewertung (nur die 49 inspizierten Zähler)

Bewertet wird: „Baseline meldet irgendeinen Fehler" gegen „Begehung
dokumentierte irgendeine Maßnahme". Zähler ohne Begehung haben
**unbekannte** Wahrheit und werden nicht bewertet.

- Basisrate: 82 % der inspizierten Zähler
  hatten mindestens eine Maßnahme - die Messlatte für „besser als
  alles-melden" liegt entsprechend hoch.
- Precision 82 %, Recall 100 %
  (TP 40, FP 9, FN 0, TN 0).

| Begehung: Massnahme | True | alle |
|---|---|---|
| False | 9 | 9 |
| True | 40 | 40 |
| alle | 49 | 49 |

### Je Fehlertyp (Mapping ist eine ANNAHME, siehe `FAULT_TO_MEASURE`)

| predicted_fault | angenommene Massnahme | n_vorhergesagt (inspiziert) | davon Massnahme dokumentiert | n_HAST mit Massnahme | davon so vorhergesagt |
|---|---|---|---|---|---|
| fouled_filter | filter_gereinigt | 2 | 1 | 24 | 1 |
| continuous_flow | durchfluss_neu | 6 | 1 | 18 | 1 |
| excess_rt | durchfluss_neu | 14 | 6 | 18 | 6 |
| low_spreading | durchfluss_neu | 0 | 0 | 18 | 0 |
| oversized_contract | vertrag_changed | 0 | 0 | 9 | 0 |
| control_hysteresis | stellmotor_getauscht / stellventil_getauscht | 27 | 0 | 3 | 0 |

### Warum die Baseline alles meldet: Regel-Auslösung auf echten Daten

| Regel | Bedingung | feuert bei |
|---|---|---|
| excess_rt (alarm) | rt_mean_winter > 48 °C | 33 % der Zähler |
| excess_rt (warn) | RT > 50 °C in > 30 % der Laststunden | 56 % der Zähler |
| continuous_flow (alarm) | Sommer-Medianfluss > 25 l/h | 27 % der Zähler |
| fouled_filter (alarm) | p95-Fluss-Trend < -3 l/h pro Monat | 14 % der Zähler |
| low_spreading (warn) | ΔT unter Last < 15 K | 16 % der Zähler |
| oversized_contract (warn) | Spitzenlast < 40 % Anschlusswert | 1 % der Zähler |
| control_hysteresis (alarm) | 4-12h-FFT-Anteil > 7 % | 95 % der Zähler |

Zentrale Diagnose: Die FFT-Regel für `control_hysteresis` ist auf
echten Daten wertlos, weil reales Zapfverhalten von Natur aus im
4-12h-Band oszilliert - sie dominiert die Vorhersagen. Der hohe
Rücklauf ist dagegen vermutlich ein ECHTES Netzphänomen (deckt sich
mit der ÜZ-Problembeschreibung), aber die Schwelle trennt nicht
zwischen normal-für-dieses-Netz und auffällig. `peak_load_share` liegt
real im Median bei 1.48 - stündliche
Spitzen ÜBERSTEIGEN die Vertragsleistung, die Synthetik nahm ~70 % an;
die `oversized_contract`-Regel ist damit real wirkungslos.

## 4. Ehrliche Einordnung

1. **Zeitliche Verzerrung:** Die Begehungen (2024-08-26
   bis 2025-09-16) liegen teils VOR oder IM
   Analysefenster. Wo eine Maßnahme den Fehler behoben hat, misst die
   Baseline bereits den reparierten Zustand - ein „verpasster" Fehler
   kann schlicht schon behoben sein. Die Zahlen oben sind deshalb eine
   Untergrenze für den Recall auf unbehobenen Fehlern.
2. **Mapping-Annahme:** Fehlertyp → Maßnahme (z. B. excess_rt →
   Durchfluss neu) ist plausibel, aber nicht mit ÜZ validiert.
3. **Begehung ≠ vollständige Wahrheit:** Eine dokumentierte Maßnahme
   heißt nicht, dass der zugehörige Fehler im Fenster sichtbar war;
   keine Maßnahme heißt nicht, dass die Station fehlerfrei ist.
4. **Schwellen sind Synthetik-kalibriert:** Die Regelschwellen stammen
   aus den synthetischen Daten; eine Rekalibrierung auf echten Daten
   (mit dieser Ground Truth) ist der nächste logische Schritt.

## 5. Offene Punkte für ÜZ / Team

1. **Netzseitige Zähler bestätigen:** 41566330, 41566331, 41566332, 48090145
   - hohe Leistung + hoher Negativanteil; vermutlich Erzeuger-/
   Netzmessung, keine HAST.
2. **Inaktive Zähler klären:** 41628863, 41704231, 41704232 - still­gelegt,
   nie in Betrieb, oder Exportfehler?
3. **Eingefrorene Zählerstände** (60 Zähler mit ≥ 7 Tagen konstantem
   Energy-Stand, siehe Datensichtung) - Exportproblem oder real?
4. **Schema-Abweichung:** Export für Zähler 81050517
   ohne ΔT-Spalte neu anfordern (oder ΔT aus Vorlauf−Rücklauf ableiten).
5. **Zählertausch-Stitching** über `Zuordnung.xlsx` für die nicht
   zugeordneten Zähler.
6. **Fehlertyp→Maßnahme-Mapping** fachlich bestätigen.
