# Vergleichsgruppen und Nachbarn

**Notebook 23:** `notebooks/5_monitoring/23_nachbarn.ipynb` · **Code:** `src/vergleichsgruppen.py`,
`src/nachbarschaft.py`, Tests in `tests/test_vergleichsgruppen.py` und `tests/test_nachbarschaft.py`

Das Notebook ergänzt den [Netzvergleich](netzvergleich.md) um zwei Fragen:

1. **Vergleichsgruppe:** Fallen andere Stationen auf, wenn jede Station nur mit Häusern verglichen wird, die im selben
   Winter ähnlich viel Wärme abgenommen haben?
2. **Nachbarn im Leitungsnetz:** Haben Nachbarn einer auffälligen Station ähnliche Probleme? Das wäre ein Hinweis auf
   eine Ursache im Netz, etwa zu wenig Vorlauf oder Differenzdruck im Strang.

Es ist eine reine Analyse, das Stationsblatt bleibt unverändert.

## Vergleichsgruppe nach Wärmemenge

- **Wärmemenge im Kernwinter** = mittlere Leistung der Betriebsstunden mal Zahl der Stunden im Kernwinter. So zählen
  Lücken nicht als geringer Verbrauch. Das ist ein Größenmaß zum Gruppieren, keine Wärmebilanz.
- Die Stationen unterscheiden sich um zwei Größenordnungen (3 bis 300 MWh), die meisten liegen bei 7 bis 14 MWh.
- Der Netzscore hängt nur schwach an der Größe (Spearman 0,11 bis 0,32, signifikant nur im kleinen Winter 22/23). Die
  Kennzahlen sind auf die Leistung bezogen und damit schon weitgehend größenunabhängig.
- **Vergleichsgruppe:** je Station die k Stationen mit der ähnlichsten Wärmemenge im selben Winter. Die z-Werte werden
  gegen diese Gruppe statt gegen das ganze Netz gerechnet. Geprüft für k = 10, 15 und 25. Bei k = 15 liegt zwischen
  größter und kleinster Station einer Gruppe im Median der Faktor 1,3.

**Ergebnis:**

- Die Rangfolge bleibt fast gleich, die Rangkorrelation liegt in allen Wintern über 0,9. Auch die Zahl der auffälligen
  Stationen ändert sich kaum.
- Es wechseln nur Grenzfälle. Bei k = 15 kommen je Winter eine bis fünf Stationen dazu, zwei bis fünf fallen weg
  (Jaccard 0,41 bis 0,58). Bei k = 25 sind es nur ein bis drei Wechsel.
- An der nächsten Begehung geprüft: Bei k = 10 fällt ein auffälliger Stationswinter ohne Ventilbefund heraus, alle drei
  verbleibenden haben einen Ventilbefund (p von 0,063 auf 0,003). Bei k = 15 und 25 bleibt es beim Ergebnis des
  Netzvergleichs. Bei drei Fällen hängt das an einer einzigen Station.
- **Der Netzvergleich bleibt der Standard.** Die Vergleichsgruppe dient als Sensitivitätsprüfung: Wer in beiden
  Varianten auffällt, ist sicherer markiert.

## Nachbarn im Leitungsnetz

- Grundlage ist der logische Leitungsgraph aus `Nodes_Edges.ods` mit 94 Hausstationen. Nachbarn liegen höchstens zwei
  Kanten auseinander, auch über Knoten ohne Zähler. Zur Prüfung zusätzlich eine und drei Kanten.
- Das Netz ist überwiegend eine Kette. Bei zwei Kanten hat eine Station im Median drei Nachbarn mit Zähler, acht
  Stationen haben gar keine.
- **Permutationstest:** Die Markierung „auffällig“ wird 10.000-mal zufällig auf die Stationen verteilt. Gezählt werden
  Nachbarpaare, bei denen beide auffällig sind. Dazu die Rangkorrelation des Scores über alle Nachbarpaare.

**Ergebnis:**

- **Keine Häufung.** In keinem Winter und bei keiner Weite gibt es mehr auffällige Nachbarpaare als zufällig erwartet
  (p 0,39 bis 1). Unter den acht chronischen Stationen gibt es nur ein benachbartes Paar.
- Die Score-Korrelation zeigt nur im Winter 22/23 etwas (direkte Nachbarn, rho ≈ 0,53), bei nur 38 Stationen und 15
  Paaren. In 23/24 und 24/25 ist sie verschwunden. Bei zwölf Tabellenzeilen ist ein p unter 0,05 auch zufällig zu
  erwarten.
- Das einzige chronische Nachbarpaar, 68956360 und 72167782, bekommt einen Vorlauf von etwa 72 bis 75 °C, also im
  Bereich des Netzmedians oder darüber. Ein Versorgungsproblem ist nicht erkennbar, eher regeln beide Stationen jede für
  sich schlecht.

## Einordnung

- **Belastbar:** Netzvergleich und Vergleichsgruppe ordnen die Stationen fast gleich (Rangkorrelation über 0,9). In
  keinem Winter häufen sich auffällige Nachbarn. Das passt zu Ursachen an der einzelnen Station, nicht im Strang.
- **Schwach:** Die bessere Validierung bei k = 10 hängt an einem Fall. Der Graph ist logisch, nicht hydraulisch: Er
  kennt keine Leitungslängen, Durchmesser oder Drücke.
- **Offen:** ob die Vergleichsgruppe als zweite Sicht ins Stationsblatt kommt. Belastbarer wäre ein Test mit dem
  hydraulischen Netzmodell der ÜZ oder mit Differenzdruckmessungen.

Wie das Netz an anderer Stelle einbezogen wurde, beschreibt [Netz einbeziehen](../netz_einbeziehen/index.md).

## Ausgaben

Das Notebook schreibt keine Dateien.
