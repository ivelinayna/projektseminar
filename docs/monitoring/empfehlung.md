# Von der Anomalie zur Empfehlung

**Notebook 17:** `notebooks/5_monitoring/17_empfehlung.ipynb` · **Code:** `src/empfehlung.py`, `src/freitext.py`,
`src/priority.py`, Tests in `tests/test_empfehlung.py` und `tests/test_freitext.py`

In [Notebook 16](anomalie.md) bestehen das netzweite und das stationseigene Rücklaufresiduum die Prüfung an den
Begehungen. Für eine Empfehlung reicht das nicht, denn die Hälfte der Stationen bekam dort kein Muster, und ohne Muster
gibt es keine Maßnahme. Dieses Notebook ordnet deshalb jeder auffälligen Station ein Muster, eine Maßnahme und einen
nachvollziehbaren Schweregrad zu und stellt daraus eine Trefferliste ohne Adressen auf.

Vorher müssen die Notebooks 00 und 04 gelaufen sein (Notebook 04 liefert `wintervergleich_kernwinter.csv`), außerdem
`python -m src.meter_quality` und `python -m src.detect_real` für die Prioritätsscores aus `src/priority.py`.

## Warum so viele Stationen ohne Muster blieben

- In Notebook 16 gilt ein Muster nur, wenn alle seine Bedingungen zugleich erfüllt sind. Ein oberes Fünftel trifft
  rund 19 von 93 Stationen, zwei unabhängige Bedingungen zusammen im Mittel knapp 4.
- 40 der 50 Stationen ohne Muster sind nicht persistent auffällig, dort ist „kein Muster“ richtig.
- Von den 26 persistent auffälligen Stationen blieben aber **19 ohne verwertbare Diagnose**: 10 ohne Muster und 9 mit
  dem Auffangmuster „Rücklauf über Erwartung“.
- Folgerung: Muster nur noch den auffälligen Stationen zuordnen und die Evidenz gewichten statt alle Bedingungen
  starr zu verknüpfen.

## Neuer Musterkatalog

- **Auffällig** heißt: nach einem der beiden Residuen an mehr als 10 % der Tage persistent auffällig.
- **Evidenz** eines Musters = gewichtetes Mittel der rangbasierten z-Werte seiner Indikatoren. Es gewinnt das Muster
  mit der höchsten Evidenz, sofern sie mindestens 0,6 beträgt. Ränge statt Median und MAD, weil etwa der Volumenstrom
  (Median 38 l/h, Maximum rund 14.500 l/h) sonst extreme z-Werte liefert.
- Sieben Muster. Die beiden allgemeinen („Rücklauf dauerhaft über der Netzerwartung“, „Verschlechterung gegenüber dem
  eigenen Normalbetrieb“) greifen nur, wenn kein spezifisches Muster reicht.

| Muster | Stationen | davon Stufe hoch |
|---|---|---|
| Durchfluss ohne Auskühlung, Verdacht hydraulischer Kurzschluss | 8 | 8 |
| Hoher Rücklauf im Sommer, Verdacht Zirkulations- oder Speicherverlust | 5 | 4 |
| Verschlechterung gegenüber dem eigenen Normalbetrieb | 5 | 0 |
| Unruhige Regelung | 4 | 1 |
| Keine nennenswerte Abnahme bei warmem Rücklauf | 3 | 1 |
| Rücklauf reagiert kaum, Verdacht festsitzendes oder offenes Ventil | 1 | 1 |

- **Alle 26 auffälligen Stationen haben ein Muster.** Die große Restkategorie war ein Konstruktionsfehler der alten
  Regeln, keine Eigenschaft der Daten.
- Unter den fünf Stationen mit 100 Punkten ist auch 68956351 mit dem drei Jahre offenen Ventil, hier als Kurzschluss
  eingeordnet. Beides sieht im Messbild ähnlich aus: viel Durchfluss, kaum Auskühlung.
- **Unsicherheit** = Abstand der Evidenz zwischen bestem und zweitbestem Muster. Bei 4 von 26 Stationen liegt er unter
  0,3, meist ist dann das Kurzschlussmuster beteiligt. Das zweite Muster sollte bei der Begehung mitgeprüft werden.

## Freitexte der Begehungen

- 66 Begehungszeilen, 57 mit Freitext. Feste Schlüsselwortlisten in `src/freitext.py` ordnen jedem Text Kategorien zu.
  Jede Zuordnung lässt sich auf das auslösende Wort zurückführen, Verneinungen werden berücksichtigt.
- 24 Texte sind eindeutig, 13 mehrdeutig, 20 ohne Fehlerhinweis, 9 leer.
- Häufigste Kategorien: Regelung defekt oder falsch eingestellt (17), Pumpe oder Zirkulation (10), Hydraulik oder
  Volumenstrom (8).

**Zwei Ranglisten, die sich nicht ineinander überführen lassen.** In den Messdaten steht der Kurzschlussverdacht vorn
(8 von 26), in den Texten die Regelung. Die Begehungen betreffen zum Teil andere Stationen, und die Monteure sehen auch
Dinge, die im Zähler keine Spur hinterlassen. Ein Teil der Protokolle beschreibt zudem nur das Gebäude.

## Erklärbares Baummodell

Ein Entscheidungsbaum soll erklären, nicht vorhersagen. Zielgröße ist das Rücklaufresiduum gegen die Netzerwartung auf
54.201 Stationstagen. Die Kreuzvalidierung hält ganze Stationen heraus.

- In allen fünf Durchläufen steht der Tagesmedian des Durchflusses an der Wurzel, mit einer Grenze bei 170 bis 200 l/h.
  Auf herausgehaltenen Stationen erreicht der Baum R² = 0,44 ± 0,09.
- Der wärmste Ast: Durchfluss über 173 l/h bei Leistung bis 4,7 kW, Residuum +28,7 K. Das ist dieselbe Konstellation
  wie beim Kurzschlussmuster.
- Die Spreizung bleibt als Merkmal draußen, weil sie rechnerisch am Rücklauf hängt. Mit ihr steigt R² auf 0,62, der
  Gewinn ist überwiegend rechnerisch.

## Schweregrad

- Drei offengelegte Teile: Abweichung in Kelvin (Gewicht 0,45), Persistenz (0,35) und Mehrdurchfluss (0,20).
  Mehrdurchfluss = Rücklaufabweichung geteilt durch die Spreizung. Anders als der Verbrauch je Heizgradstunde hängt er
  nicht von der Hausgröße ab.
- Stufen: hoch ab 55 Punkten, mittel ab 30.
- Ergebnis: 15 Stationen hoch, 3 mittel, 8 niedrig. Die fünf Stationen mit 100 Punkten sind gedeckelt und untereinander
  nicht sortiert.
- Ein Fehler ohne Spur im Rücklauf bekommt keine Punkte.

## Trefferliste und Priorität

- Die Trefferliste zeigt je Station Muster, Stufe, Punkte, Maßnahme und eine kurze Begründung. Der Export verweigert
  Spalten mit Bezug zu Adresse oder Namen.
- Beispiel für die Ausgabe an den Monteur: *Zähler 72167782, hoch, 100 Punkte. Muster: Durchfluss ohne Auskühlung,
  Verdacht hydraulischer Kurzschluss. Maßnahme: Volumenstrom am Regelventil begrenzen, Bypass und Beimischung auf
  Kurzschluss prüfen, Schmutzfänger kontrollieren.*
- `src/priority.py` zeigt, wo eine Begehung überfällig ist, die Trefferliste, wo der Betrieb heute auffällig ist.
  25 Stationen stehen in beiden Listen, Spearman 0,48. Beide zeigen in dieselbe Richtung, ersetzen sich aber nicht.

## Nutzen für die ÜZ

- **Aufwand:** 10 Begehungen decken 60 % der Punktsumme ab, 20 Begehungen 95 %.
- **Begehungen ohne Wirkung:** Referenz ist der [Wintervergleich](../begehungen/wintervergleich.md) mit 45
  Begehungen. 9 davon (20 %) brachten keine messbare Verbesserung, 4 davon stehen in der Trefferliste.
- War der Zustand nach der Begehung schlecht, stehen 54 % der Stationen in der Liste, bei gutem Zustand 16 %.
- Die Liste nutzt auch die Zeit nach den Begehungen. Gemessen wird also, ob sie Stationen richtig benennt, nicht ob sie
  vorhersagt.

## Einordnung

- **Belastbar:** Der Kurzschlussverdacht ist physikalisch stimmig, der Baum findet dieselbe Konstellation stabil als
  wärmsten Ast. Nach der Begehung trennt die Liste schlechte von guten Fällen (54 % gegen 16 %).
- **Schwach:** Text- und Messrangliste laufen auseinander. 68956351 wird als Kurzschluss statt als Ventil eingeordnet.
  Der Schweregrad sieht nur auf den Rücklauf, und fünf Zähler haben ein Jahr mehr Beobachtungszeit.
- **Offen:** Die Zuordnung von Muster zu Maßnahme ist physikalisch begründet, bleibt aber ein Vorschlag für die ÜZ.
  Mindestevidenz, Persistenzschwelle, Stufen und Gewichte sind gesetzt, nicht kalibriert. Wie sich ein offenes Ventil
  und ein Kurzschluss im Messbild trennen lassen, ist ungeklärt.

## Ausgaben

- `data/processed/empfehlungsliste.csv`: 26 Zeilen mit Muster, Stufe, Punkten, Maßnahme, Begründung, Evidenz,
  Zweitmuster und den Teilen des Schweregrads.
- `data/processed/empfehlung_kontext.json`: Schwellen, Gewichte, Musterkatalog und Kernergebnisse des Laufs.
- Nur Zählernummern, keine Adressen.
