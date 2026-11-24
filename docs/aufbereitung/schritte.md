# Die Schritte im Einzelnen

Notebook 00 arbeitet die Schritte in dieser Reihenfolge ab. Zu jedem Schritt steht, was er macht und warum. Welche
Eigenheiten der Exporte dahinterstecken, steht unter [Zählerdaten](../datengrundlage/zaehlerdaten.md#eigenheiten-der-exporte).
Wie die Schritte entstanden sind, steht unter [Wie die Aufbereitung gewachsen ist](index.md#wie-die-aufbereitung-gewachsen-ist).

## 1 · Dateien einsammeln

- Alle Exporte unter `data/raw/` werden nach Zählernummer gruppiert (siehe
  [Lieferungen](../datengrundlage/zaehlerdaten.md#lieferungen)). Ein bekannter Fehler im Dateinamen wird dabei fest
  korrigiert.
- Zähler, die keine Hausstation sind, fallen sofort heraus und landen gar nicht erst in `real_meters/`.

## 2 · Jede Datei lesen und prüfen

Die Reihenfolge ist wichtig:

1. **Spreizung ergänzen**, falls sie fehlt: Vorlauf minus Rücklauf. Das geht vor der Pflichtspaltenprüfung, sonst
   würde die Datei verworfen, und vor der Skalierungskorrektur, weil eine Differenz genauso skaliert wie ihre
   Summanden.
2. **Pflichtspalten prüfen:** Fehlt eine Pflichtspalte, wird nur dieser Zähler übersprungen und mit Grund aufgelistet.
   Der Lauf bricht nicht ab.
3. **Zeilen ohne Messwert verwerfen:** nur wenn alle fünf Messgrößen leer sind. 0 ist eine Messung, leer nicht.
4. **ODS zurückrechnen:** Liegt der Median des Vorlaufs einer Datei über 1000, sind alle Werte 1000-fach zu groß und
   werden zurückgerechnet. Das trifft nur die ODS-Dateien.
5. **Plausibilität prüfen:** Werte außerhalb physikalischer Grenzen werden leer gesetzt. Erst zurückrechnen, dann
   prüfen, sonst fiele jeder ODS-Wert heraus.

| Messgröße | erlaubter Bereich |
|---|---|
| Durchfluss | −1.000 bis 50.000 l/h |
| Leistung | −2.000 bis 2.000 kW |
| Spreizung | −60 bis 100 °C |
| Vor- und Rücklauf | −20 bis 130 °C |

Die Grenzen sind bewusst weit. Sie fangen kaputte Dateien ab, keine ungewöhnlichen, aber echten Betriebszustände.

## 3 · Je Zähler zusammenführen

- Die Dateien eines Zählers werden aneinandergehängt, auf die volle Stunde abgerundet und sortiert.
- Doppelte Stunden fallen heraus. Steht eine Stunde in mehreren Exporten, gilt der neuere. Die ODS hat keine
  Zählerstände und überschreibt deshalb keine CSV-Stunde.
- Die Zeitstempel bleiben deutsche Lokalzeit. Eine Umrechnung nach UTC hätte nur Messstunden gekostet (siehe
  [Änderungen 1](rohdaten.md#keine-umrechnung-nach-utc)).

## 4 · Lückenloses Stundenraster

- Jede Stunde zwischen erster und letzter Messung bekommt eine Zeile, nicht gemessene Stunden bleiben leer. Damit gilt
  „eine Zeile ist eine Stunde“, was die Frequenzanalyse (FFT) für die Regelhysterese voraussetzt.
- Je Zähler stehen gemessene Stunden, Rasterlänge und Abdeckung in der Übersicht (Zahlen unter
  [Zeitraum und Abdeckung](../datengrundlage/zaehlerdaten.md#zeitraum-und-abdeckung)).

## 5 · Adresse und Anschlusswert zuordnen

- Die Adresse kommt aus `Zuordnung.xlsx`. Nur bei einem Zähler, der dort fehlt, nimmt der Code sie aus
  `Nodes_Edges.ods`. Den Anschlusswert gibt es nur in `Nodes_Edges.ods` (siehe
  [Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md)).
- Der Anschlusswert wird zuerst über die Zählernummer gesucht, sonst über die Adresse, weil nach einem Zählertausch
  noch die alte Nummer in der Tabelle steht. Über die Adresse gilt er nur, wenn dort genau ein Zähler mit Daten steht.
  Stehen dort mehrere, gilt der Wert als geteilt und wird nicht übertragen.
- Bekannte Adressfehler korrigiert der Code, die Rohdaten bleiben unverändert.

## 6 · Kennzahlen je Station

Clustering braucht eine Tabelle mit einer Zeile je Station. Jede Stundenreihe wird deshalb auf 14 Kennzahlen
verdichtet, zum Beispiel:

| Kennzahl | Rechnung |
|---|---|
| `rt_mean_winter` | Mittel der Rücklauftemperatur im Winter (Dezember bis März) |
| `dt_mean_loaded` | Mittel der Spreizung, wenn die Station läuft (über 0,5 kW) |
| `summer_flow_baseline` | Median des Durchflusses im Sommer (Juni bis August), Hinweis auf Dauerdurchfluss |
| `flow_ceiling_slope_per_month` | Trend des oberen Durchflusses (95.-Perzentil) je Monat, Hinweis auf einen zusetzenden Filter |
| `flow_short_cycle_power` | Anteil der 4- bis 12-Stunden-Schwingung im Durchfluss (FFT), Hinweis auf Regelhysterese |
| `idle_share` | Anteil der gemessenen Stunden mit fast keiner Leistung |

Was die Kennzahlen im Clustering zeigen, steht unter [Merkmale und Clustering](../clustering/index.md).
