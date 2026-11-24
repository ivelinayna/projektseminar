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

- Der Loader (`src/load_begehungen.py`) ordnet jede Begehung über `Zuordnung.xlsx` einem Zähler zu (siehe
  [Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md#zahler-und-adresse-zuordnungxlsx)).
- Umfang, Datum, Uhrzeit und Änderungskategorie stehen unter [Begehungen](../datengrundlage/begehungen.md). Für diese
  Auswertung neu ist die Änderungskategorie. Die frühere Tabelle `inspections_tidy.csv` hatte sie nicht übernommen.
- Zählertausch und Adressen mit zwei Zählern trennt der Loader (siehe
  [Zählertausch und doppelte Einträge](../datengrundlage/netz_und_zuordnung.md#zahlertausch-und-doppelte-eintrage)):
  `meter_changes()` liefert nur die echten Wechsel, `parallel_meters()` die übrigen. Keine der 44 ausgewerteten
  Begehungen vergleicht dabei zwei Geräte.

## Vorher und nachher

- Je Begehung werden **21 Tage davor mit 21 Tagen danach** verglichen. Der Begehungstag selbst gehört zu keinem
  Fenster, weil dort eingegriffen wird.
- Verglichen werden die Mediane von Rücklauf und Durchfluss. Der Median, weil einzelne Zapfspitzen einen Mittelwert
  verziehen.
- Je Fenster braucht es mindestens 200 gemessene Stunden, sonst fällt die Begehung heraus. Auswertbar sind 44 von 58.
- **Warum ein kurzes Fenster:** Die Idee war, dass sich das Wetter in drei Wochen kaum ändert. Das hat am Ende wenig
  gebracht. Die meisten Begehungen lagen am Beginn der Heizperiode, nachher war es im Median 5 K kälter (13,3 gegen
  18,4 °C). Auch die Regression zur Mitte bleibt: Stationen mit hohem Ausgangswert fallen ohnehin (r = −0,61 zwischen
  Ausgangswert und Änderung, im Winter −0,55). Den Jahresgang fängt erst die
  [Kontrollgruppe](#kontrollgruppe-und-differenz-von-differenzen) ab. Ganze Winter mit Witterungskorrektur vergleicht
  [Notebook 04](wintervergleich.md).

## Vierfeldertafel: Zustand vor und nach der Begehung

Die Differenz allein sagt nicht, ob eine Station vorher und nachher schlecht lief. Deshalb bekommt jedes Fenster ein
Urteil: Rücklauf-Median über 50 °C heißt schlechte Auskühlung. Dieselbe Schwelle nutzt das Merkmal
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

- **Kontrollgruppe:** 37 Stationen, die nie begangen wurden. Stationen mit Begehung fallen ganz heraus, auch wenn die
  Begehung kein Datum hat oder hier nicht auswertbar ist. Für jedes Begehungsdatum wird die mediane Rücklaufänderung
  der Kontrollgruppe im selben Fenster berechnet.
- **Differenz-von-Differenzen (DiD):** Änderung der begangenen Station minus Änderung der Kontrollgruppe. Übrig bleibt
  der Teil, den Jahreszeit, Wetter und Netzfahrweise nicht erklären.

| Änderungskategorie | n | Rücklauf roh | Kontrolle | DiD |
|---|---|---|---|---|
| keine | 2 | +5,10 K | −1,85 K | +6,95 K |
| geringe | 3 | +1,50 K | −1,40 K | +3,10 K |
| mittlere | 25 | −1,50 K | −0,90 K | −1,56 K |
| viele | 14 | −3,82 K | −0,55 K | −3,05 K |

- **Monoton über alle vier Stufen:** Je mehr laut Begehungstabelle geändert wurde, desto stärker sinkt der Rücklauf
  gegenüber den unbehandelten Stationen.
- **Nicht signifikant:** Wilcoxon-Test p = 0,25 für „mittlere“ und p = 0,19 für „viele“. „Keine“ und „geringe“ haben
  nur 2 bzw. 3 Fälle.
- **Ohne Kontrollwert:** Für die zwei Begehungen vom September 2025 gibt es keinen DiD. Nach dem 11.07.2025 liefern
  nur noch fünf Zähler Daten, und alle fünf wurden begangen. Der DiD bei „mittlere“ und „viele“ stützt sich deshalb
  auf 24 und 13 Begehungen.
- **Auswahleffekt:** Begangen wurden vermutlich eher auffällige Stationen, die ohnehin stärker fallen. Den
  allgemeinen Trend fängt die Kontrollgruppe ab, diesen Effekt nicht.
- **Rechenweise:** Die Differenz wird je Station gebildet und erst danach der Median genommen, weil jede Station ihr
  eigenes Datum hat. Deshalb ergibt −3,82 minus −0,55 nicht genau −3,05.

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
- „Unverändert“ ist die Kontrolle: Fallen alle Gruppen gleich, passt das zum Wetter. Fällt nur „weggefallen“, passt
  das zur Umstellung.
- **Ergebnis:** Bei 5 Stationen sind Heizstunden weggefallen, bei 4 davon fiel der Durchfluss dort stärker als in den
  unveränderten Stunden. Beispiel 80912156: weggefallene Stunden −40 l/h, unveränderte +4 l/h.
- Bei dazugekommenen Stunden zeigt sich nichts. Eine längere Heizzeit erzwingt kein Heizen, das entscheidet der
  Thermostat im Haus.

## Einzelfall 68956351

- Im Mittel ist die Wirkung klein, einzelne Fälle sind aber deutlich. Den größten Ausschlag im Durchfluss zeigt Zähler
  68956351: Seit Beginn der Daten im November 2021 flossen durchgehend 500 bis 950 l/h, bei kaum Wärmeabgabe. Bei der
  Begehung am 09.09.2024 wurden Ventil und Stellmotor getauscht, noch am Nachmittag fiel der Durchfluss auf nahezu
  0 l/h.
- In den Maßnahmen-Spalten der Begehungstabelle ist dazu nichts angekreuzt, der Tausch steht nur im Freitext. Das alte
  Label `n_actions > 0` kennt damit ausgerechnet die deutlichste Reparatur im Datensatz nicht. Das ist der
  Ausgangspunkt für [Notebook 03](labels.md).

## Was offen bleibt

- **Zähler 72167783:** Nach der Begehung im September 2025 stieg der Rücklauf von 18,6 auf 71,0 °C und der Durchfluss
  von 0 auf 134 l/h, ohne dass die Station Wärme abnimmt. Was dabei passiert ist, kann nur die ÜZ klären (siehe
  [Offene Fragen an die ÜZ](../grenzen.md#offene-fragen-an-die-uz)). Was über die Station bekannt ist, steht unter
  [Qualität und Einschränkungen](../datengrundlage/qualitaet.md#zahlerdaten).
- **Freitexte:** 57 der 65 Begehungen haben eine Notiz des Monteurs. Damit lassen sich Fälle erklären, in denen
  Kategorie und Messung auseinandergehen. Wie die Notizen kodiert sind, steht unter
  [Begehungen](../datengrundlage/begehungen.md#freitexte). Ausgewertet werden sie in Notebook 14 und in der
  Handkodierung von [Notebook 03](labels.md#abgleich-mit-der-handkodierung).

## Ausgaben

- `data/processed/begehungen_aufbereitet.csv`: die aufbereitete Begehungstabelle zum Nachschlagen, 66 Zeilen ×
  26 Spalten, Semikolon und `utf-8-sig`, damit Excel sie per Doppelklick richtig öffnet. **Enthält Adressen**, bleibt
  lokal.
- `data/processed/begehungs_wirkung.csv`: eine Zeile je auswertbarer Begehung mit Rohänderung, Kontrollwert und DiD.
  `meter_gewechselt` markiert Fälle, in denen zwei Geräte verglichen werden könnten. **Enthält Adressen**, bleibt
  lokal.
- `data/processed/begehungs_wirkung.json`: Fenstergröße, Mindeststunden, Größe der Kontrollgruppe, DiD je Kategorie.
