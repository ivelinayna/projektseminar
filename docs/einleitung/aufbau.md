# Aufbau der Arbeit

Die Arbeit folgt dem Weg des Projekts: von den Daten über die Verfahren bis zum Ergebnis für die ÜZ.

- **Installation und Ausführung** erklärt, wo die Daten abgelegt werden, wie sich das Projekt mit Docker oder lokal
  starten lässt und in welcher Reihenfolge Notebooks und Befehle bis zum Dashboard laufen.
- **Datengrundlage** beschreibt die Zählerdaten, die Begehungen, das Netz mit der Zuordnung von Zählern und Adressen,
  ergänzende Daten wie Außentemperatur und Handtabellen und wo die Daten Lücken und Fehler haben.
- **Vorgehen** stellt die Arbeitsschritte vor: Daten aufbereiten, Begehungen auswerten, Merkmale und Clustering,
  Stationsbilder und Befunde, Anomalien und Monitoring, lernende Modelle, das Netz einbeziehen und die Modelle
  vergleichen. Jeder Schritt nennt die beteiligten Notebooks, was sie tun und wie ihre Ergebnisse zusammenlaufen. Die
  Liste aller Notebooks steht vorneweg unter *Überblick der Notebooks*. Zwei eigene Ansätze außerhalb der Hauptkette
  stehen unter *Weitere Versuche*.
- **Ergebnisse** fasst die Befunde aller Teile zusammen und geht die vier Ziele durch: Datenanalyse, Endmodell,
  Handlungsempfehlungen und Dashboard, mit einer Anleitung zum Erzeugen und Starten des Dashboards.
- **Grenzen und Erkenntnisse** ordnet ein, wie belastbar die Ergebnisse sind und was sich aus dem Projekt lernen lässt.
  Dort stehen auch die verworfenen Ansätze und die offenen Fragen an die ÜZ.
- **Ausblick** beschreibt den Betrieb mit neuen Daten, einen Vorschlag, wie die ÜZ künftige Begehungen plant und
  festhält, und die Weiterentwicklung, dazu eine Fassung des Dashboards als Streamlit-App.
- **Aufteilung im Team** zeigt, wer woran gearbeitet hat.
- **Der Anhang** enthält ein Verzeichnis der Fachbegriffe.

## Rahmen

Die Arbeit ist im Projektseminar der Julius-Maximilians-Universität Würzburg mit der ÜZ Mainfranken entstanden, im
Sommersemester 2026 und im Wintersemester 2026/27.

Die Rohdaten der ÜZ sind vertraulich und liegen nicht im Repository. Stationen werden in dieser Arbeit nur über ihre
Zählernummer genannt, nie über die Adresse.
