# Bayes-Diagnose

**Notebook 38:** `notebooks/weitere_versuche/38_bayes.ipynb` · **Code:** im Notebook, ohne `src/` · **Handtabellen:**
[Prüfliste und Fehler-Symptom-Matrix](../datengrundlage/ergaenzend.md#handtabellen)

Die lernenden Modelle brauchen Labels, und die Labels aus den Begehungen tragen kaum (siehe
[Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#uberwachtes-lernen-auf-begehungslabels)). Dieses Notebook geht den umgekehrten
Weg: Es lernt nichts aus den Begehungen, sondern rechnet mit Fachwissen, das von Hand in einer Tabelle steht. Die
Frage:

> Welche Fehlerart erklärt die Messdaten einer Station am besten, und wie sicher ist das?

Warum kein gelerntes Modell:

- Die Begehungslabels sind zu wenige und zu grob, um daran zu trainieren.
- Es gibt keine klaren Stationstypen (siehe [Merkmale und Clustering](../clustering/index.md)).
- Nachbarn im Netz verhalten sich nicht ähnlicher als zufällige Paare (siehe [GNN: Hilft das Netz?](gnn.md)). Jede
  Station wird deshalb für sich betrachtet.

## Die Idee: wie beim Arzt

| Beim Arzt | Hier |
|---|---|
| Symptome (Fieber, Husten) | zwölf Auffälligkeiten in den Zählerdaten, je Station ja oder nein |
| Wissen, welche Krankheit welche Symptome macht | **Fehler-Symptom-Matrix:** Wie oft zeigt eine Station mit diesem Fehler dieses Symptom? |
| Wissen, wie häufig eine Krankheit ist | **Vorwissen:** wie oft jeder Fehler bei den Begehungen gefunden wurde |

- Naive Bayes rechnet daraus je Station eine Wahrscheinlichkeit für 10 Fehlerarten und „kein Fehler“, zum Beispiel
  „Ventil/Stellantrieb 70 %, Volumenstrom/Hydraulik 20 %“. Die Werte ergeben zusammen 100 % und meinen die
  Hauptursache.
- Die Matrix wird bewusst nicht aus den Begehungen berechnet. Sonst würde das Modell an genau den Daten geprüft, aus
  denen es gebaut ist. Die Begehungen liefern nur das Vorwissen und den Lösungsschlüssel für die Prüfung.
- Das Ergebnis ist eine **Prüfreihenfolge mit Begründung**, keine Diagnose wie bei einem Termin vor Ort.

## Die zwölf Symptome

Jedes Symptom wird je Station aus einem Jahr Daten berechnet. Alle Schwellen sind Startwerte, also Annahmen.

| Kürzel | Symptom | „ja“, wenn … |
|---|---|---|
| AB | Abkühlung schlecht | kWh/m³ bei 5 °C mindestens 5 unter dem Median der Flotte |
| WA | Viel Wasser je kW | Tagesvolumen je kW Anschlusswert bei 5 °C über dem 75. Perzentil der Flotte |
| KF | Kennlinie flach | der Durchfluss im Winter kaum mit der Leistung steigt (Steigung unter 0,3) |
| DE | Durchfluss-Deckel bei Kälte | die Kennlinie nur oben flach ist, darunter normal |
| SN | Sommer nachts Durchfluss | in über der Hälfte der Sommernächte die ganze Nacht Wasser läuft (mindestens 20 l/h) |
| RW | Rücklauf dauerhaft warm | der Rücklauf in über der Hälfte der Winterstunden mit Durchfluss über 50 °C liegt |
| NA | Keine Nachtabsenkung | der Rücklauf nachts weniger als 1 K unter dem am Tag liegt |
| SA | Abkühlung wird schleichend schlechter | die Abkühlung über zwei Jahre um mehr als 3 kWh/m³ stärker nachlässt als in der Flotte |
| SD | Durchfluss bei Kälte sinkt schleichend | der Durchfluss an Frosttagen über zwei Jahre um mehr als 20 % stärker sinkt als in der Flotte |
| TA | Starkes Schwanken/Takten | der Durchfluss innerhalb eines Tages stärker schwankt als bei drei Vierteln der Flotte |
| KA | Kaum Abnahme an kalten Tagen | an über 10 % der kalten Tage fast keine Wärme abgenommen wird |
| ME | Messauffälligkeiten | an über 5 % der Tage der Zähler steht, zurückspringt oder unplausible Werte liefert |

- Reichen die Daten für ein Symptom nicht, fällt es aus der Rechnung und verschiebt nichts. Unter 6 berechenbaren
  Symptomen heißt es „zu wenig Daten“.
- Zwei Regeln kamen nach dem ersten Lauf dazu. Beide wegen offensichtlich falscher Einzelergebnisse, nicht wegen der
  Prüfmaße:
    - **Neustart nach einer Begehung:** Das Jahr beginnt frühestens 14 Tage nach der letzten Begehung. Sonst hielt das
      Modell den reparierten Ventilfall für einen Schmutzfänger, weil die Reparatur aussah wie „Durchfluss sinkt
      schleichend“.
    - **Trends gegen die Flotte:** Ohne diese Regel war SA bei 45 % der Stationen „ja“, weil die ganze Flotte 2025 im
      Median 2,6 kWh/m³ verlor. Eine gemeinsame Verschiebung ist kein Fehler einer Station.

## Matrix und Vorwissen

- **Matrix:** 11 Zeilen mal 12 Symptome, also 132 Felder. Jedes Feld hat eine Stufe von „nie“ (0,05) bis „fast
  immer“ (0,90). Die Stufen sind ein Entwurf aus der Physik, mit der ÜZ abgestimmt sind 0 von 132 Feldern (Aufbau
  unter [Ergänzende Daten](../datengrundlage/ergaenzend.md#fehler-symptom-matrix-entwurf)).
- Kein Feld ist 0 oder 1. Sonst würde ein einziges fehlendes Symptom einen Fehler ganz ausschließen.
- **Beispiel:** Bei einem hängenden Ventil ist die Abkühlung fast immer schlecht (0,90), bei einer gesunden Station
  selten (0,15). Eine schlechte Abkühlung macht das Ventil damit sechsmal wahrscheinlicher als „kein Fehler“.
- Eine Zeile, die sich kaum von „kein Fehler“ unterscheidet, etwa die Dämmung, kann das Modell kaum erkennen.
- **Vorwissen:** aus der [Prüfliste der Begehungsnotizen](../datengrundlage/ergaenzend.md#prufliste-der-begehungsnotizen),
  65 Begehungen, alle Notizen von Hand geprüft. Am häufigsten ist Regler/Einstellung (36 %), dann „kein Befund“
  (17 %), Dämmung (11 %) und Ventil/Stellantrieb (9 %).
- **Zwei Vorwissen:** Die ÜZ hat gezielt Stationen mit Optimierungsbedarf besucht, dort ist „kein Befund“ selten. Mit
  dieser Quote galten 79 von 80 Stationen als auffällig, wie bei einem Hausarzt, der mit der Quote einer
  Spezialklinik rechnet. Für die Diagnose aller Stationen gilt deshalb „kein Fehler“ = 50 % (Annahme), für die
  Prüfung an den Begehungen die Häufigkeiten aus der Prüfliste.
- **Datenbeleg:** wie viel besser der passendste Fehler die Symptome erklärt als „kein Fehler“, ganz ohne Vorwissen.
  ×1 heißt, die Daten sagen nichts, ×100 heißt deutlich. Danach richtet sich die Prüfreihenfolge.

## Der bekannte Ventilfall

Bei Station 68956351 stand das Ventil rund drei Jahre offen, am 09.09.2024 wurde der Stellmotor getauscht.

| Zeitraum | Symptome „ja“ | Ergebnis |
|---|---|---|
| Jahr vor der Begehung | AB, WA, KF, SN, RW, NA, SD | Ventil/Stellantrieb 96 %, Datenbeleg rund ×1.600 |
| Jahr bis Juli 2025 | nur TA | „kein Fehler“ 72 %, unauffällig (×0,8) |

Ein unabhängiger Test ist das nicht: Die Matrix wurde mit diesem Fall im Kopf entworfen. Er zeigt, dass die Rechnung
funktioniert, nicht, dass das Modell gut ist.

## Diagnose aller Stationen

Gerechnet für das Jahr 10.07.2024 bis 10.07.2025, 83 Stationen mit genug Daten (4 weitere mit zu wenig Daten).

- 21 Stationen bekommen „HAST prüfen“, davon 14 mit Hauptursache Ventil/Stellantrieb. 62 sind unauffällig.
- Bei 65 von 83 Stationen liegt der Datenbeleg unter ×10. Bei ihnen sagen die Symptome wenig, und das Vorwissen
  entscheidet. Ab ×10 liegen 18 Stationen, ab ×100 noch 9.
- Nur 4 Stationen haben eine Hauptursache über 90 %.
- Wie viele Stationen auffällig sind, hängt am angenommenen Anteil gesunder Stationen: bei 50 % sind es 21, bei 70 %
  19, bei 30 % aber 55.

## Prüfung an den Begehungen

- Bewertet werden 50 Begehungen an 49 Stationen. Für jede gilt das Jahr bis 14 Tage vor dem Termin, das Vorwissen
  wird ohne die eigene Station gezählt.
- Messlatten sind „nur Vorwissen“ (raten nach Häufigkeit) und 5.000 zufällige Zuordnungen der Befunde zu den
  Begehungen.

| Maß | Modell | Zufall (Mittel) |
|---|---|---|
| wahrscheinlichste Klasse ist ein Befund (Top-1) | 0,46 | 0,40 |
| Befund unter den drei wahrscheinlichsten (Top-3) | 0,90 | 0,83 |
| mittlere Wahrscheinlichkeit für den echten Befund | 0,40 | 0,31 (p = 0,0004) |

- **Ventil/Stellantrieb hat als einzige Fehlerart eine klare Spur.** Begehungen mit Ventilbefund bekamen dafür im
  Mittel 40 %, die übrigen 1 % (n = 10). Gegen „kein Befund“ liegt die AUC bei 0,92. Sah das Modell das Ventil
  vorne, war es in allen 5 Fällen ein Ventilbefund.
- **Regler/Einstellung** ist der häufigste Befund (32 von 50) und hinterlässt keine Spur (AUC 0,57). Deshalb trifft
  das Modell seltener als „immer Regler raten“ (Top-1 0,46 gegen 0,64).
- **Dämmung** ist ein Artefakt der Matrix: Ihre Zeile sieht fast aus wie „kein Fehler“, fehlende Symptome sprechen
  deshalb für Dämmung. In der Prüfung ist sie 12-mal Hauptursache, aber nur 2-mal ein Treffer.
- **Befund ja oder nein** trennt das Modell nicht, auch nicht über den Datenbeleg (AUC 0,55, p = 0,34). Nur 9
  Begehungen haben „kein Befund“.
- Die Befunde stammen aus den Notizen der Begehung. Bei einzelnen Regeln der Prüfliste entschieden die Messdaten mit
  (zum Beispiel „Anlage aus“ nur, wenn die Daten es zeigen). Das kann die Prüfung etwas zu gut aussehen lassen.

## Wie stark hängt es an der Matrix?

200-mal wird jedes Feld der Matrix zufällig um eine Stufe nach oben oder unten verschoben oder bleibt.

- Die Hauptursache einer Station bleibt im Median in 84 % der Ziehungen gleich.
- Die Prüfreihenfolge nach Datenbeleg ändert sich merklich (Rangkorrelation im Median 0,61, in 5 % der Ziehungen
  unter 0,26).
- Am unteren Rand fallen die Prüfmaße unter das Zufallsmittel (Top-1 0,28, mittlere Wahrscheinlichkeit 0,29). Wie gut
  das Modell prüft, hängt also an den genauen Stufen.

## Warum es nicht weiterverfolgt wird

- Für alle Fehlerarten außer dem Ventil ist das Modell mit den zwölf Symptomen nicht belastbar, vor allem nicht für
  Einstellungsfehler. Das passt zu Notebook 36: Nur der Ventiltausch hinterlässt eine messbare Spur (siehe
  [Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#fehlerarten-ohne-messspur)).
- Für das Ventil gibt es im Endmodell schon Erkenner, die ohne Handtabelle auskommen. Mit ihnen verglichen wurde die
  Bayes-Diagnose nicht, weil der [Modellvergleich](../vergleich/modellvergleich.md#was-sich-nicht-vergleichen-lasst) die
  Handtabellen nicht hat.
- Die Matrix ist nicht mit der ÜZ abgestimmt, und das Ergebnis ist genau so gut wie sie.
- Mehrere Symptome beschreiben dasselbe Bild „Wasser läuft durch, ohne abzukühlen“ (AB und RW hängen mit 0,75
  zusammen). Naive Bayes zählt das mehrfach und wird zu sicher.
- Je Fehlerart gibt es höchstens 10 Fälle (außer Regler). Jedes Ergebnis je Fehlerart ist nur ein Hinweis.

## Was es zum Weitermachen bräuchte

- Die Matrix mit der ÜZ durchgehen, vor allem die Zeile „kein Fehler“, die Symptome KA und ME und den Anteil gesunder
  Stationen.
- Die Prüfliste nachschärfen: „Regler/Einstellung“ in den 22 Zeilen prüfen, deren Notiz nur das Standardpaket nennt,
  und „Dämmung“ (11 Zeilen) nach der eigenen Kodierregel nicht als Befund führen. Beides verschiebt Vorwissen und
  Prüfung deutlich.
- Bessere Symptome, zum Beispiel „Ventil fest“ (Durchfluss über Monate nahe am Höchstwert) und Dauerdurchfluss im
  Sommer.

## Ausführen

- Das Notebook braucht die beiden Handtabellen unter `data/manual/`. Sie liegen nicht im Repository (siehe
  [Vorbereitung](../installation/vorbereitung.md#handtabellen-fur-notebook-38)). Ohne sie bricht nur dieses Notebook
  ab.
- Neue Einträge in den Tabellen wirken beim nächsten Lauf, ohne Codeänderung.
- Es schreibt nur mit `SPEICHERN = True`, dann zwei Tabellen nach `outputs/31_bayes_diagnose/`.
