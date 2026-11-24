# Haus oder Netz

Ohne Netz blieb offen, ob eine Abweichung am einzelnen Haus oder am Netz liegt: Es gab kein Netz-Merkmal in
den Daten. Der Rohrbaum erlaubt den Vergleich eines Hauses mit seinen Nachbarn. Weichen alle gemeinsam ab, spricht das
für das Netz. Weicht nur ein Haus ab, spricht es für das Haus. Getestet wird das in Notebook 32.

## Vorgehen

1. Je Haus ein Normalwert der Spreizung aus Außentemperatur, deren Quadrat, Uhrzeit und Wochentag (Ridge-Regression, nur
   Stunden mit Durchfluss, nur Daten vor dem 1.9.2024, damit keine Messung nach einer Begehung eingeht).
2. Die Abweichung wird zu Tageswerten gemittelt und je Haus robust standardisiert (Median und MAD, begrenzt auf ±6).
3. Nachbarn sind die 4 Häuser mit dem kürzesten Rohrweg im Baum.
4. Verglichen wird die mittlere Korrelation der Tageswerte mit den Nachbarn gegen 200 Ziehungen mit zufälligen Häusern.
5. Danach wird das Netzsignal herausgerechnet: je Tag der Median aller anderen Häuser. Mit dem Rest wird der Test
   wiederholt.

## Ergebnis

| Prüfung | Korrelation |
|---|---|
| alle Häuser untereinander | etwa 0,22 |
| Rohrbaum-Nachbarn gegen zufällige Häuser | 0,231 gegen 0,223 (95-%-Grenze 0,238) |
| nach Abzug des Netzsignals | 0,015 gegen −0,001 (95-%-Grenze 0,014) |

- Die Häuser schwanken gemeinsam. Nachbarn im Baum teilen nicht mehr als zufällige Häuser. Ein Effekt je Strang ist
  nicht nachweisbar.
- Nach dem Abzug bleibt ein winziger Rest. 0,015 erklärt rechnerisch etwa 0,02 % der Streuung.

## Gegenproben

 Weil ein Negativbefund immer auch an der Messung liegen kann, wurde auf mehreren Wegen nachgeprüft:

| Gegenprobe | Ergebnis |
|---|---|
| Nachbarn aus der Kantendatei (2, 3 und 4 Kanten Abstand) statt aus dem Rohrbaum | nach Netzabzug 0,034, 0,014, 0,004 gegen etwa 0: verschwindet mit dem Abstand |
| Häuser unter demselben Abzweig (11 Gruppen, meist Paare) | 0,122 gegen 0,002 (95-%-Grenze 0,072); die Korrelationen der Paare streuen von −0,11 bis 0,45, der Rest kommt von wenigen Paaren |
| Richtung: folgt das untere Haus dem oberen mit 1 bis 3 Stunden Versatz | 33 Paare, 52 % positiv bei 50 % Zufall, p = 0,66 |
| kurze Ereignisse (mindestens 3 Stunden in Folge mit \|z\| > 3) | keine Netztage, Nachbarn haben am selben Tag etwas häufiger ein Ereignis (3,0 % gegen 2,1 %), auf sehr kleinem Niveau |

Die Zahl „Netzanteil“ aus dem ersten Versuch (im Mittel gut 70 % der Abweichung) ist nicht aussagekräftig. Der Betrag des
Nachbarmittels bleibt auch bei unabhängigen Nachbarn über null. Aussagekräftig ist nur der Vergleich mit zufälligen
Häusern. Der Ereignistest kann außerdem Netzereignisse nicht sehen, weil das Netzsignal vorher herausgerechnet wurde.
Dass er keine Netztage findet, ist deshalb kein Befund.

## Graph aus den Daten lernen

Bisher wurde geprüft, ob Rohrbaum-Nachbarn ähnliche Messwerte haben. Hier wird umgekehrt aus den Stundenwerten gelernt,
welche Häuser zusammenhängen.

- Vom Stundenrest der Spreizung werden Netz-Median, die 3 stärksten gemeinsamen Muster (SVD) und die Trägheit jeder Reihe
  abgezogen.
- Folgt Haus b dem Haus a mit 1 bis 3 Stunden Versatz, entsteht eine Kante a → b. Als Kante gilt nur, was stärker ist als
  99,5 % von 200 um ganze Tage verschobenen Reihen.
- Abgleich: Verbinden die gelernten Kanten Rohrbaum-Nachbarn öfter als Zufall? Zeigen sie im Baum abwärts?

| Ergebnis | Wert |
|---|---|
| gelernte Kanten | 131, zufällig erwartet etwa 29 |
| davon zwischen Rohrbaum-Nachbarn | 9 % (Zufall 6 %) |
| davon zwischen Nachbarn der Kantendatei | 9 % (Zufall 4 %) |
| Kanten mit bekanntem Oben und Unten | 3, die Richtung ist nicht prüfbar |
| meiste Kanten an einem Haus | 24 |

Die Daten enthalten also zeitversetzte Zusammenhänge. Sie sind aber überwiegend nicht das Rohrnetz. Wenige Häuser
tragen sehr viele Kanten, eher ein Störer oder ein Messproblem als ein Strang. Als Grundlage für ein Graph-Modell taugt
der gelernte Graph nicht.

Eine Vorsichtsmaßnahme dabei: Die Zufallsgrenze verschiebt die Reihen nur um ganze Tage. Würden sie um beliebig viele
Stunden verschoben, ginge der gemeinsame Tagesrhythmus in der Zufallsvariante verloren, und die Grenze wäre zu locker.


