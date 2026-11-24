# Normalverhaltensmodell

**Notebook 18:** `notebooks/5_monitoring/18_normalverhalten.ipynb` · **Code:** keine Abhängigkeit zu `src/`. Teile aus
`src/load_begehungen.py` und `src/befundcodes.py` stehen als Kopie im Notebook.

Das Notebook fragt, ob sich eine Veränderung an einer Station früh und wetterbereinigt aus Tageswerten erkennen lässt,
ohne Fehlerlabel. Jede Station lernt aus ihrem ersten Jahr, wie sie sich bei welcher Außentemperatur normalerweise
verhält. Weicht sie mehrere Tage davon ab, gibt es einen Alarm. Das ist **Früherkennung, keine Prognose**: Das Modell
sagt „die Station läuft seit einigen Tagen anders als sonst bei diesem Wetter“, nicht „sie fällt in vier Wochen aus“.

Grundlage sind die Tageswerte `hast_tage.csv` aus [Notebook 10](../clustering/tagescluster.md). Dieselbe Idee setzt
[Notebook 20](tagesmonitor.md) als Modul in `src/tagesmonitor.py` um, für den Betrieb und das Endmodell.

## Warum dieser Ansatz

| Befund | Notebook | Folge hier |
|---|---|---|
| Die Begehungslabels taugen nicht, Freitext-Labels sind zu wenige | 02, 03, 14 | Zielgröße ist ein Messwert, kein Label |
| Stationen bilden keine klaren Typen | 07 bis 10 | jede Station wird mit sich selbst verglichen |
| Begehungen verschieben das Niveau der Performance, nicht die Form der Kennlinie | 11, 12 | das Modell schaut auf das Niveau in kWh/m³ |
| Vorher/Nachher ohne Wetterbereinigung vermischt Jahreszeit und Wirkung | 02, 05 | die Erwartung hängt von der Außentemperatur ab |
| Stundenwerte sind Momentaufnahmen | 10 | Tageswerte aus Zählerständen |

## Tageswerte und Kanäle

- Zwei **Kanäle**, also überwachte Messgrößen: **Abkühlung** in kWh/m³ und **Wassermenge** als Tagesvolumen. Beide
  kommen aus den Zählerständen (Stand um Mitternacht minus Stand der Mitternacht davor).
- **Nur Heiztage** mit Tagesmittel unter 15 °C. Dort hängt der Betrieb stark an der Außentemperatur, und genau diesen
  Einfluss rechnet das Modell heraus. Im Sommer hängt kWh/m³ an Warmwasser und Zirkulation. Der Preis: Fehler, die nur
  im Sommer auffallen, etwa Dauerzirkulation, sieht das Modell nicht.
- Die Markierung „wenige Stundenwerte“ aus Notebook 10 stört hier nicht, weil nur Zählerstände zählen. Das betrifft vor
  allem die Tageswert-Phase bis November 2022.
- Die Wassermenge wird logarithmiert. Aus „0,5 m³ mehr“ wird so „10 % mehr“, große und kleine Häuser werden
  vergleichbar.
- Ergebnis: 56.754 Heiztage, davon 54.774 verwendbar, an 93 Stationen vom 02.11.2021 bis 09.06.2025.

## Referenzzeitraum

- Jede Station lernt aus ihrem **ersten Jahr** mit verwendbaren Heiztagen. Ein Jahr enthält kalte und milde Tage, die
  Kennlinie deckt also den ganzen Temperaturbereich ab.
- Die Referenz endet spätestens 14 Tage vor der ersten Begehung, sonst wäre deren Wirkung unsichtbar. Das ist kein
  Datenleck, denn die ÜZ weiß im Betrieb, wann sie vor Ort war.
- **Referenz heißt nicht gesund.** Lief eine Station schon im ersten Jahr schlecht, ist das ihr Normalzustand. Das
  betrifft den Ventilfall 68956351. Dauerhaft schlechte Stationen zeigt erst der Vergleich mit der Flotte (siehe
  unten).
- Überwacht werden Stationen mit mindestens 60 Referenztagen, 8 K Temperaturspanne und Heiztagen danach.
- **89 von 93 Stationen** werden überwacht. Die Referenz endet bei 69 nach einem Jahr und bei 20 vor einer Begehung. Im
  Median sind es 228 Referenztage, 19,9 K Spanne und 241 überwachte Heiztage.

## Kennlinie je Station und Kanal

| Kanal | Form | Wie |
|---|---|---|
| Abkühlung | Gerade | Theil-Sen-Gerade über der Tagesmitteltemperatur, also der Median der Steigungen aller Tagespaare |
| Wassermenge | Klassenkennlinie | Median der Referenztage je 2-K-Temperaturklasse, mindestens 8 Tage je Klasse |

- Die Abkühlung hängt annähernd linear an der Temperatur. Die Wassermenge ist gekrümmt: steil bei Kälte, flach bei
  mildem Wetter wegen des Sockels aus Warmwasser und Zirkulation. Eine Gerade durch eine krumme Kurve erzeugt in
  Kälteperioden Scheinalarme in eine Richtung.
- **Streuung** je Station über den MAD (Median der Abstände zum Median, mal 1,4826). Eine ruhige Station schlägt bei
  kleineren Abweichungen an als eine unruhige.
- **Autokorrelation:** Folgetage hängen zusammen, weil Gebäude träge sind und Wetterlagen anhalten (im Median φ = 0,68
  bei der Abkühlung und 0,59 bei der Wassermenge). Der CUSUM zählt jeden Tag als neue Information. Deshalb wird die
  Streuung mit √((1 + φ) / (1 − φ)) vergrößert, im Median um den Faktor 2,3 bzw. 2,0.

Was die gelernten Kennlinien zeigen:

- **Abkühlung:** Steigung im Median −0,32 kWh/m³ je Kelvin wärmer, etwa halb so steil wie die −0,6 bis −0,7 über alle
  Stationen in [Notebook 05](../begehungen/performance.md). Typische Streuung 2,46 kWh/m³.
- **Wassermenge:** bei 0 °C im Median 85 % mehr Wasser als bei 10 °C, bei 92 % der Stationen ist der Wert bei Kälte
  höher. Typische Tagesstreuung rund 22 %.

## Wie gut ist die Vorhersage?

Geprüft wird auf Tagen, die das Modell nicht kannte: die ersten bis zu 120 Heiztage nach der Referenz, vor jeder
Begehung. Verglichen wird mit einem naiven Modell ohne Temperatur (immer der Median der Referenz). Skill = 1 − Fehler
Modell / Fehler naiv.

| Kanal | Stationen | Skill (Median) | Anteil Stationen mit positivem Skill |
|---|---|---|---|
| Abkühlung | 67 | 0,02 | 55 % |
| Wassermenge | 67 | 0,26 | 85 % |

Bei der Wassermenge verbessert die Temperatur die Vorhersage klar, bei der Abkühlung praktisch nicht. Das passt zur
flachen Steigung.

## Alarm mit dem CUSUM

Ein einzelner auffälliger Tag ist meist Zufall. Interessant ist, wenn eine Station mehrere Tage in dieselbe Richtung
abweicht.

- **z-Wert** = (gemessen minus erwartet) / Streuung.
- **CUSUM** (kumulierte Summe, Page 1954) als Kontostand: Jeden Tag wird der z-Wert eingezahlt und eine Gebühr
  k = 0,5 abgezogen. Das Konto fällt nicht unter null. Über der Schwelle h = 5 gibt es einen Alarm. Zwei Konten, für
  Abweichungen nach oben und nach unten.
- Liegt eine Station jeden Tag eine Streuung höher, alarmiert sie nach rund 10 Tagen, bei zwei Streuungen nach rund 4.
  Ein Ventilfall mit z um +20 alarmiert am ersten Tag.
- Ein neuer Alarm in dieselbe Richtung kommt erst, wenn das Konto zwischendurch bei null war. Der Deckel bei 10 sorgt
  dafür, dass das Konto nach der Rückkehr zum Normalzustand nach höchstens 20 Heiztagen wieder bei null ist.

**Der bekannte Fall 68956351:** Abkühlungsalarm „höher“ am 11.09.2024, zwei Tage nach dem Tausch des Stellmotors. Die
Wassermenge meldet um die Begehung nichts. Vor der Reparatur ist die Station nicht ruhig: 4 der 5 Alarme liegen davor.
Der Fall wird also gefunden, aber nur in einem Kanal.

**Alle Stationen:** 89 Stationen mit zusammen 133 Stationsjahren erzeugen 479 Alarme, also 3,6 je Station und Jahr. Das
ist weniger als beim Kennlinienmonitor aus [Notebook 13](../stationsbilder/index.md) mit knapp 5, aber deutlich mehr als die
Theorie für unabhängige Tage erwarten lässt (etwa einer alle zwei bis drei Jahre je Kanal). Bis zum Alarm vergehen im
Median 6,5 bis 10 Heiztage.

## Sieht das Modell die Begehungen?

**Wirkung (Differenz-von-Differenzen auf Residuen):** Median der Residuen der ersten 30 Heiztage nach minus der letzten
30 vor der Begehung, abzüglich derselben Rechnung bei Stationen ohne Begehung. Das Modell rechnet den Unterschied der
Temperatur heraus, die Kontrollgruppe den Rest. 43 auswertbare Fälle je Kanal, im Median 48 Kontrollstationen je Fall.

| Kanal | Diff-in-Diff (Median) | in Richtung Verbesserung | p (Wilcoxon) |
|---|---|---|---|
| Abkühlung | +1,11 kWh/m³ | 56 % | 0,20 |
| Wassermenge | −11,2 % | 65 % | 0,026 |
| Abkühlung, mechanischer Befund (15 Fälle) | +1,86 kWh/m³ | 73 % | |
| Wassermenge, mechanischer Befund (15 Fälle) | −13,8 % | 80 % | |

Mechanisch heißt: Der Freitext nennt Schmutzfänger, Ventil oder Stellantrieb, Pumpe, Zirkulation oder Hydraulik. Die
Kontrollstationen ziehen nach dem Termin im Median 14,6 % mehr Wasser, die begangenen kaum mehr.

**Treffer der Alarme:** mindestens ein Alarm im Fenster 7 Tage vor bis 60 Tage nach der Begehung, verglichen mit dem
Anteil der Kontrollstationen mit Alarm im selben Fenster. Hebel = Trefferquote / Kontrollquote.

| Prüfung | Treffer | Quote | Kontrollquote | Hebel | p (einseitig) |
|---|---|---|---|---|---|
| Abkühlung | 22 von 43 | 0,51 | 0,29 | 1,77 | 0,002 |
| Wassermenge | 23 von 43 | 0,53 | 0,36 | 1,49 | 0,014 |
| einer der beiden | 30 von 43 | 0,70 | 0,53 | 1,33 | 0,017 |

- Die Wassermenge-Alarme kommen im Median 11 Tage nach der Begehung, 83 % davon in Richtung Verbesserung. Die
  Abkühlungs-Alarme kommen im Median 22 Tage danach, aber nur 41 % in Richtung Verbesserung.
- Bei mechanischen Befunden trifft nur die Wassermenge (9 von 14, p = 0,039), die Abkühlung nicht (5 von 14). Das passt
  nur teilweise zur Wirkung oben, wo die mechanischen Befunde in beiden Kanälen stärker wirken.

## Station gegen Flotte

Die Lücke des Modells: Eine Station, die schon im ersten Jahr schlecht lief, alarmiert nie. Als Ergänzung wird die
Abkühlung jeder Station bei einer Normtemperatur von 5 °C aus ihrer Kennlinie abgelesen. So sind Stationen
vergleichbar, auch wenn ihre Daten aus verschiedenen Wintern stammen.

- Flottenmedian aktuell 26,1 kWh/m³ bei 5 °C, das entspricht 22,7 K Spreizung.
- Die zehn schwächsten Stationen liegen 12,2 bis 18,4 K Spreizung unter dem Flottenmedian, fünf davon wurden begangen.
- Bei 80912182, 72167793 und 72135453 hat sich seit der Referenz wenig geändert: dauerhaft schwache Stationen, die der
  Alarm nicht findet. Stark verschlechtert haben sich 68956360 und 80912173.
- Gegenprobe: Stationen mit vielen Tagen im schlechtesten Tagestyp aus Notebook 10 haben eine niedrige Normkennzahl
  (Spearman −0,64, n = 84). Beide messen weitgehend dasselbe.

## Zusatz: Spielt das Leitungsnetz eine Rolle?

Die Abschnitte 15 und 16 des Notebooks sind Vortests für das GNN aus Notebook 39 und brauchen die Netztabellen aus
Notebook 31.

- Bei Abkühlung und Wassermenge weichen direkte Nachbarn im Netz nicht stärker gemeinsam ab als zufällige Paare
  (p = 0,17 und 0,46).
- Nur der Vorlauf schwankt bei Nachbarn gemeinsam (r = 0,13 gegen 0,04 bei Zufall, p = 0,004).
- Die Lage im Netz erklärt nicht, warum manche Stationen dauerhaft schlechter abkühlen.

Was daraus für das GNN folgt, steht unter [GNN: Hilft das Netz?](../nicht_getragen/gnn.md).

## Einordnung

- **Belastbar:** Die Wassermenge ist der brauchbare Kanal. Die Temperatur verbessert ihre Vorhersage bei 85 % der
  Stationen, und 83 % ihrer Alarme nach Begehungen zeigen in Richtung Verbesserung. Die Prüfung nutzt eine
  Kontrollgruppe am selben Datum, der allgemeine Herbsteffekt ist damit berücksichtigt. Die Normkennzahl bei 5 °C
  liefert eine Liste dauerhaft schwacher Stationen, die der Alarm nicht findet.
- **Schwach:** Bei der Abkühlung bringt die Kennlinie auf neuen Tagen kaum etwas, und nur 41 % ihrer Treffer zeigen in
  Richtung Verbesserung. Der hohe Hebel von 1,77 ist deshalb vorsichtig zu lesen. Die Fälle sind wenige und nicht
  unabhängig, die p-Werte eher zu optimistisch. Die Alarmrate liegt deutlich über der Theorie, die Autokorrelation ist
  nur näherungsweise korrigiert.
- **Gesetzt, nicht hergeleitet:** k = 0,5 und h = 5 als Lehrbuchwerte, Referenz 365 Tage, mindestens 60 Heiztage und
  8 K Spanne, Heizgrenze 15 °C, Treffer-Fenster 7 bis 60 Tage, Normtemperatur 5 °C.
- **Offen:** Ob sich die Alarme jeden Herbst häufen, ist nur im Bild zu sehen, nicht in Zahlen ausgewertet. Ob die
  Gerade für die Abkühlung passt, ebenso. Ideen für eine Weiterentwicklung nennt das Notebook selbst: Temperatur über
  2 bis 3 Tage mitteln, Vorlauf als Einflussgröße, ein eigener Sommerkanal für den Nachtfluss und eine neue Referenz
  nach einem bestätigten Eingriff.

## Ausgaben

Alles in `data/processed/`, nur Zählernummern:

| Datei | Inhalt |
|---|---|
| `normalmodell_stationen.csv` | je Station Referenz, Status, Form, Steigung, Streuung, Korrekturfaktor, Normkennzahlen, Alarme |
| `normalmodell_tage.csv` | je Station, Kanal und Heiztag gemessen, erwartet, Residuum, z-Wert und CUSUM-Konten |
| `normalmodell_alarme.csv` | je Alarm Station, Kanal, Datum, Richtung und geschätzter Beginn |
| `normalmodell_wirkung.csv` | je Begehung und Kanal die Differenz-von-Differenzen |
| `normalmodell_treffer.csv` | je Begehung und Prüfung Treffer und Kontrollquote |
| `normalmodell.json` | alle Parameter des Laufs und die wichtigsten Kennzahlen |

Die Ausgaben nutzen die Notebooks 30 und 34.
