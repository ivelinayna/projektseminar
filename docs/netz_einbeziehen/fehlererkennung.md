# Fehlererkennung mit Netz-Merkmalen

Die Begehungen liefern Labels je Zähler. Geprüft wird mit der AUC (0,5 = Zufall, 1 = perfekte Trennung) und einem
90-%-Bereich aus 400 Bootstrap-Ziehungen. Bei 9 bis 30 positiven Fällen je Label sind Unterschiede unter etwa 0,1
Rauschen.

- **Sommernacht-Durchfluss:** Fließt im Sommer nachts (Juni bis August 2024, 0 bis 4 Uhr) Wasser, passt das zu einem
  Ventil, das nicht schließt. Das trennt Ventil gut (AUC 0,84 bis 0,87), für die anderen Labels gibt es kein Signal.
- **Andere Zielgrößen:** Vorlauf, Rücklauf und Spreizung, jeweils als Abweichung, nach Netzabzug und mit Vorzeichen
  (dauerhaft über oder unter dem Netz). Am besten schneidet bei Ventil die Spreizung dauerhaft über dem Netz ab (0,88).
  Sonst liegen die Werte zwischen 0,5 und 0,66 mit breitem Bereich.
- **Vorlauf-Defizit:** Der Vorlauf sinkt im Januar und Februar um 1,21 K je 100 m Rohrweg. Wer weniger bekommt als für
  seine Lage erwartet, liegt unter der Geraden. Dieses Merkmal trennt kein Label in der erwarteten Richtung. Bei Ventil
  liegt es sogar bei 0,13, das heißt, Ventil-Häuser haben eher einen zu warmen Vorlauf.

## Basislinie

 Eine logistische Regression mit stark gebremsten Gewichten, geprüft mit Kreuzvalidierung nach Straßen
(eine Straße nie zugleich in Training und Test), 20-mal wiederholt. Nur Labels mit mindestens 8 positiven und 8
negativen Fällen. Vier Varianten:

| Variante | Merkmale |
|---|---|
| Nachtdurchfluss allein | keine, nur eine Schwelle |
| Nachtdurchfluss | Median und Anteil aktiver Nachtstunden |
| Haus-Merkmale | Nachtdurchfluss, Spreizung, Vorlauf und Rücklauf gegen das Netz, Vorlauf-Defizit |
| Haus- und Graph-Merkmale | zusätzlich dieselben Werte der 4 Nachbarn und die Differenz Haus minus Nachbarn |

- Bei Ventil erreicht der Nachtdurchfluss allein 0,87, mit allen Haus-Merkmalen 0,89, mit Graph-Merkmalen 0,85. Die
  Graph-Merkmale bringen nichts dazu.
- Bei den anderen Labels liegt die AUC höchstens bei 0,68 (Dämmung), teils deutlich unter 0,5. Werte unter 0,5 in der
  Kreuzvalidierung sind Überanpassung ohne Signal und kein Signal in Gegenrichtung.
- Die Koeffizienten bei Ventil zeigen in die erwartete Richtung: mehr Nachtdurchfluss spricht für Ventil.

Gerechnet wurden mehrere Zielgrößen gegen mehrere Labels. Die jeweils besten zu zeigen überschätzt. Bei Ventil spricht
für ein echtes Signal, dass mehrere unabhängige Größen in dieselbe Richtung zeigen.

## GNN

Ein Graph-Modell (GNN) auf dem Rohrbaum soll zeigen, ob das Netz das Normalverhaltensmodell aus Notebook 18 verbessert.
Das Ergebnis passt zu den Tests unter [Haus oder Netz](haus_oder_netz.md): Der Beitrag des Netzes ist
je Station nicht signifikant. Aufbau, Zahlen und Gründe stehen unter [GNN: Hilft das Netz?](../weitere_versuche/gnn.md).

Der Export `daten_cache/gnn_daten.npz` aus Notebook 32 enthält 79 Häuser und 152 Streckenknoten, zusammen 231 Knoten und
460 gerichtete Kanten, dazu stündliche Messreihen und feste Merkmale je Haus (Rohrweg zum Erzeuger, Abzweige bis zum
Erzeuger, Häuser dahinter, Spitzenleistung, Länge der Anschlussleitung). Sinnvoll ist ein GNN erst, wenn eine Größe mit
Strang-Signal gefunden wird.
