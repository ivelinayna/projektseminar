# Nächste Schritte

Priorisiert; Stand 2026-07-08. Punkte mit **[Entscheidung]** brauchen
eine fachliche Entscheidung im Team bzw. Input von ÜZ und werden nicht
von KI-Assistenten allein entschieden.

## Kurzfristig

0. ~~`full_load_hours`-Bug~~ **erledigt 2026-09-21/22** (Branch
   `analyse/unsupervised-learning`): Normierung auf 8760 h/Jahr in
   `src/features.py` **und** in der Inline-Funktion von Notebook 00
   (dort steckte derselbe Bug — ohne den Notebook-Fix hätte der
   src-Fix nichts geändert). `hast_features.csv` neu erzeugt,
   Notebook 01 neu gerechnet: k = 2 trennt 97/3 (Silhouette 0,599),
   isoliert exakt den früheren Konsens-Dreier-Cluster. Neubefund:
   86792512 ist ein **BHKW** (Zuordnung.xlsx) → Stationstyp vor dem
   Clustern abziehen **[Entscheidung]**; 58202380 und 66761022 stehen
   in keiner Begehungsakte → Rückfrage an ÜZ **[extern]**. Nächster
   Schritt: Clustering-Benchmark (Skill `clustering-benchmark`) mit
   Stabilitätsprüfung der neuen Aufteilung.
1. ~~Echte Zeitreihen anschließen~~ **erledigt 2026-07-09** via
   `meter_quality.py` + `detect_real.py` (Fenster: letzte 365 Tage je
   Zähler, Mindestabdeckung 60 %, Rohwerte unverändert). Ergebnis:
   79 Zähler ausgewertet, Baseline meldet alle als fehlerhaft — siehe
   [echte-daten-integration.md](echte-daten-integration.md).
2. **Baseline-Schwellen auf echten Daten rekalibrieren.
   [Entscheidung]** Die FFT-Regel (control_hysteresis) feuert bei 95 %
   der echten Zähler und ist so unbrauchbar; RT-Schwellen trennen
   nicht zwischen netztypisch und auffällig; `oversized_contract`
   (Spitzenlast < 40 %) ist wirkungslos, weil reale Stundenspitzen die
   Vertragsleistung übersteigen. Kalibrierdaten liegen bereit
   (`features_real.csv` + `predictions_real.csv` mit Ground-Truth-Join).
3. **Fehlertyp→Maßnahme-Mapping bestätigen. [Entscheidung]** Das
   Mapping in `detect_real.FAULT_TO_MEASURE` ist eine Annahme.
4. **[Entscheidung]** Zählertausch-Stitching über `Zuordnung.xlsx`
   (8 auswertbare Zähler sind nicht zugeordnet, 14 Topologie-Zähler
   haben keine CSV).

## Mittelfristig (wartet auf externe Daten)

4. **Geocoding-Lücke lösen. [Entscheidung/extern]** Beste Option:
   GIS-Koordinaten der HAST direkt von ÜZ erfragen. Alternative:
   amtlicher BKG-Geocoder. Übergang: `data/manual/address_overrides.csv`
   pflegen. Erst danach:
5. ~~Logischen und räumlichen Graph verbinden~~ **teilweise erledigt
   2026-07-12:** `src/snap_hast.py` snappt alle 99 Stationen an den
   nächsten Rohrknoten (Median 6,7 m; 94 innerhalb 50 m, 5 darüber)
   und speichert die Distanz als Unsicherheitsmaß. **Bleibt
   näherungsweise**, solange die Koordinaten Straßenmittelpunkte sind —
   belastbar erst mit ÜZ-Koordinaten (Punkt 4).
6. **Waisen-HAST klären. [extern]** Liste der 8 kantenlosen HAST an ÜZ
   zurückspielen (Datenqualitätsfrage).

## Danach

7. **Dashboard auf echte Daten umstellen** und Ampellogik gegen
   Begehungsbefunde validieren.
8. ~~ML-Klassifikator mit Begehungslabels trainieren~~ **erledigt
   2026-07-20** (`src/ml_classifier.py`, [ml-klassifikator.md](ml-klassifikator.md)).
   **Negativergebnis:** LogReg und Random Forest schlagen weder den
   trivialen Klassifikator noch die Regel-Baseline (Balanced Accuracy
   0.33/0.42 vs. 0.50). Blockierend sind strukturelle Datenprobleme,
   nicht die Modellwahl: 84 % Label-Leakage (Begehung im Feature-Fenster),
   nur 9 negative Fälle bei n=49. **[Entscheidung/extern]** Ein sinnvoller
   nächster Versuch braucht von ÜZ Zeitreihen VOR den Begehungen
   (leakage-frei) und mehr Stationen ohne Befund.
9. **GNN/Predictive Maintenance** erst wenn 8. eine tragfähige Datenbasis
   hat: braucht leakage-freie Labels, integrierte Zeitreihen und einen
   sauberen Graph-Join. Aktuell nicht sinnvoll (siehe ML-Negativergebnis).
10. **Skalierung auf weitere ÜZ-Teilnetze** (Loader generisch halten,
    keine Wiesentheid-Hardcodes einführen).
