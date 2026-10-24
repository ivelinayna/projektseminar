# Changelog

Alle nennenswerten Änderungen am Projekt. Aufbau angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
versioniert wird nicht — Einträge sind datumsbasiert.

## [Unreleased]

### Hinzugefügt (Modellvergleich aller Modelle und Modellpakete, 2026-10-24)

- `notebooks/32_modellvergleich.ipynb` mit `src/pruefstand.py`: alle Modelle des
  Projekts auf demselben Prüfstand, Regeln eingeschlossen, mit gleichen Fällen,
  Stationen, Tagen und gleicher Alarmmenge bzw. Fehlalarmquote. 15 Wächter und
  27 Erkenner; nur GNN (`30`) und Bayes (`31`) fehlen, weil ihre Eingaben lokal
  nicht vorliegen.
  - **Alarm:** Nach Holm bleibt nur Kennlinie + CUSUM belegt (Tagesmonitor 33
    von 43 Begehungen, p = 0,017). Bei eingerechneten plötzlichen Fehlern liegt
    das Prognose-LSTM mit Schwellenregel vorn (Bypass 150 l/h 84 %, Fühler 43 %
    gegen 17 % beim Wochenmittel ohne Lernen). Kennlinienmonitor (`14`) und die
    Detektoren aus `10` taugen nicht als Alarm.
  - **Ventil:** 15 von 27 Erkennern über Raten, LR Kennzahlen + LSTM 0,89 vorn,
    keiner belegt besser als die Sommernacht-Regel und die README-Regel
    `continuous_flow` (je 0,85); Random Forest und XGBoost nicht besser. Nach dem
    Ventiltausch sinkt der Verdacht im Winter 24/25 messbar (p = 0,016).
  - **Dämmung:** Nur das Paket-Modell ist besser als Raten. Flottenmaße und die
    Nachtspreizung im Sommer zeigen die umgekehrte Richtung; die Deutung in
    `22`, Abschnitt 6, ist damit umgekehrt.
- `src/modellpaket.py`: Modellpakete unter `models/` (gitignored) mit Gewichten,
  Skalierung, Kalibrierung, Schwelle, Datenstand, Code-Stand und Prüfsummen.
  - `src/prognose_waechter.py` (LSTM aus `21`): z-Werte und alle 424 Alarme
    gleich wie `prognose_tage.csv`.
  - `src/normalmodell_waechter.py` (Tagesmonitor): Alarme und z-Werte identisch.
  - `src/fehlerklassen.py` (`18` bis `22`): Klassen für alle 91 Zähler gleich
    wie `fehlerklassen_je_hast.csv`; Kennzahlen und Embedding direkt aus den
    Stundenwerten.
- Doku `docs/modellvergleich.md`; Tests `test_pruefstand`, `test_modellpaket`,
  `test_prognose_waechter`.

### Geändert (Modell-Strang auf der neuen Datenbasis aus Notebook 00, 2026-10-24)

- `18` bis `23` neu gerechnet auf `00` mit 93 statt 96 Zählern (weggefallen:
  41704231, 41704232, 721354800, alle nie begangen). Vorher liefen `06` und
  `17` neu, weil `23` ihre Ausgaben liest. Die Daten der begangenen Zähler vor
  dem Stichtag sind unverändert (bis auf eine Stunde bei 80912174).
- `20` und `21`: alle LSTM neu trainiert. Die Validierungswochen werden aus
  allen Wochen gezogen und haben sich mit den weggefallenen Zählern verschoben;
  mit den alten Gewichten hatte `21` einen Teil der Validierungstage schon im
  Training gesehen, die Schwankung zu klein geschätzt und die Schwelle auf
  z ≥ 6 gesetzt. Neu trainiert bleibt es bei z ≥ 4.
- `22`: Die Grenze für „Regelventil tauschen“ ist fest 0,5 statt Youden-Index.
  Der Youden-Index sprang bei 11 Ventilfällen von 0,54 auf 0,17, die Klasse
  wäre von 21 auf 57 Zähler gewachsen, bei gleicher AUC.
- Texte in `18` bis `23` und `docs/pipeline.md` an die neuen Ausgaben
  angepasst. Inhaltlich verschoben hat sich: In `20` ist der Wintervorsprung
  des LSTM beim Ventil jetzt knapp belegt (+0,15 [0,02; 0,32]), vorher nicht;
  in `19` ist die Ventil-Gegenprobe nach Holm-Korrektur nicht mehr abgesichert;
  in `21` zeigt schon der erste Blick auf die Begehungen keinen Vorsprung, und
  vier neu überwachte nie begangene Zähler mit nur 14 Validierungstagen
  erzeugen einen großen Teil der Winterwarnungen; in `23` liegt Sebs
  Normalverhaltensmodell deutlicher vorne (30 von 43, McNemar p = 0,001).
- `docs/pipeline.md`: Hinweis, dass die LSTM-Gewichte nach einer Änderung der
  Datenbasis gelöscht werden müssen.

### Geändert (Modell-Strang: LSTM auf den begangenen HAST, Wächtervergleich, 2026-10-19)

- `20_lstm_fehlererkennung` und `21_prognose_lstm_waechter`: Die LSTM lernen
  nach Vorgabe der Betreuung nur auf den HAST mit Begehungsdaten; ein Netz
  auf allen HAST läuft zum Vergleich mit. In 20 zusätzlich ein Autoencoder
  als dritte Variante und die Wirkung des fraglichen Ventil-Labels, in 21
  ein Faktor je Jahreszeit und Alarme gezählt wie im Normalverhaltensmodell.
- `18` bis `22`: Jedes Notebook beginnt mit dem, was vorher versucht wurde und
  warum es nicht gereicht hat, und sieht sich die geladenen Tabellen an,
  bevor gerechnet wird.
- `18_modelldaten_labels`: Auslastung zusätzlich auf den Vertrag vor der
  Begehung bezogen (`auslastung_vertrag`). Der Anschlusswert in
  `Nodes_Edges.ods` ist bei 7 von 9 verkleinerten Verträgen schon der neue
  Wert.
- `22_xgboost_fehlerklassen`: Die Überdimensionierung wird mit
  `auslastung_vertrag` gelernt und geprüft; für nie begangene Zähler bleibt
  der Anschlusswert. Damit ist sie erkennbar (Regel AUC 0,78 statt 0,66),
  `fehlerklassen_je_hast.csv` enthält jetzt Hinweise auf Überdimensionierung.
- `21_prognose_lstm_waechter`: Der erste Blick auf die Begehungen
  (24–29 % gegen 8 %) ist als nicht belegt eingeordnet, siehe `23`.

### Hinzugefügt (Wächtervergleich, 2026-10-19)

- `23_vergleich_waechter`: Sebs Begehungsprüfung aus `17` als Funktion,
  Fall für Fall gegen seine Ergebnisse geprüft, dann auf Normalverhaltensmodell
  und Prognose-LSTM unter gleichen Bedingungen angewendet (gleiche Stationen,
  Heiztage, Fälle, Kontrollgruppe und gleiches Alarmbudget). Liest die
  Ausgaben von `06`, `17` und `21`.
- `prognose_tage.csv` enthält zusätzlich die z-Werte des Vergleichsnetzes auf
  allen HAST (`z_rl_alle`, `z_fluss_alle`).

### Hinzugefügt (Kennlinienmonitor als Modell, 2026-10-19)

- Neue Module u. a. `tagesmonitor`, `alarmbewertung`, `netzvergleich`,
  `nachbarschaft`, `netzereignisse`, `stationsblatt`, `aktualisieren`,
  `nb00_daten`, `luecken`, `zeitreihenmodell`, `vergleichsgruppen`,
  `fallsammlung` sowie die älteren Strang-Module `anomalie`, `empfehlung`,
  `freitext`, `clustervalidierung`, `jahresvergleich`, `dynamik`,
  `tagespanel`, `regelkalibrierung`, `network_graph` (jeweils mit Tests)
- Notebooks 07, 09–11 und 23–25, 27; ohne Nummer (Nummer auf main schon
  belegt, wird nachgetragen): `fallsammlung`, `arima`, `luecken`,
  `netzvergleich`, `tagesmonitor`, `alarme`
- Notebooks 08 und 12–15 durch den neuen Stand ersetzt
- `python -m src.aktualisieren` rechnet das Modell komplett neu
  (Stationsblätter, `status.csv`, Bericht unter `outputs/stationsblatt/`)
- Notebooks 00, 01, 03 zellweise zusammengeführt; wo beide Seiten dieselbe
  Zelle geändert haben, gilt der Stand von main
- requirements: `scipy`, `mapclassify`, `geopy`, `ipywidgets`
- Nicht übernommen: Notebooks 05/06 der Lieferung, GNN, Fehlerbaum,
  Doku-Seiten

### Hinzugefügt (Modell-Strang: K-Means-Einstufung, LSTM, Prognose, XGBoost, 2026-10-18)

- Notebooks 18 bis 22 auf der Datenbasis von Notebook 00, ohne neue Module
  in `src/`; genutzt werden `weather`, `inspections`, `befundcodes` und
  `load_begehungen`:
  - `18_modelldaten_labels`: Stundenwerte mit Außentemperatur, Kennzahlen
    nur aus Daten vor der ersten Begehung, Labels je Zähler.
  - `19_kmeans_einstufung_folie5`: Einstufung Optimum / schlechter nach Folie 5.
  - `20_lstm_fehlererkennung`: LSTM-Embedding und verschachtelt geprüfte
    Fehlererkennung (Ventil, Dämmung).
  - `21_prognose_lstm_waechter`: Prognose-LSTM als Überwacher, Prüfung mit
    eingerechneten Fehlern und an den Begehungen.
  - `22_xgboost_fehlerklassen`: Modellvergleich mit Wechselwirkungen und
    SHAP, drei Klassen der Folie 5 für alle Zähler. Negativbefunde
    (Baum-Modelle, Wechselwirkungen, Klassengewichtung) sind dokumentiert.
- `requirements.txt`: `torch` und `xgboost`.
- Zwischenergebnisse in `data/processed/` (gitignored): `modell_stunden.parquet`,
  `modell_kennzahlen.csv`, `modell_labels.csv`, `kmeans_einstufung.csv`,
  `lstm_embedding.csv`, `lstm_scores.csv`, `prognose_tage.csv`,
  `fehlerklassen_je_hast.csv`; Modellgewichte in `notebooks/models/` (gitignored).

### Hinzugefügt (ARIMA und SARIMAX, 2026-10-13)

- `src/zeitreihenmodell.py`: Regression mit AR-Fehlern auf Tagesmitteln
  des Rücklaufs (ARIMA und SARIMAX ohne MA-Teil), mit scipy gebaut, weil
  statsmodels fehlt. Rollender Modellvergleich und Vorher-Prognose je
  Begehung.
- `tests/test_zeitreihenmodell.py`: neun Tests auf synthetischen Reihen.
- `notebooks/18_arima.ipynb` und `docs/arima.md`; Negativbefund als
  Eintrag 15 in `docs/negativbefunde.md`.

### Hinzugefügt (Unsupervised-Strang: Ternär, Stationsbilder, Monitor, Befunde, 2026-10-09)

- Neue Module `src/weather.py`, `src/season.py`, `src/performance.py`,
  `src/ternaer.py`, `src/stationsbilder.py`, `src/kennlinien_monitor.py` und
  `src/befundcodes.py` samt Tests, dazu die Notebooks 08 und 12 bis 15.
- `src/load_timeseries.py`: ODS-Nachlieferung als dritte Exportgeneration
  (`mit_ods=True`), Gegenprobe CSV gegen ODS (`vergleiche_ueberlappung`),
  Rekonstruktion der kumulativen Kanäle. Die Ableitung der fehlenden
  Spreizungsspalte bleibt erhalten und greift jetzt auch in der
  Gegenprobe.
- `src/load_begehungen.py`: `meter_to_address()`,
  `begehung_dates_by_meter()`, Begehungstabelle wird per Glob gefunden
  (Klammerstil `(45)` / `[45]`); ohne Rohdaten bleibt der Import möglich.

### Hinzugefügt (Empfehlungsschicht & Fehlerrangliste, 2026-10-03)

- **`src/freitext.py`:** neues Modul zur regelbasierten Kodierung der 57
  Begehungs-Freitexte in acht Fehlerkategorien plus „kein Fehlerhinweis im
  Text". Schlüsselwort- und Ausschlusslisten liegen offen im Code,
  Verneinungen werden über ein Zeichenfenster vor dem Treffer geprüft,
  `pruefblatt` weist je Zeile die auslösenden Wörter aus.
- **`src/empfehlung.py`:** Schicht von der Anomalie zur priorisierten
  Handlungsempfehlung. Löst das Restkategorie-Problem durch gewichtete
  Evidenzsummen auf dem auffälligen Pool (nur eine von 28 Stationen bleibt
  ohne Muster), normiert Kennzahlen über Ränge gegen Ausreißer, berechnet
  den Schweregrad transparent aus Temperaturabweichung, Persistenz und
  Effizienzverlust und liefert einen adressfreien Export.
- **`tests/`:** 22 neue Tests in `test_freitext.py` und `test_empfehlung.py`,
  ohne Netz und ohne Rohdaten lauffähig.
- **`notebooks/11_empfehlung.ipynb`:** neues Notebook mit vollständigem
  Durchlauf von den Detektorscores zum adressfreien Export. 28 auffällige
  Stationen werden priorisiert, Monteurs-Rangliste (Texte) und
  Messdaten-Rangliste werden gegenübergestellt, ein erklärbarer Baum mit
  `flow_median` als Wurzel wird gefittet und validiert.
- **`docs/empfehlung.md`:** ausführliche Dokumentation des Verfahrens, des
  Musterkatalogs und der Nutzenbilanz.
- **`docs/negativbefunde.md`:** eigenständige Dokumentation aller
  methodischen Negativbefunde (Supervised ML, Stationsprofil-Clustering,
  Leistungsklassen, nicht bestandene Detektoren) für die Abgabe.

### Hinzugefügt (Label-freie Anomaliedetektion, 2026-10-02)

- **`src/dynamik.py`:** neues Modul für die vom Betreuer verlangten
  Dynamikkennzahlen des Rücklaufs. Erste und zweite Ableitung werden am
  Stundenraster gebildet, Ableitungen über eine Datenlücke hinweg werden
  verworfen statt interpoliert, dazu kommen die Reaktionszeit auf
  Lastwechsel und ein Tagesaggregat je Station.
- **`src/tagespanel.py`:** Panel Station × Tag als gemeinsame Grundlage
  aller Detektoren. Es vereint Tagesmittel und Tagessummen der Messkanäle,
  den Zeitanteil je Betriebszustand aus dem Stundenclustering, die
  Dynamikkennzahlen sowie Außentemperatur und Heizgradstunden. 103 643
  Stationstage über 100 Zähler; `panelbilanz` weist aus, wie viele davon je
  Baustein belegt sind.
- **`src/anomalie.py`:** Anomaliedetektion ohne Labels. Zwei Erwartungs-
  wertmodelle für den Rücklauf (netzweit und stationseigen), Isolation
  Forest auf dem Tagespanel, Zustandsanteils- und Dynamikscore, ein
  Persistenzfilter über ein Laufzeitfenster, Stationsscores, die
  Übereinstimmung der Detektoren über Spearman und Jaccard, benennbare
  Muster je Station sowie die Validierung über die Begehungen und der
  Effizienzvergleich in kWh je Heizgradstunde.
- **`src/regelkalibrierung.py`:** leitet die acht Schwellen der Regel-
  Baseline aus den Quantilen der echten Feature-Verteilungen ab und stellt
  Trefferquoten und Labelverteilung vorher gegen nachher.
- **`src/fault_detection.py`:** die bisher fest verdrahteten Schwellen
  liegen jetzt im Dict `SCHWELLEN` und lassen sich je Aufruf überschreiben.
  Das Defaultverhalten ist unverändert und durch einen Regressionstest
  abgesichert.
- **`tests/`:** 43 neue Tests in `test_dynamik.py`, `test_tagespanel.py`,
  `test_anomalie.py` und `test_regelkalibrierung.py`, ohne Netz und ohne
  Rohdaten lauffähig.
- **`notebooks/10_anomalie.ipynb`:** neues Notebook mit fünf Detektoren im
  direkten Vergleich. Validiert wird nicht gegen Labels, sondern gegen die
  Begehungen: ein brauchbarer Score muss nach einer Begehung stärker
  fallen als bei den 49 Kontrollzählern im selben Zeitraum. Diese Prüfung
  bestehen nur die beiden Erwartungswertmodelle — Netzresiduum gepaart
  −1,17 (p = 0,042) und im Diff-in-Diff −1,42 (p = 0,016), Stationsresiduum
  gepaart −0,99 (p = 0,167) und im Diff-in-Diff −1,47 (p = 0,037).
- **Negativbefunde:** Isolation Forest (Diff-in-Diff p = 0,252),
  Zustandsanteil (p = 0,707) und Dynamikscore (p = 0,228) bestehen die
  Begehungsvalidierung nicht und gehören damit nicht in die Abgabe. Der
  Dynamikscore dreht zusätzlich beim Effizienzvergleich das Vorzeichen,
  das oberste Quintil liegt bei 0,171 gegen 0,291 kWh je Heizgradstunde
  (p = 0,003) — er findet Stationen mit ruhigem Rücklauf, nicht mit
  auffälligem. Die Gegenprobe auf den Rohgrößen zeigt außerdem, dass der
  Effekt am Median des Rücklaufs hängt (Diff-in-Diff −1,47, p = 0,010) und
  nicht am Mittel unter Last (p = 0,334).
- **Übereinstimmung der Detektoren:** Netzresiduum und Zustandsanteil
  laufen mit Spearman 0,67 weitgehend parallel, Netz- und Stationsresiduum
  dagegen nur mit 0,10 — die beiden bestandenen Detektoren messen
  Verschiedenes und ersetzen einander nicht. Der Dynamikscore korreliert
  zu allen anderen negativ.
- **Persistenz:** bei einem Fenster von 14 Tagen sinkt die Trefferliste
  von 44 Stationen bei einem geforderten Tag auf 23 bei vierzehn. Am Ende
  bleiben 21 von 100 Stationen über der Marke von 10 % persistenten Tagen,
  darunter der bekannte Fall 68956351 mit dem drei Jahre offenen Ventil.
- **Nachkalibrierung der Regel-Baseline:** die beiden kaputten Regeln
  kommen in den Arbeitsbereich, `flow_short_cycle_power` von 0,908 auf
  0,153 und `peak_load_share` von 0,000 auf 0,153. Die Labelverteilung
  kippt von 47 Stationen `control_hysteresis` auf 42 `healthy`, und
  `oversized_contract` und `low_spreading` vergeben überhaupt erst Labels.
- **`docs/anomaliedetektion.md`:** vollständige Ergebnisdoku samt eigenem
  Abschnitt zu den Wegen, die nicht getragen haben.

### Hinzugefügt (Validierung der Stundencluster, 2026-10-02)

- **`src/clustervalidierung.py`:** neues Modul für die Validierung des
  Stundenclusterbefunds aus Notebook 05. Baut das Stundenpanel über alle
  Zähler auf (Leistung und Volumenstrom auf das stationseigene 95.
  Perzentil normiert, Ausschlüsse als Bilanz statt als stiller Filter),
  reichert es um Außentemperatur, Saisonsegment, Monat und Tagesstunde an
  und liefert Bootstrap-ARI nach dem Muster aus Notebook 04, Zentroid-
  profile samt Zuordnung zwischen zwei Läufen, Cramérs V und einen flachen
  Entscheidungsbaum als Kontrollrechnung, Redundanzabbau über die
  Korrelationsmatrix, drei Gewichtungsvarianten und die Leistungsklassen
  aus dem Anschlusswert.
- **`tests/test_clustervalidierung.py`:** 33 Tests, ohne Netz und ohne
  Rohdaten lauffähig (synthetische Exporte im tmp-Verzeichnis).
- **`notebooks/09_clustervalidierung.ipynb`:** neues Notebook. Die
  Saisonhypothese ist widerlegt — ein flacher Baum auf der Außentemperatur
  allein erreicht 0,371 gegen eine Trivialrate von 0,248, derselbe Baum auf
  den Clusterfeatures 0,919; die Witterung holt damit rund 18 % des
  erreichbaren Abstands. Cramérs V liegt bei 0,311 für das Saisonsegment
  und bei 0,099 für die Tagesstunde, ein Tag-Nacht-Artefakt scheidet
  ebenfalls aus. Der diagnostisch interessante Zustand (hoher Durchfluss,
  Spreizung unter 5 K, Rücklauf über 70 °C) verteilt sich mit einem Lift um
  1,0 gleichmäßig über alle vier Saisonsegmente. Bootstrap-ARI bei k=5
  **0,866**. Die Kernwinter-Gegenprobe hält nur teilweise: Silhouette 0,289
  statt 0,397, ARI 0,573, und der Kurzschlussverdacht bildet erst ab k=7
  wieder ein eigenes Cluster. Der Ground-Truth-Join trennt nicht (56
  Stationen, Basisrate 77 %, kein p-Wert unter 0,05).
- **Betreuerkritik zur Gleichgewichtung abgearbeitet:** sieben Featurepaare
  korrelieren mit einem Betrag über 0,8, die Größenachse zählt in der
  ungewichteten Distanz mehrfach. Der Redundanzabbau hebt die Silhouette
  auf Stationsebene bei k=3 von 0,281 auf 0,309 bei praktisch gleicher
  Stabilität, die PCA auf 90 % Varianz kommt auf 0,315, liefert aber exakt
  dieselbe Partition und kostet nur die Erklärbarkeit. Empfohlen wird die
  redundanzbereinigte Auswahl; Schwelle und Priorisierung bleiben offene
  Teamentscheidungen.
- **Negativbefund Leistungsklassen:** die im Meeting gewünschte Trennung
  nach Anschlusswert bringt nichts. Auf Stundenebene entstehen in jeder
  Klasse dieselben fünf Zustände bei einer Silhouette um 0,40, weil die
  Normierung auf das stationseigene Perzentil die Objektgröße bereits
  entfernt; auf Stationsebene verschlechtert die Trennung die Ergebnisse,
  weil die Klassen mit 52 und 32 Stationen zu klein sind. Die Klasse bis
  5 kW enthält auf diesen Daten genau eine Station. Der BHKW-Ausschluss
  (Zähler 86792512) wird fachlich begründet, nicht über eine
  Kennzahlverbesserung.
- **`docs/pipeline.md`:** Notebook-Index, Modultabelle, CLI-Liste und
  Smoke-Test-Abschnitt ergänzt (170 Tests grün).

### Geändert (Ablageort der offenen Entscheidungen, 2026-10-02)

- Die Notizdatei mit den offenen Entscheidungen liegt nicht mehr unter
  `docs/`, sondern lokal außerhalb des versionierten Baums. Die Verweise
  darauf wurden aus `.gitignore`, `docs/README.md`, `src/season.py`,
  `src/weather.py`, `src/jahresvergleich.py`, den Notebooks 06 bis 08 und
  den Agenten- und Skill-Dateien entfernt statt umgebogen.

### Hinzugefügt (Vierfeldertafel Zustand vor/nach der Begehung, 2026-09-24)

- **`notebooks/03_wirkungsanalyse_begehungen.ipynb`:** neuer Abschnitt 3b
  beantwortet die Meeting-Frage „Was, wenn der Zustand vor und nach der
  Begehung schlecht war?" — klassifiziert jedes 21-Tage-Fenster über die
  bereits etablierte Rücklauf-Schwelle (RT > 50 °C = schlechte Auskühlung,
  dieselbe wie im Dashboard und in `rt_above_50_share_loaded`) als
  `gut`/`schlecht` und kreuztabelliert Vorher- gegen Nachher-Zustand.
  Ergebnis (n=42 auswertbare Begehungen): 62 % gut→gut, **26 %
  schlecht→schlecht** (Begehung ohne messbare Wirkung — der wertvollste
  Befund, da er Kandidaten für eine zweite Begehung oder eine falsch
  attribuierte Ursache markiert), 10 % schlecht→gut, 2 % gut→schlecht.
  Notebook komplett neu ausgeführt (vorher ohne gespeicherte Outputs im
  Repo); dabei aufgefallen und korrigiert: die Zusammenfassung nannte
  „4 von 5" bestätigte Heizzeit-Änderungen, der aktuelle Lauf zeigt 4 von
  4 — Zahl in der Zusammenfassungstabelle angepasst.
- **`docs/pipeline.md`:** Notebook-Index-Eintrag für 03 um die
  Vierfeldertafel und den 26-%-Befund ergänzt.

### Hinzugefügt (Begehungszeitpunkt als Feature gegen Leakage, 2026-09-24)

- **`src/window_features.py`:** `windowed_features_for_meter()` bekommt
  neuen optionalen Parameter `begehungen` (Liste von Zeitpunkten). Zwei
  neue Meta-Spalten je Zustandsfenster: `begehung` (bool — Begehung fällt
  in dieses Fenster) und `days_since_begehung` (signierter Abstand in
  Tagen von der Fenstermitte zur nächstgelegenen Begehung; negativ =
  Fenster liegt davor, positiv = danach; `NaN` ohne übergebene
  Begehungen). Ohne `begehungen`-Argument unverändertes Verhalten.
  Grund: Ohne dieses Flag landen Vorher/Nachher-Zustände eines Fensters,
  das eine Begehung überspannt, unmarkiert im selben Cluster-Input — die
  geplante Wirkungsanalyse (Vierfeldertafel, nächster Schritt) und jedes
  künftige Clustering brauchen die Möglichkeit, solche Fenster gezielt
  auszuschließen oder getrennt auszuwerten. Neue Tests
  `test_begehung_flag_and_days_since`,
  `test_no_begehungen_leaves_days_since_nan`.
- **`src/load_begehungen.py`:** neue Funktion `begehung_dates_by_meter()`
  — Zählernummer → sortierte Liste ihrer Begehungstermine, direkt als
  `begehungen`-Argument für `windowed_features_for_meter()` verwendbar.
- **Bugfix `src/load_begehungen.py`:** `BEGEHUNGEN_XLSX` war auf den
  Dateinamen mit runden Klammern `...FW(45).xlsx` hartkodiert; die
  Datei in `data/raw` liegt aber mit eckigen Klammern
  (`...FW[45].xlsx`) vor, wodurch `load_begehungen()` und alles, was
  darauf aufbaut (`begehungen_mit_zaehler`, jetzt auch
  `begehung_dates_by_meter`), mit `FileNotFoundError` abbrach. Behoben
  durch denselben Glob-Ansatz, den `load_data.load_inspections()` schon
  nutzt (`*Ergebnis_Optimierung_FW*.xlsx`), damit künftige
  Klammer-Varianten in neuen Datenlieferungen nicht erneut brechen.

### Geändert (Zuordnung.xlsx statt Nodes_Edges.ods für die Adresse 2026-09-24)

- **`src/load_begehungen.py`:** neue Funktion `meter_to_address()` —
  invertiert `load_zuordnung()` zu Zählernummer → jüngste bekannte
  Adresse (102 von 102 Zählern in Zuordnung.xlsx, gegenüber 99 in
  Nodes_Edges.ods).
- **`src/features.py`:** `features_for_directory()` bekommt neuen
  optionalen Parameter `address_map`. Wenn gesetzt, hat er Vorrang vor
  `nodes_df`'s `Straße`-Spalte für die `address`-Spalte; `nodes_df`
  bleibt die einzige Quelle für `anschlusswert_kw` (Zuordnung.xlsx führt
  keinen Anschlusswert). Rückwärtskompatibel: ohne `address_map`
  unverändertes Verhalten. Neuer Regressionstest
  `test_address_map_takes_priority_over_nodes_df`.
- **`src/detect_real.py` / `src/ml_classifier.py`:** `join_ground_truth()`
  nimmt jetzt ebenfalls `address_map` entgegen und nutzt ihn für den
  Begehungs-Join; beide Aufrufer geben `meter_to_address(load_zuordnung())`
  mit.
- **`notebooks/00_eda_hast_stationsprofile.ipynb`:** die dort dupliziert
  vorliegende Feature-Schleife (nicht `src/features.py`) nutzt jetzt
  ebenfalls `Zuordnung.xlsx` zuerst für `address`; neu ausgeführt.
  Ergebnis: `address` fehlt nur noch bei 12 von 100 Stationen (vorher an
  `anschlusswert_kw` gekoppelt, 15/100). `anschlusswert_kw` bleibt bei
  15/100 fehlend — dafür gibt es keine zweite Quelle.
- **Downstream neu gerechnet:** `notebooks/01_kmeans_stationscluster.ipynb`
  und `notebooks/04_clustering_benchmark.ipynb` (Clustering-Zahlen
  Silhouette/ARI/Clustergrößen **unverändert** — die Adresse fließt
  nicht ins Clustering ein). Der Begehungs-Join ändert sich leicht:
  56 statt 55 Stationen im GT-Join (Basisrate 77 % statt 80 %,
  Fisher p ≥ 0,51/MWU p ≥ 0,08 statt ≥ 0,47/≥ 0,19) — Kernbefund
  „Ground Truth trennt nichts" bleibt unverändert. Ursache der
  Verschiebung: Station 80912177 hat in Zuordnung.xlsx über die Jahre
  zwei verschiedene Hausnummern (die jüngere gewinnt und trifft die
  Begehungsadresse nicht mehr), zwei andere Stationen sind neu
  hinzugekommen. Dokumentiert statt verschwiegen, wie in den
  Projektkonventionen gefordert.
- **`docs/echte-daten-integration.md` / `docs/ml-klassifikator.md`**
  neu generiert (`python -m src.detect_real` / `python -m
  src.ml_classifier`): Basisrate 82 % → 80 % (40/9 → 39/10 Stationen im
  ML-Klassifikator-Sample), Negativbefund und Schlussfolgerung
  unverändert.

### Behoben (Notebook-Namenskollision 2026-09-23)

- Zwei Notebooks hießen beide `04_*`: das eigene
  `04_clustering_benchmark.ipynb` (Stationsprofile, Methodenvergleich)
  und Paulines direkt auf `main` hinzugefügtes
  `04_kmeans_operatingConditions.ipynb` (stundenweises K-Means, k=5,
  fachlich interpretierbare Betriebszustände). Letzteres umbenannt zu
  `05_kmeans_stundenweise_betriebszustaende.ipynb`, da es methodisch
  eine neue Auflösungsstufe (Einzelstunde statt Stationsprofil)
  einführt und inhaltlich dort ansetzt, wo der Benchmark aufhört
  („nächster Hebel ist die zeitliche Auflösung").
- Neuer Abschnitt „Notebooks" in `docs/pipeline.md`: fortlaufender
  Index aller sechs nummerierten Notebooks mit Ansatz und Kernbefund,
  damit künftige Nummerierungskollisionen (z. B. bei parallelen
  Branches) leichter vermieden werden.
- `docs/naechste-schritte.md`-Bereinigung nachgeholt: Der vorherige Fix
  (Commit `a9bae6a` auf `analyse/unsupervised-learning`) war nicht Teil
  von PR #6 — auf `main` wurde die Datei nur manuell gelöscht, aber
  `.gitignore`-Eintrag und alle Verweise (`docs/README.md`,
  `docs/datensichtung.md`, `src/profile_timeseries.py`, `mkdocs.yml`,
  Agent- und Skill-Dateien) fehlten noch. Jetzt vollständig nachgezogen.
- `.github/agents/hast-clusteranalyse.agent.md`: Roadmap-Punkt 3 um
  Paulines Ergebnis ergänzt (offene Fragen: Stabilität, Ground-Truth-
  Join, Jahreszeiten- vs. Betriebszustand-Trennung).

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
