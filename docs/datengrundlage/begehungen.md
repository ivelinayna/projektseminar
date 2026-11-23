# Begehungen

Die ÜZ hat zwischen August 2024 und September 2025 Hausübergabestationen vor Ort begangen. Dabei wurde die Station
aufgenommen, die Regelung neu eingestellt und bei Bedarf repariert. Jede Begehung steht als Zeile in der
Begehungstabelle `*Ergebnis_Optimierung_FW*.xlsx`.

Die Begehungen sind die einzige Rückmeldung aus dem Betrieb. Im Projekt dienen sie als Labels: Was war an einer
Station falsch, und was wurde geändert?

## Umfang

- Die Tabelle hat 66 Zeilen. Nr. 40 doppelt Nr. 39 (gleiche Station, ohne Datum) und wird nicht mitgezählt. Es
  bleiben **65 Begehungen**.
- Sie verteilen sich auf 62 Stationen. Drei Stationen wurden zweimal begangen.
- 58 Begehungen haben ein Datum, 7 nicht.

| Zeitraum | Begehungen |
|---|---|
| August bis Dezember 2024 | 53, davon 34 im September |
| März 2025 | 1 |
| September 2025 | 4 |
| ohne Datum | 7 |

- Fast alle Begehungen fallen also in wenige Wochen im Herbst 2024, kurz vor der Heizperiode.
- Die Tabelle nennt die Adresse, keine Zählernummer. Der Zähler wird über `Zuordnung.xlsx` gefunden (siehe
  [Netz und Zuordnung](netz_und_zuordnung.md#zahler-und-adresse-zuordnungxlsx)). So bekommt jede Begehung einen Zähler. Die 58 datierten Begehungen liegen an 56 Zählern.

## Aufbau der Tabelle

Die Tabelle hat 133 Spalten mit zweizeiligem Kopf: oben die Gruppe, darunter `alt` und `neu` oder `von` und `bis`.

| Bereich | Spalten | ausgefüllt (von 65) |
|---|---|---|
| Termin | Nr., Datum, Adresse, Uhrzeit von und bis | Datum 58, Uhrzeit 37 |
| Anlage | Anlagenkonfiguration (Code), Stationstyp | 65 und 56 |
| Gebäude | Zusatzheizungen, Personen, beheizte Wohnfläche, Inbetriebnahmejahr, Trinkwarmwasserspeicher | 15 bis 28 |
| Zirkulation | Zirkulation im Trinkwarmwasser vorhanden: ja, nein, defekt | 56 |
| Zeiten alt und neu | Heizzeiten Raumwärme, Zeiten der Trinkwarmwasserbereitung | 54 bis 55 und 50 |
| Vertragsleistung alt und neu | in kW | 43 und 46 |
| Regelparameter alt und neu | 47 Reglerparameter (PA1.1 bis PA4.11), Sollwerte Raumwärme Tag und Nacht, Sollwert Trinkwarmwasser | 65 |
| Maßnahmen | Filter gereinigt, Durchfluss neu eingestellt, Leitungen neu gedämmt, Stellmotor, Stellventil oder Regler getauscht (ja oder nein) | siehe unten |
| Freitext | Spalte „Sonstiges“, Notiz des Monteurs | 57 |
| Bewertung | Änderungskategorie: keine, geringe, mittlere, viele | 65 |

## Was bei den Begehungen geändert wurde

- **Regelparameter und Sollwerte:** Bei 63 von 65 Begehungen unterscheidet sich mindestens ein Wert zwischen alt und
  neu, im Median 6 Werte.
- **Zeiten:** Die Heizzeiten der Raumwärme wurden bei 8 Begehungen geändert, die Zeiten des Trinkwarmwassers bei 15.
- **Vertragsleistung:** Bei 43 Begehungen stehen beide Werte. 9-mal wurde sie gesenkt, 2-mal erhöht.

| Maßnahme | ja | nein | leer |
|---|---|---|---|
| Filter gereinigt | 31 | 4 | 30 |
| Durchfluss neu eingestellt | 23 | 6 | 36 |
| Leitungen neu gedämmt | 23 | 8 | 34 |
| Stellmotor getauscht | 2 | 11 | 52 |
| Stellventil getauscht | 2 | 12 | 51 |
| Regler getauscht | 0 | 12 | 53 |

- Leere Kästchen sind häufig. Ob leer „nein“ heißt oder „nicht ausgefüllt“, geht aus der Tabelle nicht hervor.
- Die ÜZ hat jede Begehung einer Änderungskategorie zugeordnet: 35 mittlere, 21 viele, 5 geringe, 4 keine.

## Freitexte

57 der 65 Begehungen haben einen Freitext. Er enthält oft mehr als die Ja/Nein-Spalten: Befunde ohne Maßnahme oder
Reparaturen, die in den Spalten fehlen. Beim Ventilfall 68956351 stehen Ventil- und Stellmotortausch zum Beispiel nur
im Freitext.

Deshalb wurden alle 65 Begehungen von Hand gelesen und kodiert (Prüfliste
`data/manual/pruefliste_begehungsnotizen.xlsx`): bis zu zwei Befunde je Begehung, die Maßnahme am Termin und ob der Eingriff mechanisch war. Die Kodierung stützt sich nur auf die
Begehungstabelle, nicht auf die Messdaten.

| Maßnahme am Termin | Begehungen |
|---|---|
| Einstellung geändert | 49 |
| Bauteil getauscht oder repariert | 10 |
| Reinigung oder Wartung | 4 |
| keine | 2 |

| Befund | Begehungen |
|---|---|
| Regler oder Einstellung | 40 |
| Ventil oder Stellantrieb | 11 |
| Dämmung der Leitung | 11 |
| Volumenstrom oder Hydraulik | 10 |
| Schmutzfänger | 6 |
| Zirkulation | 5 |
| Sonstiges | 3 |
| Messtechnik | 2 |
| Anlage aus oder Leerstand | 1 |
| kein Befund | 12 |

- Eine Begehung kann zwei Befunde haben. Die Spalte ergibt deshalb mehr als 65.
- Mechanisch heißt: Schmutzfänger, Ventil oder Stellantrieb, Pumpe, Zirkulation oder Hydraulik. Von Hand sind es 14
  Begehungen, 1 ist unklar. Die automatische Kodierung der Freitexte kommt auf 22 und weicht bei 13 Begehungen von der
  Handkodierung ab.
- 30 Begehungen waren für eine Rückfrage an die ÜZ markiert. Zu einzelnen Fällen kann die ÜZ nachträglich aber
  nichts mehr sagen.

## Grenzen der Begehungsdaten

- **Auswahl:** Die Stationen wurden nicht zufällig ausgewählt, und fast alle Termine liegen im Herbst 2024. Eine echte
  Kontrollgruppe gibt es nicht.
- **Nie begangene Stationen:** Über die 37 Stationen ohne Begehung sagt die Tabelle nichts. Sie gelten als unbekannt,
  nicht als gesund.
- **Fehlerbeginn:** Die Tabelle sagt, was am Termin gefunden wurde, nicht seit wann.
- **Ohne Datum:** Die 7 Begehungen ohne Datum fehlen in jedem Vorher-Nachher-Vergleich.
- **Messdaten danach:** Die Zählerdaten enden für die meisten Stationen am 11.07.2025. Von den vier Begehungen im
  September 2025 haben nur zwei Messwerte danach, beide an ODS-Zählern.
- **Mehrfach begangen:** Zwei Begehungen an derselben Station sind keine unabhängigen Fälle.

Wie die Begehungen ausgewertet werden, steht unter [Vorgehen → Begehungen auswerten](../begehungen/index.md).
