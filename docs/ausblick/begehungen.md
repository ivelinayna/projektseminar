# Vorschlag für künftige Begehungen

Viele Grenzen dieses Projekts liegen nicht in den Modellen, sondern in den Daten, aus denen sie lernen. Vor allem die
Begehungen: Das Protokoll hält fest, was gemacht wurde, aber nicht, was kaputt war und seit wann. Und die Stationen
wurden gezielt ausgewählt, nicht nach einem Plan. Diese Seite schlägt vor, wie die ÜZ künftige Begehungen planen und
festhalten kann, damit diese Probleme gar nicht erst entstehen. Zu jedem Punkt steht, wo das Problem im Projekt
aufgefallen ist. Mit einer Saison so geplanter Begehungen lässt sich die Handlungsliste zum ersten Mal nach vorn
prüfen, und die Modelle können mit besseren Labels neu lernen.

## Auf einen Blick

| Problem bisher | Folge im Projekt | Vorschlag |
|---|---|---|
| Das Protokoll hält Maßnahmen fest, keine Befunde | Eine Maßnahme steht bei 76 % der Stationen, das trennt nichts | Befund und Maßnahme getrennt festhalten ([Abschnitt 1](#1-ein-festes-protokoll-je-begehung)) |
| Die Ja/Nein-Kästchen bleiben meist leer | „Leer“ wird als „nein“ gelesen, das ist eine Annahme | jede Frage mit ja, nein oder nicht geprüft |
| Reparaturen stehen oft nur im Freitext | Alle Notizen mussten von Hand gelesen und kodiert werden | feste Auswahl, Freitext nur ergänzend |
| Kein Fehlerbeginn | Eine Frühwarnung lässt sich nicht prüfen | festhalten, seit wann der Fehler vermutlich besteht |
| 7 Begehungen ohne Datum | Sie fehlen in jedem Vorher-Nachher-Vergleich | Datum und Zählernummer als Pflichtfelder |
| Stationen gezielt ausgewählt, fast alle im Herbst 2024 | Keine echte Kontrollgruppe, die Wirkung ist nur „konsistent mit“ | erst vorhersagen, dann begehen, ein Teil zufällig ([Abschnitt 2](#2-begehungen-planen)) |
| Nie begangene Stationen sind unbekannt | Ihre Klasse im Dashboard ist eine Vorhersage, keine Prüfung | auch Stationen ohne Verdacht begehen |
| Zählertausch und Vertragsänderung ohne Datum | Eine Station erscheint als zwei Zähler, der Anschlusswert ist oft schon der neue Vertrag | Änderungen mit Datum festhalten ([Abschnitt 3](#3-zahlerdaten-und-stammdaten)) |
| Die Zählerdaten enden im Juli 2025 | Kein weiterer Winter zum Prüfen | regelmäßig exportieren |

## 1 Ein festes Protokoll je Begehung

**Bisher.**

- Die Begehungstabelle hält Maßnahmen fest, keine Befunde. Eine Maßnahme steht bei 76 % der Stationen und trennt damit
  nichts ([Wirkung im 21-Tage-Fenster](../begehungen/wirkung.md#ereignis-statt-label)). Der Sollwert wurde bei fast
  zwei Dritteln gesenkt, das ist eher Routine als ein Fehler der Station
  ([Daten, Labels und Messlatte](../modelle/daten.md#labels-aus-den-begehungen)).
- Die Ja/Nein-Kästchen sind meist leer. Ein ausdrückliches „nein“ steht beim Filter nur 4-mal, beim Durchfluss 6-mal
  und bei der Dämmung 8-mal. Ein leeres Kästchen wird als „nein“ gelesen, das ist eine Annahme
  ([Daten, Labels und Messlatte](../modelle/daten.md#labels-aus-den-begehungen)).
- Reparaturen stehen oft nur im Freitext, selbst beim Ventilfall 68956351
  ([Datenanalyse](../ergebnisse/datenanalyse.md#fazit-zu-den-daten)). Alle Notizen mussten deshalb von Hand gelesen
  und kodiert werden. Automatische Kodierung und Handkodierung weichen bei 13 Begehungen voneinander ab
  ([Qualität und Einschränkungen](../datengrundlage/qualitaet.md#begehungen)).
- Die Tabelle sagt nicht, seit wann ein Fehler besteht. Ob ein Modell einen Fehler früh erkennt, lässt sich deshalb
  nicht prüfen ([Endmodell](../ergebnisse/endmodell.md#gewahltes-modell-je-frage)).
- 7 Begehungen haben kein Datum und fehlen in jedem Vorher-Nachher-Vergleich
  ([Begehungen](../datengrundlage/begehungen.md#umfang)). Zugeordnet wurden die Begehungen über die Adresse, mit
  eigenen Zuordnungstabellen ([Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md)).

**Künftig.** Jede Begehung bekommt eine Zeile mit denselben festen Feldern, etwa in einer Excel-Vorlage mit
Auswahllisten:

| Feld | Inhalt | löst |
|---|---|---|
| Zählernummer und Datum | Pflichtfelder | Zuordnung ohne Adresse, kein Termin ohne Datum |
| Anlass | Handlungsliste (mit Dringlichkeit), Zufallsgruppe, Meldung des Kunden oder Routine | Gruppen vergleichen, siehe [Abschnitt 2](#2-begehungen-planen) |
| Befund je Fehlerart | für jede Fehlerart der Liste: ja, nein oder nicht geprüft | leere Kästchen, fehlende „nein“ |
| seit wann | vermuteter Beginn des Fehlers, etwa aus einer Meldung des Kunden, sonst „unbekannt“ | Frühwarnung wird prüfbar |
| Maßnahme | was getauscht, gereinigt oder eingestellt wurde | wie bisher |
| Grund der Maßnahme | behebt einen Befund oder vorsorglich | Routine von Fehlern trennen |
| Regelparameter alt und neu | wie bisher | – |
| Freitext | nur ergänzend | Kodieren von Hand entfällt |

- **Feste Liste der Fehlerarten,** etwa Regelventil oder Stellantrieb, Regler oder Einstellung, Filter, Durchfluss,
  Dämmung, Anschlussleistung und Sonstiges. Die Liste sollte mit den Monteuren abgestimmt sein. Als Vorlage kann die
  [Prüfliste der Begehungsnotizen](../datengrundlage/ergaenzend.md#prufliste-der-begehungsnotizen) dienen, die im
  Projekt von Hand nachgetragen wurde.
- **„Kein Befund“ ist ein Ergebnis** und gehört ausdrücklich ins Protokoll. Gerade diese Fälle fehlen: Auf dem Label
  „Maßnahme ja/nein“ bleiben nur 9 Stationen ohne Maßnahme
  ([Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#uberwachtes-lernen-auf-begehungslabels)).
- **Was schon gut funktioniert, bleibt.** Die Regelparameter alt und neu sind bei allen 65 Begehungen ausgefüllt
  ([Begehungen](../datengrundlage/begehungen.md#aufbau-der-tabelle)).

## 2 Begehungen planen

**Bisher.**

- Die ÜZ hat gezielt Stationen mit Optimierungsbedarf besucht, fast alle Termine liegen im Herbst 2024. Eine echte
  Kontrollgruppe gibt es nicht ([Begehungen](../datengrundlage/begehungen.md#grenzen-der-begehungsdaten)). Aussagen zur
  Wirkung sind deshalb nur „konsistent mit“ ([Wintervergleich](../begehungen/wintervergleich.md#einordnung)), und ein
  Teil der scheinbaren Verbesserung kann Regression zur Mitte sein
  ([Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#begehungswirkung-im-diff-in-diff)).
- Weil viele Stationen in wenigen Wochen begangen wurden, verbessern sich benachbarte Stationen gemeinsam. Das sieht
  aus wie ein Effekt des Netzes, passt aber eher zu gemeinsamen Terminen
  ([Netzereignisse](../monitoring/netzereignisse.md)).
- Über die nie begangenen Stationen sagt die Tabelle nichts. Ihre Klasse im Dashboard ist eine Vorhersage, keine
  Prüfung ([Fehlerart und Klasse je Station](../modelle/klassen.md#die-klasse-je-station)).
- Alle Zahlen der Modelle sind rückblickend geprüft, an Begehungen, deren Ergebnis beim Bau der Modelle schon bekannt
  war. Wie stark das die Zahlen schönen kann, hat der Schritt vom ersten Prüfstand zum strengen Vergleich gezeigt
  (0,89 auf 0,84 beim Ventil, siehe [Modellvergleich](../vergleich/modellvergleich.md#was-zuerst-nicht-stimmte)).

**Künftig: erst vorhersagen, dann begehen.**

1. **Vorher festlegen und aufschreiben,** welche Stationen begangen werden, was erwartet wird und wie gezählt wird.
   Danach wird nichts mehr geändert.
2. **Zwei Gruppen:** die nie begangenen Stationen mit dem höchsten Ventil-Score und gleich viele zufällig gewählte aus
   den übrigen Stationen. Das Team vor Ort weiß nicht, welche Station aus welcher Gruppe kommt.
3. **Erwartung:** In der Gruppe mit hohem Ventil-Score haben mehr Stationen einen Ventilbefund als in der zufälligen
   Gruppe. In Notebook 35 hatten unter den ersten 10 nach Ventil-Score 7 einen Ventilbefund, Zufall wären etwa 2
   gewesen.
4. **Protokoll** mit den festen Feldern aus [Abschnitt 1](#1-ein-festes-protokoll-je-begehung).
5. **Auswertung:** der Anteil der Ventilbefunde in beiden Gruppen, verglichen mit einem exakten Test und mit der
   Richtung, die vorher festgelegt ist. Genauso für die Hinweise auf Dämmung und Kapazität.
6. **Termine über die Saison verteilen,** nicht als Welle in wenigen Wochen. Dann lassen sich die Wirkung einer
   Begehung und Ereignisse im Netz auseinanderhalten.

Die zufällige Gruppe hat einen zweiten Nutzen: Sie ist nicht nach schlechten Werten ausgewählt. An ihr lässt sich die
Wirkung einer Begehung messen, ohne dass Regression zur Mitte das Ergebnis schönt.

**Wie groß die Stichprobe sein sollte.** Bei kleinen Gruppen findet der Test einen echten Unterschied oft nicht. Die
Tabelle zeigt die Teststärke, also die Wahrscheinlichkeit, dass ein einseitiger exakter Test nach Fisher einen
Unterschied bei p < 0,05 erkennt (Simulation mit je 2.000 Läufen):

| Stationen je Gruppe | Ventilbefund 70 % gegen 20 % | 50 % gegen 20 % | 40 % gegen 20 % |
|---|---|---|---|
| 10 | 63 % | 25 % | 13 % |
| 15 | 81 % | 37 % | 19 % |
| 21 | 93 % | 51 % | 29 % |

- 70 % gegen 20 % entspricht dem Ergebnis aus Notebook 35 (7 von 10 gegen etwa 2 bei Zufall). Nach vorn geprüft
  fallen solche Zahlen meist kleiner aus als rückblickend.
- Mit 15 Stationen je Gruppe, also 30 Begehungen, ist der Test deutlich aussagekräftiger als mit 10. Im Stand vom
  November 2026 gibt es 42 nie begangene Stationen mit Ventil-Score, also höchstens 21 je Gruppe.
- Ein Ergebnis über p = 0,05 heißt bei diesen Gruppengrößen nicht, dass die Liste nichts taugt, sondern dass die Fälle
  für eine Aussage nicht reichen.

Mit den Stationen, die die ÜZ in einer Saison begehen kann, bleibt auch dieser Test grob. Er misst aber zum ersten Mal,
was die Liste im Betrieb bringt, ohne dass die Modelle die Antworten kennen.

## 3 Zählerdaten und Stammdaten

**Bisher.**

- Die meisten Reihen enden am 11.07.2025, ältere Stundenwerte hat laut ÜZ der Ringspeicher überschrieben. Den Winter
  2025/26 gibt es nur für fünf Zähler ([Zählerdaten](../datengrundlage/zaehlerdaten.md#zeitraum-und-abdeckung)).
- Die Tauschdaten der Zähler fehlen. Eine Station mit neuem Zähler erscheint als zwei Zähler
  ([Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md#zahlertausch-und-doppelte-eintrage)).
- Der Anschlusswert ist oft schon der neue Vertrag. Ob ein Vertrag zu groß war, zeigt aber nur der alte
  ([Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#regel-baseline-mit-festen-schwellen)).
- Stationstyp, Zusatzheizung und Personenzahl wurden nur bei begangenen Häusern erhoben. Als Merkmal würden sie
  verraten, ob eine Station begangen wurde ([Qualität und Einschränkungen](../datengrundlage/qualitaet.md#begehungen)).
  Das Baujahr der Gebäude ist nur bei 14 Stationen bekannt ([Weiterentwicklung](weiterentwicklung.md#lernende-modelle)).

**Künftig.**

- **Zählerdaten regelmäßig exportieren,** etwa monatlich und mit den Zählerständen für Energie und Volumen. Dann
  überschreibt der Ringspeicher nichts, jeder Winter lässt sich auswerten, und die Tageswerte kommen weiter aus den
  Zählerständen ([Zählerdaten](../datengrundlage/zaehlerdaten.md#stundenwerte-sind-momentaufnahmen)).
- **Zählertausch festhalten,** mit Datum, alter und neuer Zählernummer.
- **Vertragsänderungen festhalten,** mit Datum, alter und neuer Leistung.
- **Stammdaten für alle Stationen,** nicht nur für begangene: Stationstyp, Baujahr und Zusatzheizung.
- **Minutenwerte an einzelnen Stationen,** um eine Regelhysterese überhaupt sehen zu können
  ([Weiterentwicklung](weiterentwicklung.md#monitoring)).

## 4 Nach der Begehung

Nach jeder Begehung lässt sich zusätzlich prüfen, ob der Wächter eine Veränderung bemerkt. Das Monitoring-Modell hat in
Notebook 35 18 von 43 Begehungen als „besser“ bemerkt, an Vergleichsstationen waren es 24 %. Im Probebetrieb wird
seine Referenz vorher neu gelernt, sonst steht ein Teil seiner Konten am Deckel. Ob es dann mehr Begehungen bemerkt,
ist eine eigene Frage für den Test.

## Was das bringt

- **Mehr und sauberere Labels.** Jede so protokollierte Begehung ist ein Fall mit ausdrücklichem „ja“ oder „nein“.
  Bisher gibt es 11 Ventilfälle, Unterschiede unter etwa 0,1 AUC sind damit nicht sichtbar
  ([Grenzen der Methoden und Modelle](../grenzen/modelle.md)).
- **Fehlerarten ohne Spur neu prüfen.** Filter, Durchfluss und Sollwert hinterlassen in den bisherigen Labels keine
  Spur in den Zählerdaten. Mit Befund statt Maßnahme lässt sich klären, ob das an den Daten liegt oder an den Labels
  ([Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#fehlerarten-ohne-messspur)).
- **Frühwarnung prüfen.** Mit dem vermuteten Fehlerbeginn lässt sich zum ersten Mal messen, ob ein Wächter einen
  Fehler vor der Begehung bemerkt.
- **Wirkung belegen.** Die zufällige Gruppe liefert eine faire Vergleichsgruppe statt einer Annahme.
- **Modelle neu lernen.** Mit den neuen Labels lernen die Modelle nach den Regeln des
  [Betrieb mit neuen Daten](betrieb.md#regeln-fur-den-betrieb) neu: Notebook 25, dann Notebook 35. Ins Dashboard kommen die
  neuen Pakete erst nach dem Vergleich mit dem bisherigen Stand.
