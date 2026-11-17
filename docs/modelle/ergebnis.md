# Ergebnis, Grenzen und Aufteilung

## Was entschieden wurde

Notebook 39 lernt die beiden fertigen Ansätze des Projekts aus denselben Daten neu und prüft sie nach den
Regeln aus [Prüfung und Statistik](pruefung.md). Das Monitoring-Modell rechnet mit Kennlinie, CUSUM und
Netzvergleich, die lernenden Modelle aus diesem Kapitel bilden das LSTM-Modell. Keiner der beiden
Ansätze ist allein besser. Für die lernenden Modelle ergibt sich:

| Aufgabe | Modell | Ergebnis (Notebook 39) | Urteil |
|---|---|---|---|
| Veränderung an warmen Tagen, plötzlicher Dauerdurchfluss | Prognose-LSTM mit CUSUM (h = 10) | eingebaute Dauerdurchflüsse von 150 l/h im Sommer zu 78 % bei höchstens 5 % Fehlalarmen, das 7-Tage-Mittel zu 45 % | Pilot mit Einschränkungen |
| Veränderung in der Heizperiode | Monitoring-Modell, Prognose-LSTM ergänzt | zusammen 60 % statt 51 % der eingebauten Fehler, ohne mehr Fehlalarme | Prognose-LSTM als Hinweis |
| Regelventil tauschen | Regression nur auf den 16 LSTM-Zahlen | AUC 0,84 mit Modellwahl im Lernteil, gleichauf mit der Sommernacht-Regel (0,85) | Pilot |
| Hinweis Dämmung | dasselbe Modell | AUC 0,78, beste Einzelregel 0,61, Vorsprung knapp nicht gesichert | weitere Validierung nötig |
| Hinweis Kapazitätsanpassung | Regel „Spitzenlast zum alten Vertrag“ | AUC 0,76, gelernte Modelle höchstens 0,53 | Pilot mit Einschränkungen |
| Regelungsoptimierung, Filter, Durchfluss, Sollwert | keins | AUC 0,26 bis 0,57 | nicht erkennbar |

- **Reihenfolge:** Unter den ersten 10 Stationen nach Ventil-Score hatten 7 einen Ventilbefund. Nach der
  Priorität des Monitoring-Modells sind es 5, Zufall wären etwa 2.
- **Folie 5:** Die Klasse „Regelventil tauschen“ trifft das LSTM-Modell bei 8 von 11 Ventilfällen, das
  Monitoring-Modell bei 4 von 11. „Regelparameter optimieren“ trifft keins der beiden. Das Dashboard
  empfiehlt diese Klasse deshalb nicht.
- „Pilot“ heißt: brauchbar für den Probebetrieb, nicht für eine Entscheidung ohne Prüfung vor Ort.

Die vollständige Tabelle mit beiden Ansätzen steht unter [Endmodell](../endmodell.md).

## Vom Modell ins Dashboard

Gelernt wird im Notebook, gespeichert als Paket, angewendet im Modul, angezeigt im Dashboard. Notebook
39 speichert drei Pakete in `models/`: `normalmodell` (Monitoring-Modell), `prognose_lstm` (Wächter) und
`fehlerklassen` (Fingerabdruck, Regression und Klassen nach Folie 5). Ein Paket enthält nicht nur
Gewichte, sondern alles, was zum Anwenden gehört: Merkmalsliste, Skalierung, Schwellen, Zeiträume und
Version. `python -m src.dashboard_daten` wendet die Pakete auf die aktuellen Daten an, Notebook 40 baut
daraus eine HTML-Datei. Das Dashboard selbst lernt nichts neu.

Im Hausfenster wird ein Ventilverdacht mit der Sommernacht-Regel begründet, nicht mit den LSTM-Zahlen.
„LSTM-Zahl 5 ist hoch“ hilft keinem Techniker vor Ort.

## Was nicht getragen hat

**Unüberwachte Anomaliescores (Notebook 12).** Die erste Pipeline im August suchte ohne Labels nach
ungewöhnlichen Stunden: Isolation Forest, LOF, PCA und Abstand zu K-Means-Clustern. Gegen das Label
„Maßnahme ja/nein“ lag die AUC bei 0,49 bis 0,53, von 10 Ereignissen wurden höchstens 2 gefunden.
„Ungewöhnlich“ ist nicht „defekt“: Ohne Erwartung, was für diese Station bei diesem Wetter normal ist,
findet ein Score nur seltene Betriebszustände. Daraus folgten die Labels je Fehlerart und die Wächter,
die jede Station mit sich selbst vergleichen.

**Einstufung mit K-Means (Notebook 28).** K-Means teilt die Stationen nach ihrem Regelverhalten im Winter
in „Optimum“ (70) und „schlechter“ (18), mit einer Silhouette von 0,44. Die Gegenprobe gegen die
Ventilbefunde (p = 0,021) hält nach der Holm-Korrektur nicht (0,13). Die Klasse „Regelparameter
optimieren“, die darauf aufbaut, trifft in Notebook 39 keinen Befund. Das Dashboard empfiehlt sie
deshalb nicht.

**XGBoost (Notebook 31).** Gradient Boosting mit Wechselwirkungen ist nirgends besser als die
logistische Regression oder die Regel. Wechselwirkungen bringen −0,03 bis +0,05. Bei der Dämmung schwankt
die AUC je nach Startwert zwischen 0,74 und 0,87, und die wichtigsten Merkmale wechseln von Durchgang zu
Durchgang. Bei gut 50 Stationen ist ein Modell mit vielen Bäumen zu unruhig.

**Prognose-LSTM an echten Begehungen (Notebook 32).** An eingerechneten Fehlern findet das
Prognose-LSTM plötzliche Veränderungen gut. An echten Begehungen bemerkt es aber nicht mehr als an
Vergleichsstationen: 16 von 43 gegen 32 % (p = 0,26). Das Normalverhaltensmodell aus Notebook 20 bemerkt
30 von 43, Fall für Fall 15 zu 1 (McNemar p = 0,001). Ein möglicher Grund: Das LSTM bekommt die letzten
sieben Tage als Eingang, eine bleibende Veränderung wird so schnell Teil seiner Erwartung. Das Prognose-LSTM bleibt
deshalb auf die warmen Tage und plötzliche Fehler beschränkt.

**Erster Prüfstand zu optimistisch (Notebook 38).** Der erste Vergleich aller Modelle ergab beim Ventil
0,89 für die Regression auf Kennzahlen und LSTM-Zahlen. Der Encoder hatte dort aber die Teststationen
gesehen, die Schwellen kamen von den Testfällen, und die Auslastung zum Anschlusswert war als Merkmal
dabei. Notebook 39 hat alles neu und streng gerechnet, mit 0,84 als Ergebnis.

**Varianten der Netze (Notebook 29 und 30).** Nicht gewählt wurden: ein Autoencoder, der den Tag nur
nachbildet (erkennt Stationen schlechter wieder), Lernen auf allen statt nur auf begangenen Stationen
(Vorgabe der Betreuung, der Unterschied ist klein), ein Engpass von 16 statt 8 Zahlen (bei den Befunden nicht besser) und das Vorhersagen
der Abweichung vom 7-Tage-Mittel (nur im Test knapp vorn). Ein einfacher Wächter ohne Netz bemerkt an den
Begehungen vor allem den Eingriff des Technikers selbst, nicht die Veränderung danach.

**Fehlerarten ohne Spur (Notebook 41).** Neue Kennzahlen aus der Physik, mit vorher festgelegter
Richtung, finden bei Filter, Durchfluss und Sollwert nichts Gesichertes. Der Grund liegt vor dem Modell:
Nur der Ventiltausch ändert nachher messbar etwas (Durchfluss in Sommernächten, AUC 0,81, nach Holm
gesichert). Nach Dämmung, Filterreinigung oder neu eingestelltem Durchfluss bleibt die Station in den
Zählerdaten gleich. Sollwert (62 % der Begehungen) und Filter (47 %) sind eher Routine als gefundene
Fehler. Hier würden bessere Begehungsprotokolle mehr helfen als bessere Modelle. Bei der Dämmung gibt es
einen ersten physikalischen Hinweis, die Abkühlrate im Stillstand (0,69, nicht gesichert).

## Grenzen

- **Wenige Fälle:** 43 Begehungen im Test, 11 Ventil- und 9 Vertragsfälle. Unterschiede unter etwa
  0,1 AUC sind nicht sichtbar.
- **Labels:** „Gemacht“ heißt nicht „war kaputt“, und leere Kästchen werden als „nein“ gelesen. Der Beginn
  eines Fehlers ist bei keinem Befund bekannt. Echte Frühwarnung lässt sich deshalb nicht prüfen.
- **Nie begangene Stationen** sind unbekannt, nicht gesund.
- **Rückblickend geprüft:** Alle Zahlen stammen aus vorhandenen Daten. Der nächste Schritt ist ein
  prospektiver Test: Stationen mit hohem Ventil-Score gezielt begehen und das Ergebnis vorher festlegen.

## Wer diesen Teil bearbeitet hat

Dieses Kapitel und die Modelle darin hat Dominik bearbeitet:

- **Notebooks:** 12 (Gesamtpipeline, August), 27 bis 32 (Modelldaten, Einstufung, LSTM-Fingerabdruck,
  Prognose-LSTM, XGBoost, Wächtervergleich), 38 (Modellvergleich), 41 (Merkmale und Erklärbarkeit),
  zusammen mit Ivelina 39 (Endmodell) und 40 (Dashboard).
- **Code in `src/`:** `fehlerklassen.py`, `prognose_waechter.py`, `finalvergleich.py`, `pruefstand.py`,
  `modellpaket.py`, `merkmalsbau.py`, `normalmodell_waechter.py`, zusammen mit Ivelina
  `dashboard_daten.py` und `dashboard_karte.py`.
