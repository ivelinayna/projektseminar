# Strenger Vergleich

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

## Ergebnis

Welches Modell für welche Frage gewählt wurde und warum, steht unter [Ergebnisse → Endmodell](../ergebnisse_endmodell.md).
Die Grenzen dieses Vergleichs stehen unter [Grenzen der Modelle](../grenzen_modelle.md).

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
