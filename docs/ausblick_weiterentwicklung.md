# Weiterentwicklung

## Lernende Modelle

- **Bessere Begehungsprotokolle.** Der größte Hebel liegt vor dem Modell. Festhalten, ob etwas kaputt war und nicht nur,
  was gemacht wurde, und wann der Fehler vermutlich begonnen hat. Erst dann lassen sich Filter, Durchfluss und
  Sollwert als Fehlerart prüfen und eine Frühwarnung überhaupt testen (Notebook 36). Eine Vorlage und ein Befehl zum
  Einlesen liegen bereit (siehe [Betrieb bei der ÜZ](installation/betrieb.md#2-begehungsprotokoll)).
- **Mehr Fälle.** Jede protokollierte Begehung ist ein neues Label. Bei 11 Ventilfällen sind Unterschiede unter etwa
  0,1 AUC nicht sichtbar. Mit mehr Fällen lassen sich auch die Hinweise auf Dämmung und Kapazität sicherer prüfen.
- **Dämmung physikalisch erklären.** Die Abkühlrate im Stillstand ist ein erster Hinweis (AUC 0,69, nicht gesichert,
  Notebook 36). Sie sollte an neuen Daten mit vorher festgelegter Richtung geprüft werden. Dazu fehlt das Baujahr der
  Gebäude, bisher nur bei 14 Stationen bekannt. Es ist der letzte ungeprüfte Faktor, der das Muster des LSTM-Modells
  erklären könnte.
- **Winter 2025/26 auswerten,** sobald Daten für mehr Zähler vorliegen, und die Modelle danach nach den Regeln des
  [Probebetriebs](ausblick_probebetrieb.md) neu lernen.
- **Weitere Teilnetze.** Die Pakete enthalten alles, was zum Anwenden gehört. Das Prognose-LSTM muss neue Stationen
  aber erst kalibrieren, und die Fehlerklassen müssten mit Begehungen aus dem neuen Netz geprüft werden, bevor die
  Empfehlungen dort gelten.
