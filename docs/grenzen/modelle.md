# Grenzen der Modelle

Diese Seite sammelt, wo die Modelle aufhören und was ihre Zahlen nicht aussagen.

## Lernende Modelle und Modellvergleich

### Wenige Fälle

- Im Test stehen 43 Begehungen, darunter 11 Ventil- und 9 Vertragsfälle. Unterschiede unter etwa 0,1 AUC oder unter
  etwa 5 Fällen sind damit nicht sichtbar. „Nicht gesichert“ heißt hier meist, dass die Daten nicht reichen, nicht dass
  es keinen Unterschied gibt.
- Ein Netz, das direkt auf die Befunde lernt, würde bei 11 Ventilfällen jede Station auswendig lernen. Deshalb lernt
  das LSTM ohne Labels, und erst eine logistische Regression sieht die Befunde (siehe
  [LSTM-Fingerabdruck](../modelle/lstm.md)).
- Das Modell im Dashboard hängt beim Ventil vom Startwert des LSTM ab: Mit anderen Startwerten liegt die AUC zwischen
  0,83 und 0,90 (Notebook 35).

### Labels

- Labels gibt es nur für begangene Stationen. Die nie begangenen gelten als unbekannt, nicht als gesund.
- „Gemacht“ heißt nicht „war kaputt“. Leere Kästchen im Protokoll werden als „nein“ gelesen.
- Die Begehungen waren nicht zufällig ausgewählt.
- Der Beginn eines Fehlers ist bei keinem Befund bekannt. Ob ein Modell einen Fehler früh erkennt, lässt sich deshalb
  nicht prüfen.

### Was die Modelle nicht erkennen

- **Regelungsoptimierung:** Kein Modell trifft sie. In Notebook 35 landen 24 bzw. 25 von 31 Fällen in „kein
  Handlungsbedarf“.
- **Filter, Durchfluss und Sollwert als Ursache:** AUC 0,26 bis 0,57. Nach diesen Maßnahmen bleibt die Station in den
  Zählerdaten gleich (Notebook 36).
- **Dämmung:** Das LSTM-Modell findet ein Muster (AUC 0,78), die Ursache ist aber physikalisch nicht erklärt. Ein
  erster physikalischer Hinweis, die Abkühlrate im Stillstand, ist nicht gesichert (AUC 0,69, Notebook 36).

### Wächter

- **Eingebaute Fehler** zeigen, was ein Wächter grundsätzlich erkennen kann, nicht seine Trefferquote bei echten
  Fehlern.
- **Das Prognose-LSTM** bemerkt echte Begehungen nicht öfter als Vergleichsstationen, in Notebook 30 16 von 43 gegen
  32 %. Es bekommt die letzten 7 Tage als Eingang, eine bleibende Veränderung wird so schnell Teil seiner Erwartung.
- **Nach einem Eingriff** kennt das Prognose-LSTM die Station nur von vorher. Beim Ventiltausch in Notebook 30 meldet
  es die Station nach 7 Tagen und danach noch zweimal, nach 22 und 33 Tagen. Nach einem bekannten Eingriff muss es neu
  kalibriert werden.
- **Die Referenz des Monitoring-Modells veraltet:** An 43 % der Testtage steht eines seiner Konten am Deckel, dann
  kann es nicht neu melden (Notebook 35).

### Empfehlungen

- **Der Ventil-Score** ist eine Rangfolge, keine Wahrscheinlichkeit. Er sinkt nach jeder Begehung, nicht nur nach
  einem Ventiltausch.
- **Grenzen und Stufen sind gesetzt:** Ventil- und Dämmungs-Score ab 0,5, die Dringlichkeitsstufen nach festen Regeln.
  Nur die Grenze für die Kapazität ist aus den Daten gewählt.
- **Rückblickend geprüft:** Alle Zahlen stammen aus vorhandenen Daten. Ob die Liste im Betrieb trägt, zeigt erst ein
  Test nach vorn (siehe [Prüfung nach vorn](../ausblick/pruefung.md)).
- **Ein Teilnetz:** Alle Modelle sind auf einem Teilnetz gelernt und geprüft. Ob sie auf andere Teilnetze passen, ist
  offen.
