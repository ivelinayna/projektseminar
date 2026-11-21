# Wirkung im 21-Tage-Fenster

**Notebook 02:** `notebooks/2_begehungen/02_wirkung.ipynb` · **Code:** `src/load_begehungen.py`, Tests in
`tests/test_load_begehungen.py`

Das Notebook misst, ob sich das Betriebsverhalten einer Station nach einer Begehung messbar geändert hat, und ob die
Änderung zur dokumentierten Änderungskategorie passt.

## Ereignis statt Label

- Bisher wurden die Begehungen als Label genutzt: `n_actions > 0` hieß „die Station hatte einen Fehler“. Das ist bei
  76 % der Stationen wahr und trennt deshalb nichts.
- Hier ist die Begehung ein **Ereignis**: Was hat sich danach geändert? Die Zielgröße kommt aus den Messdaten selbst.

## Begehungen den Zählern zuordnen

- Über `Zuordnung.xlsx` bekommen **alle 66 Begehungen** eine Zählernummer. Über die Adressen aus `Nodes_Edges.ods`,
  die vorher genutzt wurden, waren es nur 54, dort fehlen 16 Adressen.
- Der Loader korrigiert dabei einen Tippfehler in einem Straßennamen, der allein vier Zuordnungen gekostet hat.
- 58 Begehungen haben ein Datum, 37 eine Uhrzeit, 8 eine dokumentierte Änderung der Heizzeit.
- Neu nutzbar ist die **Änderungskategorie**: keine (4), geringe (5), mittlere (36), viele (21). Die frühere Tabelle
  `inspections_tidy.csv` hatte nur 21 der 133 Spalten übernommen, diese nicht.
- Fünf Adressen führen mehr als eine Zählernummer:
    - zwei echte Zählerwechsel, z. B. 65273846 → 80912176 ab 2025. Die Daten zum Wechsel sind laut ÜZ verloren.
    - drei Adressen mit zwei Zählern im selben Jahresblatt: einmal zwei Übergabestationen auf einem Grundstück,
      zweimal ein Zähler, der 2024 unter der falschen Hausnummer stand.
    - `meter_changes()` liefert nur die echten Wechsel, `parallel_meters()` die übrigen. Ein Vorher/Nachher über einen
      echten Wechsel vergleicht zwei Geräte, nicht zwei Zustände einer Station.

## Vorher und nachher

- Je Begehung werden **21 Tage davor mit 21 Tagen danach** verglichen. Der Begehungstag selbst gehört zu keinem
  Fenster, weil dort eingegriffen wird.
- Verglichen werden die Mediane von Rücklauf und Durchfluss. Der Median, weil einzelne Zapfspitzen einen Mittelwert
  verziehen.
- Je Fenster braucht es mindestens 200 gemessene Stunden, sonst fällt die Begehung heraus. Auswertbar sind 44 von 58.
- **Warum nicht Winter gegen Winter:** Ein Jahresabstand bringt anderes Wetter und Regression zur Mitte. Stationen mit
  hohem Ausgangswert fallen ohnehin (r = −0,55 zwischen Ausgangswert und Änderung). Im engen Fenster ist beides klein.
  Den Wintervergleich rechnet [Notebook 04](wintervergleich.md) trotzdem, mit Kontrollgruppe und Witterungskorrektur.

## Vierfeldertafel: Zustand vor und nach der Begehung

Die Differenz allein sagt nicht, ob eine Station vorher und nachher schlecht lief. Deshalb bekommt jedes Fenster ein
Urteil: Rücklauf-Median über 50 °C heißt schlechte Auskühlung. Dieselbe Schwelle nutzen das Dashboard und das Merkmal
`rt_above_50_share_loaded`.

| vorher ↓ / nachher → | gut | schlecht |
|---|---|---|
| **gut** | 27 (61 %) | 2 (5 %) |
| **schlecht** | 4 (9 %) | 11 (25 %) |

- **Schlecht zu schlecht ist fachlich der wichtigste Fall.** 11 Stationen wurden begangen und blieben über der
  Schwelle. Entweder wirkte die Maßnahme nicht, oder das dokumentierte Problem war nicht der Grund für die schlechte
  Auskühlung. Diese Stationen sind Kandidaten für eine zweite Begehung.
- Die Tafel ist reine Beschreibung ohne Test. Ob eine Verbesserung ohnehin eingetreten wäre, sagt sie nicht.

## Kontrollgruppe und Differenz-von-Differenzen

Die meisten Begehungen lagen im September, also am Beginn der Heizperiode. Die rohe Änderung enthält diesen Jahresgang.

- **Kontrollgruppe:** 50 Stationen, die nie begangen wurden. Für jedes Begehungsdatum wird ihre mediane
  Rücklaufänderung im selben Fenster berechnet.
- **Differenz-von-Differenzen (DiD):** Änderung der begangenen Station minus Änderung der Kontrollgruppe. Übrig bleibt
  der Teil, den Jahreszeit, Wetter und Netzfahrweise nicht erklären.

| Änderungskategorie | n | Rücklauf roh | Kontrolle | DiD |
|---|---|---|---|---|
| keine | 2 | +5,10 K | −1,85 K | +6,95 K |
| geringe | 3 | +1,50 K | −1,40 K | +3,10 K |
| mittlere | 25 | −1,50 K | −1,00 K | −1,45 K |
| viele | 14 | −3,82 K | −0,50 K | −2,51 K |

- **Monoton über alle vier Stufen:** Je mehr laut Begehungstabelle geändert wurde, desto stärker sinkt der Rücklauf
  gegenüber den unbehandelten Stationen.
- **Nicht signifikant:** Wilcoxon-Test p = 0,30 für „mittlere“ und p = 0,46 für „viele“. „Keine“ und „geringe“ haben
  nur 2 bzw. 3 Fälle.
- **Auswahleffekt:** Begangen wurden vermutlich eher auffällige Stationen, die ohnehin stärker fallen. Den
  allgemeinen Trend fängt die Kontrollgruppe ab, diesen Effekt nicht.
- **Rechenweise:** Die Differenz wird je Station gebildet und erst danach der Median genommen, weil jede Station ihr
  eigenes Datum hat. Deshalb ergibt −3,82 minus −0,50 nicht genau −2,51.

## Ist die Begehung in den Daten sichtbar?

- Öffnet jemand die Station, läuft heißes Wasser durch, ohne Wärme abzugeben: Vorlauf hoch, Rücklauf fast genauso
  hoch, Spreizung nahe null.
- Gesucht wird die kleinste Spreizung im dokumentierten Zeitfenster der Begehung (Uhrzeit von/bis plus eine Stunde).
  Unter 3 K gilt als Treffer.
- **12 von 25** Begehungen mit Uhrzeit und Messdaten zeigen diese Spur (48 %).
- Das ist eine Kontrolle, kein Selbstzweck: Sie zeigt, dass Datum und Zählerzuordnung stimmen. Ohne sie wüsste man
  bei einem ausbleibenden Effekt nicht, ob nichts passiert ist oder ob man am falschen Zähler sucht.
- Grenze: Bei Stationen mit dauernd laufender Zirkulation kommt eine niedrige Spreizung auch im Normalbetrieb vor. Die
  Spur ist eine Bestätigung, kein Beweis.

## Heizzeit-Änderungen als Vorhersage

Bei 8 Stationen steht in der Begehungstabelle, wie die Heizzeit vorher und nachher eingestellt war, z. B. 06:00–22:00
→ 07:00–21:00. Das ist eine Vorhersage, die feststeht, bevor man in die Daten schaut.

- Die Tagesstunden werden geteilt in **weggefallen** (vorher geheizt, jetzt nicht), **unverändert** und
  **dazugekommen**.
- Verglichen wird der typische Durchfluss je Tagesstunde im Winter 2023/24 gegen 2024/25.
- „Unverändert“ ist die Kontrolle: Fallen alle Gruppen gleich, war es das Wetter. Fällt nur „weggefallen“, war es die
  Umstellung.
- **Ergebnis:** Bei 5 Stationen sind Heizstunden weggefallen, bei 4 davon fiel der Durchfluss dort stärker als in den
  unveränderten Stunden. Beispiel 80912156: weggefallene Stunden −40 l/h, unveränderte +4 l/h.
- Bei dazugekommenen Stunden zeigt sich nichts. Eine längere Heizzeit erzwingt kein Heizen, das entscheidet der
  Thermostat im Haus.

## Einzelfall 68956351

- Die Einzelfälle sagen hier mehr als der Mittelwert. Den größten Ausschlag zeigt Zähler 68956351: Ein Ventil stand
  drei Jahre offen (500 bis 950 l/h durchgehend bei 0,1 kW) und wurde am 09.09.2024 geschlossen, der Durchfluss fiel
  über Nacht von 499 auf 0 l/h.
- In der Begehungstabelle steht dazu **keine Maßnahme**. Ein Label, das die deutlichste Reparatur im Datensatz nicht
  kennt, kann kein Modell retten. Das ist der Ausgangspunkt für [Notebook 03](labels.md).

## Was offen bleibt

- **Zählerwechsel und Mehrfachzähler** bei fünf Adressen: Vorher/Nachher kann dort zwei Geräte vergleichen.
- **Zähler 72167783:** Rücklauf nach der Begehung von 18,6 auf 71,0 °C. Inbetriebnahme oder Fehler? Das sollte vor
  jeder Mittelwertbildung geklärt sein. Im Winter danach nimmt die Station praktisch keine Wärme ab
  ([Notebook 04](wintervergleich.md)).
- **Freitexte:** 57 der 66 Begehungen haben eine Notiz mit dem tatsächlichen Befund. Damit lassen sich Fälle
  erklären, in denen Kategorie und Messung auseinandergehen. Ausgewertet werden sie in Notebook 14 und in der
  Handkodierung von [Notebook 03](labels.md#abgleich-mit-der-handkodierung).

## Ausgaben

- `data/processed/begehungen_aufbereitet.csv`: die aufbereitete Begehungstabelle zum Nachschlagen, 66 Zeilen ×
  26 Spalten, Semikolon und `utf-8-sig`, damit Excel sie per Doppelklick richtig öffnet. **Enthält Adressen**, bleibt
  lokal.
- `data/processed/begehungs_wirkung.csv`: eine Zeile je auswertbarer Begehung mit Rohänderung, Kontrollwert und DiD.
  `meter_gewechselt` markiert Fälle, in denen zwei Geräte verglichen werden könnten.
- `data/processed/begehungs_wirkung.json`: Fenstergröße, Mindeststunden, Größe der Kontrollgruppe, DiD je Kategorie.
