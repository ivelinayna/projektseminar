# Lernende Modelle

Dieser Abschnitt beschreibt die Modelle, die aus den Daten lernen: zwei LSTM-Netze (neuronale Netze für Zeitreihen
mit Gedächtnis), eine logistische Regression auf dem Fingerabdruck des einen Netzes, eine Einstufung mit K-Means und
eine Regel für die Kapazität. Er erklärt, was gemacht wurde und warum. Den Code enthalten die Notebooks 27 bis 31.
Wie diese Modelle geprüft und mit den übrigen Modellen des Projekts verglichen wurden, steht unter
*Modelle vergleichen*, beginnend mit [Prüfdesign und Statistik](../vergleich/pruefung.md).

## Die Aufgabe

Folie 5 der Aufgabenstellung verlangt drei Dinge:

| Aufgabe | Frage | Antwort in diesem Abschnitt |
|---|---|---|
| Alarm | Verändert sich eine Station gerade? | Prognose-LSTM als Wächter |
| Fehler erkennen | Hat eine Station einen Dauerfehler, etwa ein Ventil, das nicht schließt? | LSTM-Fingerabdruck mit logistischer Regression |
| Fehler unterteilen | Welche Handlung ist nötig: Regelventil tauschen, Regelung optimieren oder nichts? | Klasse je Station nach Folie 5 |

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
   „Optimum oder schlechter“ und eine Regel für die Kapazität ergeben die Klasse nach Folie 5.

## Wie es zusammenläuft

```
Notebook 00   Zählerexporte  ──►  saubere Stundenreihen je Zähler
     │
Notebook 27   Stundenwerte + Außentemperatur, Labels aus den Begehungen, Kennzahlen, Messlatte
     │
     ├──► Notebook 28   K-Means: Optimum oder schlechter
     ├──► Notebook 29   LSTM-Fingerabdruck: 8 Zahlen je Tag, 16 je Station
     ├──► Notebook 30   Prognose-LSTM: Vorhersage je Tag, Abweichung, Warnung
     │
Notebook 31   Fehlerart je Station, Klassen nach Folie 5
     │
Notebook 32, 38   Vergleich mit den übrigen Modellen des Projekts
     │
Notebook 39   Endmodell: streng geprüft, als Pakete gespeichert
     │
src/dashboard_daten.py   wendet die Pakete auf aktuelle Daten an
     │
Notebook 40   Dashboard (HTML-Datei)
```

- **Notebook 27** baut die Datenbasis: Stundenwerte mit Außentemperatur, sechs Labels je begangener Station, zwölf
  Kennzahlen je Station, und prüft je Fehlerart eine einfache Kennzahl als Messlatte.
- **Notebook 28** stuft die Stationen ohne Label nach ihrem Regelverhalten ein.
- **Notebook 29 und 30** enthalten zuerst die Vorversuche, die zu den endgültigen Netzen geführt haben, danach die
  Netze selbst.
- **Notebook 31** vergleicht verschiedene Verfahren je Fehlerart und bildet die Klassen nach Folie 5.
- **Notebook 32, 38 und 39** gehören zu *Modelle vergleichen*. Notebook 39 lernt das Endmodell auf einer gemeinsamen
  Zeitachse neu, wählt das Modell nur im Lernteil und speichert drei Pakete für das Dashboard.
- **Notebook 40** zeigt das Ergebnis als Karte und Handlungsliste.
- **Notebook 41** prüft, ob die Maßnahmen bei den Begehungen überhaupt eine Spur in den Daten hinterlassen. Das
  erklärt, warum manche Fehlerarten nicht erkennbar sind (siehe [Was nicht getragen hat](../nicht_getragen.md)).

## Ausführen und Ablage

Die Notebooks laufen in dieser Reihenfolge. Jedes liest, was das vorige geschrieben hat:

| Schritt | liest | schreibt | Laufzeit (mit Grafikkarte) |
|---|---|---|---|
| Notebook 00 | Zählerexporte in `data/raw/` | Stundenreihen `data/processed/real_meters/`, `hast_features.csv` | unter 1 Minute |
| Notebook 27 | Stundenreihen, Begehungsprotokoll in `data/raw/`, Wetter (Cache `data/raw/weather/`) | `data/processed/modell_stunden.parquet`, `modell_labels.csv`, `modell_kennzahlen.csv` | gut 1 Minute |
| Notebook 28 | Dateien aus 27 | `data/processed/kmeans_einstufung.csv` | wenige Sekunden |
| Notebook 29 | Dateien aus 27 | `data/processed/lstm_embedding.csv`, `lstm_scores.csv`, Gewichte nach `notebooks/models/` | rund 7 Minuten, davon die meiste Zeit Vorversuche |
| Notebook 30 | Dateien aus 27, Gewichte der Vorversuche aus 29 | `data/processed/prognose_tage.csv`, Gewichte nach `notebooks/models/` | rund 2 Minuten |
| Notebook 31 | Dateien aus 27 bis 30 | `data/processed/fehlerklassen_je_hast.csv` | rund 11 Minuten |
| Notebook 39 | Stundenreihen, Labels | Tabellen nach `outputs/finalvergleich/`, Modellpakete nach `models/` | länger, das Endmodell lernt alle Netze je Prüfteil neu |
| `python -m src.dashboard_daten` | Modellpakete, aktuelle Stundenreihen | `outputs/dashboard/` | wenige Minuten |
| Notebook 40 | `outputs/dashboard/`, Netz-Cache aus Notebook 34 | HTML-Datei des Dashboards | wenige Minuten |

- **Ohne Grafikkarte** rechnen die Netze auf dem Prozessor, nur langsamer.
- **Gewichte:** Notebook 29 und 30 speichern ihre Gewichte unter `notebooks/models/`, die Vorversuche unter
  `notebooks/models/vorversuche/`. Beim nächsten Lauf werden sie geladen statt neu gelernt. Auf einem frischen Stand
  lernen die Notebooks neu. Weil alle Seeds fest sind, kommen dabei dieselben Zahlen heraus. Geprüft ist das auf dem
  Rechner, auf dem die Notebooks laufen. Auf anderer Hardware können die letzten Stellen abweichen.
- **Modellpakete** für das Dashboard baut Notebook 39 nach `models/`.
- **Nicht im Repository:** Rohdaten, aufbereitete Daten, Gewichte und Pakete. Sie sind aus Firmendaten der ÜZ gelernt
  und enthalten Zählernummern. Die Dashboard-Datei enthält zusätzlich Adressen.

## Das Ergebnis in Kürze

- Ein offenes Ventil ist erkennbar. Die gewählte Regression auf den 16 Zahlen des Fingerabdrucks kommt in Notebook 39
  auf eine AUC von 0,84, gleichauf mit einer einfachen Regel aus der Sommernacht (0,85).
- Bei der Dämmung findet nur das gelernte Modell ein Muster (0,78 gegen 0,61 für die beste Einzelregel). Der
  Vorsprung ist knapp nicht gesichert, deshalb zeigt das Dashboard die Dämmung nur als Hinweis.
- Das Prognose-LSTM überwacht die warmen Tage, an denen die Kennlinie des Monitoring-Modells nicht rechnet. Eingebaute
  Dauerdurchflüsse von 150 l/h findet es in Notebook 39 zu 78 % bei höchstens 5 % Fehlalarmen.
- Filter, Durchfluss und Sollwert sind nicht erkennbar. Die Maßnahmen hinterlassen schon keine messbare Spur in den
  Zählerdaten.
