# Ergänzende Daten

Neben Zählerdaten, Begehungen und Netzplan nutzt das Projekt die Außentemperatur des Deutschen Wetterdienstes (DWD),
zwei von Hand gepflegte Tabellen und Auskünfte der ÜZ.

## Außentemperatur

Im Netz selbst wird keine Außentemperatur gemessen. Sie kommt von der nächsten Wetterstation des DWD.

| | |
|---|---|
| Station | Kitzingen (DWD 2600), rund 13 km von Wiesentheid |
| Werte | Tagesmitteltemperatur (`TMK`) mit Qualitätsstufe (`QN_4`), für die Heizgradstunden auch Stundenwerte |
| Zeitraum | 2021 bis 31.12.2025, ohne fehlenden Tag, alle Tage vollständig geprüft (Qualitätsstufe 10) |
| Ablage | öffentliche Daten, lokal unter `external/dwd/`, nicht im Repository |

### Wofür die Temperatur gebraucht wird

**Temperaturgruppen (Notebook 10):** Jeder Tag bekommt nach seinem Tagesmittel eine Gruppe. Verglichen wird nur
innerhalb einer Gruppe, damit kein Sommertag neben einem Wintertag landet.

| Gruppe | Tagesmittel | Tage je Jahr |
|---|---|---|
| Heiztag | unter 15 °C, in Bändern: unter 0, 0 bis 5, 5 bis 10, 10 bis 15 °C | 230 bis 250 |
| Übergang | 15 bis 18 °C | 32 bis 50 |
| Sommer | ab 18 °C | 74 bis 100 |

- Tage unter 0 °C gibt es nur 12 bis 30 je Jahr. Deshalb gibt es dafür ein gemeinsames Band.
- Die Jahre unterscheiden sich: 2022 hatte den wärmsten Sommer (100 Sommertage), 2025 die meisten Frosttage (30).

**Heizgrenze 15 °C (Notebook 18 und 20):** Darüber wird kaum geheizt, die Station macht fast nur Warmwasser. Die
Kennlinie je Station, also der erwartete Wert bei einer bestimmten Tagesmitteltemperatur, wird deshalb nur an
Heiztagen gelernt.

**Heizgradstunden (Notebook 19):** Summe aus 15 °C minus Außentemperatur über alle Stunden unter 15 °C, je
Kernwinter. Je größer, desto kälter der Winter. So lässt sich zeigen, dass der Winter 2024/25 um 21 % kälter war als
der Winter 2023/24.

## Handtabellen

Drei Tabellen werden von Hand gepflegt. Sie liegen unter `data/manual/` und nicht im Repository. Zwei davon stehen
hier. Die dritte, die Koordinaten der Adressen, steht unter *Netz und Zuordnung*.

### Prüfliste der Begehungsnotizen

- Eine Zeile je Begehung (65). Je Zeile von Hand eingetragen: bis zu zwei Befunde, die Maßnahme am Termin und ob der
  Eingriff mechanisch war. Die Ergebnisse stehen unter *Begehungen*.
- Stand: Alle 57 Freitexte sind geprüft, die 8 Begehungen ohne Freitext von Hand gesetzt.
- Grundlage ist nur die Begehungstabelle. Die Hilfsspalten „hydraulisch wirksam“ und „Zeitpunkt passt“ sind mit
  Blick auf die Messdaten ausgefüllt. Sie werden nicht als Label verwendet, sonst würde sich ein Modell an sich
  selbst prüfen.
- Die Tabelle enthält keine Adressen, aber vertrauliche Notizen der ÜZ.
- Verwendet in Notebook 38 (Bayes-Diagnose): als Vorwissen, wie häufig jeder Fehler ist, und als Lösungsschlüssel für
  die Prüfung.

### Fehler-Symptom-Matrix (Entwurf)

- Sie beschreibt, wie oft eine Station mit einem bestimmten Fehler ein bestimmtes Symptom zeigt. Beispiel: Wenn das
  Ventil hängt, wie oft ist der Rücklauf dauerhaft warm?
- 11 Zeilen (10 Fehlerarten und „kein Fehler“) mal 12 Symptome, also 132 Felder. Jedes Feld hat eine Stufe:

| Stufe | Wert | Felder |
|---|---|---|
| fast immer | 0,90 | 6 |
| oft | 0,60 | 14 |
| manchmal | 0,30 | 25 |
| selten | 0,15 | 44 |
| nie | 0,05 | 43 |

- Die Stufen sind ein Entwurf aus der Physik, nicht aus den Begehungen berechnet. Sonst würde das Modell an genau
  den Daten geprüft, aus denen es stammt.
- Mit der ÜZ abgestimmt sind 0 von 132 Feldern. Eine Spalte für die Stufe der ÜZ ist vorbereitet. Ist sie gefüllt,
  gilt sie vor dem Entwurf.
- Verwendet in Notebook 38.

## Auskünfte der ÜZ

Die ÜZ hat im Oktober 2026 Fragen zu den Daten beantwortet. Notebook 00 setzt die Antworten um:

- 8 Zähler sind keine Hausstationen: das BHKW, die HHS-Kessel I bis IV, der Ölspitzenkessel und zwei
  Temperaturfühler im Heizhaus. Sie fallen heraus.
- Zwei Zähler standen in `Nodes_Edges.ods` und im Blatt 2024 von `Zuordnung.xlsx` unter der falschen Adresse. Die
  Korrektur steht im Code, die Rohdaten bleiben unverändert.
- Bei Zählern mit spätem Beginn hat der Ringspeicher die älteren Stundenwerte überschrieben.
- Zu einzelnen Begehungen kann die ÜZ nachträglich nichts mehr sagen.

Dazu kommen Folien der ÜZ als Vorlage. Ein Beispiel ist die Folie „Vergleich Gesamteffizienz vor und nach der
Optimierung von HAST“. Sie zeigt die Energie je m³ Heizwasser gegen die Außentemperatur. Optimierte Stationen liegen
dort rund 2,12 kWh/m³ oder 13,4 % höher (bei etwa 8,8 °C), gerechnet mit rund 60 optimierten HAST im ganzen
Versorgungsgebiet. Das Projekt hat die Folie mit den eigenen Zählerdaten nachgerechnet.
