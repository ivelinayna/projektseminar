# Grenzen und Erkenntnisse

Dieser Teil sammelt, worauf die Ergebnisse beruhen, wo sie aufhören und was das Projekt dabei gelernt hat. Jeder Punkt
verweist auf die Stelle, an der er aufgefallen ist.

## Die wichtigsten Grenzen auf einen Blick

| Grenze | Folge | aufgefallen in |
|---|---|---|
| Keine verlässlichen Labels: Die Begehungen halten fest, was gemacht wurde, nicht, was kaputt war und seit wann | Ob eine Auffälligkeit ein Fehler ist, lässt sich kaum prüfen. Eine Frühwarnung ist nicht prüfbar | [Datenanalyse](../ergebnisse/datenanalyse.md#fazit-zu-den-daten), [Alarme bewerten](../monitoring/alarme.md#einordnung) |
| Wenige Fälle: 43 Begehungen im Test, 11 Ventilfälle | Unterschiede unter etwa 0,1 AUC sind nicht sichtbar, viele Vorsprünge bleiben ungesichert | [Modellvergleich](../vergleich/modellvergleich.md#grenzen) |
| Stundenwerte sind Momentaufnahmen | Tageswerte müssen aus den Zählerständen kommen, eine Regelhysterese ist nicht nachweisbar | [Zählerdaten](../datengrundlage/zaehlerdaten.md#stundenwerte-sind-momentaufnahmen), [Datenanalyse](../ergebnisse/datenanalyse.md#schwingende-regelung) |
| Die Daten enden im Juli 2025 | Kein Netzvergleich für den Winter 2025/26, keine Prüfung an einem weiteren Winter | [Wintervergleich](../begehungen/wintervergleich.md#einordnung), [Bestes Viertel](../monitoring/bestwert.md#einordnung) |
| Ein Teilnetz, rückblickend geprüft | Ob die Modelle im Betrieb und in anderen Teilnetzen tragen, ist offen | [Prüfung nach vorn](../ausblick/pruefung.md), [Weiterentwicklung](../ausblick/weiterentwicklung.md) |

## Was auf den Unterseiten steht

- **[Grenzen der Daten](daten.md):** was Zählerdaten, Begehungen, Außentemperatur und Netzdaten nicht hergeben, und
  wo sich das in den Ergebnissen gezeigt hat.
- **[Grenzen der Methoden und Modelle](modelle.md):** was die Fallzahl bedeutet, wie weit die Aussagen zur Wirkung der
  Begehungen reichen, was die Modelle nicht erkennen, wo Wächter und Empfehlungen aufhören und welche Schwellen gesetzt
  sind.
- **[Erkenntnisse](erkenntnisse.md):** was das Projekt über die Daten und die Verfahren gelernt hat, geordnet nach den
  Teilen.
- **[Offene Fragen an die ÜZ](offene_fragen.md):** was sich aus den Daten nicht beantworten lässt.

Probleme in den Rohdaten im Einzelnen stehen unter [Qualität und Einschränkungen](../datengrundlage/qualitaet.md),
Ansätze, die nicht funktioniert haben, unter [Negativbefunde](../nicht_getragen/negativbefunde.md). Was als Nächstes
kommen sollte, steht unter [Ausblick](../ausblick/weiterentwicklung.md).
