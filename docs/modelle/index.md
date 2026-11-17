# Lernende Modelle: Überblick

Dieses Kapitel beschreibt den Teil des Projekts, der mit lernenden Modellen arbeitet: zwei LSTM-Netze
(neuronale Netze für Zeitreihen mit Gedächtnis) und eine logistische Regression darauf. Es erklärt,
was gemacht wurde und warum. Den Code enthalten die Notebooks 27 bis 32 und 38 bis 41.

## Die Aufgabe

Folie 5 der Aufgabenstellung verlangt drei Dinge:

| Aufgabe | Frage | Antwort in diesem Kapitel |
|---|---|---|
| Alarm | Verändert sich eine Station gerade? | Prognose-LSTM als Wächter |
| Fehler erkennen | Hat eine Station einen Dauerfehler, etwa ein Ventil, das nicht schließt? | LSTM-Fingerabdruck mit logistischer Regression |
| Fehler unterteilen | Welche Handlung ist nötig: Regelventil tauschen, Regelung optimieren oder nichts? | Klasse je Station nach Folie 5 |

Die erste und die zweite Aufgabe brauchen verschiedene Modelle. Ein Alarm vergleicht eine Station mit
sich selbst und braucht keine Labels. Ein Dauerfehler zeigt sich dagegen nur im Vergleich mit anderen
Stationen, und dafür braucht es die Befunde der Begehungen.

## Der Weg in fünf Schritten

1. **[Daten, Labels und Messlatte](daten.md):** Aus den Stundenwerten und dem Begehungsprotokoll
   entstehen Labels je Fehlerart und Kennzahlen je Station. Eine einzige, vorher festgelegte Kennzahl
   je Fehlerart ist die Messlatte, die jedes Modell schlagen muss.
2. **[LSTM-Fingerabdruck](lstm.md):** Ein LSTM lernt ohne Labels, den nächsten Tag einer Station
   vorherzusagen. Dabei muss es jeden Tag in 8 Zahlen pressen. Gemittelt über einen Winter und einen
   Sommer ergibt das 16 Zahlen je Station, ihren Fingerabdruck.
3. **[Prognose-LSTM als Wächter](prognose.md):** Ein zweites LSTM sagt jeden Tag Rücklauf und
   Durchfluss aus den letzten 7 Tagen vorher. Weicht die Station anhaltend davon ab, gibt es einen Alarm.
4. **[Prüfung und Statistik](pruefung.md):** Wie alle Modelle fair geprüft wurden, warum AUC statt
   Accuracy, warum Bootstrap über Stationen und warum die Modelle nicht nach den Testwerten gewählt
   wurden.
5. **[Ergebnis](ergebnis.md):** Welches Modell im Dashboard welche Aufgabe übernimmt, was nicht
   getragen hat, und wer was gemacht hat.

## Wie es zusammenläuft

```
Notebook 00   Zählerexporte  ──►  saubere Stundenreihen je Zähler
     │
Notebook 27   Stundenwerte + Außentemperatur, Labels aus den Begehungen, Kennzahlen, Messlatte
     │
     ├──► Notebook 29   LSTM-Fingerabdruck: 8 Zahlen je Tag, 16 je Station
     ├──► Notebook 30   Prognose-LSTM: Vorhersage je Tag, Abweichung, Warnung
     │
Notebook 31   Fehlerart je Station: Regression und XGBoost, Klassen nach Folie 5
Notebook 32   Wächtervergleich mit dem Normalverhaltensmodell
Notebook 38   alle Modelle des Projekts auf einem Prüfstand
     │
Notebook 39   Endmodell: beide Ansätze neu gelernt, streng geprüft, als Pakete gespeichert
     │
src/dashboard_daten.py   wendet die Pakete auf aktuelle Daten an
     │
Notebook 40   Dashboard (HTML-Datei)
```

- **Notebook 27** baut die Datenbasis: Stundenwerte mit Außentemperatur, sechs Labels je begangener
  Station, zwölf Kennzahlen je Station, und prüft je Fehlerart eine einfache Kennzahl als Messlatte.
- **Notebook 29 und 30** enthalten zuerst die Vorversuche, die zu den endgültigen Netzen geführt haben,
  danach die Netze selbst.
- **Notebook 31** prüft verschiedene Verfahren je Fehlerart und bildet die Klassen nach Folie 5.
- **Notebook 32 und 38** vergleichen die Wächter und alle Modelle unter gleichen Bedingungen.
- **Notebook 39** lernt das Endmodell auf einer gemeinsamen Zeitachse neu, wählt das Modell nur im
  Lernteil und speichert drei Pakete für das Dashboard.
- **Notebook 40** zeigt das Ergebnis als Karte und Handlungsliste.
- **Notebook 41** prüft, ob die Maßnahmen bei den Begehungen überhaupt eine Spur in den Daten
  hinterlassen. Das erklärt, warum manche Fehlerarten nicht erkennbar sind.

## Das Ergebnis in Kürze

- Ein offenes Ventil ist erkennbar. Die gewählte Regression auf den 16 Zahlen des Fingerabdrucks kommt
  auf eine AUC von 0,84, gleichauf mit einer einfachen Regel aus der Sommernacht (0,85).
- Bei der Dämmung findet nur das gelernte Modell ein Muster (0,78 gegen 0,61 für die beste Einzelregel).
  Der Vorsprung ist knapp nicht gesichert, deshalb zeigt das Dashboard die Dämmung nur als Hinweis.
- Das Prognose-LSTM überwacht die warmen Tage, an denen die Kennlinie des Monitoring-Modells nicht
  rechnet. Eingebaute Dauerdurchflüsse von 150 l/h findet es zu 78 % bei 5 % Fehlalarmen.
- Filter, Durchfluss und Sollwert sind nicht erkennbar. Die Maßnahmen hinterlassen schon keine
  messbare Spur in den Zählerdaten.
