# Bestes Viertel als Maßstab

**Notebook 22:** `notebooks/5_monitoring/22_bestwert.ipynb` · **Code:** `src/netzvergleich.py` (`bestwert`,
`grenzen_lernen`, `grenzen_anwenden`, `potenzial_je_winter`) und `src/stationsblatt.py`, Tests in
`tests/test_netzvergleich.py` und `tests/test_stationsblatt.py`

Der [Netzvergleich](netzvergleich.md) misst jede Station am Median aller Stationen. Läuft schon die typische Station
schlecht, fällt dabei wenig auf. Dieses Notebook nimmt deshalb das **beste Viertel** je Kennzahl als zweiten Maßstab
und prüft zwei Fragen:

1. Zeigt der Abstand zum besten Viertel andere Stationen als der Abstand zum Median?
2. Hätte ein Maßstab, der vor den Begehungen festgelegt wurde, die Stationen mit späterem Befund erkannt, und rücken
   begangene Stationen danach näher an die besten heran?

## Lücke und Potenzial

- **Lücke** einer Kennzahl = Abstand der Station zum Median des besten Viertels, geteilt durch den Abstand der
  typischen Station dazu. 0 heißt so gut wie das beste Viertel, 1 so weit weg wie die typische Station.
- **Potenzialwert** = Mittel der Lücken über die fünf Kennzahlen des Netzvergleichs.
- **Stufen:** unter 1 gering, 1 bis unter 2 mittel, ab 2 hoch. Die Grenzen sind gesetzt und vom Team zu bestätigen.
- Die Priorität bleibt unverändert, das Potenzial steht daneben.

## Wie weit liegt die typische Station vom besten Viertel weg?

| Kennzahl (Winter 24/25) | typische Station | bestes Viertel |
|---|---|---|
| Spreizung | 25,6 K | 34,7 K |
| Steigung der Kennlinie | 0,92 | 1,13 |
| Streuung um die Kennlinie | 0,22 | 0,13 |
| Anteil Stunden mit Rücklauf über 50 °C | 29 % | 3 % |
| Wasser je kW Anschlusswert | 14,6 l/h/kW | 7,5 l/h/kW |

- Die typische Station kühlt rund 9 K schwächer ab als das beste Viertel und braucht je kW etwa doppelt so viel Wasser.
- Die Abstände sind über die drei Winter ähnlich. Luft nach oben gibt es im ganzen Netz, nicht nur bei einzelnen
  Stationen.

## Findet das beste Viertel andere Stationen?

- **Nein.** Die Rangkorrelation zwischen Potenzialwert und Score liegt in allen Wintern bei 0,99 oder darüber. Beide
  sind Mittel über dieselben fünf Kennzahlen.
- **Neu ist die Lesart.** Lücken lassen sich in Einheiten ausdrücken, etwa „Spreizung 9 K unter dem besten Viertel“.
- Je Winter haben 3 bis 12 im Netzvergleich unauffällige Stationen trotzdem Potenzial hoch.
- Im Winter 24/25 haben alle 8 Stationen mit Priorität hoch auch Potenzial hoch. 9 im Netzvergleich unauffällige
  Stationen haben Potenzial hoch. Kein Merkmal aus den Begehungen trennt diese Gruppe, am ehesten haben sie öfter
  Befunde zu Regler oder Parametern (Fisher p = 0,026, nur ein Hinweis).

## Eingefrorener Maßstab: lernen vor den Begehungen, testen danach

Die Begehungen liegen fast alle zwischen August und November 2024. Median, Streuung, Grenze für „schlecht“ und bestes
Viertel werden deshalb aus den Wintern 22/23 und 23/24 gelernt (127 Stationswinter) und fest auf 24/25 angewendet.
Begehungslabels gehen nicht ein.

**Vorher: Waren die Stationen mit späterem Befund schon auffällig?**

| Gruppe im Winter 23/24 | Stationen | auffällig | Potenzial hoch |
|---|---|---|---|
| begangen mit Befund | 28 | 11 % | 25 % |
| begangen ohne Befund | 26 | 4 % | 15 % |
| nie begangen | 32 | 12 % | 25 % |

Kein Unterschied ist annähernd signifikant (p 0,50 bis 0,71). Viele Befunde wie Schmutzfänger, Dämmung oder
Einstellungen zeigen sich kaum in Spreizung oder Volumenstrom. „Ohne Befund“ heißt zudem nur, dass nichts notiert
wurde.

**Nachher: Rücken begangene Stationen näher an die besten heran?**

- Der Potenzialwert ändert sich von 23/24 auf 24/25 in beiden Gruppen im Median kaum (begangen −0,01, nicht begangen
  +0,01, p = 0,77).
- Von den vorher auffälligen Stationen sind unter den begangenen zwei von drei danach unauffällig, unter den nicht
  begangenen eine von vier. Das ist nur eine Beobachtung.

**Gegenprobe mit nur 22/23 als Lernwinter.** Im Hauptlauf ist 23/24 zugleich Lern- und Vorher-Winter. Mit nur 22/23
als Lernwinter bleibt die Auffälligkeit unverändert. Beim Potenzial haben begangene Stationen mit Befund öfter Potenzial
hoch als solche ohne Befund (18 % gegen 4 %, p = 0,19). Auch das ist nur ein schwacher Hinweis.

## Einordnung

- **Belastbar:** Der Abstand der typischen Station zum besten Viertel ist über drei Winter ähnlich. Die Rangfolge
  ändert sich kaum, neu sind Lücken in physikalischen Einheiten und eine weichere Stufe als „auffällig“.
- **Schwach:** Der eingefrorene Maßstab sagt weder Befunde vorher, noch zeigt er eine Verbesserung nach den
  Begehungen. Bei etwa 50 begangenen Stationen und Labels aus Freitexten ist das kein Beleg gegen die Begehungen. Die
  Winterkennzahlen bilden die Befunde aber nicht ab.
- **Offen:** die Grenzen der Potenzialstufen und ein Nachher-Test mit dem Winter 25/26, sobald Daten für mehr als vier
  Stationen vorliegen.

## Wo das Potenzial steht

Das Notebook schreibt keine Dateien. Umgesetzt ist das Potenzial im Stationsblatt, in der Statustabelle (`potenzial`,
`potenzial_score`, `groesste_luecke`, `bw_abstand_*`), im Bericht von `python -m src.aktualisieren` und im Dashboard als
eigene Färbung der Karte.
