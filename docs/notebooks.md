# Notebooks

Die Notebooks liegen in `notebooks/`, je Teil in einem eigenen Ordner (`1_daten/` bis `9_dashboard/`, dazu `weitere_versuche/`). Sie laufen in Nummernfolge. Jedes Notebook arbeitet unabhängig vom Ordner mit `notebooks/` als Arbeitsordner.

- Notebook 00 immer zuerst ausführen. Es bereitet die Stundenreihen auf. Alle anderen lesen dieses Ergebnis.
- Jedes Notebook beginnt mit einer Kopfzelle (Frage, Daten, Code) und endet mit „Zusammenfassung & Bewertung“.
- Die Spalte „vorher“ nennt Abhängigkeiten außer Notebook 00.

## Teil 1: Daten

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 00 | Daten laden und Stationsprofile<br>`00_daten.ipynb` | Die Zählerexporte der ÜZ (CSV und ODS) je Zähler zu einer sauberen Stundenreihe zusammenführen | 93 HAST mit je 20 Spalten in `data/processed/hast_features.csv`, Eingabe für Notebook 07 |  |
| 01 | Fehlende Stundenwerte füllen<br>`01_luecken.ipynb` | Das Graphennetzwerk braucht je Station für jede Stunde einen Wert. Im Carpet-Plot aus Notebook 12 (Bild Tag gegen Uhrzeit) sind bei vielen Stationen ganze Zeiträume leer | Lückenlose Stundenreihen für alle 93 Zähler über ihre Messspanne, 20,4 % der Stunden gefüllt |  |

## Teil 2: Begehungen und Wirkung

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 02 | Wirkung der Begehungen<br>`02_wirkung.ipynb` | Frage: Hat sich das Betriebsverhalten einer Station nach einer Begehung messbar geändert? | 66 von 66 Begehungen zugeordnet. Vierfeldertafel (n = 44): 61 % gut zu gut, 25 % schlecht zu schlecht. Rein beschreibend, ohne Test. |  |
| 03 | Labels: Wann ist eine Station auffällig?<br>`03_labels.ipynb` | Kein Modell, sondern die Frage davor: Was soll ein Modell überhaupt erkennen? | Aus 66 Begehungszeilen ohne brauchbares Zustands-Label wurden 2300 bewertete Station-Monate. Die Definition stammt nur aus den Messdaten: Durchfluss über 50 l/h und Spreizung unter 8 K. |  |
| 04 | Wintervergleich der Begehungen<br>`04_wintervergleich.ipynb` | Frage: Sinkt der Rücklauf einer Station von der Heizperiode vor der Begehung zur Heizperiode danach? | 45 Begehungen an 44 Zählern auswertbar (Tagesabdeckung unter 60 % ausgeschlossen). |  |
| 05 | Performance in kWh/m³ vor und nach der Begehung<br>`05_performance.ipynb` | Kennzahl aus der ÜZ-Folie „Vergleich Gesamteffizienz vor und nach der Optimierung von HAST“: Energie je m³ Heizwasser gegen Außentemperatur, je eine Gerade für unoptimierte und optimierte Stationen. | Gleiche Richtung wie auf der Folie, aber kleiner: nach der Begehung 1,2 bis 1,3 kWh/m³ mehr, etwa 1,0 bis 1,1 K mehr Spreizung, 5,2 bis 5,8 % (Folie 13,4 %). |  |
| 06 | ARIMA und SARIMAX auf dem Tagesrücklauf<br>`06_arima.ipynb` | Taugen ARIMA oder SARIMAX als Prognose für das Tagesmittel des Rücklaufs? ARIMA = Modell, das eine Reihe aus ihren eigenen letzten Werten fortschreibt. SARIMAX = dasselbe mit Saisonterm und äußeren Größen, hier die Außentemperatur | Bestes Modell: Außentemperatur mit AR(1)-Fehlern (`arx_100`), mittlerer Fehler 2,11 °C gegen 2,66 °C naiv (87 Zähler, 1.695 Fenster) |  |

## Teil 3: Clustering

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 07 | Stationscluster mit K-Means<br>`07_stationscluster.ipynb` | Lassen sich die HAST (Hausübergabestationen) anhand ihrer Kennzahlen in Betriebsprofile gruppieren? | Keine klaren Stationstypen: Silhouette unter 0,25 für alle k. Die Stationen bilden ein Kontinuum mit zwei Ausreißern. |  |
| 08 | Clusterbenchmark: K-Means, Ward, GMM und HDBSCAN<br>`08_clusterbenchmark.ipynb` | Vier Clusterverfahren auf denselben Stationsmerkmalen und mit derselben Vorverarbeitung wie in Notebook 07 vergleichen. | K-Means am stabilsten, am meisten bei k = 2 (Bootstrap-ARI 0,67). HDBSCAN trägt nicht. Kein Cluster ist signifikant maßnahmenreicher (Fisher p ≥ 0,33). | `python -m src.main` |
| 09 | Clustervalidierung: Betriebszustand oder Jahreszeit?<br>`09_clustervalidierung.ipynb` | Jede Betriebsstunde einer HAST wird einzeln geclustert (K-Means, k = 5, fünf Betriebszustände). Geprüft wird, ob das trägt: Stabilität, Jahreszeit und Abgleich mit den Begehungen. | Die Stundencluster sind stabil: k = 5, Silhouette 0,399, Bootstrap-ARI 0,851. |  |
| 10 | Tagescluster: Tagestypen je HAST<br>`10_tagescluster.ipynb` | Jede HAST bekommt für jeden Tag eine Zeile mit wenigen, gut lesbaren Merkmalen. | Vier Tagestypen an Heiztagen, drei im Sommer. Die Tage einer HAST liegen meist im selben Cluster, die Cluster beschreiben also eher Stationen als Tageszustände. Schreibt `hast_tage` (62.734 nutzbare Tage). |  |


## Teil 4: Stationsbilder und Befunde

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 11 | Ternärdiagramme je Station<br>`11_ternaer.ipynb` | Vorlage ist eine ÜZ-Folie: Punktwolke in einem Dreieck aus Leistung, Volumenstrom und Spreizung (Spreizung = Vorlauf minus Rücklauf), gefärbt nach Performance. | Das Teilnetz ist überwiegend durchflussgeregelt (74 von 92 Stationen im Winter). |  |
| 12 | Stationsbilder neben dem Ternärdiagramm<br>`12_stationsbilder.ipynb` | Das Ternärdiagramm aus Notebook 11 bringt ein Produkt (P = c · V · ΔT) auf eine Summe und verliert dabei das Niveau, also wie viel Wasser und wie warm. | Steigung nahe 0 heißt feststehender Durchfluss. Diese Stationen haben die schlechteste Performance. |  |
| 13 | Kennlinienmonitor: jede Station gegen sich selbst<br>`13_kennlinienmonitor.ipynb` | Die Kennlinie log V über log P aus Notebook 12 wird zum eigenen Modell jeder Station. Verschiebt sich die Gerade, ist etwas passiert. | Die Kennlinie funktioniert als eigenes Modell für alle 93 Stationen. |  |
| 14 | Freitexte der Begehungen: Fehlerrangliste und bessere Labels<br>`14_befunde.ipynb` | Was steht in den Freitexten der Begehungen, und ergeben sie bessere Labels als die Alt-Neu-Spalten? | Die Freitexte enthalten, was in den Alt-Neu-Spalten fehlt: 6 von 66 Begehungen nennen einen Fehler ohne Sollwertänderung, bei 68956351 den Tausch des Stellmotors. |  |
| 15 | Fallsammlung: Begehungen im Ternärbild<br>`15_fallsammlung.ipynb` | Wo zeigt das Ternärbild eine bessere Effizienz, und fällt sie mit einer Begehung zusammen? | Der saisongleiche Schnitt dreht das Ergebnis um: naiv +1,28 (Kontrolle) gegen −0,29 (Begehung), im Winterschnitt −0,76 gegen +0,81. Das betrifft auch Notebook 11. |  |

## Teil 5: Anomalien und Monitoring

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 16 | Anomalieerkennung ohne Labels<br>`16_anomalie.ipynb` | Ziel: auffällig laufende Stationen benennen, ohne vorher ein Fehlerlabel zu vergeben. | Netzresiduum und stationseigenes Residuum bestehen die Begehungsvalidierung (n = 43, 42 Kontrollzähler), drei Detektoren nicht. |  |
| 17 | Von der Anomalie zur Handlungsempfehlung<br>`17_empfehlung.ipynb` | Ausgangspunkt Notebook 16: netzweites und stationseigenes Erwartungswertmodell bestehen die Begehungsvalidierung und messen Verschiedenes (Spearman 0,14). | Alle 26 auffälligen Stationen haben jetzt ein Muster. Mit der alten Zuordnung blieben 19 ohne verwertbare Diagnose. |  |
| 18 | Normalverhaltensmodell je Station<br>`18_normalverhalten.ipynb` | Frage: Lässt sich eine Veränderung an einer Station aus den Tageswerten früh und wetterbereinigt erkennen, ohne Fehler-Labels? | 89 von 93 Stationen werden überwacht. Die Wassermenge hängt klar am Wetter (Skill 0,26), die Abkühlung kaum (Skill 0,02). | 10 |
| 19 | Netzvergleich und Wintervergleich<br>`19_netzvergleich.ipynb` | Teil A (Netzvergleich): Welche Stationen laufen schlechter als die anderen? Alle 93 HAST, egal ob begangen. Das Ergebnis geht in die Priorität ein. | Netzvergleich: 377.385 Betriebsstunden → 215 Zeilen (Station und Winter) mit 5 Kennzahlen. Stationen je Winter: 22/23 41, 23/24 86, 24/25 84. |  |
| 20 | Tagesmonitor mit CUSUM<br>`20_tagesmonitor.ipynb` | Frage: Läuft die Station schlechter als früher? Jede Station wird jeden Heiztag mit sich selbst verglichen. | Der Tagesmonitor vergleicht jede Station mit ihrem eigenen Lernjahr, über Abkühlung und Wassermenge aus Zählerständen. 55.746 nutzbare Heiztage, 89 Stationen überwacht. |  |
| 21 | Alarme bewerten<br>`21_alarme.ipynb` | Baut auf dem finalen Modell auf: Netzvergleich (Notebook 19) und Tagesmonitor mit CUSUM (Notebook 20), zusammengeführt in `stationsblatt.rechne`. | Die Treffer des CUSUM um die Begehung kommen fast ganz aus Besserungsalarmen. Das passt zu einer besseren Abkühlung nach der Begehung. |  |
| 22 | Bestes Viertel als Maßstab, mit Lern- und Testprüfung<br>`22_bestwert.ipynb` | Der Netzvergleich (Notebook 19) misst jede Station am Median. Zeigt das beste Viertel je Kennzahl als zweiter Maßstab mehr, wenn schon die typische Station schlecht läuft? | Umgesetzt im Stationsblatt, in der Statustabelle (`potenzial`, `potenzial_score`, `groesste_luecke`, `bw_abstand_*`) und im Bericht von `python -m src.aktualisieren`. Die Priorität bleibt unverändert. |  |
| 23 | Vergleichsgruppen und Nachbarn im Leitungsnetz<br>`23_nachbarn.ipynb` | Zwei Ergänzungen zum Netzvergleich aus Notebook 19: Vergleich nur mit ähnlichen Stationen und mit den Nachbarn im Leitungsnetz. | Beide Ideen ändern am finalen Modell nichts Grundsätzliches. |  |
| 24 | Netzereignisse und Monitorstatus für die Karte<br>`24_netzereignisse.ipynb` | Der Tagesmonitor (Notebook 20) bewertet jede Station einzeln. Beginnen viele Alarme gleichzeitig, liegt die Ursache eher außerhalb des Hauses (Kälte, Vorlauf, Begehungswelle). | Alarme häufen sich an einzelnen Tagen netzweit. |  |

## Teil 6: Lernende Modelle

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 25 | Daten, Labels und Messlatte<br>`25_modelldaten.ipynb` | Was soll ein Modell erkennen, woran sieht man einen Fehler in den Stundenwerten, und wie gut trennt eine einzige, vorher festgelegte Kennzahl je Fehlerart? | Datenbasis für 26 bis 29: 2,1 Mio. Stundenzeilen von 93 Zählern mit Außentemperatur, 6 Labels je begangenem Zähler, Kennzahlen vor der Begehung. Nur das Ventil ist in den Daten deutlich sichtbar. Messlatte: Ventil AUC 0,88, Überdimensionierung 0,78, Dämmung 0,64, die übrigen bei Raten. |  |
| 26 | Einstufung mit K-Means: Läuft eine Station im Optimum oder schlechter?<br>`26_einstufung.ipynb` | Folie 5 der ÜZ teilt die Stationen in drei Klassen mit je einer Empfehlung. Lässt sich das ohne Labels aus dem Winterbetrieb ablesen? | Einstufung aller 88 Zähler mit genug Wintermessungen: Optimum (70) und schlechter (18). Nur aus dem Regelverhalten im Winter 23/24, ohne Label. Gespeichert in `kmeans_einstufung.csv`. |  |
| 27 | LSTM-Fingerabdruck: Normalbetrieb lernen, Stationen beschreiben<br>`27_lstm.ipynb` | Kann ein LSTM ohne Labels lernen, was eine Station ausmacht? Vorversuche zu Sequenzen, Lernkurve, Early Stopping und Engpass, dann das endgültige Netz. | Ein LSTM (116.941 Gewichte) sagt aus einem Tag den nächsten vorher und beschreibt jeden Tag in 8 Zahlen, je Station 16 für Winter und Sommer. Wiedererkennung über zwei Winter 83 %, nie gesehene Stationen 78 %. |  |
| 28 | Prognose-LSTM: ein Wächter für neue Veränderungen<br>`28_prognose_lstm.ipynb` | Wie viele Tage Vorgeschichte, was bringt ein LSTM gegenüber dem 7-Tage-Mittel, wie weit kommt ein Wächter ohne Netz? Dann der endgültige Wächter. | 7 Tage sind am besten (U-Form). Ein Encoder-Decoder-LSTM (35.458 Gewichte) sagt für 87 Stationen jeden Tag Rücklauf und Durchfluss vorher. Eingebaute Bypässe von 150 l/h zu 84 % erkannt bei 8 % Fehlalarmen. |  |
| 29 | XGBoost: Fehlerart und Handlungsklasse je Station<br>`29_xgboost.ipynb` | Die Notebooks 25 bis 28 liefern je eine Sicht auf die Stationen: Kennzahlen, ein gelerntes LSTM-Embedding (Embedding = kurze Zahlenreihe, die das Verhalten einer Station zusammenfasst), die Abweichungen des Wächters. | Sieben Verfahren über sechs Fehlerarten verglichen, alle verschachtelt geprüft, mit Stationen und mit ganzen Straßen ausgelassen. |  |
| 30 | Wächtervergleich: Normalverhaltensmodell gegen Prognose-LSTM<br>`30_waechtervergleich.ipynb` | Im Projekt gibt es zwei Wächter, die melden, wenn sich an einer Station etwas verändert: das Normalverhaltensmodell (Notebook 18) und das Prognose-LSTM (Notebook 28). | Die Prüfung aus Notebook 18 liegt als Funktion vor, Fall für Fall gegen dessen Zahlen kontrolliert (30/43, p = 0,017). | 10, 18 |

## Teil 7: Netz

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 31 | Netz: Leitungen, Hausstationen, Zähler und Kanten<br>`31_netz.ipynb` | Aus Leitungsplan, Kantendatei und Zählerlisten ein Netzmodell bauen: welche Station hängt wo am Netz. | Netzmodell aus der Kantendatei: 110 Nodes, 110 Kanten, ein zusammenhängendes Netz mit einem Ring. |  |
| 32 | Einspeisung, Rohrbaum und Nachbarvergleich<br>`32_einspeisung.ipynb` | Wo speist das Netz ein? Schätzung aus dem Vorlauf: Er kühlt entlang der Rohre ab. | Einspeisung aus dem Vorlauf geschätzt: beste Rangkorrelation −0,70 bei einer Zufallsgrenze von −0,28. Die besten Punkte liegen beim angenommenen Erzeuger. | 31 |
| 33 | Netzkarte mit Monitorstatus<br>`33_netzkarte.ipynb` | Die Netzkarte aus Notebook 31 um den Status des Kennlinienmonitors ergänzen. | Netzkarte mit Monitorstatus: Priorität, frische Alarme und Netzereignisse je Station auf dem Netz aus Notebook 31. | 24, 31 |

## Teil 8: Modellvergleich und Ergebnis

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 34 | Modellvergleich: welches Modell für welche Aufgabe?<br>`34_modellvergleich.ipynb` | Fast jedes Notebook hat sein Modell selbst geprüft, mit eigenem Zeitraum, eigenen Stationen und eigener Alarmmenge. Die Ergebnisse sind so nicht vergleichbar. | Kein System ist allein das beste. Beste Kombination: Alarm aus dem Monitoring-Modell (Tagesmonitor), dazu das Prognose-LSTM für plötzliche Fehler; Fehlererkennung und Klasse aus der LSTM-Kette; Netzvergleich als Bestätigung, die die Dringlichkeit hebt. | 10, 18, 25 bis 29 |
| 35 | Endmodell: Monitoring-Modell gegen LSTM-Modell<br>`35_endmodell.ipynb` | Im Projekt gibt es zwei fertige Ansätze: Monitoring-Modell (Kennlinie und Netzvergleich) und LSTM-Modell (neuronales Netz). | Keins der beiden Modelle ist allein besser. Das Monitoring-Modell übernimmt Heizperiode, Erfolgskontrolle und Netzvergleich, das LSTM-Modell die warmen Tage und die Fehlerart Ventil (mit dem Fehlerbild des Monitoring-Modells als Bestätigung). | 25 bis 29 |
| 36 | Feature Engineering: Zeitstruktur und Erklärbarkeit<br>`36_merkmale.ipynb` | Notebook 35 findet bei Filter, Durchfluss und Sollwert nichts, bei der Dämmung ein Muster ohne Erklärung. Liegt das an den Daten, an den Kennzahlen oder an den Labels? | Nur der Ventiltausch hinterlässt eine messbare Spur (Sommernacht-Durchfluss sinkt, AUC 0,81, nach Holm gesichert). Dämmung, Filter und Durchfluss ändern nach der Maßnahme nichts Messbares. Erster physikalischer Hinweis zur Dämmung: Abkühlrate im Stillstand (0,69, nicht gesichert). | 27, 39 |

## Teil 9: Dashboard

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 37 | Dashboard: Handlungsempfehlungen auf dem Rohrbaum<br>`37_dashboard.ipynb` | Das fertige Dashboard: Es zeigt auf dem Rohrbaum aus Notebook 32 für jede Hausstation, was die Modelle aus Notebook 35 sagen. | Ein Dashboard mit drei Reitern auf dem Rohrbaum aus Notebook 32: Karte, Handlungsliste und „So funktioniert's“. Jede Anzeige kommt von dem Modell, das in Notebook 35 dafür am besten abgeschnitten hat. | 31, 35, `python -m src.dashboard_daten` |

## Anhang: Weitere Versuche

Eigene Ansätze, die sich nicht durchgesetzt haben und auf denen nichts aufbaut. Sie stehen hinter dem Dashboard, damit die Hauptkette 00 bis 37 durchgeht. Die Befunde aller Versuche fasst [Negativbefunde](nicht_getragen/negativbefunde.md) zusammen.

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 38 | Bayes-Diagnose je Station<br>`38_bayes.ipynb` | Frage: Welche Fehlerart erklärt die Messdaten einer Station am besten, und wie sicher ist das? | Ventil/Stellantrieb hat als einzige Fehlerart eine klare Spur: Begehungen mit Ventilbefund bekamen im Mittel 40 % dafür, die übrigen 1 % (n = 10). Im Zweikampf gegen „kein Befund“ AUC 0,92. |  |
| 39 | GNN-Entwurf: Hilft das Netz bei der Früherkennung?<br>`39_gnn.ipynb` | Frage: Verbessert ein GNN das Normalverhaltensmodell aus Notebook 18, und zwar wegen des Netzes? GNN = Graph Neural Network, ein Modell, das auch die Messwerte der Nachbarn im Netz nutzt. | Ohne Netz erklärt das Modell nach der Referenz 12,1 % (Abkühlung) und 18,5 % (Wassermenge) des Fehlers von Notebook 18. Die neuen eigenen Merkmale helfen also. | 10 |

## Wichtige Abhängigkeiten

- Notebook 10 schreibt die Tageswerte `hast_tage` für die Notebooks 18, 30, 34 und 39.
- Notebook 18 schreibt das Normalverhaltensmodell für die Notebooks 30 und 34.
- Die Notebooks 25 bis 29 schreiben Modelldaten, LSTM-Embedding und Ventil-Modell für 34 und 35.
- Notebook 24 schreibt den Monitor-Status für Notebook 33.
- Notebook 31 baut den Netz-Cache `notebooks/daten_cache/` für die Notebooks 32, 33 und 37.
- Notebook 35 baut die Modellpakete in `models/` für das Dashboard in Notebook 37.
- Notebook 35 schreibt die Vorhersagen aus Test C nach `outputs/finalvergleich/` für Notebook 36.
- Notebook 08 braucht `inspections_tidy.csv` aus `python -m src.main`.

## Alte und neue Nummern

Im Projektverlauf gab es andere Dateinamen und Nummern. Ältere Notizen und der Changelog nutzen sie noch.

| Neu | Abgabestand 13.11.2026 | Alter Dateiname |
|---|---|---|
| `00_daten.ipynb` | `00_daten.ipynb` | `00_eda_hast_stationsprofile.ipynb` |
| `01_luecken.ipynb` | `01_luecken.ipynb` | `luecken.ipynb` |
| `02_wirkung.ipynb` | `02_wirkung.ipynb` | `03_wirkungsanalyse_begehungen.ipynb` |
| `03_labels.ipynb` | `03_labels.ipynb` | `05_label_findung_defektdefinition.ipynb` |
| `04_wintervergleich.ipynb` | `04_wintervergleich.ipynb` | `07_jahresvergleich.ipynb` |
| `05_performance.ipynb` | `05_performance.ipynb` | `08_performance.ipynb` |
| `06_arima.ipynb` | `06_arima.ipynb` | `arima.ipynb` |
| `07_stationscluster.ipynb` | `07_stationscluster.ipynb` | `01_kmeans_stationscluster.ipynb` |
| `08_clusterbenchmark.ipynb` | `08_clusterbenchmark.ipynb` | `04_clustering_benchmark.ipynb` |
| `09_clustervalidierung.ipynb` | `10_clustervalidierung.ipynb` | `09_clustervalidierung.ipynb` |
| `10_tagescluster.ipynb` | `11_tagescluster.ipynb` | `06_tagesmerkmale_clusteranalyse.ipynb` |
| `11_ternaer.ipynb` | `13_ternaer.ipynb` | `12_ternaer.ipynb` |
| `12_stationsbilder.ipynb` | `14_stationsbilder.ipynb` | `13_stationsbilder.ipynb` |
| `13_kennlinienmonitor.ipynb` | `15_kennlinienmonitor.ipynb` | `14_monitor.ipynb` |
| `14_befunde.ipynb` | `16_befunde.ipynb` | `15_befunde.ipynb` |
| `15_fallsammlung.ipynb` | `17_fallsammlung.ipynb` | `fallsammlung.ipynb` |
| `16_anomalie.ipynb` | `18_anomalie.ipynb` | `10_anomalie.ipynb` |
| `17_empfehlung.ipynb` | `19_empfehlung.ipynb` | `11_empfehlung.ipynb` |
| `18_normalverhalten.ipynb` | `20_normalverhalten.ipynb` | `17_normalverhaltensmodell.ipynb` |
| `19_netzvergleich.ipynb` | `21_netzvergleich.ipynb` | `netzvergleich.ipynb` |
| `20_tagesmonitor.ipynb` | `22_tagesmonitor.ipynb` | `tagesmonitor.ipynb` |
| `21_alarme.ipynb` | `23_alarme.ipynb` | `alarme.ipynb` |
| `22_bestwert.ipynb` | `24_bestwert.ipynb` | `27_bestwert.ipynb` |
| `23_nachbarn.ipynb` | `25_nachbarn.ipynb` | `23_nachbarn.ipynb` |
| `24_netzereignisse.ipynb` | `26_netzereignisse.ipynb` | `24_netzereignisse.ipynb` |
| `25_modelldaten.ipynb` | `27_modelldaten.ipynb` | `18_modelldaten_labels.ipynb` |
| `26_einstufung.ipynb` | `28_einstufung.ipynb` | `19_kmeans_einstufung_folie5.ipynb` |
| `27_lstm.ipynb` | `29_lstm.ipynb` | `20_lstm_fehlererkennung.ipynb` |
| `28_prognose_lstm.ipynb` | `30_prognose_lstm.ipynb` | `21_prognose_lstm_waechter.ipynb` |
| `29_xgboost.ipynb` | `31_xgboost.ipynb` | `22_xgboost_fehlerklassen.ipynb` |
| `30_waechtervergleich.ipynb` | `32_waechtervergleich.ipynb` | `23_vergleich_waechter.ipynb` |
| `38_bayes.ipynb` | `33_bayes.ipynb` | `31_bayes_diagnose.ipynb` |
| `31_netz.ipynb` | `34_netz.ipynb` | `16_Netz.ipynb` |
| `32_einspeisung.ipynb` | `35_einspeisung.ipynb` | `28_Netz_experimente.ipynb` |
| `33_netzkarte.ipynb` | `36_netzkarte.ipynb` | `25_netzkarte.ipynb` |
| `39_gnn.ipynb` | `37_gnn.ipynb` | `30_gnn_entwurf.ipynb` |
| `34_modellvergleich.ipynb` | `38_modellvergleich.ipynb` | `32_modellvergleich.ipynb` |
| `35_endmodell.ipynb` | `39_endmodell.ipynb` | `34_modellvergleich_und_umsetzung_nach_aufgabenstellung.ipynb` |
| `36_merkmale.ipynb` | `41_merkmale.ipynb` | `36_feature_engineering_zeitstruktur_shap.ipynb` |
| `37_dashboard.ipynb` | `40_dashboard.ipynb` | `35_dashboard.ipynb` |
