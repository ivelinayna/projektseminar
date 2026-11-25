# Qualität und Einschränkungen

Diese Seite fasst zusammen, wie gut die Daten sind und wo sie nicht reichen. Was Notebook 00 an den Exporten
korrigiert, steht unter [Zählerdaten](zaehlerdaten.md#eigenheiten-der-exporte). Was die Einschränkungen für die
Ergebnisse bedeuten, steht unter [Grenzen und Erkenntnisse](../grenzen/index.md).

## Auf einen Blick

| Quelle | Was gut ist | Wichtigste Einschränkung |
|---|---|---|
| Zählerdaten | nach der Bereinigung keine unplausible Messung, Zählerstände fast immer in Ordnung | Stundenwerte sind Momentaufnahmen, die Daten enden meist im Juli 2025 |
| Begehungen | einzige Rückmeldung aus dem Betrieb, alle Freitexte von Hand geprüft | wenige Fälle, nicht zufällig ausgewählt, Fehlerbeginn unbekannt |
| Netz und Zuordnung | jede Begehung findet ihren Zähler, die Einspeisung ist bekannt | Anschlusswert fehlt bei 6 HAST, Bedeutung der Pfeile unklar, kein hydraulisches Modell |
| Außentemperatur | lückenlos und geprüft | eine Station für das ganze Netz, endet 2025 |

## Zählerdaten

**Was gut ist**

- Nach den Korrekturen in Notebook 00 liegt keine einzige Messzelle außerhalb der Plausibilitätsgrenzen.
- Die Zählerstände sind fast immer in Ordnung. Unter 89.142 Stationstagen findet Notebook 10 nur 3 Rücksprünge, 24
  Tage mit stehendem Zähler trotz Durchfluss und 19 unplausible Tage (über 70 kWh/m³).
- Echte Lücken sind selten. 84 % der Stunden ohne Messung fallen in die Tageswert-Phase.

**Einschränkungen**

- **Momentaufnahmen:** Durchfluss, Leistung und Temperaturen sind Momentaufnahmen zur vollen Stunde, keine
  Stundenmittel. Eine Tagessumme daraus liegt im Winter um bis zu ±30 % daneben. Tageswerte kommen deshalb aus den
  Zählerständen. Schnelles Takten der Regelung erscheint nur als Rauschen, eine Regelhysterese lässt sich nicht
  nachweisen.
- **Tageswert-Phase:** 45 Zähler liefern bis etwa November 2022 nur einen Wert je Tag, um 23 Uhr. Im Netzvergleich
  fällt der Winter 2021/22 deshalb ganz weg, der Winter 2022/23 hat nur 41 Stationen.
- **Datenende:** Die CSV-Exporte enden am 11.07.2025. Nur 5 Zähler reichen bis Juli 2026, und für 2026 gibt es keine
  Zählerstände. Für den Winter 2025/26 gibt es deshalb keinen Netzvergleich.
- **Unterschiedlich lange Reihen:** 13 Zähler haben unter 70 % Abdeckung, 7 haben unter 10.000 Messstunden. Bei spät
  beginnenden Zählern hat der Ringspeicher die älteren Werte überschrieben.
- **Nutzbare Tage:** Von 89.142 Stationstagen sind 61.408 nutzbar (69 %), im Sommer nur 56 %. Der größte Verlust
  sind Tage mit weniger als 12 Messstunden (17.136), der zweitgrößte Tage unter 5 kWh (8.802, davon 4.460 im Sommer).
  Im Sommer bleiben deshalb eher große, verbrauchsstarke Stationen übrig.
- **Zählertausch:** Die Tauschdaten fehlen. Hat eine Adresse mehrere Zähler, wird der Zähler mit Tageswerten
  genommen.
- **Sonderfälle:** 58202380 ist für ein Haus sehr groß (bis 329 kW, rund 1,9 GWh im Jahr). Ob es eine HAST ist, ist
  offen. 72167783 nimmt seit April 2025 keine Wärme mehr ab, das Wasser zirkulierte aber bis zur Absperrung im April
  2026 weiter.

## Begehungen

- **Wenige Fälle:** 65 Begehungen an 62 Stationen, 7 davon ohne Datum.
- **Auswahl:** Die Stationen wurden nicht zufällig ausgewählt, fast alle Termine liegen im Herbst 2024.
- **Leere Kästchen:** Die Ja/Nein-Spalten sind oft leer. Ob leer „nein“ heißt, geht aus der Tabelle nicht hervor.
- **Freitext statt Spalten:** Befunde und Reparaturen stehen oft nur im Freitext. Die automatische Kodierung der
  Freitexte trifft das nur zum Teil: Sie findet 22 mechanische Eingriffe, von Hand sind es 14, bei 13 Begehungen
  weichen beide voneinander ab.
- **Eine Person:** Die Handprüfung stammt von einer Person, ohne zweite unabhängige Prüfung.
- **Fehlerbeginn:** Die Tabelle sagt, was am Termin gefunden wurde, nicht seit wann.
- **Anlagendaten:** Stationstyp, Zusatzheizung und Personenzahl gibt es nur für begangene Häuser, und sie wurden erst
  bei der Begehung erhoben. Als Merkmal für alle Stationen taugen sie nicht, weil sie verraten würden, ob eine Station
  begangen wurde (Notebook 39).
- **Nach Juli 2025:** Für spätere Begehungen fehlen meist die Zählerstände danach.

## Netz und Zuordnung

**Was gut ist**

- Jede Begehung findet über ihre Adresse einen Zähler.
- **Die Einspeisung ist bekannt.** Laut Expertenangabe der ÜZ ist der Knoten „Erzeuger“ die Einspeisung des Netzes.
  Die Messdaten passen dazu: Eine Schätzung aus dem Vorlauf, der entlang der Leitungen abkühlt, landet beim Erzeuger
  (Rangkorrelation −0,70, Zufallsgrenze −0,28). Im Rohrbaum ab dem Erzeuger hat das Haus weiter oben im Strang bei
  36 von 38 Paaren den wärmeren Vorlauf (Notebook 32).

**Einschränkungen**

- **Anschlusswert:** Er fehlt bei 6 HAST. 4 Zähler stehen in keiner Tabelle, vermutlich alte, getauschte Zähler. 2
  Stationen auf einem Grundstück teilen sich einen Vertrag.
- **Adressen:** Zwei Zähler standen unter der falschen Adresse. Das ist im Code korrigiert (siehe
  [Ergänzende Daten](ergaenzend.md#auskunfte-der-uz)).
- **Kantendatei:** `Nodes_Edges.ods` verbindet 110 Adressen über 110 Kanten zu einem Netz mit genau einem Ring. Sie
  verbindet Häuser direkt miteinander, nicht über die echten Leitungen. Sie sagt also, wer nah beieinander hängt,
  nicht, wo das Wasser fließt.
- **Zähler im Netz:** 84 Zähler mit Tageswerten haben eine Adresse im Netz, 5 Adressen mit Zähler hängen an keiner
  Kante. 8 Stationen haben auch über zwei Kanten keinen Nachbarn mit Zähler (Notebook 23).
- **Pfeile:** Jede Kante hat in der Datei eine Richtung, ihre Bedeutung ist aber offen. Es gibt 7 Knoten ohne Zufluss
  und 6 mit mehreren, die Pfeile passen also zu keiner einzelnen Quelle. Richtet man alle Kanten vom Erzeuger weg aus,
  müssen 54 von 111 umgedreht werden. Der Vorlauf bestätigt keine der beiden Richtungen deutlich: Von 48 Kanten
  mit deutlichem Unterschied sinkt er in Pfeilrichtung an 22, vom Erzeuger weg an 26 (Notebook 32).
- **Weitere Einspeisepunkte:** Ob es außer dem Erzeuger weitere gibt, ist nicht bekannt. Die Schätzung aus dem
  Vorlauf könnte mehrere Einspeisepunkte nicht trennen.
- **Koordinaten:** 18 Adressen haben keine Koordinate, deshalb fehlt für 35 Kanten der Rohrweg. Die Rohrdimension am
  Hausanschluss ist für 81 der 110 Adressen bekannt.
- **Rohrdaten:** Nennweite, Länge und Baujahr je Kante gibt es nur teilweise. Das Netz ist damit ein logisches
  Modell, kein hydraulisches.
- **GNN:** Notebook 39 ist vor der Bestätigung des Erzeugers entstanden und rechnet noch mit einem eigenen Punkt rund
  50 m daneben (siehe [GNN: Hilft das Netz?](../nicht_getragen/gnn.md)).

## Außentemperatur

- Eine Station für das ganze Netz, rund 13 km entfernt.
- Das Tagesmittel bildet nicht ab, dass Gebäude träge reagieren. Ein Wetterumschwung erzeugt deshalb einen Tag mit
  großer Abweichung. Ein Mittel über 2 bis 3 Tage ist als Verbesserung vorgemerkt.
- Die Daten enden am 31.12.2025. Für 2026 gibt es ohnehin keine Zählerstände.

## Was an Daten fehlt

| Was | Wofür |
|---|---|
| Auskunft, ob es außer dem Erzeuger weitere Einspeisepunkte gibt | mehrere Quellen im Netz berücksichtigen |
| Bedeutung der Pfeile in `Nodes_Edges.ods` | Fließrichtung im Netz |
| Koordinaten der 18 Adressen ohne Position | Rohrweg für die 35 Kanten ohne Länge |
| Vorlauftemperatur am Ausgang der Heizzentrale | netzweite Schwankungen direkt erklären |
| Rohrdaten je Kante (Nennweite, Länge, Baujahr) | hydraulischer Widerstand |
| Begehungen nach Juli 2025 mit Zählerständen | neue Prüffälle für die Alarme |
| Minutenwerte oder Reglerdaten mit Stellsignal | Regelhysterese sichtbar machen |

Die Fragen an die ÜZ dazu stehen unter [Offene Fragen an die ÜZ](../grenzen/offene_fragen.md).
