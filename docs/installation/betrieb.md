# Betrieb bei der ÜZ

Im laufenden Betrieb erfüllt das Projekt zwei Aufgaben. Es hält Überwachung und Dashboard mit neuen Zählerdaten aktuell
(siehe [Neue Zählerdaten einspielen](ausfuehrung.md#neue-zahlerdaten-einspielen)). Außerdem sammelt es, was bei den
Begehungen tatsächlich gefunden wurde. Daran fehlte es dem Projekt am meisten. Jede Begehung mit sauberem Protokoll ist
ein neues Label, und erst damit lassen sich die Modelle an Fällen prüfen, deren Ergebnis vorher nicht bekannt war (siehe
[Probebetrieb](../ausblick_probebetrieb.md) und [Prüfung nach vorn](../ausblick_pruefung.md)).

Der Kreislauf hat vier Schritte:

```text
1  Handlungsliste      wird bei jedem Lauf von src.aktualisieren mit Datum gesichert
        |
2  Begehung            Monteur füllt das Begehungsprotokoll aus
        |
3  Rückmeldung         Protokolle einlesen, prüfen, mit dem Listenstand vor der Begehung verknüpfen
        |
4  Prüfung nach vorn   vorher festgelegte Stichprobe auswerten
```

Alle Befehle werden im Terminal im Projektordner ausgeführt (siehe
[Befehle im Terminal ausführen](vorbereitung.md#befehle-im-terminal-ausfuhren)). Mit Docker wird
`docker compose run --rm jupyter` vorangestellt.

## 1 Verlauf der Handlungsliste

Bei jedem Lauf von `python -m src.aktualisieren` wird die Handlungsliste unter `outputs/betrieb/listen/` gesichert,
als `handlungsliste_<Datum>_<Uhrzeit>.csv`. Bisher wurde sie bei jedem Lauf überschrieben. Ohne diesen Verlauf lässt
sich später nicht sagen, ob eine Station vor ihrer Begehung auf der Liste stand.

Jede Datei enthält je Zähler Rang, Dringlichkeit, Maßnahme, Klasse nach Folie 5, Ventil-Score, die Hinweise auf
Dämmung und Anschluss sowie die letzte bekannte Begehung. Datenstand und Version der Modellpakete stehen in jeder
Zeile mit. Adressen enthält die Datei nicht.

Von Hand sichern, z. B. nach einem einzelnen Lauf von `src.dashboard_daten`:

```bash
python -m src.betrieb liste-sichern
```

## 2 Begehungsprotokoll

Eine Excel-Vorlage für die Monteure erzeugt

```bash
python -m src.betrieb vorlage
```

Sie liegt danach unter `data/manual/begehungsprotokolle/vorlage_begehungsprotokoll.xlsx`. Eine Zeile entspricht
einer Begehung:

| Spalte | Pflicht | Inhalt |
|---|---|---|
| Zählernummer | ja | Nummer des Wärmezählers |
| Datum der Begehung | ja | Tag der Prüfung vor Ort |
| Etwas kaputt? | ja | ja, nein oder unklar |
| Fehlerart | wenn „ja“ | Auswahl, z. B. Regelventil / Stellantrieb, Dämmung, Anschluss zu groß |
| Zweite Fehlerart | nein | falls mehr als ein Fehler vorlag |
| Was war kaputt? | nein | kurze Beschreibung |
| Maßnahme | nein | Bauteil getauscht, neu eingestellt, gereinigt, keine, Sonstiges |
| Getauschtes Bauteil | nein | z. B. Stellantrieb, Ventil, Fühler |
| Fehler vermutlich seit | nein | Schätzung, seit wann der Fehler besteht |
| Bemerkung | nein | frei |

- Entscheidend ist die Spalte „Etwas kaputt?“. Die bisherigen Protokolle hielten fest, was eingestellt wurde, aber
  nicht, ob vorher ein Fehler vorlag. Deshalb ließen sich Filter, Durchfluss und Sollwert als Fehlerart nicht prüfen.
- Die Fehlerarten entsprechen den Kategorien, mit denen die bisherigen Freitexte kodiert wurden (Notebook 14). Neue und
  alte Begehungen lassen sich dadurch gemeinsam auswerten.
- Ob die Station auf der Handlungsliste stand, tragen die Monteure bewusst nicht ein. Das ergänzt das Einlesen aus dem
  Listenverlauf. So bleibt die Begehung unvoreingenommen.

Ausgefüllte Dateien kommen nach `data/manual/begehungsprotokolle/`, der Dateiname ist frei. Der Ordner enthält
Firmendaten und wird nicht ins Repository übernommen.

## 3 Rückmeldungen einlesen

```bash
python -m src.betrieb protokolle
```

- Liest alle ausgefüllten Protokolle in `data/manual/begehungsprotokolle/` ein, die Vorlage selbst nicht.
- Prüft jede Zeile: Zählernummer vorhanden, Datum lesbar und nicht in der Zukunft, „Etwas kaputt?“ ausgefüllt,
  Fehlerart angegeben, wenn etwas kaputt war, keine doppelte Begehung. Fehlerhafte Zeilen werden mit Datei und
  Zeilennummer gemeldet und nicht übernommen.
- Verknüpft jede Begehung mit der jüngsten Handlungsliste, die spätestens am Tag der Begehung gesichert wurde: Rang,
  Dringlichkeit, Maßnahme, Ventil-Score und Hinweise zu diesem Zeitpunkt.
- Leitet je Begehung drei Labels ab: Ventilbefund, Dämmungsbefund und zu großer Anschluss, jeweils ja, nein oder
  unklar.
- Schreibt alles nach `outputs/betrieb/rueckmeldungen.csv`.

Diese Tabelle ist die Grundlage, um die Modelle später nach den Regeln des [Probebetriebs](../ausblick_probebetrieb.md)
mit mehr Fällen neu zu lernen und zu prüfen.

## 4 Prüfung nach vorn

Der Test aus [Prüfung nach vorn](../ausblick_pruefung.md) prüft, ob die Handlungsliste im Betrieb tatsächlich mehr
Ventilfehler findet als eine zufällige Auswahl. Damit das Ergebnis belastbar ist, wird die Stichprobe vorher
festgelegt und danach nicht mehr verändert.

**Stichprobe festlegen:**

```bash
python -m src.betrieb pruefung-planen --anzahl 10
```

- Gruppe „hoch“: die nie begangenen Stationen mit dem höchsten Ventil-Score.
- Gruppe „zufall“: gleich viele, zufällig gezogen aus den übrigen nie begangenen Stationen.
- `--anzahl` legt die Größe je Gruppe fest. Im Stand vom November 2026 gibt es 42 nie begangene Stationen mit
  Ventil-Score, also höchstens 21 je Gruppe.

Der Befehl legt einen Ordner `outputs/betrieb/pruefung_<Datum>_<Uhrzeit>/` an:

| Datei | Inhalt | weitergeben |
|---|---|---|
| `begehungsliste.csv` | beide Gruppen gemischt, nur laufende Nummer und Zählernummer | ja, an das Team vor Ort |
| `schluessel.csv` | Gruppe und Ventil-Score je Station | nein |
| `plan.json` | Zeitpunkt, Listenstand, Startwert der Zufallsauswahl, Erwartung, Test und Prüfsummen beider Dateien | nein |

Das Team vor Ort weiß dadurch nicht, welche Station aus welcher Gruppe kommt. Ein bestehender Plan wird nie
überschrieben. Die Prüfsummen zeigen bei der Auswertung, ob eine Datei nachträglich verändert wurde.

**Auswerten,** sobald die Stationen begangen und die Protokolle abgelegt sind:

```bash
python -m src.betrieb pruefung-auswerten
```

- Liest die Protokolle neu ein und nimmt je Station die erste Begehung nach dem Festlegen des Plans.
- Vergleicht den Anteil der Ventilbefunde in beiden Gruppen mit einem einseitigen exakten Test nach Fisher, in der
  vorher festgelegten Richtung.
- Prüft als Nebenfragen, ob Stationen mit Hinweis auf Dämmung oder zu großen Anschluss häufiger einen solchen Befund
  haben.
- Schreibt das Ergebnis nach `auswertung.txt` im Ordner des Plans.

Bei zehn Stationen je Gruppe bleibt der Test grob. Er misst aber zum ersten Mal, was die Liste im Betrieb bringt, ohne
dass die Modelle die Antworten vorher kannten.

## Ablage

| Ordner | Inhalt | im Repository |
|---|---|---|
| `outputs/betrieb/listen/` | Verlauf der Handlungsliste | nein |
| `data/manual/begehungsprotokolle/` | Vorlage und ausgefüllte Protokolle | nein |
| `outputs/betrieb/rueckmeldungen.csv` | eingelesene und geprüfte Rückmeldungen | nein |
| `outputs/betrieb/pruefung_<Datum>/` | festgelegte Stichproben und ihre Auswertung | nein |

Die Ordner sollten bei der ÜZ regelmäßig gesichert werden, denn sie sind die Grundlage für jede spätere Prüfung der
Modelle.
