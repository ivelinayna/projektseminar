# Probebetrieb

Das [Endmodell](ergebnisse_endmodell.md) ist für einen Probebetrieb gedacht: Die Modelle laufen auf neuen Zählerdaten,
die ÜZ nutzt die Handlungsliste für Begehungen und meldet zurück, was vor Ort war. Damit die Zahlen dabei vergleichbar
bleiben, gelten ein paar Regeln.

## Ablauf mit neuen Daten

```
neue Zählerexporte in data/raw/
     │
python -m src.aktualisieren
     ├── Notebook 00              saubere Stundenreihen
     ├── Außentemperatur (DWD)    nachladen
     ├── Monitoring-Modell        Netzvergleich, Tagesmonitor, Priorität, Bericht
     ├── dashboard_daten          wendet die gespeicherten Pakete an, lernt nichts neu
     │                            Handlungsliste wird mit Datum gesichert
     ├── Notebook 31              Netz-Cache mit den neuen Stundenreihen
     └── Notebook 37              baut die HTML-Datei des Dashboards
```

Gelernt wird dabei nichts. Die Ergebnistabellen halten fest, mit welcher Paketversion und bis zu welchem Datum
gerechnet wurde. Wie der Befehl ausgeführt wird, steht unter
[Neue Zählerdaten einspielen](installation/ausfuehrung.md#neue-zahlerdaten-einspielen).

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

Die Regeln 1 bis 3 setzt der Code bereits um. Regel 4 und 5 sind im Code noch nicht umgesetzt, siehe
[Betrieb bei der ÜZ](installation/betrieb.md#was-noch-nicht-umgesetzt-ist).

## Rückmeldung aus dem Probebetrieb

Der Probebetrieb bringt das, was dem Projekt am meisten gefehlt hat: Begehungen, deren Ergebnis vorher vorhergesagt
wurde. Dafür sollte jede Begehung festhalten:

- Datum der Begehung,
- ob etwas kaputt war und was, nicht nur, was gemacht wurde,
- was getauscht oder eingestellt wurde,
- ob die Station vorher auf der Handlungsliste stand und mit welcher Dringlichkeit.

Dafür gibt es eine Vorlage für das Begehungsprotokoll und einen Befehl, der die ausgefüllten Protokolle prüft und mit
dem gesicherten Stand der Handlungsliste vor der Begehung verknüpft (siehe [Betrieb bei der ÜZ](installation/betrieb.md)). Wie daraus
eine Prüfung der Modelle wird, steht unter [Prüfung nach vorn](ausblick_pruefung.md).
