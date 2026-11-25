# Datenanalyse

Das erste Ziel der [Aufgabenstellung](../einleitung/aufgabe_und_ziel.md) lautet: die Leistung jeder Station auswerten
und Auffälligkeiten finden, etwa einen zu hohen Rücklauf, dauerhaften Durchfluss oder eine schwingende Regelung. Diese
Seite zeigt, wie weit das gelungen ist. Die Wege dorthin stehen unter [Vorgehen](../notebooks/index.md).

## Auf einen Blick

| Teilziel | erreicht? | wichtigster Beleg |
|---|---|---|
| Leistung jeder Station auswerten | ja | Kennzahlen, Tages- und Stundenwerte und Diagnosebilder für alle 93 Stationen |
| zu hoher Rücklauf | ja | Die Hälfte der Stationen hat in rund einem Drittel ihrer Stunden oder öfter einen Rücklauf über 50 °C |
| dauerhafter Durchfluss | ja, am deutlichsten | vier verschiedene Ansätze finden ihn, immer wieder bei denselben Stationen |
| schwingende Regelung | nur teilweise | als Muster sichtbar, aber Stundenwerte sind dafür zu grob und Befunde fehlen |

## Die Leistung jeder Station

- **Datenbasis:** 93 Hausübergabestationen (HAST) mit Zählerdaten von November 2021 bis Juli 2025, fünf davon bis
  Juli 2026. Bis Oktober 2022 gibt es bei 45 Zählern nur einen Wert am Tag, danach Stundenwerte. Wie die Exporte
  zusammengeführt und geprüft wurden, steht unter [Daten aufbereiten](../aufbereitung/index.md).
- **Maß für die Leistung** ist die Abkühlung: wie viel Wärme die Station aus jedem m³ Heizwasser holt (kWh/m³). Hoch
  ist gut, dann kommt das Wasser kalt zurück. 1 kWh/m³ entspricht rund 0,86 K Spreizung
  ([Zählerdaten](../datengrundlage/zaehlerdaten.md#abkuhlung-je-kubikmeter)).
- **Die Stationen unterscheiden sich stark.** Im Winter reicht die Abkühlung je Station von 5,7 bis 47,9 kWh/m³, im
  Median 30,9 (Notebook 11).
- **Jede Station hat ein Profil:**
    - 14 Kennzahlen über die ganze Historie, etwa Winterrücklauf, Spreizung unter Last und Sommer-Durchfluss
      ([Stationscluster](../clustering/stationscluster.md#merkmale))
    - eine Zeile je Tag mit Abkühlung, Wassermenge je kW und Nachtfluss
      ([Tagescluster](../clustering/tagescluster.md))
    - drei Diagnosebilder: Kennlinie, Carpet-Plot und Dauerlinie
      ([Stationsbilder und Befunde](../stationsbilder/index.md))
- **Klare Stationstypen gibt es nicht.** Die Stationen gehen fließend ineinander über (Silhouette 0,24; unter 0,25
  heißt: keine klare Struktur). Jede Station prägt aber ihre eigenen Tage, deshalb lohnt der Blick auf die einzelne
  Station mehr als auf Gruppen ([Merkmale und Clustering](../clustering/index.md)).

## Zu hoher Rücklauf

- **Wie gemessen:** der Anteil der gemessenen Stunden mit Rücklauf über 50 °C, über die ganze Messzeit. Dieselbe
  Grenze nutzen die Notebooks 02, 04 und 19.
- **Wie häufig:** Die Hälfte der Stationen hat in rund einem Drittel ihrer Stunden oder öfter einen Rücklauf über
  50 °C (Median 33 %). Bei einem Viertel sind es mehr als 65 % der Stunden (Notebook 12).
- **Wer auffällt:** Ein Drittel der Stationen (31 von 93) bildet im Clustering eine eigene Gruppe mit einem
  Winterrücklauf von 55,4 °C, gegen 42,2 °C beim Rest (Notebook 07).
- **Dauerhaft:** Bei 9 von 45 Begehungen lag der Rücklauf im Winter vor und nach der Begehung im Median über 50 °C.
  Diese Stationen sind Kandidaten für eine erneute Prüfung (Notebook 04,
  [Wintervergleich](../begehungen/wintervergleich.md#vierfeldertafel)).
- Wie sich der Rücklauf einer Station gegenüber dem Netz entwickelt, zeigt der
  [Netzvergleich](../monitoring/netzvergleich.md). Ob er gegenüber ihrem eigenen Verlauf steigt, prüft das
  Stationsresiduum in der [Anomalieerkennung](../monitoring/anomalie.md).

## Dauerhafter Durchfluss

Das ist die deutlichste Auffälligkeit in den Daten. Vier verschiedene Ansätze finden sie:

| Ansatz | Was er findet |
|---|---|
| Label aus Messdaten (Notebook 03) | Durchfluss über 50 l/h bei Spreizung unter 8 K in 266 von 2.300 Station-Monaten, an 24 von 93 Stationen |
| Stundencluster (Notebook 09) | ein eigener Zustand mit Verdacht auf hydraulischen Kurzschluss in 13 % der Stunden, in allen Jahreszeiten gleich häufig. 18 von 92 Stationen sind mehr als ein Fünftel ihrer Stunden in diesem Zustand |
| Tagescluster (Notebook 10) | Typ „Dauerdurchfluss“ an Heiztagen (5 bis 10 °C) bei 16 Stationen, im Sommer bei 14: rund 9 m³ am Tag bei 3,5 K Spreizung, auch nachts |
| [Kennlinie](../stationsbilder/index.md#kennlinie) (Notebook 12) | 10 Stationen, deren Durchfluss unabhängig von der Leistung feststeht. Ihre Abkühlung liegt bei 10,9 kWh/m³, bei den Stationen mit normaler Kennlinie bei 34,5 |

- **Immer dieselben Stationen:** 80912182, 72135480, 72167782, 72167793 und 68956351 (vor der Reparatur) stehen in
  den Ranglisten aller drei Notebooks 03, 09 und 12 weit oben.
- **Der einzige bestätigte Fall:** Bei 68956351 stand ein Ventil rund drei Jahre offen. Nach dem Tausch von Ventil und
  Stellmotor im September 2024 fiel der Durchfluss noch am selben Tag von rund 500 auf nahezu 0 l/h. Die Ansätze aus
  den Notebooks 03, 06, 09, 12 und 13 finden diesen Fall, ohne von der Reparatur zu wissen
  ([Einzelfall](../begehungen/wirkung.md#einzelfall-68956351)).
- **Mögliche Ursachen:** ein Ventil, das nicht schließt, ein Bypass oder Zirkulationsverluste. Welche es ist, zeigen
  die Messdaten nicht.

## Schwingende Regelung

- **Wie gemessen:** zum einen, wie stark der Durchfluss in einem Takt von 4 bis 12 Stunden schwingt (Kennzahl
  `flow_short_cycle_power`, Notebook 00). Zum anderen der Tagestyp „stark schwankend“, bei dem die Spreizung über den
  Tag um rund 23 K schwankt statt um 10 K (Notebook 10,
  [Tagescluster](../clustering/tagescluster.md#die-tagestypen)).
- **Was sich zeigt:** Der schwankende Tagestyp ist häufig, je nach Temperatur 27 bis 33 % der Heiztage. Er kann aber
  ebenso vom Wechsel zwischen Heizen und Warmwasser kommen wie von einer unruhigen Regelung. Die frühe Regel dafür
  schlug mit festen Schwellen bei 83 von 93 Stationen an und trennt damit nichts (Notebook 16).
- **Was fehlt:** ein Befund, an dem sich das prüfen ließe. In den Begehungen gibt es keinen Befund „Regelung
  schwingt“. Ob eine Station, die so aussieht, wirklich falsch regelt, lässt sich deshalb nicht prüfen
  ([Negativbefunde](../nicht_getragen/negativbefunde.md#3-regel-baseline-mit-festen-schwellen)). Auch das Label aus
  Messdaten erfasst sie nicht: Notizen zu Regelung und Konfiguration treffen keine dort auffällige Station
  (Notebook 03).
- **Warum die Daten dafür nicht reichen:**
    - Die Zähler liefern einen Wert je Stunde, und zwar als Momentaufnahme zur vollen Stunde, nicht als Mittelwert
      (siehe [Zählerdaten](../datengrundlage/zaehlerdaten.md#stundenwerte-sind-momentaufnahmen)). Was zwischen zwei
      Aufnahmen passiert, sieht man nicht.
    - Eine Schwingung lässt sich nur erkennen, wenn in jedem Zyklus mehrere Messungen liegen, mindestens zwei, besser
      deutlich mehr. Mit einem Wert pro Stunde sind nur Schwingungen sichtbar, die länger als zwei Stunden dauern. Eine
      Regelhysterese spielt sich dagegen oft innerhalb weniger Minuten ab.
    - Schnellere Schwankungen sind trotzdem in den Daten, aber verfälscht: als zufällige Streuung oder als scheinbar
      langsamere Schwingung. Die Kennzahl `flow_short_cycle_power` misst deshalb nur Zyklen von 4 bis 12
      Stunden, die eigentliche Regelhysterese erfasst sie nicht.
    - Auch die Wächter aus dem Endmodell helfen hier nicht. Eine künstlich eingebaute 6-Stunden-Schwingung findet
      keiner (höchstens 15 % bei höchstens 10 % Fehlalarmen), weil alle mit Tagesmitteln rechnen und sich die
      Schwingung über den Tag fast aufhebt (Notebook 35, Test B, siehe [Endmodell](endmodell.md)). Für die
      Regelhysterese bräuchte es ein eigenes Verfahren, das nicht über den Tag mittelt.
    - Auch die Befunde sind zu wenige: Nur 9 der 57 Notizen nennen Regler oder Parameter (Notebook 14,
      [Stationsbilder](../stationsbilder/index.md#4-liegt-es-an-den-labels-notebook-14)).
    - Nötig wären Messwerte im Minutentakt, zumindest für einzelne Stationen, und Befunde, die eine schwingende
      Regelung ausdrücklich festhalten.
- **Ergebnis:** Die schwingende Regelung ist als Muster sichtbar, als Fehler aber nicht belegt. Mit Stundenwerten
  lässt sie sich grundsätzlich nicht sicher erkennen.

## Was die Datenanalyse sonst gezeigt hat

- **Regelung über den Durchfluss ist der Normalfall:** 74 von 92 Stationen ändern ihre Leistung im Winter vor allem
  über die Wassermenge. Die 12, die über die Spreizung regeln, arbeiten schlechter, umgekehrt zur Aussage der Folie
  der ÜZ (Notebook 11,
  [Stationsbilder](../stationsbilder/index.md#1-lasst-sich-die-folie-der-uz-nachbauen-notebook-11)).
- **Auch die Daten selbst hatten Auffälligkeiten:** eine Phase bis Oktober 2022 mit nur einem Wert am Tag, Zähler, die
  keine Hausstationen sind, und Fehler in einzelnen Exporten. Sie sind unter
  [Qualität und Einschränkungen](../datengrundlage/qualitaet.md) beschrieben.

## Grenzen

- **Auffällig heißt nicht defekt.** Die Datenanalyse findet ungewöhnliches Verhalten. Ob dahinter ein Fehler steckt,
  zeigen die Messdaten allein nicht. Dafür fehlen Befunde mit Datum und klarer Fehlerart
  ([Label aus Messdaten](../begehungen/labels.md)).
- **Monats- und Tageswerte glätten:** Fehler, die nur zeitweise auftreten, können im Monatsmedian untergehen
  (Notebook 03).
- **Ein Teil der Unterschiede kann an der Bauart liegen:** Ein Altbau mit Heizkörpern und ein Neubau mit
  Fußbodenheizung können verschieden aussehen, ohne dass etwas kaputt ist. Deshalb vergleicht das Monitoring jede
  Station auch mit sich selbst.

## Fazit zu den Daten

Auf dem Papier sind es viele Daten: 93 Stationen, je Zähler bis zu 4,7 Jahre, rund 1,7 Millionen gemessene Stunden
und 85.983 Tageszeilen. Für die Frage, welche Auffälligkeit ein Fehler ist, reichen sie trotzdem nicht.

- **Es gibt keine Labels, auf die man sich berufen kann.** Nirgends steht verlässlich, ob und wann eine Station defekt
  war und was kaputt war. Die Begehungstabelle hält fest, was eingestellt wurde, nicht, was defekt war. Eine Maßnahme
  steht bei 76 % der begangenen Stationen, das trennt nichts.
- **Es gibt zu wenige Begehungen.** 65 Begehungen an 62 der 93 Stationen, 7 davon ohne Datum. Selbst die häufigsten
  Befunde, Ventil oder Stellantrieb und Reglerparameter, stehen in den Notizen nur je 9-mal. Für das Training und die
  Prüfung eines Modells ist das zu wenig.
- **Die Begehungen sind nicht zuverlässig dokumentiert.** Für Reparaturen gibt es nur Ja/Nein-Kästchen, und die sind
  meist leer (Stellmotor getauscht: 2-mal ja, 52-mal leer, siehe
  [Begehungen](../datengrundlage/begehungen.md#was-bei-den-begehungen-geandert-wurde)). Was wirklich gemacht wurde,
  steht oft nur im Freitext, im Telegrammstil und ohne feste Begriffe. Selbst beim einzigen sicher bekannten Fall, dem
  Tausch von Ventil und Stellmotor bei 68956351, ist in den Maßnahmen-Spalten nichts angekreuzt. 6 Begehungen nennen im
  Text einen Fehler, ohne dass sich ein Sollwert geändert hat.
- **Die Messwerte sind für schnelle Vorgänge zu grob.** Ein Wert je Stunde reicht nicht für Schwingungen der Regelung
  (siehe [Schwingende Regelung](#schwingende-regelung)).

Die Datenanalyse kann deshalb zeigen, wo eine Station ungewöhnlich läuft. Ob dahinter ein Fehler steckt, lässt sich
mit diesen Begehungen kaum prüfen. Am meisten würde ein festes Protokoll helfen, das Datum, Befund und Reparatur
festhält, auch wenn nichts gefunden wurde (siehe [Offene Fragen an die ÜZ](../grenzen/offene_fragen.md)).
