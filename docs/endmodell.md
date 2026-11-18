# Endmodell

- Diese Seite fasst Notebook 35 zusammen: Welches Modell beantwortet welche Frage der Aufgabenstellung, und wie kommt es ins Dashboard?
- Verglichen werden die zwei fertigen Ansätze des Projekts.
    - Monitoring-Modell: Kennlinie je Station mit CUSUM (Tagesmonitor), dazu Netzvergleich und Potenzial.
    - LSTM-Modell: Prognose-LSTM als Wächter, dazu die Fehlerklassen aus den LSTM-Zahlen.
- Der breite Vergleich aller Kandidaten steht unter [Modellvergleich](modellvergleich.md) (Notebook 34). Notebook 35 rechnet auf einer eigenen, strengeren Zeitachse. Die Zahlen unterscheiden sich deshalb, zum Beispiel bei den bemerkten Begehungen.
- Begriffe wie CUSUM, AUC oder Spreizung erklärt die Seite [Begriffe](begriffe.md).

## Fragen aus der Aufgabenstellung

- Überwachung: Hat sich eine Station verändert? Gemeint sind die Heizperiode, warme Tage und die Erfolgskontrolle nach einer Begehung.
- Einstufung nach Folie 5: Reparatur (Regelventil tauschen), Regelungsoptimierung (Regelparameter optimieren) oder kein Handlungsbedarf.
- Hinweise auf Dämmung und auf Kapazitätsanpassung (Anschluss zu groß).
- Lage im Netz: Stationsleistung, Netzeffizienz, dauerhaft schlechter Betrieb.
- Frühwarnung: Lässt sich ein Fehler vor seinem Auftreten erkennen?

## Wie geprüft wurde

- Gleiche Daten für beide Modelle: 93 Stundenreihen aus Notebook 00, 01.11.2021 bis 20.07.2026.
- Gleiche Zeitachse.
    - Lernen bis 31.01.2024, Kalibrieren 08.02. bis 31.03.2024.
    - Alarmlast im April und Mai 2024 eingestellt, Bezug ist die Schwelle h = 5 des Monitoring-Modells.
    - Test ab 08.06.2024. Teststationen und Testtage sind nie im Lernen.
- Labels nur aus Begehungen: 56 begangene Zähler mit 58 datierten Begehungen, 34 davon im September 2024. Die 37 nie begangenen Stationen gelten als unbekannt, nicht als gesund.
- Fünf Tests.

| Test | Frage | Grundlage |
|---|---|---|
| A | Bemerkt der Wächter echte Begehungen? | 43 Begehungen, Fenster −7 bis +60 Tage, Kontrollstationen |
| B | Findet der Wächter eingebaute Fehler? | 157 Fälle, 79 im Winter, 78 im Sommer |
| C | Erkennt das Modell die Fehlerart? | 53 begangene Stationen, fünffache Kreuzvalidierung über Stationsgruppen |
| D | Sagen Netzvergleich und Potenzial die Wirkung vorher? | begangene gegen nicht begangene Stationen |
| E | Taugt die Reihenfolge der Empfehlungen? | Ventilbefunde unter den ersten 10 von 53 |

## Gewähltes Modell je Frage

| Frage | Modell | Beleg aus Notebook 35 | Urteil |
|---|---|---|---|
| Veränderung in der Heizperiode, Erfolgskontrolle | Monitoring-Modell: Kennlinie + CUSUM, h = 5 | 18 von 43 Begehungen als „besser“ bemerkt, Kontrolle 24 %, p = 0,006 | Pilot mit Einschränkungen |
| Veränderung an warmen Tagen, plötzlicher Dauerdurchfluss | Prognose-LSTM + CUSUM, h = 10, auf allen Stationen gelernt | 78 % der Dauerdurchflüsse 150 l/h bei 5 % Fehlalarmen (Wochenmittel 45 %) | Pilot mit Einschränkungen |
| Reparatur, Regelventil tauschen | logistische Regression nur auf den 16 LSTM-Zahlen, gelernt auf begangenen Stationen | AUC 0,83 [0,64; 0,98], 8 von 11 bei 4 Fehlalarmen; mit Modellwahl im Lernteil 0,84 | Pilot |
| Hinweis Dämmung | dasselbe Modell | AUC 0,79 [0,65; 0,90]; mit Modellwahl im Lernteil 0,78; beste Einzelregel 0,61 | weitere Validierung nötig |
| Hinweis Kapazitätsanpassung | Regel „Spitzenlast zum alten Vertrag“ | AUC 0,76 [0,58; 0,93], 5 von 9 bei 1 Fehlalarm; gelernte Modelle höchstens 0,53 | Pilot mit Einschränkungen |
| Stationsleistung, Netzeffizienz | Monitoring-Modell: Netzvergleich je Kernwinter, Potenzial | Ventilfall 68956351 vor der Reparatur auf Rang 1 | Pilot, nur beschreibend |
| Regelungsoptimierung | keins | von keinem Modell getroffen | ungeeignet |
| Durchfluss, Sollwert, Filter, Regelhysterese als Ursache | keins | AUC 0,26 bis 0,57; Regelhysterese von keinem Wächter gefunden (höchstens 15 %) | nicht erkennbar |
| Frühwarnung | keins | Fehlerbeginn ist bei keinem Befund bekannt | nicht prüfbar |

- Die Werte in eckigen Klammern sind 95-%-Intervalle über Stationen.
- „Pilot“ heißt: brauchbar für den Probebetrieb, nicht für eine Entscheidung ohne Prüfung vor Ort.

## Warum diese Wahl

### Überwachung

- Heizperiode: Das Monitoring-Modell bemerkt Begehungen am deutlichsten. Das Prognose-LSTM liegt auf Höhe der Kontrolle (10 von 43 gegen 26 %).
- Im Winter findet das Monitoring-Modell eingebaute Fehler am besten, bei höchstens 10 % Fehlalarmen.

| eingebauter Fehler im Winter | Monitoring-Modell | LSTM mit fester Referenz | Prognose-LSTM |
|---|---|---|---|
| Rücklauf +5 K | 47 % | 46 % | 33 % |
| schleichend +5 K in 30 Tagen | 42 % | 38 % | 27 % |
| Fühler hängt | 46 % | 44 % | 38 % |
| Dauerdurchfluss 150 l/h | 77 % | 74 % | 73 % |
| Dauerdurchfluss 50 l/h | 53 % | 49 % | 53 % |

- Der Vorteil kommt von der festen Referenz, nicht vom Modelltyp. Ein LSTM, das wie der Monitoring-Wächter gebaut ist, liegt praktisch gleichauf (Vorsprung vor der Kontrolle 18 gegen 17 Prozentpunkte). Bei Gleichstand bleibt die einfachere, erklärbare Kennlinie.
- Fall für Fall ist der Vorsprung gegen das Prognose-LSTM nicht gesichert (McNemar p = 0,077 und 0,134).
- Warme Tage: Das Monitoring-Modell überwacht nur Oktober bis April. Nur das Prognose-LSTM rechnet im Sommer und schlägt dort das Wochenmittel (Dauerdurchfluss 50 l/h 44 % gegen 12 bis 14 %).
- Zusammen ergänzen sich beide im Winter bei plötzlichen Fehlern (über alle eingebauten Fehler 51 % auf 60 %), ohne mehr Fehlalarme. An echten Begehungen meldet das Prognose-LSTM aber nicht öfter als an Vergleichsstationen. Es bleibt deshalb an Heiztagen ein Hinweis.
- Ab wann bewertbar: Das Monitoring-Modell braucht 60 Heiztage mit 8 K Temperaturspanne, das LSTM rund 4 Wochen volle Stundenwerte (Median 29 Tage). 7 Stationen kann das Monitoring-Modell nicht einlernen, 6 davon auch das LSTM nicht.
- Der Wächter lernt auf allen Stationen, die er überwachen soll. Auf 17 nie gesehenen Stationen sagt das LSTM den Rücklauf um 0,54 K [0,20; 1,07] schlechter voraus.

### Fehlerart und Einstufung nach Folie 5

- Ventil: Mit Modellwahl im Lernteil (0,84) liegt das gelernte Modell gleichauf mit der festen Sommernacht-Regel (0,85; Unterschied −0,01 [−0,14; +0,12]). Besser ist es nicht belegt. Die Sommernacht-Regel bleibt im Hausfenster die Begründung.
- In der inneren Validierung lagen zwei Kandidaten gleichauf (Ventil beide 0,84, Dämmung 0,77 und 0,76). Gewählt ist der einfachere: Regression nur auf den 16 LSTM-Zahlen (`fv.ENDMODELL = "LR nur LSTM-Embedding"`). Er vermeidet auch ein Leck über das Vorwissen: Die 12 Kennzahlen wurden festgelegt, als die Begehungsprotokolle schon bekannt waren, die LSTM-Zahlen sind ohne Befund-Labels gelernt.
- Die zuerst gewählte Ventil-AUC von 0,88 war um etwa 0,05 zu optimistisch, weil der Sieger nach den Testwerten gewählt war. Für Aussagen gelten die Werte mit Modellwahl im Lernteil: Ventil 0,84, Dämmung 0,78.
- Das Fehlerbild „ventil“ des Monitoring-Modells dient als Bestätigung: 4 von 4 richtig, aber nur 4 von 11 Ventilfällen gefunden.
- Reihenfolge (Test E): Unter den ersten 10 nach Ventil-Score hatten 7 einen Ventilbefund. Die Priorität des Monitoring-Modells kommt auf 5, Zufall auf etwa 2.
- Gegenprobe nach der Reparatur: Wo das Ventil getauscht wurde, sinkt der Score von 0,71 auf 0,25 (p = 0,04). Er sinkt aber auch an begangenen Stationen ohne Ventilarbeit (0,27 auf 0,08, p < 0,001).
- Dämmung: Nur das gelernte Modell findet ein Muster. Der Vorsprung vor der besten Einzelregel (+0,17 [−0,04; +0,38]) ist knapp nicht gesichert, die Ursache physikalisch ungeklärt. Deshalb nur ein Hinweis mit niedriger Dringlichkeit.
- Kapazität: Das gelernte Modell scheitert, weil ihm die Auslastung zum alten Vertrag fehlt. Dieses Merkmal ist ausgeschlossen, weil 7 von 9 verkleinerten Verträgen schon den neuen Wert zeigen. Die Regel bleibt.
- Folie 5: Die Klasse Reparatur trifft das LSTM-Modell 8 von 11, das Monitoring-Modell 4 von 11. Regelungsoptimierung trifft keins: 24 bzw. 25 von 31 Fällen landen in „kein Handlungsbedarf“ (Kappa 0,16 und 0,19). Das Dashboard empfiehlt Regelungsoptimierung deshalb nicht.
- XGBoost bringt keinen Mehrwert. Bei der Dämmung schwankt es je nach Startwert zwischen 0,74 und 0,87.

### Lage im Netz

- Netzvergleich und Potenzial beschreiben die Station, sie sagen die Wirkung einer Begehung kaum vorher (Rangkorrelation 0,16, p = 0,30).
- Begangene Stationen kühlen im Winter 24/25 um 0,26 kWh/m³ besser, nicht begangene um 0,56 schlechter. Der Unterschied von 0,82 kWh/m³ ist nicht gesichert (p = 0,37).
- Das Dashboard zeigt deshalb Rang und Potenzial, aber keine Einspar-Schätzung in Euro oder Prozent.

## Modellpakete bauen und anwenden

- Ein Modellpaket enthält alles zum Anwenden: Gewichte oder Kennlinien, Skalierung, Kalibrierung, Schwelle, Lernzeitraum, Code-Stand und Prüfsummen.
- Die Pakete liegen in `models/` und sind gitignored.

| Paket | Inhalt | Rolle im Dashboard | Bauen ohne Notebook |
|---|---|---|---|
| `normalmodell` | Kennlinien des Monitoring-Modells je Station, CUSUM h = 5 | Alarm in der Heizperiode | `python -m src.normalmodell_waechter --bauen` |
| `prognose_lstm` | Prognose-LSTM, Kalibrierung je Station, CUSUM h = 10 | Alarm an warmen Tagen, Hinweis an Heiztagen | `python -m src.prognose_waechter --bauen --gegenprobe` |
| `fehlerklassen` | Regression auf LSTM-Zahlen für Ventil und Dämmung, Folie-5-Klassen, Regel Spitzenlast | Ventil-Score, Klasse, Hinweise Dämmung und Vertrag | `python -m src.fehlerklassen --bauen --gegenprobe` |

- Wo mit Befunden gelernt wird (Fehlerart), nur auf begangenen Stationen. Wo Normalverhalten gelernt wird (Wächter), auf allen Stationen.
- Notebook 35 speichert genau die geprüften Modelle (Abschnitt 17). Die Versionsnamen beginnen mit `nb34_`, weil Notebook 35 früher Notebook 34 hieß.
- Die jeweils andere Fassung liegt als `nb34gegenprobe_...` daneben (Prognose-LSTM nur auf begangenen Stationen, Fehlerklassen auf allen Stationen). Sie ist nicht aktiv. Umschalten mit `mp.setze_aktuell(name, version)`, alte Versionen bleiben erhalten.
- Nach dem Speichern prüft Notebook 35, dass die geladenen Pakete dasselbe liefern wie im Speicher.
    - Prognose-LSTM: größte Abweichung im z-Wert des Rücklaufs etwa 0,0000015.
    - Normalmodell: 313 Alarme, gleich viele wie im Notebook.
    - Fehlerklassen auf 91 Zählern: 61 kein Handlungsbedarf, 25 Regelventil tauschen, 4 Regelparameter optimieren, 1 nicht einstufbar.
- `python -m src.modellpaket` listet die gespeicherten Pakete.
- `python -m src.dashboard_daten` wendet die aktiven Pakete auf die aktuellen Daten an und schreibt nach `outputs/dashboard/`. Das Dashboard (Notebook 37) rechnet nichts selbst. Ablauf und Felder stehen unter [Dashboard](dashboard.md) und [Pipeline](pipeline.md).
- Die Handlungsliste sortiert nach Dringlichkeit, dann nach Ventil-Score.
    - hoch: Reparatur, wenn das Fehlerbild „ventil“ des Monitoring-Modells dazukommt.
    - mittel: Reparatur nach Ventil-Score.
    - niedrig: Kapazität, Dämmung, Daten prüfen.

## Grenzen

Die Fallzahlen sind klein: 43 Begehungen im Test, 11 Ventil- und 9 Vertragsfälle. Unterschiede unter etwa 0,1 AUC oder 5 Fällen sind nicht sichtbar, „nicht gesichert“ heißt hier meist, dass die Daten nicht reichen. Labels gibt es nur für begangene Stationen, der Beginn eines Fehlers ist nie bekannt, und die Begehungen waren nicht zufällig ausgewählt. Die feste Referenz des Monitoring-Modells veraltet: An 43 % der Testtage steht eines seiner Konten am Deckel, bei 31 von 81 Stationen mehr als die Hälfte der Zeit. Eingebaute Fehler zeigen, was ein Wächter grundsätzlich kann, nicht seine Trefferquote bei echten Fehlern. Der Ventil-Score ist eine Rangfolge, keine Wahrscheinlichkeit, und er sinkt nach jeder Begehung, nicht nur nach einem Ventiltausch. „Keine Meldung“ heißt nie „in Ordnung“. Die nächsten Schritte sind: die Kennlinie des Monitoring-Modells nach jeder Begehung und zu jeder Heizperiode neu lernen und Test A und B wiederholen, nie begangene Stationen mit hohem Ventil-Score gezielt begehen und eine mit der ÜZ abgestimmte Fehler-Symptom-Matrix (Notebook 38) aufbauen. Weitere Punkte stehen unter [Grenzen und offene Fragen](grenzen.md) und [Negativbefunde](negativbefunde.md).
