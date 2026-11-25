# Negativbefunde

Hier stehen die Ansätze, die nicht getragen haben. Sie sind methodische Ergebnisse und gehören zur Abgabe: Sie zeigen, wo die Daten an Grenzen stoßen und welche Wege sich nicht lohnen. Notebooks sind mit ihrer Nummer im Abgabestand genannt, die Zahlen stammen aus den Notebooks oder aus dem [Modellvergleich](../vergleich/modellvergleich.md).

## 1 Überwachtes Lernen auf Begehungslabels

- Probiert: Klassifikator auf dem Label „Maßnahme ja/nein“ aus der Begehungstabelle, Code in `src/ml_classifier.py`. Läuft nur über die Befehlszeile (siehe [Pipeline](../installation/pipeline.md)), nicht in einem Notebook.
- Ergebnis: Balanced Accuracy 0,33 bzw. 0,42 gegen 0,50 für die triviale Vorhersage (Notebook 16).
- Das Label ist bei 40 von 49 Stationen wahr, es bleiben 9 Negative (Notebook 25 und 29). Notebook 38 nennt dazu Label-Leakage.
- Das Label ist zu grob: „Maßnahme“ sagt nicht, welcher Fehler vorlag.
- In Notebook 29 trägt erst ein Label je Fehlerart. Nötig wären mehr Begehungen mit ausdrücklichem „kein Befund“.

## 2 Labelqualität der Begehungstabelle

- Zähler 68956351: Ventil drei Jahre offen (500 bis 950 l/h), am 09.09.2024 geschlossen, danach Durchfluss von 499 auf 0 l/h. In der Begehungstabelle steht `n_actions = 0`, die Reparatur steht nur im Freitext (Notebook 02, 13).
- Das Label `n_actions > 0` ist bei 76 % der Stationen wahr (Notebook 02). Es trennt kaum.
- Notebook 03: Das Label taugt nur als Detektor für Dauerzustände, die Stichwortsuche im Freitext besteht die Prüfung nicht.
- Notebook 14: 6 von 66 Begehungen mit Fehler ohne Sollwertänderung, 57 Notizen.
- Notebook 25: „leer heißt nein“ ist eine Annahme, ausdrücklich „nein“ steht nur 4- bis 8-mal da.
- Nötig wäre ein festes Protokollfeld für Befund und Reparatur, auch wenn nichts gefunden wurde.

## 3 Regel-Baseline mit festen Schwellen

- Probiert: feste Regeln aus `src/fault_detection.py`, kalibriert in Notebook 16 (Abschnitt 12 und 13).
- Mit den alten Schwellen trifft `flow_short_cycle_power` 83 von 93 Stationen (89 %), `rt_above_50_share_loaded` 56 von 93. `peak_load_share` für `oversized_contract` trifft keine von 85.
- Alte Labelverteilung: 44 von 93 Stationen `control_hysteresis`, kein `healthy`. Nach der Kalibrierung auf rund 15 % je Regel: 38 `healthy` und sechs Fehlerbilder. Das Notebook nennt das „bewertbar, nicht richtig“.
- Im Modellvergleich liegt `oversized_contract` bei AUC 0,51. Ein Grund: Der Anschlusswert ist oft schon der neue Vertrag.
- Für `control_hysteresis` gibt es kein Befund-Label, die Regel ist nicht prüfbar.
- Zum Vergleich tragen andere Regeln: `continuous_flow` 0,85 und `excess_rt` 0,84 beim Ventil (siehe [Modellvergleich](../vergleich/modellvergleich.md)).

## 4 Stationsclustering

- Probiert: K-Means, Ward, GMM und HDBSCAN auf Stationsmerkmalen (Notebook 07, 08).
- Notebook 07: 93 Stationen, k=2 mit 62 und 31 Stationen, Silhouette 0,237. Früher mit BHKW 97 zu 3 bei 0,599, das war ein Effekt des Stationstyps.
- Notebook 08: Ab k=3 liegen alle Silhouetten unter 0,25. HDBSCAN liefert ab Mindestgröße 5 nur Rauschen, bei 3 bleibt rund die Hälfte ohne Cluster.
- Die Verfahren stimmen kaum überein (paarweiser ARI 0,35 bis 0,48), einig sind sie nur bei den Ausreißern 58202380 und 66761022. Das BHKW 86792512, früher der dritte Ausreißer, ist seit Notebook 00 ausgeschlossen.
- Gegen die Begehungen trennt kein Cluster: Fisher p ≥ 0,33, Mann-Whitney p ≥ 0,08, Basisrate 77 %. Die Daten sind konsistent mit einem Kontinuum statt mit Gruppen.
- Notebook 07 und 08 bilden Profile über die ganze Historie und haben damit ein Datenleck. Das Cluster „schlechter“ aus Notebook 26 erreicht AUC 0,67 und ist belegt schlechter als die Sommernacht-Regel (siehe [Modellvergleich](../vergleich/modellvergleich.md)).

## 5 Clustering je Leistungsklasse

- Probiert in Notebook 09: Redundanz abbauen, BHKW ausschließen, getrennt nach Leistungsklasse clustern.
- Der Redundanzabbau hebt die Silhouette bei k=3 nur von 0,261 auf 0,272.
- Je Leistungsklasse sinkt die Silhouette auf 0,154 bis 0,255 gegen 0,308 gepoolt. Nutzbar sind nur zwei Klassen plus die Gruppe ohne Anschlusswert.
- Auf Stundenebene ändern Klassen und BHKW-Ausschluss die fünf Zustände kaum. Die Stundenebene selbst trägt (k=5, Silhouette 0,399, ARI 0,851).
- Ground-Truth-Join ohne p < 0,05, bei 13 Stationen ohne Maßnahme erwartbar.
- Folge: Leistungsklasse nur als Kontext, nicht als Trennlinie.

## 6 Begehungswirkung im Diff-in-Diff

- Probiert in Notebook 02: 21-Tage-Fenster vor und nach der Begehung, 37 nie begangene Stationen als Kontrolle. Auswertbar sind 44 von 58 Begehungen.
- Der DiD fällt mit der Zahl der Maßnahmen: +6,95, +3,10, −1,56 und −3,05 K je Kategorie. Die Reihenfolge passt, signifikant ist es nicht (Wilcoxon p = 0,25 bei „mittlere“ mit n = 24, p = 0,19 bei „viele“ mit n = 13).
- Vierfeldertafel: 11 von 44 Begehungen bleiben schlecht.
- Andere Notebooks finden einen Effekt: Wintervergleich DiD −2,0 K, p ≈ 0,008 bei 45 Begehungen (Notebook 04), Abkühlung +2,2 kWh/m³ bei p = 0,046 mit 24 Fällen (Notebook 20).
- Gegen 29 Kontrollstationen in Notebook 19 Teil B dagegen p 0,30 bis 0,92. Die Wirkung hängt damit an Fenster und Kontrollgruppe.
- In Notebook 26 ist die Wirkung wegen Regression zur Mitte nicht nachweisbar. Nötig wären längere Fenster nach der Begehung und eine zufällig gezogene Kontrollgruppe.

## 7 Vorjahresvergleich über ein langes Fenster

- Probiert in Notebook 04: ein volles Jahr vor gegen nach der Begehung.
- Ein volles Jahr danach gibt es nur für 2 von 58 Begehungen. Die meisten Zähler enden am 11.07.2025, die früheste Begehung war am 26.08.2024, also höchstens 319 Tage.
- Mit 270 Tagen und Vorjahresversatz bleiben 27 auswertbare Begehungen, aber der halbe Sommer liegt im Fenster.
- Ersetzt durch den Vergleich gleicher Kernwinter (Dezember bis Februar). Für ein Jahresfenster fehlen Daten nach Juli 2025.

## 8 Flachere Kennlinie nach Optimierung

- Probiert in Notebook 05: die ÜZ-Folie nachrechnen, Energie je m³ gegen Außentemperatur, optimiert gegen nicht optimiert.
- Der Abstand zeigt in dieselbe Richtung, ist aber kleiner und nicht von null unterscheidbar: +1,3 kWh/m³ (p ≈ 0,13) bzw. +1,2 kWh/m³ (p ≈ 0,21).
- Die flachere Steigung auch nicht: Unterschied +0,08 (p ≈ 0,26) bzw. +0,14 (p ≈ 0,16) gegen 0,165 auf der Folie. Mit Gewichtung wird sie kleiner.
- „Optimiert“ ist im Mittel 2,7 K bzw. 2,3 K kälter. Das verzerrt die Steigungen.
- Es gibt keine Kontrollgruppe, der Vergleich bleibt beschreibend.

## 9 ARIMA als Zeitreihenmodell

- Probiert in Notebook 06 mit `src/zeitreihenmodell.py`: Prognose des Tagesrücklaufs 14 Tage voraus, 87 Zähler, 1.695 Fenster.
- Reines ARIMA ist schlechter als naiv: ARIMA(1,1,0) 2,79 °C, 7-Tage-Mittel 2,66 °C mittlerer Fehler.
- Am besten ist `arx_100` mit 2,11 °C. Der Gewinn kommt aus der Außentemperatur: Der AR-Term bringt gegenüber der reinen Kennlinie nur 0,02 °C, der Wochenterm nichts.
- Als Wächter: 16 von 40 Begehungen außerhalb z = ±2 (40 % gegen 19 % Placebo, p = 0,002). Im typischen Fall kein Unterschied (Median −0,55 gegen −0,24 °C, p = 0,23). 13 Begehungen sind nicht auswertbar.
- Im Wächtervergleich 22 von 43 bei p = 0,016, nach Holm 0,16 (siehe [Modellvergleich](../vergleich/modellvergleich.md)).

## 10 Modulationsart und Kennlinienparameter als Erfolgsmaß

- Probiert in Notebook 11 und 12: Ändert sich die Regelart oder die Kennlinie durch die Begehung?
- Modulationsart unverändert: p = 0,70 (Stunde) und 0,34 (Tag).
- Steigung (p = 0,67) und Bestimmtheitsmaß (p = 0,76) der Kennlinie ändern sich ebenfalls nicht. Ausnahme ist 68956351 mit einem Sprung der Steigung von −0,058 auf 1,276.
- Dauerlinien zeigen nur eine schwache, nicht gesicherte Veränderung: Rücklauf über 50 °C −1,4 Prozentpunkte (n = 47, p = 0,096), Tagesperformance +0,73 kWh/m³ (n = 45, p = 0,069).
- Ohne Kontrollgruppe nur konsistent mit einer Wirkung der Begehung. Mehr dazu in [Stationsbilder](../stationsbilder/index.md).

## 11 Anomaliedetektoren

- Probiert in Notebook 16: Isolation Forest, Zustandsanteil, Dynamikscore, Netz- und Stationsresiduum. Prüfung an 43 Begehungen (Isolation Forest 42) gegen 42 Kontrollzähler.
- Nicht bestanden: Isolation Forest (+0,001, p = 0,62), Zustandsanteil (Median 0, p = 0,76), Dynamikscore (+0,02, p = 0,89).
- Der Dynamikscore ordnet sogar umgekehrt (0,19 gegen 0,31 kWh/Kh, p < 0,001). Die zweite Ableitung bei 0,1 K Auflösung ist wohl Quantisierungsrauschen.
- Die Residuen bestehen (DiD −1,34, p = 0,017 bzw. −0,86, p = 0,041). Der Median des Rücklaufs allein liefert aber dasselbe (−1,74 K, p = 0,009). Das Netzmodell erklärt nur R² = 0,035.
- Als Alarm treffen die Detektoren 6 bis 18 von 43 Begehungen, p ≥ 0,07, nach Holm ≥ 0,57 (siehe [Modellvergleich](../vergleich/modellvergleich.md)).

## 12 Restkategorie in der Musterzuordnung

- Probiert in Notebook 17: Muster je Station aus Median und MAD, danach Empfehlung.
- Erste Fassung: 50 von 93 Stationen ohne eindeutiges Muster. Von 26 dauerhaft auffälligen blieben 19 ohne verwertbare Diagnose.
- Ursache: Ein oberes Quintil trifft rund 19 von 93 Stationen, zwei unabhängige Bedingungen zusammen im Mittel knapp 4. Der Volumenstrom (Median 38 l/h, Maximum rund 14.500 l/h) liefert mit MAD extreme z-Werte.
- Mit Rängen statt MAD haben alle 26 ein Muster. Die Restkategorie war ein Konstruktionsfehler.
- Offen bleibt: 68956351 wird als Kurzschluss statt Ventil eingeordnet.

## 13 Kennlinienmonitor

- Probiert in Notebook 13 mit `src/kennlinien_monitor.py`: Sprünge in der stationseigenen Kennlinie.
- Gegen alle Begehungen nur 25 bis 34 % über Zufall: Parameterkanal 25 von 53 (p = 0,10), Residuenkanal 21 von 53 (p = 0,077).
- Der stärkste Alarm je Station trifft schlechter als Zufall (Parameterkanal 4 von 53).
- Bei mechanischen Eingriffen trifft der Residuenkanal 10 von 19 (0,526 gegen 0,296, p = 0,030, Notebook 14). Diese Teilung wurde aber erst nach dem Nullergebnis gewählt.
- Im Wächtervergleich 27 von 43 gegen 53 % Kontrolle, p = 0,14, nach Holm 0,94.
- Nötig wären hergeleitete Schwellen und dokumentierte Zählertausche.

## 14 CUSUM als Frühwarnung

- Probiert in Notebook 20 und 21: CUSUM auf Abkühlung und Wassermenge, Treffer um die Begehung und im halben Jahr davor.
- Der Hebel von rund 2 kommt fast ganz aus Alarmen Richtung besser (25 von 43, Hebel 2,7, p < 0,001), also nach der Begehung.
- Verschlechterungsalarme sind um die Begehung nicht häufiger als bei Kontrollen (15 von 43, Hebel 1,04, p = 0,49). In den 180 Tagen davor auch nicht (11 von 32, Hebel 0,98).
- Der Ventilfall 68956351 wurde nie als Fehler gemeldet, weil das offene Ventil im Lernjahr als normal gilt. Der Alarm „besser“ kam 2 Tage nach der Reparatur.
- Für die Priorität fehlen Labels: 50 Stationswinter mit Begehung danach, davon 3 im Netz auffällig.
- Der CUSUM taugt zur Erfolgskontrolle, nicht zur Frühwarnung. Nötig wäre ein vorab geplanter Test mit zufällig gezogenen Stationen.

## 15 Nachbarn und Netzereignisse

- Probiert in Notebook 23 und 24: Häufen sich auffällige Stationen im Leitungsnetz? Alarmieren Nachbarn gemeinsam?
- Keine Häufung: in keinem Winter und bei keiner Weite mehr auffällige Paare als zufällig (p 0,39 bis 1).
- Verschlechterungen beginnen bei Nachbarn im Leitungsgraphen nicht häufiger gemeinsam (p 0,21 bis 0,48). Gemeinsame Verbesserungen sind etwas häufiger (p 0,018 bis 0,035), passen aber zu gemeinsamen Begehungsterminen.
- Über Koordinaten: Bei 50 m hängen die Scores leicht zusammen (rho 0,32, 0,11 und 0,15), bei 100 m nicht mehr. Gleichzeitige Verschlechterungen sind in allen drei Radien etwas häufiger (p 0,01 bis 0,04). Das passt eher zu ähnlichen Gebäuden, geprüft ist es nicht.
- Die netzweite Welle von Verschlechterungen im Dezember 2022 folgt einem Kälteeinbruch. Das ist ein Hinweis auf die Kennlinie, nicht auf Hausfehler.
- Der Graph ist logisch, nicht hydraulisch. 8 Stationen haben keine Nachbarn mit Zähler. Nötig wären das hydraulische Netzmodell der ÜZ oder Differenzdruckmessungen.

## 16 Graphenmodell auf dem Netz

- Probiert in Notebook 39: Entwurf eines GraphSAGE in numpy, Ablation gegen ein MLP ohne Netz.
- Beitrag des Netzes an 59 Stationen: +0,010 (Abkühlung) und −0,009 (Wassermenge).
- Je Station (58) nicht signifikant: Wilcoxon p = 0,172 bzw. 0,423 bei Schwelle 0,025.
- Im Ventilfall ist das GNN schlechter (Fehler 0,77 gegen 0,53 bei der Abkühlung). Der eigene Vorlauf ist kein unabhängiges Signal.
- Im Modellvergleich ist „Netzmedian abziehen“ mit 25 von 43 belegt schlechter, Nachbar-Merkmale bringen beim Ventil +0,004.
- Nötig wären Rohrdaten (Durchmesser, Länge), Lage der Heizzentrale, Bedeutung der Kantenrichtung und ein hydraulisches Modell.
- Ausführlich unter [GNN: Hilft das Netz?](gnn.md).

## 17 Geocoding und Netzgeometrie

- Probiert: Positionen der Stationen über Nominatim. Es fand meist nur die Straße und ist nur noch optional (Notebook 24, 31).
- Positionen kommen jetzt aus einer Handliste mit 101 Einträgen, die nicht im Repository liegt.
- Notebook 31: 93 von 100 Adressen einem Rohrende zugeordnet (höchstens 40 m), 7 ohne. Im Netz verankert sind 93 von 110 Knoten.
- Notebook 32: Anschlussabstand im Median 6 m, höchstens 36 m (109 Häuser).
- Notebook 39: 35 von 110 Kanten ohne Rohrweg, 18 Einträge ohne Position, die Kantenrichtung passt zu keiner Quelle.
- Nötig wären Koordinaten der Hausanschlüsse aus dem GIS der ÜZ.

## 18 Wächtervergleich

- Probiert in Notebook 30 und 34: 15 Wächter am selben Maßstab, 43 Begehungen, Holm-Korrektur.
- Nach Holm bleibt nur Kennlinie mit CUSUM belegt (Tagesmonitor 33 von 43, Holm 0,017). „Ohne Netzereignisse“ ist dieselbe Kennlinie.
- Normalverhaltensmodell 30 von 43, Holm 0,08. LSTM mit CUSUM Holm 0,20.
- Prognose-LSTM mit Schwelle: 16 von 43 gegen 32 %, p = 0,26. Gegen das Normalverhaltensmodell McNemar 15 zu 1, p = 0,001.
- Notebook 28 sieht schon auf den ersten Blick keinen Vorsprung: Alarm in den 14 Tagen nach der Begehung bei 11 bis 17 % der begangenen Stationen, bei nie begangenen 13 %.
- An warmen Tagen bleibt das Prognose-LSTM im Dashboard trotzdem der Wächter, weil die Kennlinie dort nicht rechnet. Dort ist es nur an eingebauten Fehlern geprüft: Dauerdurchfluss 150 l/h zu 78 % bei höchstens 5 % Fehlalarmen, das Wochenmittel zu 45 % (Notebook 35, Test B).
- Details in [Modellvergleich](../vergleich/modellvergleich.md).

## 19 Fehlerarten ohne Messspur

- Probiert in Notebook 29 und 38: je Fehlerart ein Modell, dazu ein Bayes-Ansatz.
- Filter, Durchfluss und Temperatur sind nicht erkennbar (AUC 0,24 bis 0,64).
- Random Forest und XGBoost sind nicht besser als logistische Regression oder Regel. Wechselwirkungen bringen −0,03 bis +0,05, Klassengewichtung nichts.
- Regler und Einstellung ohne Spur: AUC 0,57, Top-1 0,46 gegen 0,64 für „immer Regler“. Befund ja/nein AUC 0,55, p = 0,34.
- Dämmung ist ein Artefakt der Matrix: 12-mal Hauptursache, 2 Treffer. Den Bayes-Ansatz beschreibt [Bayes-Diagnose](bayes.md).
- In Notebook 26 hält die Ventil-Gegenprobe nach Holm nicht (p = 0,021, Holm 0,13).
- Notebook 36 prüft mit vorab festgelegter Richtung, ob die Maßnahmen überhaupt eine Spur hinterlassen. Nur der Ventiltausch tut es (Sommernacht-Durchfluss, AUC 0,81, nach Holm gesichert). Dämmung, Filter und Durchfluss ändern nichts Messbares, neue Kennzahlen finden nichts Gesichertes. Bessere Labels würden hier mehr helfen als bessere Modelle. Bei der Dämmung gibt es einen ersten physikalischen Hinweis, die Abkühlrate im Stillstand (AUC 0,69, nicht gesichert).

## 20 Bestwert und Lückenfüllung

- Bestwert aus Notebook 22: sagt keine Befunde vorher und zeigt keine Verbesserung nach Begehungen.
- Notebook 19: Streuung nur bedingt aussagekräftig, Regelhysterese nicht nachweisbar.
- Notebook 01: Bei Lücken über einen Tag bleibt der Rücklauffehler der Füllung bei 5 bis 6 K.

## 21 Varianten der lernenden Modelle

- Probiert in Notebook 27: ein LSTM direkt auf die Befunde. Schon das kleine Netz der Vorversuche hat 283.856 Gewichte, beim Ventil gibt es 11 Fälle. Es würde jede Station auswendig lernen. Deshalb lernt das LSTM ohne Labels, und erst eine logistische Regression sieht die Befunde.
- Nicht gewählt in Notebook 27: ein Autoencoder, der den Tag nur nachbildet (erkennt Stationen schlechter wieder), ein Engpass von 16 statt 8 Zahlen (bei den Befunden nicht besser, Ventil 0,79 gegen 0,83) und Lernen auf allen statt nur auf begangenen Stationen (Vorgabe der Betreuung, der Unterschied ist klein).
- Nicht gewählt in Notebook 28: die Abweichung vom 7-Tage-Mittel vorherzusagen. Sie liegt nur im Test knapp vorn (4,21 gegen 4,28 K), und nach dem Test auszuwählen wäre zu optimistisch.
- Einfacher Wächter ohne Netz (Notebook 28): das 7-Tage-Mittel als Erwartung, Alarm ab 5 Streuungen. 12 seiner 16 Treffer an Begehungen liegen am Begehungstag oder am Tag danach. Er bemerkt den Eingriff, nicht die bleibende Veränderung, und an einen echten Schaden gewöhnt er sich nach einer Woche.
- Klasse „Regelparameter optimieren“ aus K-Means (Notebook 26): In Notebook 35 trifft sie keinen Befund, 24 bzw. 25 von 31 Fällen mit Regelungsoptimierung landen in „kein Handlungsbedarf“. Das Dashboard empfiehlt sie deshalb nicht.
- Details unter [LSTM-Fingerabdruck](../modelle/lstm.md), [Prognose-LSTM als Wächter](../modelle/prognose.md) und [Fehlerart und Klasse je Station](../modelle/klassen.md).

## 22 Erster Prüfstand

- Probiert in Notebook 34: alle Wächter und Kandidaten unter denselben Bedingungen.
- Der Vergleich war an mehreren Stellen zu großzügig: Der LSTM-Encoder kannte die Teststationen, das beste Modell und die Schwellen für das gleiche Alarmbudget wurden auf den Prüffällen gewählt, und die Auslastung war zum Anschlusswert statt zum alten Vertrag gerechnet.
- Beim Ventil kam die Regression auf Kennzahlen und LSTM-Zahlen dort auf 0,89. Im strengen Vergleich in Notebook 35, mit jeder Wahl nur im Lernteil, sind es 0,84.
- Die Rollen der Modelle haben sich dadurch nicht geändert, nur die Zahlen. Für Aussagen gelten die aus Notebook 35.
- Details im [Modellvergleich](../vergleich/modellvergleich.md#was-zuerst-nicht-stimmte).

## Nicht mehr im Abgabestand

Diese Versuche liegen nur im lokalen Archiv, nicht im Abgabestand. Ihre Zahlen sind hier nicht wiederholt, weil sie sich nicht an den Abgabe-Notebooks prüfen lassen. Ausnahme ist die Gesamtpipeline, deren Notebook im Verlauf des Repositorys liegt.

- Entscheidungsbaum als Vorhersagemodell: schlägt die Mehrheitsklasse nicht.
- Erste Fassung der Stundencluster (früher Notebook 09): ersetzt durch Notebook 09, das dasselbe Clustering über `src/clustervalidierung.py` rechnet und zusätzlich prüft.
- Gesamtpipeline (August, früher Notebook 12): Ein eigenständiges Notebook las die Rohdaten selbst, clusterte die
  Stationen und verglich unüberwachte Anomaliescores mit Wartungen als Ersatzlabel. Ergebnis: Die Rangfolgen
  lagen beim Zufall (AUC 0,49 bis 0,53), die Scores fanden höchstens 2 von 10 Ereignissen. Das Notebook ist nicht mehr
  im Abgabestand: Es nutzte eine eigene Datenaufbereitung mit 78 statt 93 Stationen, seine Zahlen passen deshalb
  nicht zu den übrigen Notebooks, und kein anderes Notebook baut darauf auf. Es liegt im Verlauf des Repositorys
  (Commit `1b5798b`).
- Graph Neural Network auf dem Leitungsnetz: nicht besser als dasselbe Netz ohne Kanten oder eine logistische Regression.
- Netzeffekt und gedämpfte Temperatur im Tagesmonitor: weniger Wellenalarme, aber mehr Alarme insgesamt und ein schwächerer Hebel.
- Treffer je Fehlerart aus den Freitexten: zu wenige Fälle je Fehlerart, kein Unterschied belegbar.
- Neue Stundenkennzahlen und Netzvergleich je Leistungsklasse: kein belastbarer Gewinn, Rangfolge fast gleich.
- Warmwasser-Ausschluss, Auflösungssperre und PELT im Fenstermonitor: keiner der Schalter verbessert den Monitor.
- Schwellen per zeitlicher Kreuzvalidierung: gewählte Schwellen nicht besser als die Voreinstellung.
- LSTM-Embedding gegen den Netzvergleich: Vorsprung des LSTM nicht belegt.
- Frühwarnung durch den Tagesmonitor: vor der Begehung keine Häufung von Alarmen.
- Varianten der Kontrollgruppe: Richtung gleich, Größe und Signifikanz der Begehungswirkung nicht.
- Neue Referenz nach der Begehung: der scheinbare Rückfall entsteht auch bei Scheinbegehungen, er kommt aus der kürzeren Referenz.
- Priorität vor der Begehung und Dämmung als Restkategorie: Richtung stimmt, belegt ist es nicht; die Restkategorie-Vermutung trägt nicht.
- Eingerechnete Fühlerfehler: der Tagesmonitor findet Fühlerfehler kaum.
- Vortagstemperatur und Sprungpause gegen Kältewellen: die Wellen bleiben.