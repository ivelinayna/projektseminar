# Dashboard

Das Dashboard bringt die Ergebnisse des Projekts dorthin, wo die ÜZ sie braucht: Für jede Hausstation zeigt es, ob
Handlungsbedarf besteht, welche Maßnahme die Modelle vorschlagen und warum. Es ist eine einzelne HTML-Datei mit drei
Reitern und läuft in jedem Browser, ohne Python und ohne Server. Gebaut wird es in Notebook 40.

Das Dashboard deckt die vier Ziele der Aufgabenstellung ab (siehe [Aufgabe und Ziel](aufgabe_und_ziel.md)):

| Ziel | im Dashboard |
|---|---|
| Datenanalyse | Netzeffizienz je Monat, Stand jeder Station im Netz, Meldungen bei überhöhtem Rücklauf oder Dauerdurchfluss |
| Modellentwicklung | Meldungen der Wächter und Verdacht auf eine Fehlerart: Ventil, Dämmung oder zu großer Anschluss |
| Visualisierung | Karte mit Zeitregler auf dem Rohrbaum des Netzes, gefärbt nach Dringlichkeit, Maßnahme, Meldungen, Potenzial oder Messwerten |
| Handlungsempfehlungen | Handlungsliste mit Maßnahme, Dringlichkeit und Begründung je Zähler |

## Welche Notebooks zusammenlaufen

```
Notebook 00        Zählerexporte  ──►  Stundenreihen je Zähler
     │
     ├──► Notebook 21, 22        Monitoring-Modell: Netzvergleich, Kennlinie je Station, Tagesmonitor
     ├──► Notebook 27 bis 31     lernende Modelle: Labels, Fingerabdruck, Prognose-LSTM, Fehlerklassen
     │
Notebook 39        lernt alle Modelle auf einer gemeinsamen Zeitachse neu, prüft sie, speichert drei Pakete
     │
Programm dashboard_daten     wendet die Pakete auf die aktuellen Stundenreihen an
     │
     │        Notebook 34, 35     Leitungsnetz, Lage der Häuser, Rohrbaum vom Erzeuger
     │              │
     └──────────────┴──►  Notebook 40     baut die HTML-Datei: Karte, Handlungsliste, Erklärung
```

| Schritt | Notebook | was es beiträgt |
|---|---|---|
| Stundenreihen | 00 | saubere Stundenreihen für alle 93 Hausstationen, die Grundlage für jedes Modell |
| Stand im Netz und Potenzial | 21 | Netzvergleich je Kernwinter: Rang im Netz, Fehlerbild, Abstand zum besten Viertel |
| Wächter für die Heizperiode | 22 | Tagesmonitor des Monitoring-Modells: Kennlinie je Station mit CUSUM |
| Daten, Labels, Fingerabdruck, Klassen | 27 bis 29, 31 | Labels aus den Begehungen, Kennzahlen, LSTM-Fingerabdruck, Einstufung mit K-Means, Klassen nach Folie 5 (siehe [Lernende Modelle](modelle/index.md)) |
| Wächter für warme Tage | 30 | Prognose-LSTM, das jeden Tag Rücklauf und Durchfluss vorhersagt |
| Endmodell | 39 | lernt die gewählten Modelle neu, prüft sie streng und speichert sie als Pakete (siehe [Strenger Vergleich und Entscheidung](vergleich/endmodell.md)) |
| Anwendung | Programm dashboard_daten | wendet die Pakete auf die aktuellen Daten an, ohne neu zu lernen. Die Ergebnistabellen enthalten nur Zählernummern. |
| Netz und Rohrbaum | 34, 35 | Leitungsnetz und Lage der Häuser aus einer von Hand gepflegten Koordinatentabelle (siehe *Datengrundlage → Netz und Zuordnung*), dazu der Rohrbaum vom Erzeuger zu jedem Haus |
| Dashboard | 40 | verbindet die Ergebnistabellen mit dem Rohrbaum und schreibt die HTML-Datei |

Das Dashboard rechnet selbst nichts und lernt nichts neu. Es zeigt genau das, was mit einer bestimmten Version der
Pakete gerechnet wurde. Deshalb ist es schnell und braucht keine Grafikkarte. Wie die Schritte ausgeführt werden,
steht unter *Installation und Ausführung → Ausführung bis zum Dashboard*.

## Was das Dashboard zeigt

| Reiter | Inhalt |
|---|---|
| Karte | Hausstationen auf dem Rohrbaum. Die Karte zeigt immer nur eine Färbung: Dringlichkeit, Maßnahme, Meldungen, Potenzial oder Messwerte. Ein Klick öffnet das Hausfenster mit Empfehlung, Leistung im Netz, Verdacht, Veränderung und Befund. Eine Seitenleiste „Netz“ zeigt das Netz als Ganzes. |
| Handlungsliste | alle Zähler, sortiert nach Dringlichkeit und Ventil-Score. Ein Klick springt zur Station auf der Karte. |
| So funktioniert's | welche Frage mit welchem Modell beantwortet wird und warum |

Damit das Dashboard nicht überladen wirkt, zeigt das Hausfenster immer dieselben Punkte. Modellvergleiche und AUC-Werte
stehen nicht im Dashboard, sondern in Notebook 39.

## Welches Modell welche Anzeige liefert

Jede Anzeige kommt von dem Modell, das in Notebook 39 dafür am besten abgeschnitten hat:

| Anzeige | Modell | warum dieses Modell |
|---|---|---|
| Meldung an Heiztagen | Monitoring-Modell: Kennlinie + CUSUM, h = 5 | bemerkt Begehungen am deutlichsten: 18 von 43 als „besser“ gegen 24 % an Vergleichsstationen |
| Meldung an warmen Tagen | Prognose-LSTM + CUSUM, h = 10 | rechnet als einziges Modell im Sommer; findet eingebaute Dauerdurchflüsse von 150 l/h zu 78 % bei höchstens 5 % Fehlalarmen, das Wochenmittel zu 45 % |
| Verdacht Ventil | logistische Regression auf den 16 LSTM-Zahlen | AUC 0,84 mit Modellwahl im Lernteil; unter den ersten 10 nach Ventil-Score hatten 7 einen Ventilbefund (Test E) |
| Hinweis Dämmung | dasselbe Modell | AUC 0,78, beste Einzelregel 0,61; der Vorsprung ist knapp nicht gesichert, deshalb nur ein Hinweis |
| Hinweis Kapazität | Regel: Spitzenlast im Verhältnis zur Anschlussleistung | in Notebook 39 mit der Vertragsleistung vor der Begehung geprüft: AUC 0,76, gelernte Modelle höchstens 0,53 |
| Stand im Netz, Potenzial | Netzvergleich des Monitoring-Modells | beschreibt die Station gut, sagt die Wirkung einer Begehung aber kaum vorher |

**Ein Wächter je Tag.** An einem Heiztag, an dem der Tagesmonitor rechnen kann, zählt seine Meldung. An warmen Tagen
und bei Stationen ohne Referenz zählt das Prognose-LSTM. Meldungen des Prognose-LSTM an Heiztagen bleiben als Hinweis
in der Liste, färben die Karte aber nicht. So meldet für jede Station und jeden Tag genau ein Wächter.

**Begründung im Hausfenster.** Ein Ventilverdacht wird mit dem Anteil der Sommernächte mit Durchfluss begründet, nicht
mit den LSTM-Zahlen. „LSTM-Zahl 5 ist hoch“ hilft keinem Techniker, „in den meisten Sommernächten läuft Wasser durch“
schon.

## Handlungsliste und Dringlichkeit

| Dringlichkeit | wann |
|---|---|
| hoch | Reparatur, bestätigt durch das Fehlerbild „ventil“ des Monitoring-Modells. Dieses Fehlerbild war in Notebook 39 bei 4 von 4 Stationen richtig. |
| mittel | Reparatur nur nach dem Ventil-Score. Die Klasse fand in Notebook 39 8 von 11 Ventilfällen. |
| niedrig | nur Hinweise: Kapazität prüfen, Dämmung prüfen, Daten prüfen |

- Innerhalb einer Stufe wird nach dem Ventil-Score sortiert. Das ist der Teil der Reihenfolge, den Notebook 39 belegt.
- **Sonderfälle** bekommen nur „Daten prüfen“, keine Reparatur. Sonderfall heißt: Mindestens zwei Kennzahlen liegen
  außerhalb dessen, woraus das Modell gelernt hat, oder die Station hat mehr als 10 % des Wintervolumens im Netz und
  ist damit keine typische Hausstation.
- Die Stufen sind festgelegt, nicht gelernt. Ob die Reihenfolge im Betrieb trägt, zeigt erst eine Begehung nach der
  Liste.

## Was das Dashboard bewusst nicht tut

- **Keine Empfehlung „Regelung optimieren“.** Kein Modell erkennt diese Maßnahme (Notebook 39, Test C).
- **Kein Sortieren nach Meldungen.** Vor Begehungen mit Befund gab es nicht mehr Verschlechterungen als bei
  Vergleichsstationen (Notebook 23).
- **Kein Sortieren nach Potenzial und keine Einspar-Schätzung in Euro.** Das Potenzial sagt nicht vorher, wo eine
  Begehung am meisten bringt (Notebook 39, Test D, Rangkorrelation 0,16).
- **Kein „in Ordnung“.** Keine Meldung heißt nicht, dass die Station in Ordnung ist. Stationen, für die ein Wächter
  noch keine Referenz hat, stehen als „noch nicht bewertbar“ im Dashboard. Das betrifft 7 Stationen beim
  Monitoring-Modell, 6 davon auch beim Prognose-LSTM.

## Datenschutz

Die Ergebnistabellen der Modelle enthalten nur Zählernummern. Die Adressen kommen erst in Notebook 40 aus der
Zuordnungstabelle dazu, für die Karte. Die fertige HTML-Datei enthält deshalb Adressen. Sie ist nicht im Repository,
ist nur für den internen Gebrauch bestimmt und wird in dieser Dokumentation nicht als Bild gezeigt.

## Grenzen

- Empfehlung und Verdacht gelten für den letzten Winter mit genug Daten. Sie ändern sich nicht mit dem Zeitregler der
  Karte.
- Dämmung erscheint oft. Sie ist bei 41 % der begangenen Stationen eingetragen, das Modell gibt dazu nur einen Hinweis.
- Die Referenz des Tagesmonitors veraltet: An 43 % der Testtage steht eines seiner Konten am Deckel, dann kann er nicht
  neu melden. Die Referenz sollte nach jeder Begehung und zu jeder Heizperiode neu gelernt werden.
