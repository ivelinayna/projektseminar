# Strenger Vergleich und Entscheidung

Der [erste Prüfstand](pruefstand.md) hat gezeigt, welches System welche Aufgabe besser löst, war aber an vier Stellen
zu optimistisch. Notebook 39 lernt deshalb die beiden fertigen Ansätze des Projekts aus denselben Daten neu und prüft
sie nach den Regeln aus [Prüfdesign und Statistik](pruefung.md):

- **Monitoring-Modell:** Kennlinie je Station mit CUSUM (Tagesmonitor), dazu Netzvergleich und Potenzial.
- **LSTM-Modell:** das [Prognose-LSTM](../modelle/prognose.md) als Wächter und die
  [Fehlerklassen](../modelle/klassen.md) aus dem [Fingerabdruck](../modelle/lstm.md).

Am Ende speichert Notebook 39 die gewählten Modelle als Pakete für das Dashboard.

## Wie geprüft wurde

- **Gleiche Daten:** die 93 Stundenreihen aus Notebook 00, 01.11.2021 bis 20.07.2026.
- **Gleiche Zeitachse:** Lernen bis 31.01.2024, Kalibrieren vom 08.02. bis 31.03.2024, Alarmlast im April und Mai
  2024 einstellen, Test ab 08.06.2024. Teststationen und Testtage sind nie im Lernen.
- **Labels nur aus Begehungen:** 56 begangene Zähler mit 58 datierten Begehungen. Die 37 nie begangenen Stationen
  gelten als unbekannt, nicht als gesund.
- **Fehlerart:** Der LSTM-Encoder wird in jedem der fünf Prüfteile ohne die Teststationen neu gelernt, und das Modell
  wird nur im Lernteil gewählt.

| Test | Frage | Grundlage |
|---|---|---|
| A | Bemerkt der Wächter echte Begehungen? | 43 Begehungen, Fenster −7 bis +60 Tage, Kontrollstationen |
| B | Findet der Wächter eingebaute Fehler? | 157 Fälle, 79 im Winter, 78 im Sommer |
| C | Erkennt das Modell die Fehlerart? | 53 begangene Stationen, fünffache Kreuzvalidierung über Stationsgruppen |
| D | Sagen Netzvergleich und Potenzial die Wirkung einer Begehung vorher? | begangene gegen nicht begangene Stationen |
| E | Taugt die Reihenfolge der Empfehlungen? | Ventilbefunde unter den ersten 10 von 53 |

## Gewähltes Modell je Frage

| Frage | Modell | Ergebnis in Notebook 39 | Urteil |
|---|---|---|---|
| Veränderung in der Heizperiode, Erfolgskontrolle | Monitoring-Modell: Kennlinie + CUSUM, h = 5 | 18 von 43 Begehungen als „besser“ bemerkt, Kontrolle 24 %, p = 0,006 | Pilot mit Einschränkungen |
| Veränderung an warmen Tagen, plötzlicher Dauerdurchfluss | Prognose-LSTM + CUSUM, h = 10, auf allen Stationen gelernt | 78 % der Dauerdurchflüsse von 150 l/h bei höchstens 5 % Fehlalarmen, Wochenmittel 45 % | Pilot mit Einschränkungen |
| Regelventil tauschen | logistische Regression nur auf den 16 LSTM-Zahlen | AUC 0,84 mit Modellwahl im Lernteil, gleichauf mit der Sommernacht-Regel (0,85) | Pilot |
| Hinweis Dämmung | dasselbe Modell | AUC 0,78 mit Modellwahl im Lernteil, beste Einzelregel 0,61 | weitere Validierung nötig |
| Hinweis Kapazitätsanpassung | Regel „Spitzenlast zum alten Vertrag“ | AUC 0,76 [0,58; 0,93], 5 von 9 bei 1 Fehlalarm, gelernte Modelle höchstens 0,53 | Pilot mit Einschränkungen |
| Stationsleistung, Netzeffizienz | Monitoring-Modell: Netzvergleich je Kernwinter, Potenzial | Ventilfall 68956351 vor der Reparatur auf Rang 1 | Pilot, nur beschreibend |
| Regelungsoptimierung | keins | von keinem Modell getroffen | ungeeignet |
| Durchfluss, Sollwert, Filter als Ursache | keins | AUC 0,26 bis 0,57 | nicht erkennbar |
| Frühwarnung vor einem Fehler | keins | der Beginn ist bei keinem Befund bekannt | nicht prüfbar |

Die Werte in eckigen Klammern sind 95-%-Intervalle über Stationen. „Pilot“ heißt: brauchbar für den Probebetrieb,
nicht für eine Entscheidung ohne Prüfung vor Ort.

## Warum diese Wahl

**Überwachung.**

- In der Heizperiode bemerkt das Monitoring-Modell die Begehungen am deutlichsten. Das Prognose-LSTM liegt auf Höhe der
  Kontrolle (10 von 43 gegen 26 %).
- An eingebauten Fehlern im Winter liegt das Monitoring-Modell vorn, zum Beispiel beim Rücklauf +5 K mit 47 % gegen 33 %.
  Der Vorteil kommt von der festen Referenz, nicht vom Modelltyp: Ein LSTM, das wie das Monitoring-Modell gegen eine feste
  Referenz prüft, liegt praktisch gleichauf (46 %). Bei Gleichstand bleibt die einfachere, erklärbare Kennlinie.
- An warmen Tagen rechnet nur das Prognose-LSTM. Dort schlägt es das Wochenmittel deutlich.
- Zusammen ergänzen sich beide im Winter: Über alle eingebauten Fehler steigt die Trefferquote von 51 % auf 60 %,
  ohne mehr Fehlalarme. An echten Begehungen meldet das Prognose-LSTM aber nicht öfter als an Vergleichsstationen. An
  Heiztagen bleibt es deshalb ein Hinweis.

**Fehlerart und Klasse.**

- Ventil: Mit Modellwahl im Lernteil liegt das gelernte Modell gleichauf mit der festen Sommernacht-Regel
  (Unterschied −0,01 [−0,14; +0,12]). Besser ist es nicht belegt. Im Hausfenster des Dashboards wird ein Verdacht
  deshalb mit der Sommernacht-Regel begründet, die ein Techniker nachvollziehen kann.
- Warum die Regression nur auf den LSTM-Zahlen gewählt ist und die zuerst genannten 0,88 nicht gelten, steht unter
  [Prüfdesign und Statistik](pruefung.md#warum-das-modell-im-lernteil-gewahlt-wird).
- Reihenfolge (Test E): Unter den ersten 10 Stationen nach Ventil-Score hatten 7 einen Ventilbefund. Nach der
  Priorität des Monitoring-Modells sind es 5, Zufall wären etwa 2.
- Folie 5: Die Klasse „Regelventil tauschen“ trifft das LSTM-Modell bei 8 von 11 Ventilfällen, das Monitoring-Modell bei 4
  von 11. Dessen Fehlerbild „ventil“ ist dafür sehr genau (4 von 4 richtig) und dient als Bestätigung. „Regelparameter
  optimieren“ trifft keins der beiden.
- Dämmung: Nur das gelernte Modell findet ein Muster. Der Vorsprung vor der besten Einzelregel (+0,17 [−0,04; +0,38])
  ist knapp nicht gesichert, die Ursache physikalisch ungeklärt. Deshalb nur ein Hinweis mit niedriger Dringlichkeit.
- Kapazität: Dem gelernten Modell fehlt die Auslastung zum alten Vertrag, deshalb bleibt die Regel.

**Lage im Netz.** Netzvergleich und Potenzial beschreiben eine Station, sagen die Wirkung einer Begehung aber kaum
vorher (Rangkorrelation 0,16, p = 0,30). Das Dashboard zeigt deshalb Rang und Potenzial, aber keine Einspar-Schätzung.

## Vom Modell ins Dashboard

Gelernt wird im Notebook, gespeichert als Paket, angewendet auf die aktuellen Daten, angezeigt im Dashboard. Ein Paket
enthält nicht nur Gewichte, sondern alles, was zum Anwenden gehört: Merkmalsliste, Skalierung, Kalibrierung,
Schwellen, Lernzeitraum und Prüfsummen. Notebook 39 speichert drei Pakete:

| Paket für | Inhalt | Rolle im Dashboard |
|---|---|---|
| das Monitoring-Modell | Kennlinie je Station, CUSUM h = 5 | Meldungen in der Heizperiode |
| das Prognose-LSTM | Netz, Kalibrierung je Station, CUSUM h = 10 | Meldungen an warmen Tagen, Hinweis an Heiztagen |
| die Fehlerklassen | Regression auf den LSTM-Zahlen für Ventil und Dämmung, K-Means, Regel für die Kapazität | Ventil-Score, Klasse nach Folie 5, Hinweise |

- Wo mit Befunden gelernt wird (Fehlerart), nur auf begangenen Stationen. Wo Normalverhalten gelernt wird (Wächter),
  auf allen Stationen, die überwacht werden sollen.
- Nach dem Speichern prüft Notebook 39, dass die geladenen Pakete dasselbe liefern wie die Modelle im Speicher.
- Wie die Pakete auf aktuelle Daten angewendet werden und was das Dashboard daraus macht, steht unter
  [Dashboard](../ergebnisse_dashboard.md).

## Grenzen

- **Wenige Fälle:** 43 Begehungen im Test, 11 Ventil- und 9 Vertragsfälle. Unterschiede unter etwa 0,1 AUC oder 5
  Fällen sind nicht sichtbar. „Nicht gesichert“ heißt hier meist, dass die Daten nicht reichen.
- **Labels:** Es gibt sie nur für begangene Stationen. „Gemacht“ heißt nicht „war kaputt“, leere Kästchen werden als
  „nein“ gelesen, und die Begehungen waren nicht zufällig ausgewählt. Der Beginn eines Fehlers ist bei keinem Befund
  bekannt, echte Frühwarnung lässt sich deshalb nicht prüfen.
- **Eingebaute Fehler** zeigen, was ein Wächter grundsätzlich kann, nicht seine Trefferquote bei echten Fehlern.
- **Der Ventil-Score** ist eine Rangfolge, keine Wahrscheinlichkeit. Er sinkt nach jeder Begehung, nicht nur nach
  einem Ventiltausch. „Keine Meldung“ heißt nie „in Ordnung“.
- **Rückblickend geprüft:** Alle Zahlen stammen aus vorhandenen Daten. Der nächste Schritt ist ein Test nach vorn:
  nie begangene Stationen mit hohem Ventil-Score gezielt begehen und das erwartete Ergebnis vorher festlegen.
