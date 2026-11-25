# Lernende Modelle

Dieser Abschnitt beschreibt die Modelle, die aus den Daten lernen: zwei LSTM-Netze (neuronale Netze für Zeitreihen
mit Gedächtnis), eine logistische Regression auf dem Fingerabdruck des einen Netzes, eine Einstufung mit K-Means und
eine Regel für die Kapazität. Er erklärt, was gemacht wurde und warum. Den Code enthalten die Notebooks 25 bis 29.
Wie diese Modelle geprüft und mit den übrigen Modellen des Projekts verglichen wurden, steht unter
*Modelle vergleichen*, beginnend mit [Prüfdesign und Statistik](../vergleich/pruefung.md).

## Die Aufgabe

Die Aufgabenstellung verlangt drei Dinge:

| Aufgabe | Frage | Antwort in diesem Abschnitt |
|---|---|---|
| Alarm | Verändert sich eine Station gerade? | Prognose-LSTM als Wächter |
| Fehler erkennen | Hat eine Station einen Dauerfehler, etwa ein Ventil, das nicht schließt? | LSTM-Fingerabdruck mit logistischer Regression |
| Fehler unterteilen | Welche Handlung ist nötig: Regelventil tauschen, Regelung optimieren oder nichts? | Klasse je Station |

Die erste und die zweite Aufgabe brauchen verschiedene Modelle. Ein Alarm vergleicht eine Station mit sich selbst und
braucht keine Labels. Ein Dauerfehler zeigt sich dagegen nur im Vergleich mit anderen Stationen, und dafür braucht es
die Befunde der Begehungen.

## Der Weg

1. **[Daten, Labels und Messlatte](daten.md):** Aus den Stundenwerten und dem Begehungsprotokoll entstehen Labels je
   Fehlerart und Kennzahlen je Station. Eine einzige, vorher festgelegte Kennzahl je Fehlerart ist die Messlatte, die
   jedes Modell schlagen muss.
2. **[LSTM-Fingerabdruck](lstm.md):** Ein LSTM lernt ohne Labels, den nächsten Tag einer Station vorherzusagen. Dabei
   muss es jeden Tag in 8 Zahlen pressen. Gemittelt über einen Winter und einen Sommer ergibt das 16 Zahlen je
   Station, ihren Fingerabdruck.
3. **[Prognose-LSTM als Wächter](prognose.md):** Ein zweites LSTM sagt jeden Tag Rücklauf und Durchfluss aus den
   letzten 7 Tagen vorher. Weicht die Station anhaltend davon ab, gibt es einen Alarm.
4. **[Fehlerart und Klasse je Station](klassen.md):** Eine logistische Regression je Fehlerart, K-Means für
   „Optimum oder schlechter“ und eine Regel für die Kapazität ergeben die Klasse.

## Wie es zusammenläuft

```
Notebook 00   Zählerexporte  ──►  saubere Stundenreihen je Zähler
     │
Notebook 25   Stundenwerte + Außentemperatur, Labels aus den Begehungen, Kennzahlen, Messlatte
     │
     ├──► Notebook 26   K-Means: Optimum oder schlechter
     ├──► Notebook 27   LSTM-Fingerabdruck: 8 Zahlen je Tag, 16 je Station
     ├──► Notebook 28   Prognose-LSTM: Vorhersage je Tag, Abweichung, Warnung
     │
Notebook 29   Fehlerart je Station, drei Klassen
     │
Notebook 30, 34   Vergleich mit den übrigen Modellen des Projekts
     │
Notebook 35   Endmodell: streng geprüft, als Pakete gespeichert
     │
src/dashboard_daten.py   wendet die Pakete auf aktuelle Daten an
     │
Notebook 37   Dashboard (HTML-Datei)
```

- **Notebook 25** baut die Datenbasis: Stundenwerte mit Außentemperatur, sechs Labels je begangener Station, zwölf
  Kennzahlen je Station, und prüft je Fehlerart eine einfache Kennzahl als Messlatte.
- **Notebook 26** stuft die Stationen ohne Label nach ihrem Regelverhalten ein.
- **Notebook 27 und 28** enthalten zuerst die Vorversuche, die zu den endgültigen Netzen geführt haben, danach die
  Netze selbst.
- **Notebook 29** vergleicht verschiedene Verfahren je Fehlerart und bildet die drei Klassen.
- **Notebook 30, 34 und 35** gehören zu *Modelle vergleichen*. Notebook 35 lernt das Endmodell auf einer gemeinsamen
  Zeitachse neu, wählt das Modell nur im Lernteil und speichert drei Pakete für das Dashboard.
- **Notebook 37** zeigt das Ergebnis als Karte und Handlungsliste.
- **Notebook 36** prüft, ob die Maßnahmen bei den Begehungen überhaupt eine Spur in den Daten hinterlassen. Das
  erklärt, warum manche Fehlerarten nicht erkennbar sind (siehe [Was nicht getragen hat](../nicht_getragen/negativbefunde.md#19-fehlerarten-ohne-messspur)).

Den Hauptweg zum Endergebnis bilden die Notebooks 25, 27, 28, 35 und 37. Die Notebooks 26, 29, 30, 34 und 36 sind
Vergleiche und Gegenproben. Sie begründen, warum das Endmodell so aussieht.

## Ausführen und Ablage

Die Notebooks laufen in dieser Reihenfolge. Jedes liest, was das vorige geschrieben hat:

| Schritt | liest | schreibt | Laufzeit (mit Grafikkarte) |
|---|---|---|---|
| Notebook 00 | Zählerexporte in `data/raw/` | Stundenreihen `data/processed/real_meters/`, `hast_features.csv` | unter 1 Minute |
| Notebook 25 | Stundenreihen, Begehungsprotokoll in `data/raw/`, Wetter (Cache `data/raw/weather/`) | `data/processed/modell_stunden.parquet`, `modell_labels.csv`, `modell_kennzahlen.csv` | gut 1 Minute |
| Notebook 26 | Dateien aus 25 | `data/processed/kmeans_einstufung.csv` | wenige Sekunden |
| Notebook 27 | Dateien aus 25 | `data/processed/lstm_embedding.csv`, `lstm_scores.csv`, Gewichte nach `notebooks/models/` | rund 7 Minuten, davon die meiste Zeit Vorversuche |
| Notebook 28 | Dateien aus 25, Gewichte der Vorversuche aus 27 | `data/processed/prognose_tage.csv`, Gewichte nach `notebooks/models/` | rund 2 Minuten |
| Notebook 29 | Dateien aus 25 bis 28 | `data/processed/fehlerklassen_je_hast.csv` | rund 11 Minuten |
| Notebook 35 | Stundenreihen, Labels | Tabellen nach `outputs/finalvergleich/`, Modellpakete nach `models/` | gut 20 Minuten, das Endmodell lernt alle Netze je Prüfteil neu |
| `python -m src.dashboard_daten` | Modellpakete, aktuelle Stundenreihen | `outputs/dashboard/` | wenige Minuten |
| Notebook 37 | `outputs/dashboard/`, Netz-Cache aus Notebook 31 | HTML-Datei des Dashboards | wenige Minuten |

- **Ohne Grafikkarte** rechnen die Netze auf dem Prozessor, nur langsamer.
- **Selbst lernen nur auf Wunsch:** Die Notebooks 27, 28, 29, 34 und 35 haben im Setup den Schalter
  `SELBST_TRAINIEREN = False`. Damit laden 27 und 28 ihre Gewichte aus `notebooks/models/`, die Vorversuche aus
  `notebooks/models/vorversuche/`. 29, 34 und 35 halten vor dem Lernen an, ihre Ergebnisse stehen in den gespeicherten
  Ausgaben. Mit `True` lernen alle neu. Weil alle Seeds fest sind, kommen dabei dieselben Zahlen heraus. Geprüft ist das auf dem
  Rechner, auf dem die Notebooks laufen. Auf anderer Hardware können die letzten Stellen abweichen.
- **Modellpakete** für das Dashboard baut Notebook 35 nach `models/`, wenn es mit `SELBST_TRAINIEREN = True` läuft.
- **Nicht im Repository:** Rohdaten, aufbereitete Daten, Gewichte und Pakete. Sie sind aus Firmendaten der ÜZ gelernt
  und enthalten Zählernummern. Die Dashboard-Datei enthält zusätzlich Adressen.

## Das Ergebnis in Kürze

- Ein offenes Ventil ist erkennbar. Die gewählte Regression auf den 16 Zahlen des Fingerabdrucks kommt in Notebook 35
  auf eine AUC von 0,84, gleichauf mit einer einfachen Regel aus der Sommernacht (0,85).
- Bei der Dämmung findet nur das gelernte Modell ein Muster (0,78 gegen 0,61 für die beste Einzelregel). Der
  Vorsprung ist knapp nicht gesichert, deshalb zeigt das Dashboard die Dämmung nur als Hinweis.
- Das Prognose-LSTM überwacht die warmen Tage, an denen die Kennlinie des Monitoring-Modells nicht rechnet. Eingebaute
  Dauerdurchflüsse von 150 l/h findet es in Notebook 35 zu 78 % bei höchstens 5 % Fehlalarmen.
- Filter, Durchfluss und Sollwert sind nicht erkennbar. Die Maßnahmen hinterlassen schon keine messbare Spur in den
  Zählerdaten.
