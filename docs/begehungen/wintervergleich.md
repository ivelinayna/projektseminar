# Wintervergleich

**Notebook 04:** `notebooks/2_begehungen/04_wintervergleich.ipynb` · **Code:** `src/jahresvergleich.py`,
Winterabgrenzung in `src/season.py`, Tests in `tests/test_jahresvergleich.py`

Die drei Wochen aus [Notebook 02](wirkung.md#vorher-und-nachher) liegen meist am Beginn der Heizperiode und messen den Jahresgang mit.
Dieses Notebook vergleicht deshalb ganze Heizperioden: **Sinkt der Rücklauf einer Station vom Winter vor der Begehung
zum Winter danach?** Beide Fenster decken dieselben Kalendermonate ab, ohne Sommer. Die Witterung geht über
Heizgradstunden ein, Einflüsse des Netzes über eine Kontrollgruppe.

## Warum nicht das volle Jahr

- Ein Vorjahresvergleich über ein langes Fenster scheitert an der Datenlage. Fast alle Zähler enden am 11.07.2025, die
  früheste Begehung war am 26.08.2024. Danach bleiben höchstens 319 Tage.
- Ein volles Jahr danach gibt es nur für 2 der 58 Begehungen. Mit 270 Tagen wären es 27 Begehungen, dann liegt aber der
  halbe Sommer im Fenster.

## Kernwinter als Fenster

- Verglichen wird der **Kernwinter Dezember bis Februar**. Bei einer Begehung zwischen zwei Kernwintern sind es die
  beiden benachbarten, bei einer Begehung im September 2024 also 2023/24 gegen 2024/25.
- Liegt die Begehung selbst in einem Kernwinter, fällt dieser heraus. Das betrifft eine Begehung.
- **Auswertbar sind 45 Begehungen an 44 Zählern.** Von den 58 Begehungen mit Zählernummer und Datum haben 53 eine
  Zeitreihe. Davon sind 7 ausgeschlossen, weil ihre Historie nicht beide Winter deckt, und 1 mit einer Tagesabdeckung
  unter 60 % im Winter danach.
- Geprüft wird die Abdeckung je Tag, nicht je Stunde. Bis etwa November 2022 liefern 45 Zähler nur einen Wert je Tag
  (siehe [Zählerdaten](../datengrundlage/zaehlerdaten.md#zeitraum-und-abdeckung)). Auf dem Stundenraster sähe ein
  solcher Monat fast leer aus, obwohl kein Tag fehlt. In den verglichenen Wintern ab 2023/24 betrifft das keinen Fall.

## Vorher und nachher

- **Rücklauf-Median: −1,2 K** (n = 45, Wilcoxon p = 0,09).
- Rohe Energie und Durchfluss steigen dagegen (+632 kWh, p = 0,002; +11 l/h, p = 0,010). Der Grund: Der Winter danach
  war rund **21 % kälter** (Heizgradstunden im Median 27.366 gegen 22.619 Kh). Heizgradstunden summieren, wie weit die
  Außentemperatur unter der Heizgrenze von 15 °C liegt.
- Auf Heizgradstunden normiert sinkt die Energie (`energie_je_kh`).
- 43 der 45 Fälle liegen im Winterpaar 2023/24 gegen 2024/25. Die Schieflage im Wetter lässt sich nicht herausmitteln,
  deshalb zählt die Kontrollgruppe mehr als der reine Vorher/Nachher-Test.

## Kontrollgruppe und Diff-in-Diff

- **Kontrollgruppe:** 42 Zähler ohne datierte Begehung (5 davon mit Begehung ohne Datum), mit derselben Winterlogik und
  demselben Datum, also bei gleicher Witterung und Netzfahrweise.
- Eine Kontrollgruppe haben 43 der 45 Begehungen. Die beiden vom September 2025 haben keine, weil den Winter 2025/26
  nur die Nachlieferungszähler abdecken.
- Bei diesen 43 liegt die Kontrollgruppe im Median bei +0,4 K, die begangenen Stationen bei −1,6 K.
  **Diff-in-Diff: −2,0 K** (n = 43, p ≈ 0,008).
- Das ist der belastbarste Teil der Auswertung. Auch die witterungsnormierte Energie sinkt gegenüber der
  Kontrollgruppe (−0,014 kWh/Kh, p ≈ 0,005).
- Je Änderungskategorie: mittlere −1,73 K (n = 24), viele −3,88 K (n = 13). „Geringe“ und „keine“ sind zu dünn
  besetzt.
- Keine Kausalaussage, weil die begangenen Stationen nicht zufällig ausgewählt wurden. Wer vorher auffällig war, hat
  mehr Spielraum nach unten.

## Vierfeldertafel

Wie in [Notebook 02](wirkung.md#vierfeldertafel-zustand-vor-und-nach-der-begehung): Rücklauf-Median über 50 °C heißt
schlecht.

| vorher ↓ / nachher → | gut | schlecht |
|---|---|---|
| **gut** | 27 (60 %) | 4 (9 %) |
| **schlecht** | 5 (11 %) | 9 (20 %) |

Die 9 Stationen, die in beiden Wintern über 50 °C lagen, sind Kandidaten für eine erneute Prüfung. Zwei davon sanken
deutlich (−14,8 K und −21,6 K), blieben aber über der Schwelle.

## Gegenproben

- **Abgrenzung:** September bis April statt Kernwinter ergibt −0,9 K (n = 35, p = 0,07). Mit strenger Abdeckung je
  Stunde bleiben alle 45 Fälle drin.
- **Früherer Jahresvergleich:** Der kalendergleiche Vergleich über 270 Tage kam mit 27 Fällen auf −1,7 K und einen
  Diff-in-Diff von −1,5 K (n = 25), der über 180 Tage mit 35 Fällen auf −1,1 K. Der Wintervergleich hat mehr Fälle.
  Vorher gegen nachher fällt der Rückgang etwas kleiner aus (−1,2 statt −1,7 K, p = 0,09 statt 0,04), im Diff-in-Diff
  größer (−2,0 statt −1,5 K).
- **Ohne Nachlieferung:** Schneidet man die fünf
  [Nachlieferungszähler](../datengrundlage/zaehlerdaten.md#lieferungen) am 11.07.2025 ab, fallen zwei Begehungen vom
  September 2025 weg. Ergebnis: −1,6 K (n = 43, p ≈ 0,03). Beide Nachlieferungsfälle haben einen steigenden Rücklauf.
  72167783 nimmt im Winter 2025/26 praktisch keine Wärme ab, der Rücklauf liegt auf Vorlaufniveau. Das passt zu einem
  Betriebszustand, nicht zu einer Wirkung der Begehung (siehe
  [Qualität und Einschränkungen](../datengrundlage/qualitaet.md#zahlerdaten)).

## Einordnung

- **Belastbar:** Der Rückgang bleibt nach Abzug der Kontrollgruppe und hängt kaum an der Winterabgrenzung. Das ist
  konsistent mit einer Wirkung der Begehungen.
- **Schwach:** Fast alle Fälle liegen in einem Winterpaar mit deutlich kälterem Winter danach. Die
  Änderungskategorien sind zu dünn besetzt, die Kontrollgruppe ist nicht zufällig.
- **Offen:** Den Winter 2025/26 gibt es nur für die fünf Nachlieferungszähler.

## Ausgaben

`data/processed/wintervergleich_kernwinter.csv` und `wintervergleich_erweitert.csv`, je Begehung Winter davor gegen
Winter danach. Nur Zählernummern, keine Adressen.
