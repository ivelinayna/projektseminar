# Lernplan

Jede Phase hat ein eigenes Notebook (`A_frage_und_daten.ipynb`, `B_baseline.ipynb`, …).
Am Ende jeder Phase kommt ein Abschnitt in `docs/lernpfad.md`.

## A · Frage und Daten

- [x] 1. Fragestellung festlegen: Was wird bewertet, was ist Eingabe, was ist Label, wie wird aufgeteilt?
- [x] 2. Eine Zählerreihe laden und verstehen: Spalten, Einheiten, Stundenraster
- [x] 3. Datenqualität für alle Zähler: Lücken, negative und Fehlwerte, Abdeckung
- [x] 4. Außentemperatur dazu, Heiztage
- [x] 5. Begehungen und Labels zeitlich einordnen: Stichtag, nur Daten vor der Begehung, Leakage
- [x] Report: Abschnitt A

## B · Erste Baseline mit scikit-learn

- [x] 6. Wenige Kennzahlen je Station von Hand
- [x] 7. Regel ohne Lernen und logistische Regression, Leave-one-out, AUC
- [x] 8. Ehrlich prüfen: verschachtelte Kreuzvalidierung, Bootstrap, Straßen auslassen, Zufallstest
- [x] Report: Abschnitt B

## C · Vom Tag zur Sequenz

- [x] 9. Tage als Tensor (Tage × 24 Stunden × Kanäle), Skalierung
- [x] 10. „Nächsten Tag vorhersagen“ mit Baselines: wie gestern, Mittel der letzten 7 Tage, Ridge
- [x] 11. Aufteilung für Zeitreihen: ganze Wochen, Testzeit danach
- [x] Report: Abschnitt C

## D · Das erste LSTM

- [x] 12. PyTorch-Grundlagen: Tensor, `nn.LSTM`, Trainingsschleife, Loss
- [x] 13. LSTM-Vorhersage trainieren: Lernkurve, Overfitting, Early Stopping, Vergleich mit den Baselines
- [x] 14. Engpass von 8 Zahlen: Encoder–Decoder und Embedding
- [x] Report: Abschnitt D

## E · Embedding zur Fehlererkennung

- [x] 15. Embedding je Station, Wiedererkennung über zwei Winter
- [x] 16. Logistische Regression auf Embedding gegen Kennzahlen gegen Regel, auch nur Winter
- [x] 17. Varianten vergleichen und ohne Labels auswählen; warum kein LSTM direkt auf die Labels
- [x] Report: Abschnitt E

## F · Der Wächter

- [x] 18. Prognose aus 7 Tagen, z-Werte je Station, Warnregel
- [x] 19. Eingerechnete Fehler und Fehlalarmrate
- [x] 20. Vergleich mit dem Normalverhaltensmodell (Notebook 20) und Grenzen
- [x] Report: Abschnitt F

## G · Ergebnis nach Folie 5

- [x] 21. Kennzahlen für alle 96 Zähler, auch die nie begangenen
- [x] 22. Ventil-Verdacht mit der Nachtdurchfluss-Regel, Grenze für die Klasse
- [x] 23. Optimum oder schlechter mit K-Means, Gegenprobe an den Befunden
- [x] 24. Klassen nach Folie 5, Alarm aus dem Wächter, Vergleich mit Notebook 31
- [x] Report: Abschnitt G

## Abschluss

- [x] Ergebnisse gegen die Notebooks 27 bis 32 und die Vorarbeit stellen, Abweichungen erklären
