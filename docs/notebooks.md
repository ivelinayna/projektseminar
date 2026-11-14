# Notebooks

Alle Notebooks liegen in `notebooks/`. Sie sind in acht Teile gegliedert und laufen in Nummernfolge.

- Notebook 00 immer zuerst ausführen. Es bereitet die Stundenreihen auf. Alle anderen lesen dieses Ergebnis.
- Jedes Notebook beginnt mit einer Kopfzelle (Frage, Daten, Code) und endet mit „Zusammenfassung & Bewertung“.
- Die Spalte „vorher“ nennt Abhängigkeiten außer Notebook 00.

## Teil 1: Daten

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 00 | Daten laden und Stationsprofile<br>`00_daten.ipynb` | Die Zählerexporte der ÜZ (CSV und ODS) je Zähler zu einer sauberen Stundenreihe zusammenführen | 93 HAST mit je 20 Spalten in `data/processed/hast_features.csv`, Eingabe für Notebook 07 |  |
| 01 | Fehlende Stundenwerte füllen<br>`01_luecken.ipynb` | Das Graphennetzwerk braucht je Station für jede Stunde einen Wert. Im Carpet-Plot aus Notebook 14 (Bild Tag gegen Uhrzeit) sind bei vielen Stationen ganze Zeiträume leer | Lückenlose Stundenreihen für alle 100 Zähler über ihre Messspanne, 30,4 % der Stunden gefüllt |  |

## Teil 2: Begehungen und Wirkung

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 02 | Wirkung der Begehungen<br>`02_wirkung.ipynb` | Frage: Hat sich das Betriebsverhalten einer Station nach einer Begehung messbar geändert? | 66 von 66 Begehungen zugeordnet. Vierfeldertafel (n = 42): 62 % gut zu gut, 26 % schlecht zu schlecht. Rein beschreibend, ohne Test. |  |
| 03 | Labels: Wann ist eine Station auffällig?<br>`03_labels.ipynb` | Kein Modell, sondern die Frage davor: Was soll ein Modell überhaupt erkennen? | Aus 66 Begehungszeilen ohne brauchbares Zustands-Label wurden 2368 bewertete Station-Monate. Die Definition stammt nur aus den Messdaten: Durchfluss über 50 l/h und Spreizung unter 8 K. |  |
| 04 | Wintervergleich der Begehungen<br>`04_wintervergleich.ipynb` | Frage: Sinkt der Rücklauf einer Station von der Heizperiode vor der Begehung zur Heizperiode danach? | 44 Begehungen an 43 Zählern auswertbar (Tagesabdeckung unter 60 % ausgeschlossen). |  |
| 05 | Performance in kWh/m³ vor und nach der Begehung<br>`05_performance.ipynb` | Kennzahl aus der ÜZ-Folie „Vergleich Gesamteffizienz vor und nach der Optimierung von HAST“: Energie je m³ Heizwasser gegen Außentemperatur, je eine Gerade für unoptimierte und optimierte Stationen. | Gleiche Richtung wie auf der Folie: nach der Begehung 2,0 bis 2,2 kWh/m³ mehr, etwa 1,7 bis 1,9 K mehr Spreizung, 9,5 bis 10,4 % (Folie 13,4 %). |  |
| 06 | ARIMA und SARIMAX auf dem Tagesrücklauf<br>`06_arima.ipynb` | Taugen ARIMA oder SARIMAX als Prognose für das Tagesmittel des Rücklaufs? ARIMA = Modell, das eine Reihe aus ihren eigenen letzten Werten fortschreibt. SARIMAX = dasselbe mit Saisonterm und äußeren Größen, hier die Außentemperatur | Bestes Modell: Außentemperatur mit AR(1)-Fehlern (`arx_100`), mittlerer Fehler 2,12 °C gegen 2,69 °C naiv (87 Zähler, 1.538 Fenster) |  |

## Teil 3: Clustering

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 07 | Stationscluster mit K-Means<br>`07_stationscluster.ipynb` | Lassen sich die HAST (Hausübergabestationen) anhand ihrer Kennzahlen in Betriebsprofile gruppieren? | Keine klaren Stationstypen: Silhouette unter 0,25 für alle k. Die Stationen bilden ein Kontinuum mit einem Ausreißer-Trio. |  |
| 08 | Clusterbenchmark: K-Means, Ward, GMM und HDBSCAN<br>`08_clusterbenchmark.ipynb` | Vier Clusterverfahren auf denselben Stationsmerkmalen und mit derselben Vorverarbeitung wie in Notebook 07 vergleichen. | K-Means mit k = 3 am stabilsten (Bootstrap-ARI 0,71). HDBSCAN trägt nicht. Kein Cluster ist signifikant maßnahmenreicher (Fisher p ≥ 0,51). | `python -m src.main` |
| 09 | Stundencluster: Betriebszustände mit K-Means<br>`09_stundencluster.ipynb` | Jede Betriebsstunde einer HAST (Hausübergabestation) wird einzeln geclustert, nicht die Station als Ganzes. | Fünf gut lesbare Betriebszustände in 1 658 002 Stunden, darunter ein Verdacht auf hydraulischen Kurzschluss (hoher Durchfluss, kleine Spreizung). |  |
| 10 | Clustervalidierung: Betriebszustand oder Jahreszeit?<br>`10_clustervalidierung.ipynb` | Notebook 09 findet in den Betriebsstunden bei k = 5 fünf Zustände. Es fehlten Stabilitätsprüfung, Saisonkontrolle und Abgleich mit den Begehungen. | Die Stundencluster aus Notebook 09 reproduzieren sich: k = 5, Silhouette 0,404, Bootstrap-ARI 0,853. |  |
| 11 | Tagescluster: Tagestypen je HAST<br>`11_tagescluster.ipynb` | Jede HAST bekommt für jeden Tag eine Zeile mit wenigen, gut lesbaren Merkmalen. | Vier Tagestypen an Heiztagen, drei im Sommer. Die Tage einer HAST liegen meist im selben Cluster, die Cluster beschreiben also eher Stationen als Tageszustände. Schreibt `hast_tage` (61.408 nutzbare Tage). |  |
| 12 | Gesamtpipeline: von Rohdaten bis Wartungsbenchmark<br>`12_gesamtpipeline.ipynb` | Ein Notebook, das ohne Vorarbeit läuft: Rohdaten lesen, bereinigen, Wartungen zuordnen, clustern, Anomaliescores vergleichen. | Aus den Rohdaten entstehen 78 vergleichbare HAST mit 18.518 gemeinsamen Stunden. Alle 10 Checks des Laufs sind bestanden. |  |

## Teil 4: Stationsbilder und Befunde

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 13 | Ternärdiagramme je Station<br>`13_ternaer.ipynb` | Vorlage ist eine ÜZ-Folie: Punktwolke in einem Dreieck aus Leistung, Volumenstrom und Spreizung (Spreizung = Vorlauf minus Rücklauf), gefärbt nach Performance. | Das Teilnetz ist überwiegend durchflussgeregelt (75 von 94 Stationen im Winter). |  |
| 14 | Stationsbilder neben dem Ternärdiagramm<br>`14_stationsbilder.ipynb` | Das Ternärdiagramm aus Notebook 13 bringt ein Produkt (P = c · V · ΔT) auf eine Summe und verliert dabei das Niveau, also wie viel Wasser und wie warm. | Steigung nahe 0 heißt feststehender Durchfluss. Diese Stationen haben die schlechteste Performance. |  |
| 15 | Kennlinienmonitor: jede Station gegen sich selbst<br>`15_kennlinienmonitor.ipynb` | Die Kennlinie log V über log P aus Notebook 14 wird zum eigenen Modell jeder Station. Verschiebt sich die Gerade, ist etwas passiert. | Die Kennlinie funktioniert als eigenes Modell für alle 100 Stationen. |  |
| 16 | Freitexte der Begehungen: Fehlerrangliste und bessere Labels<br>`16_befunde.ipynb` | Was steht in den Freitexten der Begehungen, und ergeben sie bessere Labels als die Alt-Neu-Spalten? | Die Freitexte enthalten, was in den Alt-Neu-Spalten fehlt: 6 von 66 Begehungen nennen einen Fehler ohne Sollwertänderung, bei 68956351 den Tausch des Stellmotors. |  |
| 17 | Fallsammlung: Begehungen im Ternärbild<br>`17_fallsammlung.ipynb` | Wo zeigt das Ternärbild eine bessere Effizienz, und fällt sie mit einer Begehung zusammen? | Der saisongleiche Schnitt dreht das Ergebnis um: naiv +1,13 (Kontrolle) gegen 0,00 (Begehung), im Winterschnitt −0,58 gegen +0,81. Das betrifft auch Notebook 13. |  |

## Teil 5: Anomalien und Monitoring

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 18 | Anomalieerkennung ohne Labels<br>`18_anomalie.ipynb` | Ziel: auffällig laufende Stationen benennen, ohne vorher ein Fehlerlabel zu vergeben. | Netzresiduum und stationseigenes Residuum bestehen die Begehungsvalidierung (n = 42, 49 Kontrollzähler), drei Detektoren nicht. |  |
| 19 | Von der Anomalie zur Handlungsempfehlung<br>`19_empfehlung.ipynb` | Ausgangspunkt Notebook 18: netzweites und stationseigenes Erwartungswertmodell bestehen die Begehungsvalidierung und messen Verschiedenes (Spearman 0,14). | 25 von 26 auffälligen Stationen haben jetzt ein Muster. Mit der alten Zuordnung blieben 21 ohne verwertbare Diagnose. |  |
| 20 | Normalverhaltensmodell je Station (Modell Seb)<br>`20_normalverhalten.ipynb` | Frage: Lässt sich eine Veränderung an einer Station aus den Tageswerten früh und wetterbereinigt erkennen, ohne Fehler-Labels? | 89 von 94 Stationen werden überwacht. Die Wassermenge hängt klar am Wetter (Skill 0,27), die Abkühlung kaum (Skill 0,02). | 11 |
| 21 | Netzvergleich und Wintervergleich<br>`21_netzvergleich.ipynb` | Teil A (Netzvergleich): Welche Stationen laufen schlechter als die anderen? Alle 93 HAST, egal ob begangen. Das Ergebnis geht in die Priorität ein. | Netzvergleich: 377.385 Betriebsstunden → 215 Zeilen (Station und Winter) mit 5 Kennzahlen. Stationen je Winter: 22/23 41, 23/24 86, 24/25 84. |  |
| 22 | Tagesmonitor mit CUSUM<br>`22_tagesmonitor.ipynb` | Frage: Läuft die Station schlechter als früher? Jede Station wird jeden Heiztag mit sich selbst verglichen. | Der Tagesmonitor vergleicht jede Station mit ihrem eigenen Lernjahr, über Abkühlung und Wassermenge aus Zählerständen. 55.746 nutzbare Heiztage, 89 Stationen überwacht. |  |
| 23 | Alarme bewerten<br>`23_alarme.ipynb` | Baut auf dem finalen Modell auf: Netzvergleich (Notebook 21) und Tagesmonitor mit CUSUM (Notebook 22), zusammengeführt in `stationsblatt.rechne`. | Die Treffer des CUSUM um die Begehung kommen fast ganz aus Besserungsalarmen. Das passt zu einer besseren Abkühlung nach der Begehung. |  |
| 24 | Bestes Viertel als Maßstab, mit Lern- und Testprüfung<br>`24_bestwert.ipynb` | Der Netzvergleich (Notebook 21) misst jede Station am Median. Zeigt das beste Viertel je Kennzahl als zweiter Maßstab mehr, wenn schon die typische Station schlecht läuft? | Umgesetzt im Stationsblatt, in der Statustabelle (`potenzial`, `potenzial_score`, `groesste_luecke`, `bw_abstand_*`) und im Bericht von `python -m src.aktualisieren`. Die Priorität bleibt unverändert. |  |
| 25 | Vergleichsgruppen und Nachbarn im Leitungsnetz<br>`25_nachbarn.ipynb` | Zwei Ergänzungen zum Netzvergleich aus Notebook 21: Vergleich nur mit ähnlichen Stationen und mit den Nachbarn im Leitungsnetz. | Beide Ideen ändern am finalen Modell nichts Grundsätzliches. |  |
| 26 | Netzereignisse und Monitorstatus für die Karte<br>`26_netzereignisse.ipynb` | Der Tagesmonitor (Notebook 22) bewertet jede Station einzeln. Beginnen viele Alarme gleichzeitig, liegt die Ursache eher außerhalb des Hauses (Kälte, Vorlauf, Begehungswelle). | Alarme häufen sich an einzelnen Tagen netzweit. |  |

## Teil 6: Lernende Modelle

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 27 | Modelldaten: Stundenwerte, Kennzahlen und Labels je Zähler<br>`27_modelldaten.ipynb` | Hier entsteht noch kein Modell. Das Notebook stellt die Daten bereit, aus denen die Notebooks 28 bis 31 lernen. | `modell_stunden.parquet`: 2,1 Mio. Stundenzeilen von 93 Zählern, mit Außentemperatur. Gebraucht in Notebook 29 und 30. |  |
| 28 | Einstufung mit K-Means: Läuft eine Station im Optimum oder schlechter?<br>`28_einstufung.ipynb` | Folie 5 der ÜZ teilt die Stationen in drei Klassen mit je einer Empfehlung. Lässt sich das ohne Labels aus dem Winterbetrieb ablesen? | Einstufung aller 88 Zähler mit genug Wintermessungen: Optimum (70) und schlechter (18). Nur aus dem Regelverhalten im Winter 23/24, ohne Label. Gespeichert in `kmeans_einstufung.csv`. |  |
| 29 | LSTM: Normalbetrieb lernen, Fehler finden<br>`29_lstm.ipynb` | Die Kennzahlen aus Notebook 27 sind von Hand ausgewählt. Ein LSTM (neuronales Netz für Zeitreihen mit Gedächtnis) soll aus den Stundenwerten selbst lernen, was eine Station ausmacht, ohne Labels. | Ein LSTM (117.000 Gewichte, 11 Sekunden Training auf der GPU) sagt aus einem Tag einer Station den nächsten vorher und beschreibt dabei jede Station in acht Zahlen. |  |
| 30 | Prognose-LSTM: ein Wächter für neue Veränderungen<br>`30_prognose_lstm.ipynb` | Notebook 29 zeigt: Ein LSTM (neuronales Netz für Zeitreihen mit Gedächtnis) kann das Verhalten einer Station lernen. Hier wird daraus ein Wächter. | Ein Encoder-Decoder-LSTM (35.000 Gewichte, 24 Sekunden Training auf der GPU) sagt für 87 Stationen jeden Tag Rücklauf und Durchfluss vorher. Gelernt nach Vorgabe nur auf begangenen HAST, ein Netz auf allen HAST dient zum Vergleich. |  |
| 31 | XGBoost: Fehlerart und Handlungsklasse je Station<br>`31_xgboost.ipynb` | Die Notebooks 27 bis 30 liefern je eine Sicht auf die Stationen: Kennzahlen, ein gelerntes LSTM-Embedding (Embedding = kurze Zahlenreihe, die das Verhalten einer Station zusammenfasst), die Abweichungen des Wächters. | Sieben Verfahren über sechs Fehlerarten verglichen, alle verschachtelt geprüft, mit Stationen und mit ganzen Straßen ausgelassen. |  |
| 32 | Wächtervergleich: Normalverhaltensmodell gegen Prognose-LSTM<br>`32_waechtervergleich.ipynb` | Im Projekt gibt es zwei Wächter, die melden, wenn sich an einer Station etwas verändert: Sebs Normalverhaltensmodell (Notebook 20) und Dominiks Prognose-LSTM (Notebook 30). | Sebs Prüfung aus Notebook 20 liegt als Funktion vor, Fall für Fall gegen seine Zahlen kontrolliert (30/43, p = 0,017). | 11, 20 |
| 33 | Bayes-Diagnose je Station<br>`33_bayes.ipynb` | Frage: Welche Fehlerart erklärt die Messdaten einer Station am besten, und wie sicher ist das? | Ventil/Stellantrieb hat als einzige Fehlerart eine klare Spur: Begehungen mit Ventilbefund bekamen im Mittel 40 % dafür, die übrigen 1 % (n = 10). Im Zweikampf gegen „kein Befund“ AUC 0,92. |  |

## Teil 7: Netz

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 34 | Netz: Leitungen, Hausstationen, Zähler und Kanten<br>`34_netz.ipynb` | Aus Leitungsplan, Kantendatei und Zählerlisten ein Netzmodell bauen: welche Station hängt wo am Netz. | Netzmodell aus der Kantendatei: 110 Nodes, 110 Kanten, ein zusammenhängendes Netz mit einem Ring. |  |
| 35 | Einspeisung, Rohrbaum und Nachbarvergleich<br>`35_einspeisung.ipynb` | Wo speist das Netz ein? Schätzung aus dem Vorlauf: Er kühlt entlang der Rohre ab. | Einspeisung aus dem Vorlauf geschätzt: beste Rangkorrelation −0,69 bei einer Zufallsgrenze von −0,27. Die besten Punkte liegen beim angenommenen Erzeuger. | 34 |
| 36 | Netzkarte mit Monitorstatus<br>`36_netzkarte.ipynb` | Die Netzkarte aus Notebook 34 um den Status des Kennlinienmonitors ergänzen. | Netzkarte mit Monitorstatus: Priorität, frische Alarme und Netzereignisse je Station auf dem Netz aus Notebook 34. | 26, 34 |
| 37 | GNN-Entwurf: Hilft das Netz bei der Früherkennung?<br>`37_gnn.ipynb` | Frage: Verbessert ein GNN das Normalverhaltensmodell aus Notebook 20, und zwar wegen des Netzes? GNN = Graph Neural Network, ein Modell, das auch die Messwerte der Nachbarn im Netz nutzt. | Ohne Netz erklärt das Modell nach der Referenz 12,1 % (Abkühlung) und 18,5 % (Wassermenge) des Fehlers von Notebook 20. Die neuen eigenen Merkmale helfen also. | 11 |

## Teil 8: Modellvergleich und Ergebnis

| Nr. | Notebook | Worum es geht | Ergebnis | vorher |
|---|---|---|---|---|
| 38 | Modellvergleich: welches Modell für welche Aufgabe?<br>`38_modellvergleich.ipynb` | Fast jedes Notebook hat sein Modell selbst geprüft, mit eigenem Zeitraum, eigenen Stationen und eigener Alarmmenge. Die Ergebnisse sind so nicht vergleichbar. | Kein System ist allein das beste. Beste Kombination: Alarm aus dem Monitoring-Modell (Tagesmonitor), dazu das Prognose-LSTM für plötzliche Fehler; Fehlererkennung und Klasse aus der LSTM-Kette; Netzvergleich als Bestätigung, die die Dringlichkeit hebt. | 11, 20, 27 bis 31 |
| 39 | Endmodell: Modell Ivelina gegen Modell LSTM<br>`39_endmodell.ipynb` | Im Projekt gibt es zwei fertige Ansätze: Modell Ivelina (Kennlinie und Netzvergleich) und Modell LSTM (neuronales Netz). | Keins der beiden Modelle ist allein besser. Modell Ivelina übernimmt Heizperiode, Erfolgskontrolle und Netzvergleich, Modell LSTM die warmen Tage und die Fehlerart Ventil (mit Ivelinas Fehlerbild als Bestätigung). | 27 bis 31 |
| 40 | Dashboard: Handlungsempfehlungen auf dem Rohrbaum<br>`40_dashboard.ipynb` | Das fertige Dashboard: Es zeigt auf dem Rohrbaum aus Notebook 35 für jede Hausstation, was die Modelle aus Notebook 39 sagen. | Ein Dashboard mit drei Reitern auf dem Rohrbaum aus Notebook 35: Karte, Handlungsliste und „So funktioniert's“. Jede Anzeige kommt von dem Modell, das in Notebook 39 dafür am besten abgeschnitten hat. | 34, 39, `python -m src.dashboard_daten` |

## Wichtige Abhängigkeiten

- Notebook 11 schreibt die Tageswerte `hast_tage` für die Notebooks 20, 32, 37 und 38.
- Notebook 20 schreibt das Normalverhaltensmodell für die Notebooks 32 und 38.
- Die Notebooks 27 bis 31 schreiben Modelldaten, LSTM-Embedding und Ventil-Modell für 38 und 39.
- Notebook 26 schreibt den Monitor-Status für Notebook 36.
- Notebook 34 baut den Netz-Cache `notebooks/daten_cache/` für die Notebooks 35, 36 und 40.
- Notebook 39 baut die Modellpakete in `models/` für das Dashboard in Notebook 40.
- Notebook 08 braucht `inspections_tidy.csv` aus `python -m src.main`.

## Alte und neue Nummern

Im Projektverlauf gab es andere Dateinamen und Nummern. Ältere Notizen und der Changelog nutzen sie noch.

| Neu | Alter Dateiname |
|---|---|
| `00_daten.ipynb` | `00_eda_hast_stationsprofile.ipynb` |
| `01_luecken.ipynb` | `luecken.ipynb` |
| `02_wirkung.ipynb` | `03_wirkungsanalyse_begehungen.ipynb` |
| `03_labels.ipynb` | `05_label_findung_defektdefinition.ipynb` |
| `04_wintervergleich.ipynb` | `07_jahresvergleich.ipynb` |
| `05_performance.ipynb` | `08_performance.ipynb` |
| `06_arima.ipynb` | `arima.ipynb` |
| `07_stationscluster.ipynb` | `01_kmeans_stationscluster.ipynb` |
| `08_clusterbenchmark.ipynb` | `04_clustering_benchmark.ipynb` |
| `09_stundencluster.ipynb` | `04_kmeans_operatingConditions.ipynb` |
| `10_clustervalidierung.ipynb` | `09_clustervalidierung.ipynb` |
| `11_tagescluster.ipynb` | `06_tagesmerkmale_clusteranalyse.ipynb` |
| `12_gesamtpipeline.ipynb` | `02_gesamtpipeline_rohdaten_bis_wartungsbenchmark.ipynb` |
| `13_ternaer.ipynb` | `12_ternaer.ipynb` |
| `14_stationsbilder.ipynb` | `13_stationsbilder.ipynb` |
| `15_kennlinienmonitor.ipynb` | `14_monitor.ipynb` |
| `16_befunde.ipynb` | `15_befunde.ipynb` |
| `17_fallsammlung.ipynb` | `fallsammlung.ipynb` |
| `18_anomalie.ipynb` | `10_anomalie.ipynb` |
| `19_empfehlung.ipynb` | `11_empfehlung.ipynb` |
| `20_normalverhalten.ipynb` | `17_normalverhaltensmodell.ipynb` |
| `21_netzvergleich.ipynb` | `netzvergleich.ipynb` |
| `22_tagesmonitor.ipynb` | `tagesmonitor.ipynb` |
| `23_alarme.ipynb` | `alarme.ipynb` |
| `24_bestwert.ipynb` | `27_bestwert.ipynb` |
| `25_nachbarn.ipynb` | `23_nachbarn.ipynb` |
| `26_netzereignisse.ipynb` | `24_netzereignisse.ipynb` |
| `27_modelldaten.ipynb` | `18_modelldaten_labels.ipynb` |
| `28_einstufung.ipynb` | `19_kmeans_einstufung_folie5.ipynb` |
| `29_lstm.ipynb` | `20_lstm_fehlererkennung.ipynb` |
| `30_prognose_lstm.ipynb` | `21_prognose_lstm_waechter.ipynb` |
| `31_xgboost.ipynb` | `22_xgboost_fehlerklassen.ipynb` |
| `32_waechtervergleich.ipynb` | `23_vergleich_waechter.ipynb` |
| `33_bayes.ipynb` | `31_bayes_diagnose.ipynb` |
| `34_netz.ipynb` | `16_Netz.ipynb` |
| `35_einspeisung.ipynb` | `28_Netz_experimente.ipynb` |
| `36_netzkarte.ipynb` | `25_netzkarte.ipynb` |
| `37_gnn.ipynb` | `30_gnn_entwurf.ipynb` |
| `38_modellvergleich.ipynb` | `32_modellvergleich.ipynb` |
| `39_endmodell.ipynb` | `34_modellvergleich_und_umsetzung_nach_aufgabenstellung.ipynb` |
| `40_dashboard.ipynb` | `35_dashboard.ipynb` |
