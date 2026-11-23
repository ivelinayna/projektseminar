# Ergänzende Daten

Neben Zählerdaten, Begehungen und Netzplan nutzt das Projekt die Außentemperatur des Deutschen Wetterdienstes (DWD),
von Hand gepflegte Tabellen und Auskünfte der ÜZ.

## Außentemperatur

Im Netz selbst wird keine Außentemperatur gemessen. Sie kommt von der nächsten Wetterstation des DWD.

| | |
|---|---|
| Station | Kitzingen (DWD 2600), rund 13 km von Wiesentheid |
| Werte | Tagesmitteltemperatur (`TMK`) mit Qualitätsstufe (`QN_4`), für die Heizgradstunden auch Stundenwerte |
| Zeitraum | 2021 bis 31.12.2025, ohne fehlenden Tag, alle Tage vollständig geprüft (Qualitätsstufe 10) |
| Ablage | öffentliche Daten, nicht im Repository. `python -m src.weather` lädt sie nach `data/raw/weather/`, die Tageswerte nach `data/raw/weather/tageswerte/` |

### Wofür die Temperatur gebraucht wird

**Temperaturgruppen (Notebook 10):** Jeder Tag bekommt nach seinem Tagesmittel eine Gruppe. Verglichen wird nur
innerhalb einer Gruppe, damit kein Sommertag neben einem Wintertag landet.

| Gruppe | Tagesmittel | Tage je Jahr |
|---|---|---|
| Heiztag | unter 15 °C, in Bändern: unter 0, 0 bis 5, 5 bis 10, 10 bis 15 °C | 223 bis 244 |
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

Vier Tabellen werden von Hand gepflegt. Keine liegt im Repository: Der Ordner `data/` ist ausgeschlossen, und drei
der Tabellen enthalten Adressen oder vertrauliche Notizen der ÜZ. Die Koordinaten der Adressen beschreibt
[Netz und Zuordnung](netz_und_zuordnung.md#koordinaten-der-adressen-handtabelle), die anderen drei stehen hier.

| Tabelle | Datei | gebraucht von |
|---|---|---|
| Prüfliste der Begehungsnotizen | `data/manual/pruefliste_begehungsnotizen.xlsx` | Notebook 38 |
| Fehler-Symptom-Matrix | `data/manual/fehler_symptom_matrix_entwurf.xlsx` | Notebook 38 |
| Kodierbogen der Freitexte | `data/processed/kodierbogen_freitexte.xlsx` | Notebook 03 |
| Koordinaten der Adressen | `data/manual/adressen_koordinaten.ods` | Notebook 31 bis 33 und Dashboard |

### Prüfliste der Begehungsnotizen

- Eine Zeile je Begehung (65). Je Zeile von Hand eingetragen: bis zu zwei Befunde, die Maßnahme am Termin und ob der
  Eingriff mechanisch war. Die Ergebnisse stehen unter [Begehungen](begehungen.md#freitexte).
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
- Verwendet in Notebook 38.

### Kodierbogen der Freitexte

- Alle 57 Freitextnotizen der Begehungen, von Hand und blind eingeordnet: ohne zu sehen, welche Station eine Regel als
  auffällig einstuft.
- Je Notiz: ob sie zur Regel passt (ja, nein, unklar), welche Art von Befund sie beschreibt, dazu eine Anmerkung.
- Er ist nicht dieselbe Tabelle wie die Prüfliste. Verwendet in Notebook 03, Ergebnisse unter
  [Label aus Messdaten](../begehungen/labels.md#abgleich-mit-der-handkodierung). Ohne den Kodierbogen überspringt
  Notebook 03 diesen Abschnitt.

## Auskünfte der ÜZ

Die ÜZ hat im Oktober 2026 Fragen zu den Daten beantwortet. Die meisten Antworten setzt Notebook 00 um:

- 8 Zähler sind keine Hausstationen: das BHKW, die HHS-Kessel I bis IV, der Ölspitzenkessel und zwei
  Temperaturfühler im Heizhaus. Sie fallen heraus.
- Ein Export trug einen falschen Dateinamen (`721354800` statt `72135480`). Er wird beim Einlesen dem richtigen Zähler
  zugeordnet, es bleiben 93 statt 94 HAST.
- Zwei Zähler standen in `Nodes_Edges.ods` und im Blatt 2024 von `Zuordnung.xlsx` unter der falschen Adresse. Die
  Korrektur steht im Code, die Rohdaten bleiben unverändert.
- Bei Zählern mit spätem Beginn hat der Ringspeicher die älteren Stundenwerte überschrieben.
- Zu einzelnen Begehungen kann die ÜZ nachträglich nichts mehr sagen.
- Der Knoten „Erzeuger“ in der Kantendatei ist die Einspeisung des Netzes. Das nutzt Notebook 32.

Was sich dadurch in der Aufbereitung geändert hat, steht unter
[Änderungen 3: Rückmeldung der ÜZ](../aufbereitung/uez_rueckmeldung.md).

Dazu kommen Folien der ÜZ als Vorlage. Ein Beispiel ist die Folie „Vergleich Gesamteffizienz vor und nach der
Optimierung von HAST“. Sie zeigt die Energie je m³ Heizwasser gegen die Außentemperatur. Optimierte Stationen liegen
dort rund 2,12 kWh/m³ oder 13,4 % höher (bei etwa 8,8 °C), gerechnet mit rund 60 optimierten HAST im ganzen
Versorgungsgebiet. Das Projekt hat die Folie mit den eigenen Zählerdaten nachgerechnet, siehe
[Performance](../begehungen/performance.md).
