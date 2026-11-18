# Modellvergleich: welches Modell für welche Aufgabe?

Im Projekt sind viele Modelle und Regeln entstanden. Fast jedes Notebook hat sich selbst geprüft, mit eigenem Zeitraum,
eigenen Stationen, eigener Kontrollgruppe und eigener Alarmmenge. Diese Seite zeigt, wie daraus ein fairer Vergleich
wird, und fasst das Ergebnis zusammen.

- Gerechnet wird in `notebooks/8_modellvergleich/34_modellvergleich.ipynb`.
- Die Prüfungen stehen in `src/pruefstand.py`.
- Die Umsetzung als Endmodell steht in `notebooks/8_modellvergleich/35_endmodell.ipynb` (Seite [Endmodell](endmodell.md)).

## So wird verglichen

Ein Modell ist nicht allgemein „gut“, sondern gut für eine Frage und gemessen an einem Prüfstein.

1. Aufgabe festlegen. Folie 5 der Aufgabenstellung verlangt drei Aufgaben:
    - Alarm: die Station verändert sich,
    - Fehler erkennen: die Station hat einen Dauerfehler,
    - Fehler unterteilen: welche Handlung ist nötig.
2. Prüfstein festlegen, bevor man Ergebnisse sieht.
    - Alarm: Begehungstermine (echte Veränderungen) und eingerechnete Fehler (bekannter Beginn).
    - Fehlerart: Befunde der Begehungen, nur mit Daten von vor der Begehung.
    - Klassen: Treffer der Klasse gegen den Befund.
3. Alle Kandidaten durch dieselbe Prüfung schicken. Regeln gehören dazu. Eine Regel ist ein Modell ohne Lernen.
4. Gleiche Bedingungen herstellen.
    - dieselben Stationen und Tage (Schnittmenge aller Kandidaten),
    - dieselbe Alarmmenge, denn wer öfter alarmiert, trifft automatisch öfter,
    - nur Daten, die das Modell nicht gelernt hat (Kreuzvalidierung oder Zeit nach dem Lernen).
5. Unsicherheit angeben und gepaart vergleichen. Bei 11 Ventilfällen streut die AUC um etwa ±0,15. Vertauschte Labels
   erreichen 0,27 bis 0,73 (Notebook 29). Deshalb steht hinter jeder Zahl ein Intervall. Zwei Kandidaten werden auf
   denselben Stationen verglichen (gepaarter Bootstrap, McNemar). Bei vielen Tests wird nach Holm korrigiert.
6. Bei Gleichstand gewinnt das Einfachere. Eine Regel ist erklärbar und braucht kein Training.

### Werkzeuge im Prüfstand

| Aufgabe | Funktion | Was sie misst |
|---|---|---|
| Alarm | `trefferpruefung`, `bilanz` | Alarm im Fenster −7 bis +60 Tage um eine Begehung gegen Kontrollstationen im selben Fenster; Hebel, einseitiger Binomialtest (Verfahren aus Notebook 18, Fall für Fall nachgeprüft) |
| Alarm | `gemeinsame_tage`, `auf_tagen` | Schnittmenge der überwachten Stationstage |
| Alarm | `budget_anpassen` | Schwelle bzw. CUSUM-Grenze, bei der ein Kandidat gleich viele Alarme gibt wie der Bezug |
| Alarm | `einrechnen` | Bypass, hängender Fühler, verstellter Sollwert in echte Stundenwerte schreiben (Notebook 28) |
| Alarm | `mcnemar`, `alarme_je_jahr`, `erster_alarm_nach` | Fall-für-Fall-Vergleich, Alarmlast, Reaktionszeit |
| Fehler erkennen | `bewerte_scores` | AUC mit Bootstrap-Intervall, P@10, Zufallstest mit Holm, gepaarte Differenz zu einem Bezug |
| Fehler unterteilen | `vierfelder`, `kappa` | Precision und Trefferquote einer Klasse gegen den Befund; Übereinstimmung zweier Einteilungen |

Ein Wächter besteht aus zwei Bausteinen, die sich getrennt austauschen lassen:

- Erwartung: Kennlinie, LSTM oder Wochenmittel.
- Alarmregel: Schwelle an zwei Tagen oder CUSUM (Summe der Abweichungen, schlägt an, wenn sie zu groß wird).

In `src/prognose_waechter.py` liegen beide Alarmregeln auf denselben z-Werten. So lässt sich trennen, was am Modell
liegt und was an der Regel.

## Ergebnis A: Alarm

Gemeinsame Grundlage:

- 79 Stationen und 15.142 Heiztage vom 01.06.2024 bis 09.06.2025,
- dieselben 43 Begehungen,
- Alarmbudget 204 (so viele Alarme gibt das Normalverhaltensmodell auf diesen Tagen).

| Wächter (Erwartung + Regel) | Begehungen bemerkt | Kontrolle | p | in 14 Tagen |
|---|---|---|---|---|
| Tagesmonitor (Kennlinie + CUSUM, h = 4,5) | 33/43 | 53 % | 0,001 | 18/39 gegen 24 %, p = 0,003 |
| Normalverhaltensmodell, Notebook 18 (Kennlinie + CUSUM, h = 5) | 30/43 | 50 % | 0,008 | 14/39 gegen 22 %, p = 0,033 |
| Wochenmittel + Schwelle (ohne Lernen) | 24/43 | 36 % | 0,006 | 14/39 gegen 17 %, p = 0,003 |
| Prognose-LSTM + CUSUM | 24/43 | 40 % | 0,022 | 8/39, p = 0,15 |
| Wochenmittel + CUSUM | 16/43 | 20 % | 0,005 | 7/39, p = 0,13 |
| Prognose-LSTM + Schwelle (Notebook 28) | 16/43 | 32 % | 0,26 | 7/39, kein Signal |

Plötzliche Fehler, eingerechnet in den Sommer 2024, bei höchstens 10 % Fehlalarmen in 8 Tagen:

| Erwartung + Regel | Fehlalarm | Bypass 50 l/h | Bypass 150 l/h | Fühler hängt | Sollwert +5 K |
|---|---|---|---|---|---|
| Prognose-LSTM + Schwelle z ≥ 4 | 8 % | 55 % | 84 % | 43 % | 19 % |
| Prognose-LSTM + CUSUM | 6 % | 48 % | 81 % | 36 % | 17 % |
| Wochenmittel + Schwelle | 8 % | 40 % | 78 % | 17 % | 16 % |
| Wochenmittel + CUSUM | 7 % | 43 % | 77 % | 18 % | 15 % |

- Ventilfall 68956351: Kennlinie und Tagesmonitor melden den Tausch nach 2 Tagen, das LSTM nach 4 (CUSUM) bzw. 7 Tagen
  (Schwelle).
- Alarmlast: 3,5 bis 3,8 Alarme je Station und Jahr, das Wochenmittel liegt bei 4,9 bis 5,7.

Was das heißt:

- Es gibt zwei Wächter mit verschiedenen Aufgaben. Kennlinie mit CUSUM findet kleine, bleibende Veränderungen und ist an
  echten Begehungen belegt. Das LSTM findet große, plötzliche Fehler, auch im Sommer. Es ist nur an eingerechneten
  Fehlern belegt.
- Die Alarmregel ist ein eigener Baustein. Dieselben LSTM-z-Werte bemerken mit CUSUM 24 statt 16 Begehungen.
- Zur Kennlinie fehlen dem LSTM trotzdem 6 bis 9 Fälle. Es nimmt die letzten sieben Tage als Eingang und übernimmt eine
  bleibende Veränderung nach einer Woche in seine Erwartung.
- Tagesmonitor und Normalverhaltensmodell sind gleichwertig. Fall für Fall hat der Tagesmonitor 3 Fälle mehr und keinen
  weniger (McNemar p = 0,25). Im Betrieb läuft der Tagesmonitor, weil er als Modul auf neuen Daten läuft.

### Alle Wächter des Projekts

Dazu kommen alle übrigen Ansätze, die einen Tagesalarm liefern können:

- Kennlinienmonitor (Notebook 13),
- Tagesmonitor mit Netzereignis-Filter (Notebook 24),
- ARIMA-Wächter: das beste Modell aus Notebook 06 (Tagesrücklauf aus Außentemperatur mit AR(1)), hier als täglicher
  Wächter gebaut,
- die fünf Detektoren aus Notebook 16.

Alle laufen auf denselben Tagen und Fällen. Die Holm-Korrektur geht über alle 15:

| Wächter | bemerkt (−7 bis +60) | Kontrolle | p | p (Holm) |
|---|---|---|---|---|
| Tagesmonitor (Kennlinie + CUSUM) | 33/43 | 53 % | 0,001 | 0,017 |
| Tagesmonitor ohne Netzereignisse (Notebook 24) | 33/43 | 53 % | 0,001 | 0,017 |
| Wochenmittel + CUSUM / + Schwelle | 16/43 / 24/43 | 20 % / 36 % | 0,005 / 0,006 | 0,07 |
| Normalverhaltensmodell (Notebook 18) | 30/43 | 50 % | 0,008 | 0,08 |
| ARIMA-Wächter + Schwelle | 22/43 | 34 % | 0,016 | 0,16 |
| Prognose-LSTM + CUSUM | 24/43 | 40 % | 0,022 | 0,20 |
| Kennlinienmonitor (Notebook 13) | 27/43 | 53 % | 0,14 | 0,94 |
| ARIMA-Wächter + CUSUM | 20/43 | 40 % | 0,22 | 1 |
| Prognose-LSTM + Schwelle (Notebook 28) | 16/43 | 32 % | 0,26 | 1 |
| Notebook 16: Dynamik, Kurzschluss-Zustand, Residuen, Isolation Forest | 6 bis 18 | – | ≥ 0,07 | ≥ 0,57 |

- Nur Kennlinie mit CUSUM bleibt nach der Korrektur belegt. In den ersten 14 Tagen kommt das Wochenmittel mit Schwelle
  dazu.
- Der Netzereignis-Filter (Notebook 24) ändert im Prüfzeitraum nichts. Das einzige Netzereignis mit Verschlechterungen
  liegt im Dezember 2022.
- Der Kennlinienmonitor (Notebook 13) trifft viel, aber die Kontrollen genauso (Hebel 1,18).
- Die Detektoren aus Notebook 16 taugen nicht als Alarm. Fall für Fall verliert jeder gegen das Normalverhaltensmodell
  (McNemar p ≤ 0,017). Sie sind als Rangliste je Station gebaut und laufen deshalb in Teil B mit.

## Ergebnis B: Fehler erkennen

### Ventil

11 Befunde unter 52 begangenen Zählern. Nur Daten vor der Begehung. Gelernte Modelle aus der verschachtelten
Kreuzvalidierung. „README-Regeln“ sind die ersten Regeln des Projekts aus `src/fault_detection.py`.

| Kandidat | Art | AUC [95 %] | gegen Sommernacht-Regel |
|---|---|---|---|
| LR Kennzahlen + LSTM-Embedding | gelernt | 0,89 [0,78; 0,98] | +0,04, nicht unterscheidbar |
| Sommer-Nachtdurchfluss | Regel | 0,88 [0,73; 0,99] | +0,03, nicht unterscheidbar |
| README-Regel `continuous_flow` (Sommer-Median Durchfluss) | Regel | 0,85 [0,69; 0,98] | ±0 |
| Sommernacht-Regel (Anteil Nächte mit Durchfluss) | Regel | 0,85 [0,67; 0,98] | Bezug |
| README-Regel `excess_rt` (Winter-Rücklauf) | Regel | 0,84 [0,68; 0,96] | −0,01 |
| LSTM-Embedding allein | gelernt | 0,84 [0,71; 0,94] | −0,01 |
| LR Kennzahlen | gelernt | 0,79 [0,58; 0,97] | −0,06 |
| Netzvergleich-Score Winter 23/24 | Flottenvergleich | 0,73 [0,55; 0,90] | −0,12 |
| Abkühlung bei 5 °C (Notebook 18) | Normkennzahl | 0,68 [0,47; 0,87] | −0,17 |
| K-Means „schlechter“ | Clustering | 0,67 [0,51; 0,83] | −0,18, belegt schlechter |

Fürs Ventil laufen insgesamt 27 Kandidaten mit, darunter:

- Stationsbilder (Notebook 12), Ternär und Fallsammlung (Notebooks 11 und 15),
- Kurzschluss-Zeitanteil (Notebooks 09 und 16), Persistenzanteile (Notebook 16), Schweregrad (Notebook 17),
- Tagestypen (Notebook 10), Potenzial (Notebook 22), Vergleichsgruppen (Notebook 23),
- Random Forest und XGBoost auf allen Merkmalen (Notebook 29).

Jeder Kandidat wird gepaart mit der Sommernacht-Regel auf den 53 Zählern verglichen, mit Holm über alle 27:

- 15 Kandidaten sind besser als Raten. Vorn liegen Paket-Modell (0,89), Sommer-Nachtdurchfluss (0,88) und die
  Schweregrad-Punkte aus Notebook 17 (0,87). Keiner ist belegt besser als die Regel.
- Random Forest (0,77) und XGBoost (0,75) sind auch mit allen Merkmalen nicht besser. XGBoost ist belegt schlechter als
  die Regel.
- Flottenvergleiche liegen bei 0,67 bis 0,74: Netzvergleich, Vergleichsgruppen, Potenzial, K-Means,
  Kennliniensteigung, Durchflussanteil der Modulation.
- Eine unruhige Kennlinie (Residuenstreuung, Notebook 12) spricht gegen ein Ventil (0,39). Ein offenes Ventil läuft
  gleichmäßig durch.

### Dämmung

18 von 42 in der Haupttabelle, paarweise mit allen Kandidaten 22 von 53.

- Nur das Paket-Modell ist besser als Raten: logistische Regression auf Kennzahlen + LSTM, 0,75 [0,58; 0,89]. Das gilt
  auch, wenn alle Kandidaten mitlaufen.
- Gegen die Kennzahlen allein ist es nicht belegt besser (+0,06).
- Flottenmaße zeigen die umgekehrte Richtung: Netzvergleich (0,38), Vergleichsgruppen (0,37), Potenzial (0,39) und
  Anteil Rücklauf über 50 °C (0,30) sind belegt schlechter als der Bezug.
- Ein Dämmungsbefund kommt also eher bei Stationen vor, die im Netz gut aussehen. Der Hinweis „Dämmung prüfen“ ist
  statistisch erkennbar, aber physikalisch nicht erklärt.
- Die Deutung aus Notebook 29 (ungedämmte Leitungen erhöhen die Nachtspreizung im Sommer) hält nicht: Mit
  Dämmungsbefund ist die Nachtspreizung kleiner (AUC 0,29 in der vorab festgelegten Richtung).

### Überdimensionierung

9 von 35.

- Eine niedrige Auslastung zum Vertrag vor der Begehung erreicht 0,78 [0,53; 0,98].
- Das ist belegt besser als der Anschlusswert (+0,12 [0,02; 0,24]).
- Die README-Regel `oversized_contract` liegt bei Raten (0,51). Sie nimmt den Anschlusswert, und der ist oft schon der
  neue Vertrag.

### Ventil als Entscheidung

Basisrate 21 %.

| Entscheidung | Ja | richtig | Trefferquote |
|---|---|---|---|
| Netzvergleich auffällig 23/24 | 4 | 4 (100 %) | 36 % |
| Klasse „Regelventil tauschen“ (p ≥ 0,5) | 12 | 8 (67 %) | 73 % |
| Sommernacht-Regel ≥ 0,5 | 14 | 9 (64 %) | 82 % |
| README-Regel `continuous_flow` (25 l/h) | 15 | 8 (53 %) | 73 % |
| README-Regel `excess_rt` (48 °C) | 32 | 10 (31 %) | 91 % |

### Gegenprobe mit neuen Daten

Das Paket wurde unverändert auf Winter 24/25 und Sommer 2025 angewendet.

- Ventil getauscht (8 Zähler mit Befund und vorherigem Verdacht): Der Verdacht sinkt im Median von 0,81 auf 0,37
  (Wilcoxon p = 0,016).
- Nie begangene Verdachtsfälle (12): Der Verdacht bleibt, 0,76 auf 0,61, keine belegte Änderung.
- Zähler 68956351 fällt von 1,00 auf 0,09.

Was das heißt:

- Ein offenes Ventil ist mit einfachen Mitteln gut erkennbar. Das Modell ist nicht belegt besser als die
  Sommernacht-Regel. Es braucht aber den Sommer nicht und ist deshalb das Ventil-Modell für Folie 5. Die Regel steht
  als Gegenprobe daneben.
- Regeln gehören in jeden Vergleich. Die erste Regel des Projekts (README) ist so gut wie das beste Modell, sobald sie
  auf dem richtigen Zeitraum rechnet.
- Clustering und Flottenvergleiche erkennen das Ventil schwächer. Sie messen „schlechter als andere“, und das ist nur
  zur Hälfte ein Ventil. Der Netzvergleich ist dafür das genaueste Signal, wenn er anschlägt.

## Ergebnis C: Fehler unterteilen und empfehlen

| Klasse (Folie 5) | Handlung (Aufgabenstellung) | Woraus | gegen Befund |
|---|---|---|---|
| Regelventil tauschen | Reparatur | Ventil-Modell, p ≥ 0,5 | 8 von 12 richtig, Trefferquote 73 % |
| Regelparameter optimieren | Regelungsoptimierung | K-Means „schlechter“ ohne Ventilverdacht | 3 begangene, keiner mit Ventilbefund |
| kein Handlungsbedarf | – | K-Means „Optimum“ | 3 von 39 mit Ventilbefund |
| Hinweis Überdimensionierung | Kapazitätsanpassung | Auslastungsregel | 6 von 7 richtig |
| Hinweis Dämmung | Reparatur (Dämmung) | Dämmungsmodell | 12 von 15 richtig |

Das Fehlerbild „ventil“ des Netzvergleichs und die Klasse passen mäßig zusammen (Kappa 0,46). Alle 8
Netz-Ventilfälle stehen auch in der Klasse. Die Klasse findet mehr, der Netzvergleich ist strenger.

Vorschlag für die Dringlichkeit in der Empfehlungsliste:

- hoch: Reparatur, bestätigt durch das Netz-Fehlerbild „ventil“ oder mit p ≥ 0,8,
- mittel: übrige Reparatur und Regelungsoptimierung,
- niedrig: nur Hinweise (Kapazität, Dämmung, Daten prüfen),
- innerhalb einer Stufe zuerst Stationen mit Verschlechterung im Tagesmonitor in der letzten Heizperiode, dann nach dem
  Optimierungspotenzial (Abstand zum besten Viertel), dann nach dem Ventilverdacht.

Eine Verschlechterung hebt die Stufe nicht. Im Winter 24/25 hatte fast jede zweite Station eine, und vor Begehungen mit
Befund gab es nicht mehr davon als bei Kontrollen (Notebook 21). Die Stufen sind gesetzt, nicht gelernt.

## Monitoring-Modell gegen LSTM-Kette

Im Projekt gibt es zwei vollständige Systeme:

| | Monitoring-Modell (Kennlinien-Strang) | LSTM-Kette (Modell-Strang) |
|---|---|---|
| Notebooks | 13, 19 bis 24, Stationsblatt | 25 bis 30 |
| Alarm | Tagesmonitor: Kennlinie + CUSUM | Prognose-LSTM + Schwelle |
| Fehler erkennen | Netzvergleich je Kernwinter | Kennzahlen + LSTM-Embedding → LR |
| Unterteilen und Reihenfolge | Fehlerbild, Priorität hoch/mittel/niedrig | Klassen nach Folie 5 |

Kopf an Kopf, gepaart auf denselben Fällen bzw. Stationen (Notebook 34, Abschnitt 4b):

| Aufgabe | Monitoring | LSTM-Kette | gepaart | besser |
|---|---|---|---|---|
| Alarm: Begehungen (60 Tage) | 33/43 gegen 53 %, p = 0,001 | 16/43 (Schwelle), 24/43 (CUSUM) | 17 zu 0 Fälle, p < 0,001; gegen CUSUM 13 zu 4, p = 0,049 | Monitoring |
| Alarm: erste 14 Tage | 18/39, p = 0,003 | 7/39, kein Signal | – | Monitoring |
| Alarm: plötzliche Fehler | nicht prüfbar | Bypass 84 %, Fühler 43 % | – | LSTM |
| Ventilfall 68956351 | 2 Tage | 7 bzw. 4 Tage | – | Monitoring |
| Ventil erkennen (AUC) | Netzvergleich 0,73 | 0,89 | +0,16 [+0,02; +0,31] | LSTM |
| Dämmung erkennen (AUC) | Netzvergleich 0,38 | 0,75 | +0,37 [+0,12; +0,61] | LSTM |
| Entscheidung Ventil | Fehlerbild „ventil“: 4 von 4 richtig, findet 36 % | Klasse: 8 von 12 richtig, findet 73 % | – | ergänzen sich |
| Priorität | „hoch“: 1 begangene Station; „hoch oder mittel“: 32 % mit Ventilbefund (Basisrate 21 %) | – | – | trennt kaum |

Was das heißt:

- Beim Alarm gewinnt das Monitoring-Modell. Es merkt kleine, bleibende Veränderungen.
- Beim Erkennen gewinnt die LSTM-Kette. Der Netzvergleich misst „schlechter als die anderen“, und das ist nur zur
  Hälfte ein Ventil.
- Die beste Lösung kombiniert beide: Alarm aus dem Tagesmonitor, dazu das LSTM für plötzliche Fehler, Klasse aus der
  LSTM-Kette, Netzvergleich als Bestätigung. So ist das Endmodell in Notebook 35 gebaut.

## Haus oder Netz

Mehrere Notebooks haben das Netz untersucht: 18 (Abschnitt 15), 23, 24, 32, 38 und die Vorarbeit zu 29. Notebook 34
(Abschnitt 3b) prüft das Netz zusätzlich als Kandidat, mit dem logischen Graphen aus `Nodes_Edges.ods` (Nachbarn bis
zwei Kanten).

| Kandidat | Ergebnis |
|---|---|
| Tagesmonitor ohne gemeinsame Nachbar-Alarme (Notebook 24) | 34/43 statt 33/43, Fall für Fall nicht unterscheidbar |
| Tagesmonitor, Nachbarn abgezogen | 30/43, etwas schlechter |
| Tagesmonitor, Netzmedian abgezogen | 25/43, belegt schlechter (die Begehungen kamen als Welle, der Abzug nimmt ihre Wirkung heraus) |
| Nachbarn: Sommer-Durchfluss bzw. Ventilverdacht → eigenes Ventil | AUC 0,44 bzw. 0,42, belegt schlechter als die eigene Regel |
| Paket-Modell + Nachbar-Merkmale | Ventil +0,004, Dämmung −0,02: keine Verbesserung |
| Vorlauf unter dem Netz (Strangende) → Ventil | 0,20, also umgekehrt: Stationen mit offenem Ventil haben einen wärmeren Vorlauf, weil durchlaufendes Wasser die Zuleitung warm hält |

Was das heißt:

- Die Fehler sitzen im einzelnen Haus. Offene Ventile häufen sich nicht in Strängen.
- Das Netz zählt nur als Ganzes: Wetter, Vorlauf, Begehungswellen. Das fangen Kennlinie und Tagesmonitor schon ab.

## Zusammenfassung

Verglichen wurden 15 Wächter, 27 Erkenner und die Netz-Varianten, also jedes Modell des Projekts, das einen Tagesalarm
oder einen Wert je Station liefert. Nur GNN und Bayes fehlen, weil ihre Eingaben hier nicht vorliegen. Das
Monitoring-Modell gewinnt beim Alarm, die LSTM-Kette beim Erkennen. Das Netz verbessert keins von beiden.

| Aufgabe | Bestes Verfahren | Einfachere Alternative | Im Betrieb (Paket) |
|---|---|---|---|
| Alarm: schleichende Veränderung | Kennlinie + CUSUM (einziger nach Holm belegter von 15) | Wochenmittel + Schwelle | `normalmodell`, Hauptkanal |
| Alarm: plötzlicher Fehler, Sommer | Prognose-LSTM + Schwelle | Wochenmittel + Schwelle | `prognose_lstm`, Hinweiskanal |
| Fehler erkennen: Ventil | LR Kennzahlen + LSTM (nicht belegt besser) | Sommernacht-Regel | `fehlerklassen` |
| Fehler erkennen: Dämmung | LR Kennzahlen + LSTM | – | `fehlerklassen`, Hinweis |
| Fehler erkennen: Überdimensionierung | Regel: Auslastung zum Vertrag | – | `fehlerklassen`, Hinweis |
| Fehler unterteilen | Ventil-Modell → K-Means | Netz-Fehlerbild | Klasse je Station, Dringlichkeit |

## Was nicht verglichen werden kann

| Notebook | Warum nicht | Was stattdessen gilt |
|---|---|---|
| 38 GNN | braucht die Kanten- und Positionsdateien aus Notebook 31 in `notebooks/` | eigenes Ergebnis: kleiner Gewinn, kein Strang-Effekt; dieselbe Frage prüft der Abschnitt „Haus oder Netz“ |
| 37 Bayes | braucht die Handtabellen unter `data/manual/` | eigenes Ergebnis: Ventil im Zweikampf AUC 0,92, mit einer Matrix, die noch nicht mit der ÜZ abgestimmt ist |
| 07 Stationscluster, 08 Clusterbenchmark | Profile über die ganze Historie, also auch nach der Begehung (Datenleck) | eigenes Ergebnis: kein Cluster trennt die Begehungen; verglichen wird K-Means aus Notebook 26 |
| 03 Labels | Label-Vorschlag, kein Erkenner | dieselben Größen stecken in den README- und Kennzahl-Regeln |
| 34 Netz, 36 Netzkarte | Karte und Graphaufbau, kein Modell je Station | das Netz selbst ist als Kandidat geprüft (Abschnitt „Haus oder Netz“) |
| 01, 02, 04, 05 | messen die Wirkung der Begehungen oder bereiten Daten auf | sie liefern den Prüfstein |

## Grenzen

- Kleine Fallzahlen: 43 Begehungen und 11 Ventilfälle. Unterschiede unter etwa 0,1 AUC bzw. 5 Fällen sind nicht zu
  sehen.
- Die Parameter für das gleiche Alarmbudget wurden auf den Fällen gewählt, an denen auch gemessen wird. Das gilt für alle
  Kandidaten gleich, die p-Werte sind aber leicht optimistisch.
- Je ein Wächter ist nur halb geprüft. Das Normalverhaltensmodell ist nicht mit eingerechneten Fehlern geprüft (es
  rechnet aus Zählerständen). Das LSTM ist nicht an echten Ereignissen belegt.
- Für die Regelhysterese gibt es kein eigenes Befund-Label. Die README-Regel `control_hysteresis` lässt sich deshalb
  nicht prüfen.
- Die Dringlichkeit ist nicht getestet. Nötig wäre ein Test nach vorn: Stationen der Stufe hoch und gleich viele
  zufällige begehen, ohne zu wissen, welche welche ist.
