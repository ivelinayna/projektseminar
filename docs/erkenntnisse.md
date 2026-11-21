# Erkenntnisse

## Lernende Modelle und Modellvergleich

**1. Ohne Erwartung findet ein Modell keinen Fehler, nur Seltenes.** Die erste Pipeline suchte ohne Labels nach
ungewöhnlichen Stunden und kam gegen „Maßnahme ja oder nein“ auf eine AUC von 0,49 bis 0,53. Getragen hat erst der
Vergleich jeder Station mit ihrem eigenen Normalverhalten: mit der Kennlinie im Monitoring-Modell und mit der
Vorhersage im Prognose-LSTM (siehe [Was nicht getragen hat](nicht_getragen.md)).

**2. Erst ein strenger Prüfstand zeigt, was ein Modell kann.** Im ersten Prüfstand (Notebook 34) kam die Regression
auf Kennzahlen und LSTM-Zahlen beim Ventil auf eine AUC von 0,89. Dort hatte der Encoder die Teststationen gesehen,
und die Schwellen kamen aus den Testfällen. Im strengen Vergleich (Notebook 35), mit Modellwahl nur im Lernteil,
bleiben für das LSTM-Modell 0,84 (siehe [Erster Prüfstand](vergleich/pruefstand.md)).

**3. Eine einfache Regel ist oft gleich gut.** Beim Ventil liegt das LSTM-Modell mit 0,84 gleichauf mit der
Sommernacht-Regel (0,85). Bei der Kapazität ist die Regel mit 0,76 klar besser als jedes gelernte Modell (höchstens
0,53). Bei Gleichstand ist die erklärbare Regel gewählt, im Dashboard dient sie als Begründung.

**4. Das LSTM lohnt sich dort, wo Regeln fehlen.** An warmen Tagen rechnet nur das Prognose-LSTM: Es findet
eingebaute Dauerdurchflüsse von 150 l/h bei höchstens 5 % Fehlalarmen zu 78 %, das Wochenmittel zu 45 %. Bei der Dämmung findet nur das LSTM-Modell ein Muster (0,78
gegen 0,61 für die beste Einzelregel, nicht gesichert). Und unter den ersten 10 nach seinem Ventil-Score hatten 7
einen Ventilbefund, nach der Priorität des Monitoring-Modells 5 (Notebook 35, Test E).

**5. Überwachung braucht eine feste Referenz.** An echten Begehungen bemerkt das Normalverhaltensmodell aus
Notebook 18 bei gleich vielen Alarmen 30 von 43, das Prognose-LSTM 16 (Notebook 30, McNemar p = 0,001). Das
Prognose-LSTM sieht die letzten 7 Tage und gewöhnt sich an eine bleibende Veränderung. Dass es an der Referenz liegt
und nicht am Modelltyp, zeigt Notebook 35: Ein LSTM, das gegen eine feste Referenz prüft, findet einen eingebauten
Rücklauf +5 K praktisch so oft wie die Kennlinie des Monitoring-Modells (46 % gegen 47 %).

**6. Merkmale und Labels begrenzen mehr als das Verfahren.** XGBoost und Random Forest sind nirgends besser als die
logistische Regression oder die Regel (Notebook 29). Der Gewinn steckt in den Merkmalen: im Fingerabdruck bei Ventil
und Dämmung, in der richtig bezogenen Auslastung bei der Kapazität. Mit 11 Ventilfällen ist ein größeres Modell nicht
besser, sondern unruhiger.

**7. Nur der Ventiltausch hinterlässt eine Spur.** Nach dem Ventiltausch ändert sich der Durchfluss in Sommernächten
messbar (AUC 0,81, nach Holm gesichert). Nach Dämmung, Filterreinigung oder neu eingestelltem Durchfluss bleibt die
Station in den Zählerdaten gleich (Notebook 36). Sollwert (62 % der Begehungen) und Filter (47 %) sind eher Routine
als gefundene Fehler. Hier helfen bessere Begehungsprotokolle mehr als bessere Modelle: festhalten, ob etwas kaputt
war, nicht nur, was gemacht wurde.
