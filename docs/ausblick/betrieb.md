# Betrieb mit neuen Daten

Das [Endmodell](../ergebnisse/endmodell.md) ist für einen Probebetrieb gedacht, also für einen ersten Einsatz auf
Probe: Die ÜZ spielt regelmäßig neue Zählerdaten ein, die Modelle bewerten damit die Stationen neu, und das Dashboard
zeigt die aktuelle Handlungsliste. Die ÜZ begeht Stationen nach dieser Liste und hält fest, was vor Ort war. Diese
Seite beschreibt, was beim Einspielen neuer Daten passiert und welche Regeln dabei gelten, damit die Zahlen
vergleichbar bleiben.

## Ablauf mit neuen Daten

```
neue Zählerexporte in data/raw/
     │
python -m src.aktualisieren
     ├── Notebook 00              saubere Stundenreihen
     ├── Außentemperatur (DWD)    nachladen
     ├── Monitoring-Modell        Netzvergleich, Tagesmonitor, Priorität, Bericht
     ├── dashboard_daten          wendet die gespeicherten Pakete an, lernt nichts neu
     ├── Notebook 31              Netz-Cache mit den neuen Stundenreihen
     └── Notebook 37              baut die HTML-Datei des Dashboards
```

Gelernt wird dabei nichts. Die Ergebnistabellen halten fest, mit welcher Paketversion und bis zu welchem Datum
gerechnet wurde. Wie der Befehl ausgeführt wird, steht unter
[Neue Zählerdaten einspielen](../installation/ausfuehrung.md#neue-zahlerdaten-einspielen).

## Regeln für den Betrieb

1. **Nur anwenden, nicht lernen.** Ein Modell, das bei jedem Lauf neu lernt, verschiebt still seine Schwellen. Lernen
   braucht eine Prüfung wie in Notebook 35.
2. **Skalierung und Kalibrierung bleiben eingefroren.** Neue Daten werden mit den gespeicherten Werten skaliert. Würde
   man die Skalierung aus den neuen Daten rechnen, verschöbe ein lange anhaltender Fehler den Maßstab, an dem er
   gemessen wird.
3. **Neue Stationen erst einlernen.** Das Monitoring-Modell braucht 60 Heiztage, das Prognose-LSTM rund vier Wochen
   volle Stundenwerte (Notebook 35). Bis dahin steht die Station als „noch nicht bewertbar“ im Dashboard.
4. **Nach einem bekannten Eingriff neu kalibrieren.** Das Prognose-LSTM kennt eine Station nur von vor dem Eingriff
   und meldet eine Reparatur sonst immer wieder (Notebook 30: nach 7, 22 und 33 Tagen). Die Referenz des
   Monitoring-Modells sollte nach jeder Begehung und zu jeder Heizperiode neu gelernt werden, sonst stehen seine Konten
   am Deckel (an 43 % der Testtage in Notebook 35).
5. **Neu lernen nur mit Prüfung.** Ändert sich die Datenbasis deutlich, etwa durch neue Zähler oder einen neuen Winter,
   werden die Modelle neu gelernt: Notebook 00, dann Notebook 25 für Labels und Kennzahlen, dann Notebook 35 mit
   `SELBST_TRAINIEREN = True`. Erst wenn die Zahlen aus Notebook 35 mit dem bisherigen Stand verglichen sind, kommen
   die neuen Pakete ins Dashboard.

## Rückmeldung nach jeder Begehung

Der Probebetrieb bringt das, was dem Projekt am meisten gefehlt hat: Begehungen, deren Ergebnis vorher vorhergesagt
wurde. Damit sie sich auswerten lassen, braucht jede Begehung ein festes Protokoll: was kaputt war, nicht nur, was
gemacht wurde, seit wann, und ob die Station vorher auf der Handlungsliste stand. Wie dieses Protokoll aussehen kann
und wie die Stationen ausgewählt werden, steht unter [Vorschlag für künftige Begehungen](begehungen.md). Nach jeder
Begehung gilt außerdem Regel 4: Die Referenz der Station wird neu gelernt.
