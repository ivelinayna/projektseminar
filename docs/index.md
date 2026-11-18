# Fehlererkennung im Fernwärmenetz

Projektseminar der Julius-Maximilians-Universität Würzburg mit der ÜZ Mainfranken, SS 2026 und WS 2026.

## Worum es geht

- Ein Fernwärmenetz versorgt Gebäude über Hausanschlussstationen (HAST). Jede HAST hat einen Wärmezähler mit Stundenwerten.
- Fehler an einer HAST, etwa ein klemmendes Ventil oder eine schlecht eingestellte Regelung, zeigen sich vor allem als hoher Rücklauf.
- Ziel: solche Fehler aus den Zählerdaten erkennen und eine Maßnahme vorschlagen.
- Grundlage: etwa 100 Zähler eines Teilnetzes, 66 Begehungen durch Monteure und der Leitungsplan.

## Vorgehen

- Zuerst Daten aufbereiten und die Wirkung der Begehungen messen.
- Dann ohne Labels arbeiten: Clustering, Kennlinien je Station, Vergleich mit dem Netz, Alarm bei Abweichung.
- Danach lernende Modelle (LSTM, XGBoost) und die Netzstruktur prüfen.
- Am Ende alle Verfahren unter gleichen Bedingungen vergleichen und das beste je Frage auswählen.

## Ergebnis in Kürze

- Überwachtes Lernen direkt auf den Begehungen scheitert an zu wenigen und unvollständigen Labels.
- Stationen bilden keine klaren Typen. Betriebsstunden lassen sich dagegen gut in fünf Zustände einteilen.
- Für die laufende Überwachung trägt der Tagesmonitor: Kennlinie je Station mit CUSUM-Alarm.
- Für die Einstufung nach den Handlungsklassen der ÜZ dient eine logistische Regression auf einem LSTM-Embedding.
- Viele Ansätze haben nicht getragen. Sie sind als Negativbefunde dokumentiert.
- Für die ÜZ gibt es ein Dashboard als HTML-Datei mit Karte und Handlungsliste.

Mehr unter [Ergebnisse](ergebnisse.md), [Endmodell](endmodell.md) und [Negativbefunde](negativbefunde.md).

## Wo was steht

| Seite | Inhalt |
|---|---|
| [Schnellstart](schnellstart.md) | Projekt lokal einrichten und ausführen |
| [Docker](docker.md) | Projekt ohne eigene Python-Installation starten |
| [Daten](daten.md) | Datenquellen, Aufbereitung, bekannte Probleme |
| [Notebooks](notebooks.md) | alle 39 Notebooks mit Frage, Ergebnis und Reihenfolge |
| [Ergebnisse](ergebnisse.md) | wichtigste Ergebnisse je Teil |
| [Stationsbilder und Befunde](stationsbilder.md) | Ternärdiagramme, Kennlinienmonitor, Freitexte |
| [Modellvergleich](modellvergleich.md) | alle Verfahren auf demselben Prüfstand |
| [Endmodell](endmodell.md) | gewählte Modelle je Frage, Modellpakete |
| [Negativbefunde](negativbefunde.md) | was nicht funktioniert hat und warum |
| [Pipeline und Module](pipeline.md) | Code in `src/`, Datenfluss, Befehle, Tests |
| [Dashboard](dashboard.md) | Aufbau und Erzeugung des Dashboards |
| [Grenzen und offene Fragen](grenzen.md) | Annahmen, Grenzen, Fragen an die ÜZ |
| [Begriffe](begriffe.md) | Fachbegriffe kurz erklärt |

## Datenschutz

- Die Rohdaten der ÜZ liegen nicht im Repo.
- Diese Doku nennt Stationen nur über die Zählernummer, nie über die Adresse.
