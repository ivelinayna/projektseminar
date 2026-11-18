# Ergebnisse

- Diese Seite fasst die wichtigsten Ergebnisse der 41 Notebooks zusammen, geordnet nach den acht Teilen.
- Je Teil stehen zuerst die belastbaren Ergebnisse, danach die zentralen Schwächen.
- Alle Zahlen stammen aus den Ausgaben und Zusammenfassungen der Notebooks. Mehr Tiefe bieten [Stationsbilder und Befunde](stationsbilder.md), [Modellvergleich](modellvergleich.md), [Endmodell](endmodell.md) und [Negativbefunde](negativbefunde.md).
- Über alle Teile hinweg gilt: Einfache Regeln und Modelle liegen meist gleichauf mit komplexen. Die größte Grenze sind die Labels: wenige Begehungen, Befunde ohne bekannten Fehlerbeginn, Freitexte statt klarer Fehlerarten.

## Teil 1 Daten

- 93 Hausanschlussstationen (HAST) bilden die Datenbasis. 8 Zähler sind laut ÜZ keine HAST und sind ausgeschlossen (Notebook 00).
- Exportfehler sind erkannt und korrigiert: Faktor 1000 in 5 ODS-Dateien, Minutenversatz mit 17 bis 47 % Dubletten bei 3 Zählern, ein falscher Dateiname (Notebook 00).
- 80 % der Stunden im Raster sind gemessen. 84 % der ungemessenen Stunden stammen aus der Phase bis 11/2022, in der viele Zähler nur einen Wert je Tag lieferten (Notebook 00).
- Lücken sind gefüllt: 30,4 % der Stunden sind gerechnet, die Herkunft steht je Stunde dabei (Notebook 01).
- Schwach: 13 Zähler haben unter 70 % Abdeckung. Bei Lücken über einen Tag liegt der Rücklauffehler der Füllung bei 6 bis 7 K. Tages- und Stundenwerte sind gemischt (Notebook 00, 01). Details unter [Daten](daten.md).

## Teil 2 Begehungen und Wirkung

- Alle 66 von 66 Begehungen sind über die Zählernummer zugeordnet. Vierfeldertafel mit Rücklauf über 50 °C als „schlecht“ (n = 42): 62 % gut zu gut, 26 % schlecht zu schlecht, 10 % schlecht zu gut, 2 % gut zu schlecht. Das ist reine Beschreibung ohne Test (Notebook 02).
- Wintervergleich an 44 Begehungen: Der Rücklauf-Median sinkt um 1,55 K (p ≈ 0,09). Gegen 49 Zähler ohne Begehung (Differenz-in-Differenzen) sind es −1,9 K (p ≈ 0,01). Das ist konsistent mit einer Wirkung der Begehungen (Notebook 04).
- Der ARIMA-Ansatz findet nach 15 von 40 Begehungen einen deutlichen Sprung (außerhalb z = ±2), gegen 18 % der Placebo-Fenster (p = 0,002) und 19 % der Kontrolltermine (p = 0,028). Der typische Fall ändert sich aber kaum (p = 0,21) (Notebook 06).
- Nach der Begehung liegt die Abkühlung um 2,0 bis 2,2 kWh/m³ höher (9,5 bis 10,4 %, auf der Folie 13,4 %), allerdings ohne Kontrollgruppe (Notebook 05).
- Schwach: Die Kontrollgruppe ist nicht zufällig, fast alle Fälle liegen in einem Winterpaar mit 21 % kälterem Nachher-Winter. Ein Label aus Messdaten (2368 Station-Monate) taugt nur für schwere Dauerzustände, der Freitext bestätigt nur die Richtung (p = 0,346 und 0,317) (Notebook 03, 04).

## Teil 3 Clustering

- Stationscluster über die ganze Historie zeigen keine klaren Typen: Silhouette unter 0,25 (k = 2: 0,245). Die Flotte ist ein Kontinuum mit einem Ausreißer-Trio (Notebook 07, 08).
- Im Benchmark ist K-Means mit k = 3 am stabilsten (Bootstrap-ARI 0,71 bzw. 0,60 ohne BHKW). HDBSCAN trägt auf diesen Merkmalen nicht. Kein Cluster ist signifikant maßnahmenreicher (Fisher p ≥ 0,51) (Notebook 08).
- Stundencluster tragen: k = 5, Silhouette 0,404, Bootstrap-ARI 0,853. Ein Kurzschlussverdacht (hoher Durchfluss bei kleiner Spreizung) umfasst rund 12 % der Stunden und bleibt auch im Kernwinter ein eigener Cluster (Notebook 09, 10).
- Tagescluster: An Heiztagen entstehen vier, im Sommer drei Typen. Die Tage einer HAST liegen meist im selben Cluster (Median 0,67 bis 0,86 gegen 0,35 bis 0,54 bei Zufall). Die Cluster beschreiben damit eher Stationen als Tageszustände (Notebook 11).
- Schwach: Im Kernwinter allein fällt die Silhouette der Stundencluster auf 0,315, der Abgleich mit den Begehungen bleibt ohne p < 0,05. Unüberwachte Anomaliescores erreichen nur ROC-AUC 0,49 bis 0,53 und finden höchstens 2 von 10 Proxy-Ereignissen (Notebook 10; Gesamtpipeline, siehe [Negativbefunde](negativbefunde.md)).

## Teil 4 Stationsbilder und Befunde

- Das Teilnetz ist überwiegend durchflussgeregelt. Spreizungsgeregelte Stationen sind schlechter, umgekehrt zur Aussage der Folie (Notebook 13).
- Der Anteil der Stunden mit Rücklauf über 50 °C zeigt eine Veränderung nach den Begehungen, Modulationsart und Kennlinienparameter nicht. Er ist das bessere Erfolgsmaß (Notebook 14).
- Der Kennlinienmonitor liegt gegen alle Begehungen nur 27 bis 39 % über Zufall (p = 0,090 und 0,054). Mit kodierten Freitexten trifft er mechanische Eingriffe in 10 von 19 Fällen (0,526 gegen 0,285, p = 0,023) (Notebook 15, 16).
- Die Fallsammlung zeigt: Ein saisongleicher Vergleich dreht das naive Ergebnis um. Daraus entstehen sieben Vorschläge für nie begangene Stationen (Notebook 17).
- Schwach: nur 19 mechanische Termine, die Einteilung wurde nach dem Nullergebnis gewählt. Die Schwelle von 50 °C ist gesetzt. Ausführlich unter [Stationsbilder und Befunde](stationsbilder.md).

## Teil 5 Anomalien und Monitoring

- Netzresiduum und stationseigenes Residuum bestehen die Begehungsvalidierung (n = 42), drei weitere Detektoren nicht. 20 von 100 Stationen sind an mehr als 10 % ihrer Tage auffällig (Notebook 18).
- Sebs Normalverhaltensmodell bemerkt 29 von 41 Begehungen gegen eine Kontrollquote von 0,53 (p = 0,016). Die Wassermenge ist der brauchbare Kanal (Notebook 20).
- Der Netzvergleich findet 8 chronisch auffällige Stationen, 4 davon nie begangen. Die Rangliste ist über die Winter stabil (Spearman 0,81 und 0,74) (Notebook 21).
- Der Tagesmonitor (Kennlinie mit CUSUM) bemerkt in der Abkühlung 22 von 43 Begehungen (Hebel 1,87, p = 0,001). Die Treffer kommen aus „besser“-Alarmen nach der Begehung: Erfolgskontrolle, keine Frühwarnung (Notebook 22, 23).
- Schwach: Die Residuen bringen gegenüber dem rohen Tagesmedian keinen Gewinn. Fehler, die schon im Lernjahr bestanden, sieht der Tagesmonitor nicht. Alarmwellen fallen auf Kälteeinbrüche. Nachbarn häufen sich nicht, und der Bestwert-Maßstab sagt keine Befunde vorher (Notebook 18, 22, 24 bis 26).

## Teil 6 Lernende Modelle

- Das Ventil hat ein klares Signal: 9 von 11 Ventilfällen laufen im Sommer nachts durch, gegen 3 von 42 ohne Befund (Notebook 27).
- K-Means trennt Optimum (70) und schlechter (18) mit Silhouette 0,44. Die Gegenprobe Ventil (p = 0,021) ist nach Holm-Korrektur nicht mehr signifikant (0,13) (Notebook 28).
- Das LSTM erkennt Stationen über zwei Winter wieder (83 %, nie gesehene 78 %, Zufall 2 %). Ventil AUC 0,89, aber nicht belegt besser als die Sommernacht-Regel (0,85) (Notebook 29). Im Endmodell mit Modellwahl im Lernteil sind es 0,84 (Notebook 39).
- Das Prognose-LSTM sagt den Rücklauf besser voraus als „wie gestern“ (4,3 K gegen 6,2 K) und findet einen eingerechneten Bypass von 150 l/h zu 84 % bei 8 % Fehlalarmen. An echten Begehungen bemerkt es 16 von 43, Sebs Prüfung 30 von 43 (McNemar p = 0,001) (Notebook 30, 32).
- Schwach: Filter, Durchfluss und Temperatur liegen bei AUC 0,24 bis 0,64, im Bereich des Zufalls. XGBoost ist nirgends besser als die beste Regression oder Regel. Die Bayes-Diagnose (Ventil AUC 0,92) beruht auf einer Matrix, von der 0 von 132 Feldern mit der ÜZ abgestimmt sind (Notebook 31, 33).

## Teil 7 Netz

- Das Netzmodell hat 110 Nodes und 110 Kanten, 88 Zähler sind zugeordnet. Die Pfeilrichtung der Kantendatei passt oft nicht zum Vorlaufgefälle (22 Kanten plausibel, 25 verdächtig) (Notebook 34).
- Entlang des Rohrbaums ist das obere Haus bei 36 von 38 Paaren wärmer. Rohrbaum-Nachbarn schwanken aber nicht stärker gemeinsam als zufällige Häuser (0,370 gegen 0,365). Ein Effekt je Strang ist nicht nachweisbar (Notebook 35).
- Nachbarn alarmieren nicht häufiger gemeinsam als zufällige Paare (8 von 9 Tests mit p > 0,05) (Notebook 36).
- Das GNN gewinnt durch das Netz nichts Messbares: Beitrag +0,010 und −0,009 (p = 0,172 und 0,423) (Notebook 37).
- Schwach: Der Graph ist logisch, nicht hydraulisch. Lage der Quelle und Kantenrichtung sind Annahmen.

## Teil 8 Modellvergleich und Ergebnis

- Im Vergleich aller Kandidaten bleibt nach Holm über 15 Wächter nur der Tagesmonitor belegt (33 von 43 Begehungen gegen 53 % Kontrolle, p = 0,017 nach Holm). Beim Ventil ist kein Modell belegt besser als die Sommernacht-Regel. Nachbarn und Lage im Netz verbessern nichts (Notebook 38, [Modellvergleich](modellvergleich.md)).
- Endmodell auf strengerer Zeitachse: Modell Ivelina übernimmt Heizperiode, Erfolgskontrolle und Netzvergleich (18 von 43 als „besser“ gegen 24 %, p = 0,006). Modell LSTM übernimmt warme Tage (Dauerdurchfluss 150 l/h 78 % bei 5 % Fehlalarmen) und die Fehlerart Ventil (AUC 0,84). Dämmung ist nur ein Hinweis (0,78), Kapazität nur per Regel (0,76) (Notebook 39, [Endmodell](endmodell.md)).
- Das Dashboard zeigt Karte, Handlungsliste und Erklärungen. Unter den ersten 10 nach Ventil-Score hatten 7 einen Ventilbefund, Zufall wäre etwa 2 (Notebook 39, 40).
- Warum manche Fehlerarten nicht erkennbar sind: Nur der Ventiltausch hinterlässt eine messbare Spur, der Sommernacht-Durchfluss sinkt danach (AUC 0,81, nach Holm gesichert). Nach Dämmung, Filter und Durchfluss ändert sich nichts Messbares, Sollwert (62 %) und Filter (47 %) sind eher Routine als gefundene Fehler. Erster physikalischer Hinweis zur Dämmung ist die Abkühlrate im Stillstand (0,69, nicht gesichert) (Notebook 41, [Was nicht getragen hat](nicht_getragen.md)).
- Schwach: 43 Begehungen, 11 Ventil- und 9 Vertragsfälle. Viele Vorsprünge sind nicht gesichert. Regelungsoptimierung und echte Frühwarnung sind nicht erkennbar bzw. nicht prüfbar. Ivelinas Referenz steht an 43 % der Testtage am Deckel und muss neu gelernt werden (Notebook 39).

## Was die ÜZ nutzen kann

- Das [Dashboard](dashboard.md) mit Karte, Handlungsliste und Reiter „So funktioniert's“. Es wendet nur geprüfte Modellpakete an und wird mit `python -m src.dashboard_daten` aktualisiert.
- Den Tagesmonitor als Alarm in der Heizperiode und zur Erfolgskontrolle nach einer Begehung. Ein Alarm heißt „Veränderung“, nicht „Fehler“.
- Die Handlungsliste als Prüfreihenfolge: zuerst Verdacht auf Ventil, sortiert nach Ventil-Score. Sie ersetzt keine Prüfung vor Ort.
- Kandidaten für die nächsten Begehungen: 4 chronisch auffällige, nie begangene Stationen (Notebook 21) und 7 Vorschläge aus der Fallsammlung (Notebook 17).
- Was nicht funktioniert hat, steht unter [Negativbefunde](negativbefunde.md), offene Punkte unter [Grenzen und offene Fragen](grenzen.md).
