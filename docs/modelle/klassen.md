# Fehlerart und Klasse je Station

Der Projektpartner hat vorgegeben, jede Station in eine von drei Klassen mit je einer Handlung einzuteilen:

| Klasse | Handlung |
|---|---|
| Regelventil schließt nicht | Regelventil tauschen (Reparatur) |
| Station läuft schlechter als möglich, Technik in Ordnung | Regelparameter optimieren |
| Station läuft gut | kein Handlungsbedarf |

Dazu kommen zwei Hinweise aus der Aufgabenstellung: Leitungen dämmen und die Anschlussleistung anpassen. Diese Seite
beschreibt, wie eine Station zu ihrer Klasse kommt. Die Bausteine sind der
[LSTM-Fingerabdruck](lstm.md) und die Kennzahlen aus [Daten, Labels und Messlatte](daten.md). Gerechnet wird in
Notebook 26 (K-Means) und Notebook 29 (Fehlerart und Klassen). Das Paket für das Dashboard baut Notebook 35.

## Ein Modell je Fehlerart

Jede Fehlerart wird einzeln gegen „kein Befund dieser Art“ gelernt. Viele Befunde treten gemeinsam auf, ein
gemeinsames Modell für alle würde sie vermischen.

Notebook 29 vergleicht sieben Verfahren über die sechs Fehlerarten: von der einzelnen Regel über logistische
Regressionen auf Kennzahlen, auf den LSTM-Zahlen und auf beidem bis zu Random Forest und XGBoost. Alle werden
verschachtelt geprüft, mit ausgelassenen Stationen und mit ausgelassenen Straßen (siehe
[Prüfdesign und Statistik](../vergleich/pruefung.md)).

| Fehlerart | bestes Verfahren in Notebook 29 | AUC [95 %] | ganze Straßen ausgelassen |
|---|---|---|---|
| Ventil | logistische Regression auf Kennzahlen und LSTM-Zahlen | 0,89 [0,78; 0,97] | 0,83 |
| Dämmung | dasselbe Verfahren | 0,75 [0,59; 0,88] | 0,82 |
| Überdimensioniert | Regel: Auslastung zum alten Vertrag | 0,78 [0,53; 0,98] | 0,78 |
| Filter, Durchfluss, Temperatur | keins | 0,24 bis 0,64 | – |

Das ist der erste Stand. Die strengere Prüfung in Notebook 35 kommt beim Ventil auf 0,84 und bei der Dämmung auf
0,78, mit der Regression nur auf den 16 LSTM-Zahlen (siehe
[Endmodell](../ergebnisse/endmodell.md)).

**Warum eine logistische Regression.** Bei 11 Ventil- und 9 Vertragsfällen kann ein Modell nur wenige Gewichte
sicher lernen. Die logistische Regression hat je Merkmal ein Gewicht, ihre Regularisierung wird in der inneren
Prüfung gewählt. Random Forest und XGBoost sind nirgends besser. Wechselwirkungen zwischen Merkmalen bringen −0,03
bis +0,05, nicht gesichert. Bei der Dämmung schwankt XGBoost je nach Startwert zwischen 0,74 und 0,87, und die
wichtigsten Merkmale wechseln. Der Gewinn steckt in den Merkmalen, nicht im Verfahren: im Fingerabdruck bei Ventil
und Dämmung, in einer richtig bezogenen Zahl bei der Überdimensionierung.

## Kapazität: eine Regel statt eines Modells

Eine Station ist überdimensioniert, wenn sie ihre Vertragsleistung nie braucht. Die Regel teilt die Spitzenlast vor
der Begehung durch die Vertragsleistung vor der Begehung. Ist diese Auslastung niedrig, gibt es einen Hinweis. Die
Grenze wird über den Youden-Index auf den begangenen Stationen gewählt.

- Die Vertragsleistung kommt aus dem Begehungsprotokoll, nicht aus dem Netzplan. Im Netzplan steht bei 7 der 9
  verkleinerten Verträge schon der neue Wert. Darauf bezogen ist das Signal weg (siehe
  [Daten, Labels und Messlatte](daten.md)).
- In Notebook 29 sind 6 von 7 Hinweisen richtig. Die Regel ist dort gesichert besser als die Regression auf den
  Kennzahlen.
- In Notebook 35 kommt die Regel auf eine AUC von 0,76. Die gelernten Modelle kommen höchstens auf 0,53, weil ihnen
  die Auslastung zum alten Vertrag als Merkmal fehlt.

## Optimum oder schlechter: K-Means

Für die Stationen ohne Ventilverdacht bleibt die Frage: Läuft die Station gut oder schlechter als
möglich? Dafür gibt es kein Label, kein Monteur hat „läuft schlechter als möglich“ notiert. Notebook 26 gruppiert die
Stationen deshalb ohne Label mit K-Means.

- **Merkmale:** drei Größen aus dem Winter 2023/24, die beschreiben, wie eine Station regelt: wie stark der
  Durchfluss der Last folgt (Anteil Volumenstrom, niedrig heißt: das Ventil drosselt nicht), wie weit ihre
  Betriebspunkte streuen und wie heiß das Wasser unter Last zurückkommt (lastgewichteter Rücklauf). Alle drei werden
  standardisiert. Zähler mit weniger als 200 Laststunden im Winter werden nicht eingestuft.
- **Zahl der Gruppen:** Elbow und Silhouette sprechen für zwei. Die Silhouette liegt bei 0,44, deutlich über den
  Stationsclustern aus Notebook 07 mit allen Kennzahlen (unter 0,25).
- **Benennung:** Die Gruppe mit dem kälteren lastgewichteten Rücklauf ist das Optimum, die andere „schlechter“.
- **Ergebnis:** Von 88 Zählern mit genug Wintermessungen liegen 70 im Optimum und 18 in „schlechter“.
- **Stabilität:** Über 20 Startwerte ist die Einteilung identisch, im Bootstrap stimmt sie im Median zu 98 %
  überein. Im schlechtesten Zwanzigstel der Ziehungen sind es nur 70 %. Grenzfälle wechseln also die Gruppe.

**Warum K-Means hier trägt.** Im Projekt wurde K-Means vorher dreimal eingesetzt: Stationscluster (Notebook 07),
Betriebszustände auf Stundenwerten (Notebook 09) und Tagestypen (Notebook 10). Gruppen fand es jedes Mal, aber „weit weg vom Zentrum“ hieß nicht „defekt“. Hier soll K-Means keinen
Fehler finden, sondern nur das Regelverhalten beschreiben. Das kann es.

**Gegenprobe.** In der Gruppe „schlechter“ hatten 50 % der begangenen Stationen einen Ventilbefund, im Optimum 14 %
(p = 0,021, nach der Holm-Korrektur 0,13, also nicht gesichert). Etwa die Hälfte von „schlechter“ ist das Ventilbild.
Daraus folgt die Reihenfolge der Klassen: erst das Ventil, dann für den Rest K-Means.

## Die Klasse je Station

Jede Station durchläuft dieselbe Reihenfolge:

1. Ventil-Score ab 0,5: **Regelventil tauschen.**
2. sonst K-Means „schlechter“: **Regelparameter optimieren.**
3. sonst K-Means „Optimum“: **kein Handlungsbedarf.**
4. ohne genug Daten: **nicht einstufbar.**

Unabhängig von der Klasse kommen die Hinweise Dämmung (Dämmungs-Score ab 0,5, im Paket aus Notebook 35 fest wie beim Ventil) und Kapazität
(Auslastung zum Vertrag unter der Grenze).

**Warum die Ventil-Grenze fest bei 0,5 liegt.** Der Youden-Index läge bei 0,17. Bei 11 Ventilfällen hat die Kurve
aber mehrere fast gleich hohe Spitzen, und welche vorne liegt, kippt schon bei kleinen Änderungen der Daten. Die feste
Grenze steht vorher fest und hängt nicht an einzelnen Fällen.

Notebook 29 stuft alle 91 Zähler mit Kennzahlen ein, auch die 37 nie begangenen: 24 Regelventil tauschen, 5
Regelparameter optimieren, 61 kein Handlungsbedarf, 1 nicht einstufbar. Das Paket aus Notebook 35 kommt auf 25, 4,
61 und 1. Bei den nie begangenen Stationen ist die Klasse eine Vorhersage, keine Prüfung.

## Was daraus folgt

- **Regelventil tauschen** trägt. Die Klasse trifft in Notebook 35 8 von 11 Ventilfällen.
- **Regelparameter optimieren** trägt nicht. In Notebook 35 trifft die Klasse weder beim LSTM-Modell noch beim
  Monitoring-Modell einen Befund: Von 31 Fällen landen 24 bzw. 25 in „kein Handlungsbedarf“. Das Dashboard empfiehlt
  diese Klasse deshalb nicht.
- **Kapazität** bleibt eine Regel, weil das entscheidende Merkmal sauber nur als Regel vorliegt.
- **Filter, Durchfluss und Temperatur** lassen sich nicht einstufen. Warum, zeigt Notebook 36 (siehe
  [Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#fehlerarten-ohne-messspur)).
