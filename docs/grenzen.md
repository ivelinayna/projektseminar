# Grenzen und offene Fragen

Diese Seite sammelt, worauf die Ergebnisse beruhen und wo sie aufhören.
Probleme in den Rohdaten stehen in der Tabelle
[Bekannte Probleme](daten.md#bekannte-probleme) und werden hier nicht wiederholt.
Ansätze, die nicht funktioniert haben, stehen unter [Negativbefunde](negativbefunde.md).

## Annahmen

- Die Begehungen sind die einzige Quelle für Labels.
    - Es gibt 66 Begehungen, 57 davon mit Freitext.
    - Ein leeres Kästchen im Protokoll gilt als „nein“ (NB 25). Ein ausdrückliches „nein“ steht nur selten im Protokoll.
    - Was im Protokoll steht, gilt als der Fehler. Was nicht drinsteht, gilt als nicht vorhanden. Das gilt nur für begangene Stationen.
    - Nie begangene Stationen gelten als unbekannt, nicht als gesund (NB 35).
    - Warum nötig: Es gibt keine andere Rückmeldung aus dem Betrieb.
- Die Außentemperatur kommt von der DWD-Station Kitzingen (Nr. 2600) und gilt für das ganze Netz.
    - Warum nötig: Im Netz selbst wird keine Außentemperatur gemessen. Kitzingen ist die nächste Station mit lückenlosen Stundenwerten (rund 13 km entfernt, NB 10).
- Der Netzvergleich nutzt nur den Kernwinter (Dezember bis Februar) und nur Betriebsstunden (NB 19).
    - Stunden ±7 Tage um eine Begehung fallen heraus.
    - Eine Station braucht mindestens 300 Betriebsstunden im Winter.
    - Warum nötig: So hängen die Kennzahlen weniger vom Wetter und von Eingriffen ab.
- Als Heizgrenze gelten 15 °C Außentemperatur (NB 18, NB 20).
- Zähler und Abnahmestelle werden immer über `Zuordnung.xlsx` verbunden.
    - So lassen sich alle 66 Begehungsadressen einem Zähler zuordnen, über `Nodes_Edges.ods` nur 54 (NB 02).
    - Der Anschlusswert steht nur in `Nodes_Edges.ods`. Dort steht teils schon der Wert nach der Begehung. Deshalb wird die Auslastung mit der alten Vertragsleistung gerechnet (NB 25).
- Sonderfälle bei Zählern und Gebäuden (NB 00):
    - 8 Zähler sind laut ÜZ keine Übergabestationen und fallen heraus: BHKW 86792512, Kessel I bis IV, Ölspitzenkessel, zwei Temperaturfühler im Heizhaus.
    - Der Netzmedian im Netzvergleich und im Tagesmonitor wird ohne BHKW gebildet.
    - Die Datei `721354800__n.csv` hat eine 0 zu viel und gehört zu Zähler 72135480.
    - Einige Gebäude haben zwei Zähler.
    - Zähler 72167783 hat seit April 2025 keine Abnahme mehr, aber Zirkulation.
- Die Referenz einer Station gilt als „normal“.
    - Der Wächter lernt je Station ein Referenzjahr. Ein Fehler, der schon in diesem Jahr bestand, wird mitgelernt (Beispiel Zähler 68956351).
- Viele Schwellen sind gesetzt, nicht hergeleitet.
    - Beispiele: CUSUM mit k = 0,5 und h = 5, Deckel 10, Referenz 365 Tage, Fenster −7 bis +60 Tage um die Begehung, Leistungsklassen 5 und 10 kW.
    - Die Zielquote von rund 15 % Treffern je Regel ist gesetzt (NB 16), ebenso Stufen und Gewichte der Empfehlung (NB 17).
- Die Lage der Einspeisung ist aus dem Wärmenetzplan angenommen (NB 32, NB 39). Die Richtung der Kanten ist offen.
- Die Fehler-Symptom-Matrix im Bayes-Modell ist ein Entwurf (NB 38).
    - 0 von 132 Feldern sind mit der ÜZ abgestimmt.
    - Der Anteil gesunder Stationen ist mit 50 % angenommen.

## Grenzen

### Wenige Fälle

- Im Test stehen 43 Begehungen, darunter 11 Ventilfälle und 9 Fälle mit zu großer Vertragsleistung.
- Unterschiede unter etwa 0,1 AUC oder unter etwa 5 Fällen sind damit nicht sichtbar.
- Bei 11 Ventilfällen schwankt die AUC je nach Trainingslauf um etwa ±0,15 (NB 27, NB 34).
- Ein einziges Label verschiebt die Winter-AUC beim Ventil um 0,06 (NB 27).
- Mechanische Eingriffe sind nur bei 19 Terminen kodiert (NB 14).
- Die größte Fehlerkategorie hat 9 Fälle. Für einen Entscheidungsbaum über alle Kategorien reicht das nicht.
- Nur 10 begangene Stationen liegen in der „schlechteren“ Gruppe der Einstufung (NB 26).

### Datenzeitraum

- Die CSV-Daten enden im Juli 2025. Die Nachlieferung reicht bis Juli 2026, aber nur für 5 Zähler.
- Für den Winter 2025/26 fehlen damit fast alle Zähler. Der Netzvergleich hat dort nur 4 Stationen und gibt keine Netzwerte aus. Nötig wären mindestens 20 (NB 19).
- Der Winter 2021/22 fällt heraus, weil es damals nur Tageswerte gab.
- Der Winter 2022/23 hat nur 41 Stationen. Ein Vergleich zweier Winter geht nur mit diesen 41 Zählern.
- Viele Stationen haben Daten erst ab Herbst 2023.
- Ein Zählertausch ist nicht zusammengeführt. Eine Station mit Tausch erscheint als zwei Zähler (NB 18).
- Gut ein Fünftel der Stunden im Raster hat keine Messung, der größte Teil davon in der Tageswert-Phase bis November 2022 (NB 01). Gefüllte Stunden sind gerechnet, nicht gemessen.

### Begehungen und Kausalität

- Die Begehungen wurden nicht zufällig ausgewählt. Die meisten lagen zwischen August und November 2024.
- Die Kontrollgruppe ist nicht zufällig zugeteilt. Aussagen zur Wirkung sind deshalb nur „konsistent mit“, kein Nachweis.
- Der Wintervergleich zeigt nach der Begehung eine niedrigere Rücklauftemperatur (Diff-in-Diff −2,0 K, p ≈ 0,008, NB 04). Der Winter danach war aber 21 % kälter.
- Gegen 29 Kontrollstationen ist im Netzvergleich keine Wirkung nachweisbar (p zwischen 0,30 und 0,92, NB 19).
- Ohne Kontrollgruppe sind die Ergebnisse zur Wirkung schwächer. Beispiel NB 05: Die Phase „optimiert“ war im Mittel 2,3 bis 2,7 K kälter.
- Der Beginn eines Fehlers ist nie bekannt. Ob ein Wächter einen Fehler früh erkennt, lässt sich deshalb nicht prüfen.

### Was die Modelle nicht erkennen

- Fühlerfehler sind kaum zu sehen. „Fühler hängt“ wird zu 43 % erkannt, ein um 5 K verstellter Sollwert zu 19 % (NB 28). Das ist nur an eingerechneten Fehlern geprüft, nicht an echten.
- Regelungsoptimierung, Filter, Durchfluss und Hysterese sind als Ursache nicht erkennbar (AUC um oder unter 0,5).
- Stundenwerte sind Momentaufnahmen. Takten der Regelung erscheint darin als Rauschen.
- Dämmung ist statistisch erkennbar, aber physikalisch nicht erklärt. Die Flottenkennzahlen zeigen die umgekehrte Richtung (NB 27, NB 38).
- Das Prognose-LSTM ist nur an eingerechneten Fehlern geprüft, nicht an echten Ereignissen. Das Normalverhaltensmodell ist umgekehrt nicht an eingerechneten Fehlern geprüft (NB 30).
- Stationen, die von Anfang an falsch eingestellt sind, haben keine gesunde Referenz (NB 13).
- Stillstand sieht der Kennlinienmonitor nicht (NB 13).

### Wächter und Alarme

- Der Tagesmonitor vergleicht mit einer festen Referenz (NB 20).
    - An 43 % der Testtage steht ein Konto am Deckel.
    - Bei 31 von 81 Stationen ist das mehr als die Hälfte der Zeit so.
- Der Wächter eignet sich für die Erfolgskontrolle nach einer Begehung, nicht als Frühwarnung.
- Die Alarmlast ist hoch. Kälteeinbrüche lösen Wellen aus, zum Beispiel vom 09. bis 12.12.2022 bei 12 von 40 Stationen (NB 20).
- 7 Stationen sind „noch nicht bewertbar“, weil ihnen die Referenz fehlt.
- Die Parameter für das Alarmbudget wurden an denselben Fällen gewählt, an denen sie geprüft wurden. Die p-Werte sind daher leicht zu günstig.
- Die Dringlichkeitsstufen sind nicht vorab an neuen Begehungen getestet.
- Keine Meldung heißt nicht, dass eine Station in Ordnung ist.
- Potenzial und Netzeffizienz beschreiben den Ist-Zustand. Sie sagen keine Einsparung voraus. Euro-Beträge werden nicht genannt.

### Netz

- Der Netzgraph ist logisch, nicht hydraulisch. Leitungslängen, Durchmesser und Drücke fehlen (NB 23).
- 35 von 110 Kanten haben keinen Rohrweg (NB 39).
- Die Pfeile in `Nodes_Edges.ods` passen zu keiner Quelle. Gegen die angenommene Einspeisung zeigen etwa gleich viele hin wie weg (NB 39).
- Ein Einfluss des Strangs auf die Fehler ist nicht nachweisbar (NB 23, NB 32, NB 34).

### Vergleichbarkeit und Übertragbarkeit

- Alle Modelle sind nur auf einem Teilnetz gelernt und geprüft. Ob sie auf andere Teilnetze passen, ist offen.
- Das GNN (NB 39) und das Bayes-Modell (NB 38) lassen sich nicht mit den übrigen Modellen vergleichen, weil ihnen Eingaben fehlen. Details unter [Modellvergleich](modellvergleich.md).
- Die Stationscluster (NB 07, NB 08) nutzen die ganze Historie, also auch die Zeit nach der Begehung. Für einen Vergleich mit Labels sind sie deshalb ungeeignet.
- Auf Stationsebene gibt es keine klaren Typen. Die Silhouette bleibt unter 0,25, die Flotte ist eher ein Kontinuum (NB 07, NB 08).

## Offene Fragen an die ÜZ

- Zählerwechsel
    - Wann wurde welcher Zähler getauscht?
    - Gab es vor November 2022 einen Wechsel der Messauflösung?
- Begehungen
    - Welche Reparaturen fehlen in der Begehungstabelle? Beispiel Zähler 68956351: Ventil- und Stellmotortausch stehen nur im Freitext.
    - Welche Daten gehören zu den 8 Begehungen ohne Datum?
    - Gibt es Begehungen nach Juli 2025, möglichst mit Zählerständen?
    - Können die chronisch auffälligen, nie begangenen Stationen 68956360, 72135453, 72135480 und 72167793 begangen werden?
    - Was steckt hinter den Stationen 72135442, 80912173 und 68956359, die nach der Begehung mehr Wasser brauchen?
    - Was ist bei Zähler 72167783 passiert? Der Rücklauf stieg nach der Begehung von 18,6 auf 71,0 °C.
    - Was erklärt die großen Sprünge im Herbst 2024 ohne Begehung (72167777, 69513891, 80956410, NB 06)?
    - Kann das Protokoll künftig festhalten, ob etwas kaputt war, und nicht nur, was gemacht wurde? Sollwert und Filter wurden bei 62 % und 47 % der Begehungen gemacht, eine Spur im Zähler hinterlassen sie nicht (NB 36).
- Betrieb
    - Welche Alarmlast ist im Betrieb tragbar?
    - Soll die CUSUM-Schwelle bei h = 5 bleiben oder auf h = 8 steigen? h = 8 bringt etwa ein Drittel weniger Alarme.
    - Wo sollen die Grenzen der Dringlichkeitsstufen liegen?
    - Welche Maßnahme gehört zu welchem Fehlerbild?
- Fehlerkategorien
    - Passen die neun Fehlerkategorien?
    - Sollen Zirkulation und Pumpe getrennt geführt werden?
    - Ist Dämmung ein Befund an der Übergabestation?
    - Kann die ÜZ die Fehler-Symptom-Matrix und den Anteil gesunder Stationen abstimmen?
- Erzeuger und Sonderzähler
    - Wie sollen BHKW und Kessel in der Auswertung behandelt werden?
    - Was sind die Zähler 58202380 und 66761022? Sie fallen in allen Clusterverfahren als Ausreißer auf (NB 07, NB 08).
- Netz und Hydraulik
    - Wo liegen die Heizzentrale und die Einspeisepunkte?
    - Was bedeuten die Pfeile in `Nodes_Edges.ods`?
    - Gibt es ein hydraulisches Netzmodell, Rohrdaten (Nennweite, Länge) oder Differenzdrücke?
    - Gibt es die Vorlauftemperatur am Ausgang der Heizzentrale?
    - Wie sollen Übergabestationen ohne Kante im Netz behandelt werden?
- Weitere Daten
    - Gibt es Minutenwerte oder Reglerdaten mit Stellsignal? Ohne sie bleibt Hysterese unsichtbar.
    - Gibt es das Baujahr je Gebäude? Es ist der letzte ungeprüfte Störfaktor für das Dämmungsmuster des gelernten Modells (NB 36).

## Mögliche nächste Schritte

- Die Referenz je Station nach jeder Begehung und zu jeder Heizperiode neu lernen.
- Einen Test vorab festlegen: auffällige Stationen und gleich viele zufällig gewählte begehen, ohne dass das Team vor Ort weiß, welche welche ist.
- Die Fehler-Symptom-Matrix mit der ÜZ abstimmen. Je Befund den geschätzten Beginn des Fehlers erfassen.
- Die Außentemperatur über 2 bis 3 Tage glätten, damit Kälteeinbrüche weniger Alarme auslösen.
- Den Nachtdurchfluss im Sommer als Kennzahl in den Netzvergleich aufnehmen.
- Den Winter 2025/26 auswerten, sobald Daten für mehr Zähler vorliegen.
- Neue Begehungen nach vorab festgelegten Regeln auswerten.
- Die Abkühlrate im Stillstand (Dämmung) und die Filter-Sättigung an neuen Daten prüfen, Richtung vorab festgelegt (NB 36).
- Die Pipeline auf weitere Teilnetze übertragen.
