# Modellvergleich: welches Modell für welche Aufgabe?

Im Projekt sind viele Modelle und Regeln entstanden, und fast jedes Notebook hat sich selbst
geprüft: mit eigenem Zeitraum, eigenen Stationen, eigener Kontrollgruppe und eigener Alarmmenge.
Diese Seite erklärt, wie man daraus einen fairen Vergleich macht, und fasst das Ergebnis zusammen.
Gerechnet wird alles in `notebooks/32_modellvergleich.ipynb`, die Prüfungen stehen in
`src/pruefstand.py`.

## Wie findet man das beste Modell für eine Aufgabe?

Ein Modell ist nicht „gut“, sondern gut **für eine Frage, gemessen an einem Prüfstein**. Die Reihenfolge:

1. **Aufgabe festlegen.** Folie 5 verlangt drei: *Alarm* (die Station verändert sich), *Fehler
   erkennen* (die Station hat einen Dauerfehler), *Fehler unterteilen* (welche Handlung). Ein Modell
   für den Alarm wird anders geprüft als eines für die Fehlerart.
2. **Prüfstein festlegen, bevor man Ergebnisse sieht.**
   - Für den Alarm: die Begehungstermine (echte Veränderungen) und eingerechnete Fehler (bekannter
     Beginn).
   - Für die Fehlerart: die Befunde der Begehungen, nur mit Daten von **vor** der Begehung.
   - Für die Klassen: Treffer der Klasse gegen den Befund.
3. **Alle Kandidaten durch dieselbe Prüfung schicken.** Dazu gehören auch Regeln: Eine Regel ist ein
   Modell ohne Lernen. Sie liefert einen Wert je Station oder einen Alarm je Tag, genau wie ein gelerntes
   Modell. Das meint „nebeneinanderschalten“: gleiche Art Ausgabe, gleiche Bewertung.
4. **Gleiche Bedingungen herstellen.**
   - dieselben Stationen und Tage, als Schnittmenge aller Kandidaten,
   - dieselbe Alarmmenge bzw. Fehlalarmquote, denn wer öfter alarmiert, trifft automatisch öfter,
   - nur Daten, die das Modell nicht gelernt hat: Kreuzvalidierung oder Zeit nach dem Lernen.
5. **Unsicherheit angeben und gepaart vergleichen.** Bei 11 Ventilfällen streut die AUC um etwa
   ±0,15, vertauschte Labels erreichen 0,27 bis 0,73 (Notebook 22). Deshalb steht hinter jeder Zahl ein
   Intervall. Zwei Kandidaten werden auf **denselben** Stationen verglichen (gepaarter Bootstrap,
   McNemar). Bei vielen Tests wird nach Holm korrigiert.
6. **Bei Gleichstand gewinnt das Einfachere.** Eine Regel ist erklärbar, braucht kein Training und
   bricht nicht still, wenn sich die Daten ändern.

### Die Werkzeuge im Prüfstand

| Aufgabe | Funktion | Was sie misst |
|---|---|---|
| Alarm | `trefferpruefung`, `bilanz` | Alarm im Fenster −7 bis +60 Tage um eine Begehung gegen Kontrollstationen im selben Fenster; Hebel, einseitiger Binomialtest (Sebs Verfahren aus NB 17, Fall für Fall nachgeprüft) |
| Alarm | `gemeinsame_tage`, `auf_tagen` | Schnittmenge der überwachten Stationstage |
| Alarm | `budget_anpassen` | Schwelle bzw. CUSUM-Grenze, bei der ein Kandidat gleich viele Alarme gibt wie der Bezug |
| Alarm | `einrechnen` | Bypass, hängender Fühler, verstellter Sollwert in echte Stundenwerte schreiben (NB 21) |
| Alarm | `mcnemar`, `alarme_je_jahr`, `erster_alarm_nach` | Fall-für-Fall-Vergleich, Alarmlast, Reaktionszeit |
| Fehler erkennen | `bewerte_scores` | AUC mit Bootstrap-Intervall, P@10, Zufallstest mit Holm, gepaarte Differenz zu einem Bezug, auf den Stationen, die alle Kandidaten haben |
| Fehler unterteilen | `vierfelder`, `kappa` | Precision und Trefferquote einer Klasse gegen den Befund; Übereinstimmung zweier Einteilungen |

Ein Wächter besteht aus zwei Bausteinen, die sich getrennt austauschen lassen:
- **Erwartung:** Kennlinie, LSTM oder Wochenmittel.
- **Alarmregel:** Schwelle an zwei Tagen oder CUSUM.

In `src/prognose_waechter.py` liegen beide Alarmregeln auf denselben z-Werten. Nur so lässt sich
trennen, was am Modell liegt und was an der Regel.

## Ergebnis A: Alarm

**Gemeinsame Grundlage:**
- 79 Stationen und 15.142 Heiztage vom 01.06.2024 bis 09.06.2025,
- dieselben 43 Begehungen,
- Alarmbudget 204, so viele Alarme gibt das Normalverhaltensmodell auf diesen Tagen.

| Wächter (Erwartung + Regel) | Begehungen bemerkt | Kontrolle | p | in 14 Tagen |
|---|---|---|---|---|
| **Tagesmonitor** (Kennlinie + CUSUM, h = 4,5) | **33/43** | 53 % | **0,001** | 18/39 gegen 24 %, p = 0,003 |
| Normalverhaltensmodell NB 17 (Kennlinie + CUSUM, h = 5) | 30/43 | 50 % | 0,008 | 14/39 gegen 22 %, p = 0,033 |
| Wochenmittel + Schwelle (ohne Lernen) | 24/43 | 36 % | 0,006 | 14/39 gegen 17 %, p = 0,003 |
| Prognose-LSTM + CUSUM | 24/43 | 40 % | 0,022 | 8/39, p = 0,15 |
| Wochenmittel + CUSUM | 16/43 | 20 % | 0,005 | 7/39, p = 0,13 |
| Prognose-LSTM + Schwelle (NB 21) | 16/43 | 32 % | 0,26 | 7/39, kein Signal |

**Plötzliche Fehler**, eingerechnet in den Sommer 2024, bei höchstens 10 % Fehlalarmen in 8 Tagen:

| Erwartung + Regel | Fehlalarm | Bypass 50 l/h | Bypass 150 l/h | Fühler hängt | Sollwert +5 K |
|---|---|---|---|---|---|
| **Prognose-LSTM + Schwelle z ≥ 4** | 8 % | **55 %** | **84 %** | **43 %** | **19 %** |
| Prognose-LSTM + CUSUM | 6 % | 48 % | 81 % | 36 % | 17 % |
| Wochenmittel + Schwelle | 8 % | 40 % | 78 % | 17 % | 16 % |
| Wochenmittel + CUSUM | 7 % | 43 % | 77 % | 18 % | 15 % |

**Ventilfall 68956351:** Kennlinie und Tagesmonitor melden den Tausch nach 2 Tagen, das LSTM nach 4
(CUSUM) bzw. 7 Tagen (Schwelle). **Alarmlast:** 3,5 bis 3,8 Alarme je Station und Jahr; das
Wochenmittel liegt bei 4,9 bis 5,7.

**Was das heißt:**
- **Zwei Wächter mit verschiedenen Aufgaben.** Die Kennlinie mit CUSUM findet kleine, bleibende
  Veränderungen; sie ist an echten Begehungen belegt. Das LSTM findet große, plötzliche Fehler, auch im
  Sommer; es ist nur an eingerechneten Fehlern belegt.
- **Die Alarmregel ist ein eigener Baustein.** Dieselben LSTM-z-Werte bemerken mit CUSUM 24 statt 16
  Begehungen. Zur Kennlinie fehlen trotzdem 6 bis 9 Fälle: Das LSTM nimmt die letzten sieben Tage als
  Eingang und übernimmt eine bleibende Veränderung nach einer Woche in seine Erwartung.
- **Tagesmonitor und Normalverhaltensmodell sind gleichwertig.** Fall für Fall hat der Tagesmonitor 3
  Fälle mehr und keinen weniger (McNemar p = 0,25). Im Betrieb läuft der Tagesmonitor, weil er als Modul
  auf neuen Daten läuft.

### Alle Wächter des Projekts

Dazu kommen alle übrigen Ansätze, die einen Tagesalarm liefern können:
- **Kennlinienmonitor** (NB 14),
- **Tagesmonitor mit Netzereignis-Filter** (NB 24),
- **ARIMA-Wächter:** das beste Modell aus dem Notebook `arima` (Tagesrücklauf aus Außentemperatur mit AR(1)), hier
  als täglicher Wächter gebaut,
- **die fünf Detektoren aus Notebook 10.**

Alle laufen auf denselben Tagen und Fällen. Die Holm-Korrektur geht über alle 15:

| Wächter | bemerkt (−7 bis +60) | Kontrolle | p | p (Holm) |
|---|---|---|---|---|
| **Tagesmonitor** (Kennlinie + CUSUM) | **33/43** | 53 % | 0,001 | **0,017** |
| Tagesmonitor ohne Netzereignisse (NB 24) | 33/43 | 53 % | 0,001 | 0,017 |
| Wochenmittel + CUSUM / + Schwelle | 16/43 / 24/43 | 20 % / 36 % | 0,005 / 0,006 | 0,07 |
| Normalverhaltensmodell (NB 17) | 30/43 | 50 % | 0,008 | 0,08 |
| ARIMA-Wächter + Schwelle | 22/43 | 34 % | 0,016 | 0,16 |
| Prognose-LSTM + CUSUM | 24/43 | 40 % | 0,022 | 0,20 |
| Kennlinienmonitor (NB 14) | 27/43 | 53 % | 0,14 | 0,94 |
| ARIMA-Wächter + CUSUM | 20/43 | 40 % | 0,22 | 1 |
| Prognose-LSTM + Schwelle (NB 21) | 16/43 | 32 % | 0,26 | 1 |
| NB 10: Dynamik, Kurzschluss-Zustand, Residuen, Isolation Forest | 6 bis 18 | – | ≥ 0,07 | ≥ 0,57 |

- **Nur die Kennlinie mit CUSUM bleibt nach der Korrektur belegt.** In den ersten 14 Tagen kommt das
  Wochenmittel mit Schwelle dazu.
- **Der Netzereignis-Filter (NB 24) ändert im Prüfzeitraum nichts.** Das einzige Netzereignis mit
  Verschlechterungen liegt im Dezember 2022.
- **Kennlinienmonitor (NB 14):** Er trifft viel, aber die Kontrollen genauso (Hebel 1,18).
- **Detektoren aus NB 10:** Sie sind als Alarm ungeeignet. Fall für Fall verliert jeder gegen das
  Normalverhaltensmodell (McNemar p ≤ 0,017). Sie sind als Rangliste je Station gebaut und laufen deshalb in
  Teil B mit.

## Ergebnis B: Fehler erkennen

**Ventil:** 11 Befunde unter 52 begangenen Zählern, nur Daten vor der Begehung, gelernte Modelle aus
der verschachtelten Kreuzvalidierung.

| Kandidat | Art | AUC [95 %] | gegen Sommernacht-Regel |
|---|---|---|---|
| LR Kennzahlen + LSTM-Embedding | gelernt | **0,89** [0,78; 0,98] | +0,04, nicht unterscheidbar |
| Sommer-Nachtdurchfluss | Regel | 0,88 [0,73; 0,99] | +0,03, nicht unterscheidbar |
| README `continuous_flow` (Sommer-Median Durchfluss) | Regel | 0,85 [0,69; 0,98] | ±0 |
| Sommernacht-Regel (Anteil Nächte mit Durchfluss) | Regel | 0,85 [0,67; 0,98] | Bezug |
| README `excess_rt` (Winter-Rücklauf) | Regel | 0,84 [0,68; 0,96] | −0,01 |
| LSTM-Embedding allein | gelernt | 0,84 [0,71; 0,94] | −0,01 |
| LR Kennzahlen | gelernt | 0,79 [0,58; 0,97] | −0,06 |
| Netzvergleich-Score Winter 23/24 | Flottenvergleich | 0,73 [0,55; 0,90] | −0,12 |
| Abkühlung bei 5 °C (NB 17) | Normkennzahl | 0,68 [0,47; 0,87] | −0,17 |
| K-Means „schlechter“ | Clustering | 0,67 [0,51; 0,83] | −0,18, belegt schlechter |

**Alle Erkenner des Projekts:** Fürs Ventil laufen 27 Kandidaten mit. Dazu gehören:
- Stationsbilder (NB 13), Ternär und Fallsammlung (NB 12),
- Kurzschluss-Zeitanteil (NB 04, 09, 10), Persistenzanteile (NB 10), Schweregrad (NB 11),
- Tagestypen (NB 06), Potenzial (NB 27), Vergleichsgruppen (`23_nachbarn`),
- Random Forest und XGBoost auf allen Merkmalen (NB 22).

Jeder Kandidat wird gepaart mit der Sommernacht-Regel auf den 53 Zählern verglichen, mit Holm über alle 27:
- **Über Raten:** 15 Kandidaten. Vorn liegen Paket-Modell (0,89), Sommer-Nachtdurchfluss (0,88) und die
  **Schweregrad-Punkte aus NB 11** (0,87). Keiner ist belegt besser als die Regel.
- **Bäume:** Random Forest (0,77) und XGBoost (0,75) sind auch mit allen Merkmalen nicht besser. XGBoost ist belegt
  schlechter als die Regel.
- **Flottenvergleiche** liegen bei 0,67 bis 0,74: Netzvergleich, Vergleichsgruppen, Potenzial, K-Means,
  Kennliniensteigung, Durchflussanteil der Modulation.
- **Eine unruhige Kennlinie** (Residuenstreuung, NB 13) spricht **gegen** ein Ventil (0,39). Ein offenes Ventil
  läuft gleichmäßig durch.

**Dämmung** (in der Haupttabelle 18 von 42; paarweise mit allen Kandidaten 22 von 53):
- **Nur das Paket-Modell ist besser als Raten.** Das gilt auch, wenn alle Kandidaten mitlaufen.
- **Flottenmaße zeigen die umgekehrte Richtung:** Netzvergleich (0,38), Vergleichsgruppen (0,37), Potenzial (0,39)
  und Anteil Rücklauf über 50 °C (0,30) sind belegt schlechter als der Bezug.
- **Was das heißt:** Ein Dämmungsbefund kommt eher bei Stationen vor, die im Netz **gut** aussehen. Der Hinweis
  „Dämmung prüfen“ ist statistisch erkennbar, aber physikalisch nicht erklärt.

**Dämmung im Einzelnen** (18 von 42):
- **Paket-Modell:** Die logistische Regression auf Kennzahlen + LSTM erreicht 0,75 [0,58; 0,89]. Sie ist
  als einzige nach Holm besser als Raten.
- **Gegen die Kennzahlen allein:** nicht belegt besser (+0,06).
- **Deutung in NB 22:** Sie nahm an, ungedämmte Leitungen erhöhten die Nachtspreizung im Sommer. Das hält
  nicht: Mit Dämmungsbefund ist die Nachtspreizung kleiner (AUC 0,29 in der vorab festgelegten Richtung).

**Überdimensionierung** (9 von 35):
- **Regel mit dem Vertrag vor der Begehung:** Eine niedrige Auslastung erreicht 0,78 [0,53; 0,98].
- **Gegen den Anschlusswert:** belegt besser (+0,12 [0,02; 0,24]).
- **README-Regel `oversized_contract`:** liegt bei Raten (0,51). Sie nimmt den Anschlusswert, und der
  ist oft schon der neue Vertrag.

**Ventil als Entscheidung**, Basisrate 21 %:

| Entscheidung | Ja | richtig | Trefferquote |
|---|---|---|---|
| Netzvergleich auffällig 23/24 | 4 | 4 (100 %) | 36 % |
| Klasse „Regelventil tauschen“ (p ≥ 0,5) | 12 | 8 (67 %) | 73 % |
| Sommernacht-Regel ≥ 0,5 | 14 | 9 (64 %) | 82 % |
| README `continuous_flow` (25 l/h) | 15 | 8 (53 %) | 73 % |
| README `excess_rt` (48 °C) | 32 | 10 (31 %) | 91 % |

**Gegenprobe mit neuen Daten.** Das Paket wurde unverändert auf Winter 24/25 und Sommer 2025
angewendet:
- **Ventil getauscht** (8 Zähler mit Befund und vorherigem Verdacht): Der Verdacht sinkt im Median von
  0,81 auf 0,37 (Wilcoxon p = 0,016).
- **Nie begangene Verdachtsfälle** (12): Der Verdacht bleibt, 0,76 → 0,61, keine belegte Änderung.
- **68956351:** fällt von 1,00 auf 0,09.

**Was das heißt:**
- **Ein offenes Ventil ist gut erkennbar, mit einfachen Mitteln.** Das Modell ist nicht belegt besser
  als die Sommernacht-Regel. Es braucht aber den Sommer nicht und ist deshalb das Ventil-Modell für
  Folie 5. Die Regel steht als Gegenprobe daneben.
- **Regeln gehören in jeden Vergleich.** Die erste Regel des Projekts (README) ist so gut wie das beste
  Modell, sobald sie auf dem richtigen Zeitraum rechnet.
- **Clustering und Flottenvergleiche erkennen das Ventil schwächer.** Sie messen „schlechter als
  andere“, und das ist nur zur Hälfte ein Ventil. Der Netzvergleich ist dafür das genaueste Signal, wenn
  er anschlägt.

## Ergebnis C: Fehler unterteilen und empfehlen

| Klasse (Folie 5) | Handlung (Aufgabenstellung) | Woraus | gegen Befund |
|---|---|---|---|
| Regelventil tauschen | Reparatur | Ventil-Modell, p ≥ 0,5 | 8 von 12 richtig, Trefferquote 73 % |
| Regelparameter optimieren | Regelungsoptimierung | K-Means „schlechter“ ohne Ventilverdacht | 3 begangene, keiner mit Ventilbefund |
| kein Handlungsbedarf | – | K-Means „Optimum“ | 3 von 39 mit Ventilbefund |
| Hinweis Überdimensionierung | Kapazitätsanpassung | Auslastungsregel | 6 von 7 richtig |
| Hinweis Dämmung | Reparatur (Dämmung) | Dämmungsmodell | 12 von 15 richtig |

Das Fehlerbild „ventil“ des Netzvergleichs und die Klasse passen mäßig zusammen (Kappa 0,46). Alle 8
Netz-Ventilfälle stehen auch in der Klasse; die Klasse findet mehr, der Netzvergleich ist strenger.

**Dringlichkeit in der Empfehlung** (Vorschlag für die Empfehlungsliste):
- **hoch:** Reparatur, bestätigt durch das Netz-Fehlerbild „ventil“ oder mit p ≥ 0,8.
- **mittel:** übrige Reparatur und Regelungsoptimierung.
- **niedrig:** nur Hinweise (Kapazität, Dämmung, Daten prüfen).
- **Reihenfolge innerhalb der Stufe:** zuerst Stationen mit einer Verschlechterung im Tagesmonitor in der
  letzten Heizperiode, dann nach dem Optimierungspotenzial (Abstand zum besten Viertel), dann nach dem
  Ventilverdacht.

Eine Verschlechterung hebt die Stufe nicht. Im Winter 24/25 hatte fast jede zweite Station eine, und vor
Begehungen mit Befund gab es nicht mehr davon als bei Kontrollen (`alarme.ipynb`). Die Stufen sind
gesetzt, nicht gelernt.

## Das Monitoring-Modell gegen das LSTM

Im Projekt gibt es zwei vollständige Systeme:

| | Monitoring-Modell (Kennlinien-Strang) | LSTM-Kette (Modell-Strang) |
|---|---|---|
| Notebooks | 14, `tagesmonitor`, `netzvergleich`, `alarme`, 24, 25, 27; Stationsblatt | 18 bis 23 |
| Alarm | Tagesmonitor: Kennlinie + CUSUM | Prognose-LSTM + Schwelle |
| Fehler erkennen | Netzvergleich je Kernwinter | Kennzahlen + LSTM-Embedding → LR |
| Unterteilen und Reihenfolge | Fehlerbild, Priorität hoch/mittel/niedrig | Klassen nach Folie 5 |

Hier stehen sie Kopf an Kopf, jeweils gepaart auf denselben Fällen bzw. Stationen (Notebook 32, Abschnitt 4b):

| Aufgabe | Monitoring | LSTM-Kette | gepaart | besser |
|---|---|---|---|---|
| Alarm: Begehungen (60 Tage) | **33/43** gegen 53 %, p = 0,001 | 16/43 (Schwelle), 24/43 (CUSUM) | 17 zu 0 Fälle, p < 0,001; gegen CUSUM 13 zu 4, p = 0,049 | **Monitoring** |
| Alarm: erste 14 Tage | **18/39**, p = 0,003 | 7/39, kein Signal | – | **Monitoring** |
| Alarm: plötzliche Fehler | nicht prüfbar | **Bypass 84 %**, Fühler 43 % | – | **LSTM** |
| Ventilfall 68956351 | **2 Tage** | 7 bzw. 4 Tage | – | Monitoring |
| Ventil erkennen (AUC) | Netzvergleich 0,73 | **0,89** | +0,16 [+0,02; +0,31] | **LSTM** |
| Dämmung erkennen (AUC) | Netzvergleich 0,38 | **0,75** | +0,37 [+0,12; +0,61] | **LSTM** |
| Entscheidung Ventil | Fehlerbild „ventil“: 4 von 4 richtig, findet 36 % | Klasse: 8 von 12 richtig, findet 73 % | – | ergänzen sich |
| Priorität | „hoch“: 1 begangene Station; „hoch oder mittel“: 32 % mit Ventilbefund (Basisrate 21 %) | – | – | trennt kaum |

**Was das heißt:**
- **Beim Alarm gewinnt das Monitoring-Modell.** Es merkt kleine, bleibende Veränderungen.
- **Beim Erkennen gewinnt die LSTM-Kette.** Der Netzvergleich misst „schlechter als die anderen“, das ist nur zur
  Hälfte ein Ventil.
- **Die beste Lösung kombiniert beide:**
  - Alarm aus dem Tagesmonitor, dazu das LSTM für plötzliche Fehler,
  - Klasse aus der LSTM-Kette,
  - Netzvergleich als Bestätigung.

## Haus oder Netz

Sechs Notebooks haben das Netz untersucht: 17 (Abschnitt 15), `23_nachbarn`, 24, 28, 30 und die Vorarbeit zu 22.
Notebook 32 (Abschnitt 3b) prüft das Netz zusätzlich als Kandidat, mit dem logischen Graphen aus `Nodes_Edges.ods`
(Nachbarn bis zwei Kanten).

| Kandidat | Ergebnis |
|---|---|
| Tagesmonitor ohne gemeinsame Nachbar-Alarme (NB 24) | 34/43 statt 33/43, Fall für Fall nicht unterscheidbar |
| Tagesmonitor, Nachbarn abgezogen | 30/43, etwas schlechter |
| Tagesmonitor, Netzmedian abgezogen | 25/43, **belegt schlechter** (die Begehungen kamen als Welle; der Abzug nimmt ihre Wirkung heraus) |
| Nachbarn: Sommer-Durchfluss bzw. Ventilverdacht → eigenes Ventil | AUC 0,44 bzw. 0,42, belegt schlechter als die eigene Regel |
| Paket-Modell + Nachbar-Merkmale | Ventil +0,004, Dämmung −0,02: keine Verbesserung |
| Vorlauf unter dem Netz (Strangende) → Ventil | 0,20, also umgekehrt: Stationen mit offenem Ventil haben einen **wärmeren** Vorlauf, weil durchlaufendes Wasser die Zuleitung warm hält |

**Was das heißt:**
- **Die Fehler sitzen im einzelnen Haus.** Offene Ventile häufen sich nicht in Strängen.
- **Das Netz zählt nur als Ganzes:** Wetter, Vorlauf, Begehungswellen. Das fangen Kennlinie und Tagesmonitor schon ab.

## Zusammenfassung

Verglichen wurden 15 Wächter, 27 Erkenner und die Netz-Varianten, also jedes Modell des Projekts, das einen
Tagesalarm oder einen Wert je Station liefert. Nur GNN und Bayes fehlen, weil ihre Eingaben hier nicht vorliegen.
Das Monitoring-Modell gewinnt beim Alarm, die LSTM-Kette beim Erkennen. Das Netz verbessert keins von beiden.

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
| `30_gnn_entwurf` | braucht die Kanten- und Positionsdateien aus Notebook 16 in `notebooks/` | eigenes Ergebnis: kleiner Gewinn, kein Strang-Effekt; dieselbe Frage prüft Abschnitt „Haus oder Netz“ mit Nachbar-Varianten |
| `31_bayes_diagnose` | braucht die Handtabellen unter `data/manual/` | eigenes Ergebnis: Ventil im Zweikampf AUC 0,92, mit einer Matrix, die noch nicht mit der ÜZ abgestimmt ist |
| `02_gesamtpipeline_…` | eigene Aufbereitung im Notebook, Stundenscores ohne Modul | eigenes Ergebnis: AUC 0,51, höchstens 2 von 10 Ereignissen |
| `01_kmeans`, `04_clustering_benchmark` | Profile über die ganze Historie, also auch nach der Begehung (Datenleck) | eigenes Ergebnis: kein Cluster trennt die Begehungen; verglichen wird K-Means aus NB 19 |
| `05_label_findung` | Label-Vorschlag, kein Erkenner | dieselben Größen stecken in den README- und Kennzahl-Regeln |
| `16_Netz`, `25_netzkarte` | Karte und Graphaufbau, kein Modell je Station | das Netz selbst ist als Kandidat geprüft (Abschnitt „Haus oder Netz“) mit dem logischen Graphen |
| `03`, `07`, `08`, `luecken` | messen die Wirkung der Begehungen oder bereiten Daten auf | sie liefern den Prüfstein |

## Grenzen

- **Kleine Fallzahlen:** 43 Begehungen und 11 Ventilfälle. Unterschiede unter etwa 0,1 AUC bzw. 5
  Fällen sind nicht zu sehen.
- **Parameter auf denselben Fällen gewählt:** Die Parameter für das gleiche Alarmbudget wurden auf den
  Fällen gewählt, an denen auch gemessen wird. Das gilt für alle Kandidaten gleich, die p-Werte sind
  leicht optimistisch.
- **Je ein Wächter nur halb geprüft:** Das Normalverhaltensmodell ist nicht mit eingerechneten Fehlern
  geprüft (es rechnet aus Zählerständen). Das LSTM ist nicht an echten Ereignissen belegt.
- **Keine Hysterese-Prüfung:** Für die Regelhysterese gibt es kein eigenes Befund-Label. Die README-Regel
  `control_hysteresis` lässt sich deshalb nicht prüfen.
- **Kein Test der Dringlichkeit:** Ein prospektiver Test wäre nötig: Stationen der Stufe hoch und gleich
  viele zufällige begehen, ohne zu wissen, welche welche ist.
