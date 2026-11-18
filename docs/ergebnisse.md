# Ergebnisse

- Diese Seite fasst die wichtigsten Ergebnisse der 39 Notebooks zusammen, geordnet nach den Teilen.
- Je Teil stehen zuerst die belastbaren Ergebnisse, danach die zentralen Schwächen.
- Alle Zahlen stammen aus den Ausgaben und Zusammenfassungen der Notebooks. Mehr Tiefe bieten [Stationsbilder und Befunde](stationsbilder.md), [Modellvergleich](modellvergleich.md), [Endmodell](endmodell.md) und [Negativbefunde](negativbefunde.md).
- Über alle Teile hinweg gilt: Einfache Regeln und Modelle liegen meist gleichauf mit komplexen. Die größte Grenze sind die Labels: wenige Begehungen, Befunde ohne bekannten Fehlerbeginn, Freitexte statt klarer Fehlerarten.

## Teil 1 Daten

- 93 Hausanschlussstationen (HAST) bilden die Datenbasis. 8 Zähler sind laut ÜZ keine HAST und sind ausgeschlossen (Notebook 00).
- Exportfehler sind erkannt und korrigiert: Faktor 1000 in 5 ODS-Dateien, Minutenversatz mit 17 bis 47 % Dubletten bei 3 Zählern, ein falscher Dateiname (Notebook 00).
- 80 % der Stunden im Raster sind gemessen. 84 % der ungemessenen Stunden stammen aus der Phase bis 11/2022, in der viele Zähler nur einen Wert je Tag lieferten (Notebook 00).
- Lücken sind gefüllt: 20,4 % der Stunden sind gerechnet, die Herkunft steht je Stunde dabei (Notebook 01).
- Schwach: 13 Zähler haben unter 70 % Abdeckung. Bei Lücken über einen Tag liegt der Rücklauffehler der Füllung bei 5 bis 6 K. Tages- und Stundenwerte sind gemischt (Notebook 00, 01). Details unter [Daten](daten.md).

## Teil 2 Begehungen und Wirkung

- Alle 66 von 66 Begehungen sind über die Zählernummer zugeordnet. Vierfeldertafel mit Rücklauf über 50 °C als „schlecht“ (n = 44): 61 % gut zu gut, 25 % schlecht zu schlecht, 9 % schlecht zu gut, 5 % gut zu schlecht. Das ist reine Beschreibung ohne Test (Notebook 02).
- Wintervergleich an 45 Begehungen: Der Rücklauf-Median sinkt um 1,2 K (p ≈ 0,09). Gegen 42 Zähler ohne Begehung (Differenz-in-Differenzen) sind es −2,0 K (p ≈ 0,008). Das ist konsistent mit einer Wirkung der Begehungen (Notebook 04).
- Der ARIMA-Ansatz findet nach 16 von 40 Begehungen einen deutlichen Sprung (außerhalb z = ±2), gegen 19 % der Placebo-Fenster (p = 0,002) und 22 % der Kontrolltermine (p = 0,035). Der typische Fall ändert sich aber kaum (p = 0,23) (Notebook 06).
- Nach der Begehung liegt die Abkühlung um 1,2 bis 1,3 kWh/m³ höher (5,2 bis 5,8 %, auf der Folie 13,4 %). Der Abstand ist nicht von null unterscheidbar (p ≈ 0,13 und 0,21), eine Kontrollgruppe fehlt (Notebook 05).
- Schwach: Die Kontrollgruppe ist nicht zufällig, fast alle Fälle liegen in einem Winterpaar mit 21 % kälterem Nachher-Winter. Ein Label aus Messdaten (2300 Station-Monate) taugt nur für schwere Dauerzustände, der Freitext bestätigt nur die Richtung (p = 0,346 und 0,317) (Notebook 03, 04).

## Teil 3 Clustering

- Stationscluster über die ganze Historie zeigen keine klaren Typen: Silhouette unter 0,25 (k = 2: 0,237). Die Flotte ist ein Kontinuum mit zwei Ausreißern (Notebook 07, 08).
- Im Benchmark ist K-Means am stabilsten, am meisten bei k = 2 (Bootstrap-ARI 0,67). HDBSCAN trägt auf diesen Merkmalen nicht. Kein Cluster ist signifikant maßnahmenreicher (Fisher p ≥ 0,33) (Notebook 08).
- Stundencluster tragen: k = 5, Silhouette 0,399, Bootstrap-ARI 0,851. Ein Kurzschlussverdacht (hoher Durchfluss bei kleiner Spreizung) umfasst rund 13 % der Stunden und bleibt auch im Kernwinter ein eigener Cluster (Notebook 09).
- Tagescluster: An Heiztagen entstehen vier, im Sommer drei Typen. Die Tage einer HAST liegen meist im selben Cluster (Median 0,68 bis 0,88 gegen 0,35 bis 0,54 bei Zufall). Die Cluster beschreiben damit eher Stationen als Tageszustände (Notebook 10).
- Schwach: Im Kernwinter allein fällt die Silhouette der Stundencluster auf 0,285, der Abgleich mit den Begehungen bleibt ohne p < 0,05 (Notebook 09).

## Teil 4 Stationsbilder und Befunde

- Das Teilnetz ist überwiegend durchflussgeregelt. Spreizungsgeregelte Stationen sind schlechter, umgekehrt zur Aussage der Folie (Notebook 11).
- Der Anteil der Stunden mit Rücklauf über 50 °C deutet nach den Begehungen eine Verbesserung an (nicht gesichert, p = 0,096), Modulationsart und Kennlinienparameter ändern sich nicht. Als Erfolgsmaß eignet er sich eher als die Kennlinie (Notebook 12).
- Der Kennlinienmonitor liegt gegen alle Begehungen nur 25 bis 34 % über Zufall (p = 0,10 und 0,077). Mit kodierten Freitexten trifft er mechanische Eingriffe in 10 von 19 Fällen (0,526 gegen 0,296, p = 0,030) (Notebook 13, 14).
- Die Fallsammlung zeigt: Ein saisongleicher Vergleich dreht das naive Ergebnis um. Daraus entstehen sieben Vorschläge für nie begangene Stationen (Notebook 15).
- Schwach: nur 19 mechanische Termine, die Einteilung wurde nach dem Nullergebnis gewählt. Die Schwelle von 50 °C ist gesetzt. Ausführlich unter [Stationsbilder und Befunde](stationsbilder.md).

## Teil 5 Anomalien und Monitoring

- Netzresiduum und stationseigenes Residuum bestehen die Begehungsvalidierung (n = 43), drei weitere Detektoren nicht. 19 von 93 Stationen sind an mehr als 10 % ihrer Tage auffällig (Notebook 16).
- Das Normalverhaltensmodell bemerkt 30 von 43 Begehungen gegen eine Kontrollquote von 0,53 (p = 0,017). Die Wassermenge ist der brauchbare Kanal (Notebook 18).
- Der Netzvergleich findet 8 chronisch auffällige Stationen, 4 davon nie begangen. Die Rangliste ist über die Winter stabil (Spearman 0,81 und 0,74) (Notebook 19).
- Der Tagesmonitor (Kennlinie mit CUSUM) bemerkt in der Abkühlung 22 von 43 Begehungen (Hebel 1,87, p = 0,001). Die Treffer kommen aus „besser“-Alarmen nach der Begehung: Erfolgskontrolle, keine Frühwarnung (Notebook 20, 21).
- Schwach: Die Residuen bringen gegenüber dem rohen Tagesmedian keinen Gewinn. Fehler, die schon im Lernjahr bestanden, sieht der Tagesmonitor nicht. Die Welle von Verschlechterungsalarmen im Dezember 2022 fällt auf einen Kälteeinbruch. Nachbarn häufen sich nicht, und der Bestwert-Maßstab sagt keine Befunde vorher (Notebook 16, 20, 22 bis 24).

## Teil 6 Lernende Modelle

- Das Ventil hat ein klares Signal: 9 von 11 Ventilfällen laufen im Sommer nachts durch, gegen 3 von 42 ohne Befund (Notebook 25).
- K-Means trennt Optimum (70) und schlechter (18) mit Silhouette 0,44. Die Gegenprobe Ventil (p = 0,021) ist nach Holm-Korrektur nicht mehr signifikant (0,13) (Notebook 26).
- Das LSTM erkennt Stationen über zwei Winter wieder (85 %, nie gesehene 83 %, Zufall 2 %). Ventil AUC 0,89, aber nicht belegt besser als die Sommernacht-Regel (0,85) (Notebook 27).
- Das Prognose-LSTM sagt den Rücklauf besser voraus als „wie gestern“ (4,3 K gegen 6,2 K) und findet einen eingerechneten Bypass von 150 l/h zu 84 % bei 8 % Fehlalarmen. An echten Begehungen bemerkt es 16 von 43, das Normalverhaltensmodell 30 von 43 (McNemar p = 0,001) (Notebook 28, 30).
- Schwach: Filter, Durchfluss und Temperatur liegen bei AUC 0,24 bis 0,64, im Bereich des Zufalls. XGBoost ist nirgends besser als die beste Regression oder Regel. Die Bayes-Diagnose (Ventil AUC 0,92) beruht auf einer Matrix, von der 0 von 132 Feldern mit der ÜZ abgestimmt sind (Notebook 29, 37).

## Teil 7 Netz

- Das Netzmodell hat 110 Nodes und 110 Kanten, 89 Zähler sind zugeordnet. Die Pfeilrichtung der Kantendatei passt oft nicht zum Vorlaufgefälle (22 Kanten plausibel, 26 verdächtig) (Notebook 31).
- Entlang des Rohrbaums ist das obere Haus bei 36 von 38 Paaren wärmer. Rohrbaum-Nachbarn schwanken aber nicht stärker gemeinsam als zufällige Häuser (0,231 gegen 0,223). Ein Effekt je Strang ist nicht nachweisbar (Notebook 32).
- Nachbarn im Leitungsgraphen beginnen Verschlechterungen nicht häufiger gemeinsam als zufällige Paare (p 0,21 bis 0,48). Gemeinsame Verbesserungen passen zu gemeinsamen Begehungsterminen (Notebook 24).
- Das GNN gewinnt durch das Netz nichts Messbares: Beitrag +0,010 und −0,009 (p = 0,172 und 0,423) (Notebook 38).
- Schwach: Der Graph ist logisch, nicht hydraulisch. Lage der Quelle und Kantenrichtung sind Annahmen.

## Teil 8 Modellvergleich und Ergebnis

- Im Vergleich aller Kandidaten bleibt nach Holm über 15 Wächter nur der Tagesmonitor belegt (33 von 43 Begehungen gegen 53 % Kontrolle, p = 0,017 nach Holm). Beim Ventil ist kein Modell belegt besser als die Sommernacht-Regel. Nachbarn und Lage im Netz verbessern nichts (Notebook 34, [Modellvergleich](modellvergleich.md)).
- Endmodell auf strengerer Zeitachse: Das Monitoring-Modell übernimmt Heizperiode, Erfolgskontrolle und Netzvergleich (18 von 43 als „besser“ gegen 24 %, p = 0,006). Das LSTM-Modell übernimmt warme Tage (Dauerdurchfluss 150 l/h 78 % bei 5 % Fehlalarmen) und die Fehlerart Ventil (AUC 0,84). Dämmung ist nur ein Hinweis (0,78), Kapazität nur per Regel (0,76) (Notebook 35, [Endmodell](endmodell.md)).
- Das Dashboard zeigt Karte, Handlungsliste und Erklärungen. Unter den ersten 10 nach Ventil-Score hatten 7 einen Ventilbefund, Zufall wäre etwa 2 (Notebook 35, 36).
- Schwach: 43 Begehungen, 11 Ventil- und 9 Vertragsfälle. Viele Vorsprünge sind nicht gesichert. Regelungsoptimierung und echte Frühwarnung sind nicht erkennbar bzw. nicht prüfbar. Die Referenz des Monitoring-Modells steht an 43 % der Testtage am Deckel und muss neu gelernt werden (Notebook 35).

## Was die ÜZ nutzen kann

- Das [Dashboard](dashboard.md) mit Karte, Handlungsliste und Reiter „So funktioniert's“. Es wendet nur geprüfte Modellpakete an und wird mit `python -m src.dashboard_daten` aktualisiert.
- Den Tagesmonitor als Alarm in der Heizperiode und zur Erfolgskontrolle nach einer Begehung. Ein Alarm heißt „Veränderung“, nicht „Fehler“.
- Die Handlungsliste als Prüfreihenfolge: zuerst Verdacht auf Ventil, sortiert nach Ventil-Score. Sie ersetzt keine Prüfung vor Ort.
- Kandidaten für die nächsten Begehungen: 4 chronisch auffällige, nie begangene Stationen (Notebook 19) und 7 Vorschläge aus der Fallsammlung (Notebook 15).
- Was nicht funktioniert hat, steht unter [Negativbefunde](negativbefunde.md), offene Punkte unter [Grenzen und offene Fragen](grenzen.md).
