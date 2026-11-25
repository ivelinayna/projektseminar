# Grenzen der Methoden und Modelle

Diese Seite sammelt, wo die Verfahren aufhören und was ihre Zahlen nicht aussagen. Jeder Punkt verweist auf die
Stelle, an der das aufgefallen ist. Grenzen, die schon in den Daten liegen, stehen unter
[Grenzen der Daten](daten.md).

## Was die Fallzahl bedeutet

- Im Test stehen 43 Begehungen, darunter 11 Ventil- und 9 Vertragsfälle. Unterschiede unter etwa 0,1 AUC oder unter
  etwa 5 Fällen sind damit nicht sichtbar. „Nicht gesichert“ heißt hier meist, dass die Daten nicht reichen, nicht dass
  es keinen Unterschied gibt ([Modellvergleich](../vergleich/modellvergleich.md#grenzen)).
- Ein Netz, das direkt auf die Befunde lernt, würde bei 11 Ventilfällen jede Station auswendig lernen. Deshalb lernt
  das LSTM ohne Labels, und erst eine logistische Regression sieht die Befunde
  ([LSTM-Fingerabdruck](../modelle/lstm.md)). Ein einzelnes fragliches Label verschiebt die Winter-AUC beim Ventil um
  0,06 ([LSTM-Fingerabdruck](../modelle/lstm.md#das-endgultige-netz)).
- Das Modell im Dashboard hängt beim Ventil vom Startwert des LSTM ab: Mit anderen Startwerten liegt die AUC zwischen
  0,83 und 0,90 (Notebook 35, Abschnitt 8.4).
- Auch im Monitoring sind die Fallzahlen klein: 4 chronisch auffällige Stationen mit Befund im Netzvergleich, 7
  mechanische Fälle im Tagesmonitor, viele Tests nebeneinander
  ([Netzvergleich](../monitoring/netzvergleich.md#einordnung),
  [Tagesmonitor](../monitoring/tagesmonitor.md#einordnung)).
  Die Tendenz von Priorität und Fehlerbild „ventil“ zu Ventilbefunden beruht auf drei Fällen
  ([Alarme bewerten](../monitoring/alarme.md#einordnung)).
- Der Abgleich der Stundencluster mit den Begehungen stützt sich auf nur 13 Stationen ohne Maßnahme
  ([Stundencluster und Validierung](../clustering/validierung.md#einordnung)).

## Wirkung der Begehungen

- **Nur „konsistent mit“.** Die Begehungen und damit auch die Kontrollgruppe sind nicht zufällig zugeteilt. Der
  Wintervergleich zeigt gegen die Kontrollgruppe −2,0 K beim Rücklauf (p ≈ 0,008), fast alle Fälle liegen aber in
  einem Winterpaar mit 21 % kälterem Winter danach ([Wintervergleich](../begehungen/wintervergleich.md#einordnung)).
- **Ohne Kontrollgruppe ist das Bild unsicherer.** Die Performance steigt je nach Rechnung um 4 bis 9 %, Station für
  Station ist das nicht gesichert. Die Phase „optimiert“ war zudem im Mittel 2,3 bis 2,7 K kälter
  ([Performance](../begehungen/performance.md#einordnung)). In den Stationsbildern fehlt eine Kontrollgruppe ganz
  ([Stationsbilder](../stationsbilder/index.md#was-offen-bleibt)).
- **Mit ganzen Wintern ist keine Wirkung nachweisbar.** Im Netzvergleich unterscheiden sich 41 begangene und 29 nicht
  begangene Stationen nicht (p 0,30 bis 0,92)
  ([Netzvergleich](../monitoring/netzvergleich.md#teil-b-kernwinter-vor-gegen-kernwinter-nach-der-begehung)).
- **Der typische Fall ändert sich kaum.** Nach Begehungen gibt es häufiger einen deutlichen Sprung im Rücklauf, im
  Median ändert sich aber wenig ([ARIMA](../begehungen/arima.md#einordnung)).

## Was die Modelle nicht erkennen

- **Regelungsoptimierung:** Kein Modell trifft sie. In Notebook 35 landen 24 bzw. 25 von 31 Fällen in „kein
  Handlungsbedarf“ ([Endmodell](../ergebnisse/endmodell.md#gewahltes-modell-je-frage)).
- **Filter, Durchfluss und Sollwert als Ursache:** AUC 0,26 bis 0,57. Nach diesen Maßnahmen bleibt die Station in den
  Zählerdaten gleich ([Endmodell](../ergebnisse/endmodell.md#gewahltes-modell-je-frage),
  [Verworfene Ansätze](verworfene_ansaetze.md#fehlerarten-ohne-messspur)).
- **Dämmung:** Das LSTM-Modell findet ein Muster (AUC 0,78), die Ursache ist aber physikalisch nicht erklärt. Ein
  erster physikalischer Hinweis, die Abkühlrate im Stillstand, ist nicht gesichert (AUC 0,69)
  ([Endmodell](../ergebnisse/endmodell.md#warum-diese-wahl),
  [Modellvergleich](../vergleich/modellvergleich.md#warum-das-so-ausgeht)).
- **Regelhysterese:** Stundenwerte sind Momentaufnahmen, und die Wächter rechnen mit Tagesmitteln. Eine eingebaute
  6-Stunden-Schwingung findet keiner (höchstens 15 % bei höchstens 10 % Fehlalarmen)
  ([Datenanalyse](../ergebnisse/datenanalyse.md#schwingende-regelung),
  [Endmodell](../ergebnisse/endmodell.md#gewahltes-modell-je-frage)).
- **Fühlerfehler und verstellter Sollwert:** Das Prognose-LSTM erkennt einen hängenden Fühler zu 43 %, einen um 5 K
  verstellten Sollwert zu 19 %. Ein solcher Sollwert liegt in der normalen Schwankung von Tag zu Tag
  ([Prognose-LSTM](../modelle/prognose.md#der-endgultige-wachter)).
- **Frühwarnung:** nicht prüfbar, weil der Fehlerbeginn fehlt. Vor Begehungen gibt es nicht mehr
  Verschlechterungsalarme als bei den Kontrollen, die Treffer kommen aus Besserungsalarmen danach
  ([Alarme bewerten](../monitoring/alarme.md#einordnung)).
- **Fehler, die schon im Lernjahr bestanden:** Wer eine Station mit sich selbst vergleicht, lernt einen Dauerfehler
  als normal mit. Beim Ventilfall 68956351 war das Ventil schon im Lernjahr offen
  ([Tagesmonitor](../monitoring/tagesmonitor.md#einordnung),
  [Anomalien und Monitoring](../monitoring/index.md#gesamtbild)).
- **Offenes Ventil oder Kurzschluss:** Im Messbild sehen beide gleich aus. 68956351 wird in der Musterzuordnung als
  Kurzschluss statt als Ventil eingeordnet ([Von der Anomalie zur Empfehlung](../monitoring/empfehlung.md#einordnung)).
- **Stationstypen:** Das Clustering findet keine klaren Gruppen von Stationen (Silhouette unter 0,25)
  ([Merkmale und Clustering](../clustering/index.md#gesamtbild)).

## Wächter

- **Eingebaute Fehler** zeigen, was ein Wächter grundsätzlich erkennen kann, nicht seine Trefferquote bei echten
  Fehlern ([Endmodell](../ergebnisse/endmodell.md#warum-diese-wahl)).
- **Das Prognose-LSTM** bemerkt echte Begehungen nicht öfter als Vergleichsstationen, in Notebook 30 16 von 43 gegen
  32 % ([Modellvergleich](../vergleich/modellvergleich.md)). Es bekommt die letzten 7 Tage als Eingang, eine bleibende
  Veränderung wird so schnell Teil seiner Erwartung ([Prognose-LSTM](../modelle/prognose.md#der-endgultige-wachter)).
- **Nach einem Eingriff** kennt das Prognose-LSTM die Station nur von vorher. Beim Ventiltausch in Notebook 30 meldet
  es die Station nach 7 Tagen und danach noch zweimal, nach 22 und 33 Tagen. Nach einem bekannten Eingriff muss es neu
  kalibriert werden ([Probebetrieb](../ausblick/probebetrieb.md#regeln-fur-den-betrieb)).
- **Die Referenz des Monitoring-Modells veraltet:** An 43 % der Testtage steht eines seiner Konten am Deckel, bei 31
  von 81 Stationen mehr als die Hälfte der Zeit. Dann kann es nicht neu melden (Notebook 35,
  [Dashboard](../ergebnisse/dashboard.md#grenzen)).
- **Hohe Alarmlast:** Kälteeinbrüche lösen Wellen von Alarmen aus (siehe [Grenzen der Daten](daten.md#auentemperatur)),
  und eine dauerhafte Änderung wird nur einmal gemeldet ([Tagesmonitor](../monitoring/tagesmonitor.md#einordnung)).
- **Abkühlungskanal des Normalverhaltensmodells:** Die Kennlinie bringt auf neuen Tagen kaum etwas, und nur 41 % der
  Treffer zeigen in Richtung Verbesserung. Der hohe Hebel ist deshalb vorsichtig zu lesen
  ([Normalverhaltensmodell](../monitoring/normalverhalten.md#einordnung)).
- **Keine Meldung heißt nicht „in Ordnung“.** 7 Stationen sind noch nicht bewertbar, weil ihnen die Referenz fehlt
  ([Dashboard](../ergebnisse/dashboard.md#keine-meldung-heit-nicht-in-ordnung)).

## Beschreiben, nicht vorhersagen

- **Auffällig heißt nicht defekt.** Die Datenanalyse findet ungewöhnliches Verhalten, ob ein Fehler dahintersteckt,
  zeigen die Messdaten allein nicht ([Datenanalyse](../ergebnisse/datenanalyse.md#grenzen)).
- **Netzvergleich und Potenzial** beschreiben eine Station, sagen die Wirkung einer Begehung aber kaum vorher
  (Rangkorrelation 0,16). Das Dashboard nennt deshalb keine Einsparung
  ([Endmodell](../ergebnisse/endmodell.md#warum-diese-wahl)).
- **Der Bestwert-Maßstab** sagt weder Befunde vorher, noch zeigt er eine Verbesserung nach den Begehungen
  ([Bestes Viertel](../monitoring/bestwert.md#einordnung)).
- **Die Residuen** bringen gegenüber dem rohen Rücklauf keinen Gewinn, das Netzmodell erklärt wenig (R² = 0,035)
  ([Anomalieerkennung](../monitoring/anomalie.md#einordnung)).
- **Fehlerbilder** sind beschreibend, keine geprüfte Diagnose ([Alarme bewerten](../monitoring/alarme.md#einordnung)).

## Empfehlungen

- **Der Ventil-Score** ist eine Rangfolge, keine Wahrscheinlichkeit. Er sinkt nach jeder Begehung, nicht nur nach
  einem Ventiltausch
  ([Handlungsempfehlungen](../ergebnisse/handlungsempfehlungen.md#wie-verlasslich-die-empfehlungen-sind)).
- **Grenzen und Stufen sind gesetzt:** Ventil- und Dämmungs-Score ab 0,5, die Dringlichkeitsstufen nach festen Regeln.
  Nur die Grenze für die Kapazität ist aus den Daten gewählt
  ([Handlungsempfehlungen](../ergebnisse/handlungsempfehlungen.md#dringlichkeit)). Getestet sind die Stufen nicht
  ([Modellvergleich](../vergleich/modellvergleich.md#grenzen)).
- **Muster und Maßnahme:** Welche Maßnahme zu welchem Muster gehört, ist physikalisch begründet, bleibt aber ein
  Vorschlag für die ÜZ ([Von der Anomalie zur Empfehlung](../monitoring/empfehlung.md#einordnung)).
- **Dämmung erscheint oft.** Sie ist bei 41 % der begangenen Stationen eingetragen, das Modell gibt dazu nur einen
  Hinweis ([Dashboard](../ergebnisse/dashboard.md#grenzen)).
- **Ein Stand je Station:** Empfehlung und Verdacht gelten für den letzten Winter mit genug Daten und ändern sich nicht
  mit dem Zeitregler der Karte ([Dashboard](../ergebnisse/dashboard.md#grenzen)).

## Gesetzt, nicht hergeleitet

Viele Schwellen sind gesetzt, nicht aus den Daten hergeleitet. Wo sie stehen:

| Verfahren | gesetzte Werte | Seite |
|---|---|---|
| Label aus Messdaten | Durchfluss über 50 l/h, Spreizung unter 8 K | [Label aus Messdaten](../begehungen/labels.md#die-regel) |
| Vierfeldertafel, Wintervergleich, Stationsbilder, Netzvergleich | Rücklauf über 50 °C gilt als schlecht | [Wintervergleich](../begehungen/wintervergleich.md#vierfeldertafel) |
| Anomalieerkennung | Zielquote von rund 15 % Treffern je Regel | [Anomalieerkennung](../monitoring/anomalie.md#einordnung) |
| Empfehlung | Mindestevidenz, Persistenzschwelle, Stufen und Gewichte | [Von der Anomalie zur Empfehlung](../monitoring/empfehlung.md#einordnung) |
| Normalverhaltensmodell | k = 0,5, h = 5, Referenz 365 Tage, mindestens 60 Heiztage und 8 K Spanne, Heizgrenze 15 °C, Treffer-Fenster 7 bis 60 Tage, Normtemperatur 5 °C | [Normalverhaltensmodell](../monitoring/normalverhalten.md#einordnung) |
| Tagesmonitor | dazu Deckel des Kontos 10, Toleranz ±2 Stunden um Mitternacht, 30 Heiztage | [Tagesmonitor](../monitoring/tagesmonitor.md#einordnung) |
| Netzvergleich | schlechtestes Zehntel, mindestens 2 Kennzahlen, 2 Winter für chronisch, 300 Betriebsstunden, 20 Stationen je Winter, Leistungsklassen 5 und 10 kW, 7 Tage Puffer | [Netzvergleich](../monitoring/netzvergleich.md#einordnung) |
| Bestes Viertel | Grenzen der Potenzialstufen | [Bestes Viertel](../monitoring/bestwert.md#einordnung) |
| Dashboard | Ventil- und Dämmungs-Score ab 0,5, Dringlichkeitsstufen | [Handlungsempfehlungen](../ergebnisse/handlungsempfehlungen.md#dringlichkeit) |

## Wie geprüft wurde

- **Rückblickend geprüft:** Alle Zahlen stammen aus vorhandenen Daten. Ob die Liste im Betrieb trägt, zeigt erst ein
  Test nach vorn ([Prüfung nach vorn](../ausblick/pruefung.md)).
- **Erst der strenge Prüfstand zählt.** Im ersten Prüfstand waren Schwellen in den Testfällen eingestellt, und der
  Encoder hatte die Teststationen gesehen. Notebook 35 rechnet deshalb strenger, die Ventil-AUC sinkt dort von 0,89 auf
  0,84 ([Modellvergleich](../vergleich/modellvergleich.md#was-zuerst-nicht-stimmte)). Im Normalverhaltensmodell sind die
  Fälle wenige und nicht unabhängig, die p-Werte eher zu optimistisch
  ([Normalverhaltensmodell](../monitoring/normalverhalten.md#einordnung)).
- **Nicht alles ist vergleichbar.** GNN und Bayes-Diagnose fehlen Eingaben, die die übrigen Modelle haben. Sie sind
  deshalb nicht im gemeinsamen Vergleich ([Modellvergleich](../vergleich/modellvergleich.md)).
- **Ein Teilnetz:** Alle Modelle sind auf einem Teilnetz gelernt und geprüft. Ob sie auf andere Teilnetze passen, ist
  offen ([Weiterentwicklung](../ausblick/weiterentwicklung.md)).
