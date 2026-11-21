# Dashboard

Das Dashboard bringt die Ergebnisse des Projekts dorthin, wo die ÜZ sie braucht: Für jede Hausstation zeigt es, ob
Handlungsbedarf besteht, welche Maßnahme die Modelle vorschlagen und warum. Es ist eine einzelne HTML-Datei mit drei
Reitern und läuft in jedem Browser, ohne Python und ohne Server. Gebaut wird es in Notebook 37.

Das Dashboard deckt die vier Ziele der Aufgabenstellung ab (siehe [Aufgabe und Ziel](einleitung/aufgabe_und_ziel.md)):

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
     ├──► Notebook 19, 20        Monitoring-Modell: Netzvergleich, Kennlinie je Station, Tagesmonitor
     ├──► Notebook 25 bis 29     lernende Modelle: Labels, Fingerabdruck, Prognose-LSTM, Fehlerklassen
     │
Notebook 35        lernt alle Modelle auf einer gemeinsamen Zeitachse neu, prüft sie, speichert drei Pakete
     │
Programm dashboard_daten     wendet die Pakete auf die aktuellen Stundenreihen an
     │
     │        Notebook 31, 32     Leitungsnetz, Lage der Häuser, Rohrbaum vom Erzeuger
     │              │
     └──────────────┴──►  Notebook 37     baut die HTML-Datei: Karte, Handlungsliste, Erklärung
```

| Schritt | Notebook | was es beiträgt |
|---|---|---|
| Stundenreihen | 00 | saubere Stundenreihen für alle 93 Hausstationen, die Grundlage für jedes Modell |
| Stand im Netz und Potenzial | 19 | Netzvergleich je Kernwinter: Rang im Netz, Fehlerbild, Abstand zum besten Viertel |
| Wächter für die Heizperiode | 20 | Tagesmonitor des Monitoring-Modells: Kennlinie je Station mit CUSUM |
| Daten, Labels, Fingerabdruck, Klassen | 25 bis 27, 29 | Labels aus den Begehungen, Kennzahlen, LSTM-Fingerabdruck, Einstufung mit K-Means, Klassen nach Folie 5 (siehe [Lernende Modelle](modelle/index.md)) |
| Wächter für warme Tage | 28 | Prognose-LSTM, das jeden Tag Rücklauf und Durchfluss vorhersagt |
| Endmodell | 35 | lernt die gewählten Modelle neu, prüft sie streng und speichert sie als Pakete (siehe [Strenger Vergleich](vergleich/endmodell.md)) |
| Anwendung | Programm dashboard_daten | wendet die Pakete auf die aktuellen Daten an, ohne neu zu lernen. Die Ergebnistabellen enthalten nur Zählernummern. |
| Netz und Rohrbaum | 31, 32 | Leitungsnetz und Lage der Häuser aus einer von Hand gepflegten Koordinatentabelle (siehe *Datengrundlage → Netz und Zuordnung*), dazu der Rohrbaum vom Erzeuger zu jedem Haus |
| Dashboard | 37 | verbindet die Ergebnistabellen mit dem Rohrbaum und schreibt die HTML-Datei |

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
stehen nicht im Dashboard, sondern in Notebook 35.

## Welches Modell welche Anzeige liefert

Jede Anzeige kommt von dem Modell, das in Notebook 35 dafür am besten abgeschnitten hat:

| Anzeige | Modell | warum dieses Modell |
|---|---|---|
| Meldung an Heiztagen | Monitoring-Modell: Kennlinie + CUSUM, h = 5 | bemerkt Begehungen am deutlichsten: 18 von 43 als „besser“ gegen 24 % an Vergleichsstationen |
| Meldung an warmen Tagen | Prognose-LSTM + CUSUM, h = 10 | rechnet als einziges Modell im Sommer; findet eingebaute Dauerdurchflüsse von 150 l/h zu 78 % bei höchstens 5 % Fehlalarmen, das Wochenmittel zu 45 % |
| Verdacht Ventil | logistische Regression auf den 16 LSTM-Zahlen | AUC 0,84 mit Modellwahl im Lernteil; unter den ersten 10 nach Ventil-Score hatten 7 einen Ventilbefund (Test E) |
| Hinweis Dämmung | dasselbe Modell | AUC 0,78, beste Einzelregel 0,61; der Vorsprung ist knapp nicht gesichert, deshalb nur ein Hinweis |
| Hinweis Kapazität | Regel: Spitzenlast im Verhältnis zur Anschlussleistung | in Notebook 35 mit der Vertragsleistung vor der Begehung geprüft: AUC 0,76, gelernte Modelle höchstens 0,53 |
| Stand im Netz, Potenzial | Netzvergleich des Monitoring-Modells | beschreibt die Station gut, sagt die Wirkung einer Begehung aber kaum vorher |

**Ein Wächter je Tag.** An einem Heiztag, an dem der Tagesmonitor rechnen kann, zählt seine Meldung. An warmen Tagen
und bei Stationen ohne Referenz zählt das Prognose-LSTM. Meldungen des Prognose-LSTM an Heiztagen bleiben als Hinweis
in der Liste, färben die Karte aber nicht. So meldet für jede Station und jeden Tag genau ein Wächter.

**Begründung im Hausfenster.** Ein Ventilverdacht wird mit dem Anteil der Sommernächte mit Durchfluss begründet, nicht
mit den LSTM-Zahlen. „LSTM-Zahl 5 ist hoch“ hilft keinem Techniker, „in den meisten Sommernächten läuft Wasser durch“
schon.

## Handlungsliste

Die Handlungsliste ordnet alle Zähler nach Dringlichkeit und innerhalb einer Stufe nach dem Ventil-Score. Wie Handlung
und Dringlichkeit entstehen, was beim aktuellen Datenstand herauskommt und was bewusst nicht empfohlen wird, steht unter
[Handlungsempfehlungen](ergebnisse_handlungsempfehlungen.md).

## Keine Meldung heißt nicht „in Ordnung“

Das Dashboard zeigt nie „in Ordnung“. Stationen, für die ein Wächter noch keine Referenz hat, stehen als „noch nicht
bewertbar“ im Dashboard, nicht als „kein Alarm“. Im aktuellen Stand sind das 7 Stationen, bei beiden Wächtern
dieselben. Das Monitoring-Modell braucht dafür 60 Heiztage, das Prognose-LSTM rund vier Wochen volle Stundenwerte
(Notebook 35).

## Datenschutz

Die Ergebnistabellen der Modelle enthalten nur Zählernummern. Die Adressen kommen erst in Notebook 37 aus der
Zuordnungstabelle dazu, für die Karte. Die fertige HTML-Datei enthält deshalb Adressen. Sie ist nicht im Repository,
ist nur für den internen Gebrauch bestimmt und wird in dieser Dokumentation nicht als Bild gezeigt.

## Grenzen

- Empfehlung und Verdacht gelten für den letzten Winter mit genug Daten. Sie ändern sich nicht mit dem Zeitregler der
  Karte.
- Dämmung erscheint oft. Sie ist bei 41 % der begangenen Stationen eingetragen, das Modell gibt dazu nur einen Hinweis.
- Die Referenz des Tagesmonitors veraltet: An 43 % der Testtage steht eines seiner Konten am Deckel, dann kann er nicht
  neu melden. Die Referenz sollte nach jeder Begehung und zu jeder Heizperiode neu gelernt werden.
