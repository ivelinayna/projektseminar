# Grenzen der Daten

Diese Seite sammelt, wo die Daten den Ergebnissen eine Grenze setzen, und verweist jeweils auf die Stelle, an der das
aufgefallen ist. Wie die Daten im Einzelnen aussehen und was an ihnen korrigiert wurde, steht unter
[Datengrundlage](../datengrundlage/zaehlerdaten.md) und [Qualität und Einschränkungen](../datengrundlage/qualitaet.md).
Grenzen der Verfahren stehen unter [Grenzen der Methoden und Modelle](modelle.md).

## Zählerdaten

- **Stundenwerte sind Momentaufnahmen.** Durchfluss, Leistung und Temperaturen werden zur vollen Stunde abgelesen,
  nicht über die Stunde gemittelt. Eine Tagessumme daraus liegt im Winter um bis zu ±30 % daneben, Tageswerte kommen
  deshalb aus den Zählerständen ([Zählerdaten](../datengrundlage/zaehlerdaten.md#stundenwerte-sind-momentaufnahmen)).
  Was zwischen zwei Ablesungen passiert, fehlt: Eine Regelhysterese lässt sich nicht nachweisen
  ([Datenanalyse](../ergebnisse/datenanalyse.md#schwingende-regelung)), und die Streuung eines Tages enthält auch
  zufällige Warmwasserzapfungen ([Tagescluster](../clustering/tagescluster.md#was-offen-bleibt)).
- **Tageswert-Phase.** Bis etwa November 2022 liefern 45 Zähler nur einen Wert am Tag. Im Netzvergleich fällt der
  Winter 2021/22 deshalb ganz weg, der Winter 2022/23 hat nur 41 Stationen
  ([Qualität](../datengrundlage/qualitaet.md#zahlerdaten)). Im Tagescluster stammen 96 % der Tage mit zu wenigen
  Messstunden aus dieser Zeit ([Tagescluster](../clustering/tagescluster.md#tage-markieren-statt-loschen)).
- **Datenende Juli 2025.** Die meisten Reihen enden am 11.07.2025, nur fünf nachgelieferte Zähler reichen bis Juli
  2026 ([Zählerdaten](../datengrundlage/zaehlerdaten.md#zeitraum-und-abdeckung)). Das hat drei Folgen:
    - Den Winter 2025/26 gibt es nur für diese fünf Zähler. Ein Netzvergleich ist dort nicht möglich, und weder der
      Wintervergleich noch der Bestwert-Maßstab lassen sich an einem weiteren Winter prüfen
      ([Wintervergleich](../begehungen/wintervergleich.md#einordnung),
      [Bestes Viertel](../monitoring/bestwert.md#einordnung)).
    - Von den vier Begehungen im September 2025 haben nur zwei Messwerte danach
      ([Begehungen](../datengrundlage/begehungen.md#grenzen-der-begehungsdaten)).
    - Nach dem 11.07.2025 sind die Stunden der Nachlieferungszähler fast alle aufsummiert, nicht gemessen. In der
      Performance-Auswertung ziehen sie den Abstand nach unten ([Performance](../begehungen/performance.md#zeitraum)).
- **Unterschiedlich lange Reihen.** Die Abdeckung reicht je Zähler von 46 bis 100 %, 13 Zähler liegen unter 70 %
  ([Zählerdaten](../datengrundlage/zaehlerdaten.md#zeitraum-und-abdeckung)). Im Stationscluster zählen trotzdem alle
  Stationen gleich ([Stationscluster](../clustering/stationscluster.md#was-offen-bleibt)).
- **Gefüllte Stunden sind gerechnet.** Gut ein Fünftel der Stunden im Raster hat keine Messung und wird für das
  Graphennetz gefüllt. Bei Lücken über einen Tag liegt der Rücklauf der Füllung um 5 bis 6 K daneben
  ([Verworfene Ansätze](verworfene_ansaetze.md#luckenfullung)).
- **Wenige nutzbare Sommertage.** Von allen Stationstagen sind 69 % nutzbar, im Sommer nur 56 %. Im Sommer bleiben
  eher große, verbrauchsstarke Stationen übrig ([Qualität](../datengrundlage/qualitaet.md#zahlerdaten),
  [Tagescluster](../clustering/tagescluster.md#was-offen-bleibt)).
- **Zählertausch.** Die Tauschdaten fehlen. Eine Station mit getauschtem Zähler erscheint als zwei Zähler, und ein
  Teil der großen Ausschläge in den Stationsbildern könnte ein Tausch sein
  ([Tagescluster](../clustering/tagescluster.md#was-offen-bleibt),
  [Stationsbilder](../stationsbilder/index.md#was-offen-bleibt)).

## Begehungen und Labels

- **Wenige Fälle.** Es gibt 65 Begehungen an 62 Stationen, 7 davon ohne Datum
  ([Begehungen](../datengrundlage/begehungen.md#umfang)). Labels gibt es für die 56 Zähler mit datierter Begehung,
  darunter nur 11 Ventilfälle und 9 verkleinerte Verträge
  ([Daten, Labels und Messlatte](../modelle/daten.md#labels-aus-den-begehungen)). Im strengen Modellvergleich stehen
  43 Begehungen im Test ([Modellvergleich](../vergleich/modellvergleich.md#grenzen)). Die größte Fehlerkategorie in
  den Notizen hat 9 Fälle, für einen Entscheidungsbaum reicht das nicht
  ([Stationsbilder](../stationsbilder/index.md#was-offen-bleibt)). Was die kleine Fallzahl für die Statistik bedeutet,
  steht unter [Grenzen der Methoden und Modelle](modelle.md).
- **Nicht zufällig ausgewählt.** Fast alle Termine liegen im Herbst 2024, eine echte Kontrollgruppe gibt es nicht
  ([Begehungen](../datengrundlage/begehungen.md#grenzen-der-begehungsdaten)). Aussagen zur Wirkung sind deshalb nur
  „konsistent mit“ ([Wintervergleich](../begehungen/wintervergleich.md#einordnung)). Gemeinsame Verbesserungen
  benachbarter Stationen passen eher zu gemeinsamen Terminen als zum Netz
  ([Netzereignisse](../monitoring/netzereignisse.md)).
- **Nie begangene Stationen sind unbekannt, nicht gesund.** Über 37 Stationen sagt die Tabelle nichts
  ([Begehungen](../datengrundlage/begehungen.md#grenzen-der-begehungsdaten)). Ihre Klasse im Dashboard ist eine
  Vorhersage, keine Prüfung ([Fehlerart und Klasse](../modelle/klassen.md#die-klasse-je-station)).
- **Kein Fehlerbeginn.** Die Tabelle sagt, was am Termin gefunden wurde, nicht seit wann
  ([Begehungen](../datengrundlage/begehungen.md#grenzen-der-begehungsdaten)). Ob ein Modell einen Fehler früh erkennt,
  lässt sich deshalb nicht prüfen ([Endmodell](../ergebnisse/endmodell.md#gewahltes-modell-je-frage)).
- **„Gemacht“ heißt nicht „war kaputt“.** Die Tabelle hält Maßnahmen fest, keine Befunde. Eine Maßnahme steht bei
  76 % der Stationen, das trennt nichts ([Wirkung im 21-Tage-Fenster](../begehungen/wirkung.md#ereignis-statt-label)).
  Der Sollwert wurde bei fast zwei Dritteln gesenkt, das ist eher Routine als ein Fehler der Station
  ([Daten, Labels und Messlatte](../modelle/daten.md#labels-aus-den-begehungen)).
- **Leere Kästchen.** Die Ja/Nein-Spalten sind meist leer. Ein leeres Kästchen wird als „nein“ gelesen, das ist eine
  Annahme ([Daten, Labels und Messlatte](../modelle/daten.md#labels-aus-den-begehungen)). Reparaturen stehen oft nur im
  Freitext, selbst beim bekannten Ventilfall 68956351
  ([Datenanalyse](../ergebnisse/datenanalyse.md#fazit-zu-den-daten)).
- **Freitexte sind schwer auszuwerten.** Sie sind im Telegrammstil und ohne feste Begriffe geschrieben. Automatische
  Kodierung und Handkodierung weichen bei 13 Begehungen voneinander ab, und die Handprüfung stammt von einer Person
  ([Qualität](../datengrundlage/qualitaet.md#begehungen)). Mechanische Eingriffe sind nur bei 19 Terminen kodiert
  ([Stationsbilder](../stationsbilder/index.md#4-liegt-es-an-den-labels-notebook-14)).
- **Ein Label aus Messdaten ersetzt das nicht.** Die Regel aus Notebook 03 erkennt nur schwere, monatelang anhaltende
  Zustände ([Label aus Messdaten](../begehungen/labels.md#einordnung)).
- **Mehrfach begangen.** Zwei Begehungen an derselben Station sind keine unabhängigen Fälle
  ([Begehungen](../datengrundlage/begehungen.md#grenzen-der-begehungsdaten)).
- **Anlagendaten nur bei begangenen Häusern.** Stationstyp, Zusatzheizung und Personenzahl wurden erst bei der
  Begehung erhoben. Als Merkmal würden sie verraten, ob eine Station begangen wurde
  ([Qualität](../datengrundlage/qualitaet.md#begehungen)).

## Außentemperatur

- **Eine Station für das ganze Netz.** Im Netz selbst wird keine Außentemperatur gemessen. Sie kommt von der
  DWD-Station Kitzingen, rund 13 km entfernt ([Ergänzende Daten](../datengrundlage/ergaenzend.md#auentemperatur),
  [ARIMA](../begehungen/arima.md#einordnung)).
- **Tagesmittel.** Gebäude reagieren träge, das Tagesmittel bildet das nicht ab. Ein Kälteeinbruch löst deshalb Wellen
  von Alarmen aus, etwa vom 09. bis 12.12.2022 bei 12 von 40 Stationen
  ([Tagesmonitor](../monitoring/tagesmonitor.md#einordnung), [Netzereignisse](../monitoring/netzereignisse.md)). Ein
  Mittel über 2 bis 3 Tage ist vorgemerkt ([Qualität](../datengrundlage/qualitaet.md#auentemperatur)).

## Netzdaten

- **Logisches, kein hydraulisches Netz.** Die Kantendatei verbindet Häuser direkt miteinander, nicht über die echten
  Leitungen. Leitungslängen, Durchmesser und Drücke fehlen
  ([Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md#kantendatei)). Ein Einfluss des Strangs lässt sich
  damit nur grob prüfen, gefunden wurde keiner
  ([Vergleichsgruppen und Nachbarn](../monitoring/nachbarn.md#einordnung),
  [Netz einbeziehen](../netz_einbeziehen/index.md#annahmen-und-grenzen),
  [GNN](../weitere_versuche/gnn.md#warum-das-netz-nichts-gebracht-hat)).
- **Richtung der Kanten unklar.** Die Pfeile passen zu keiner einzelnen Quelle, und der Vorlauf bestätigt keine
  Richtung: An 22 Kanten sinkt er in Pfeilrichtung, an 26 steigt er
  ([Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md#kantendatei)). Der Rohrbaum geht deshalb vom Erzeuger
  aus, seine Richtungen bleiben Annahmen ([Rohrbaum](../netz_einbeziehen/rohrbaum.md#8-grenzen)).
- **Weitere Einspeisepunkte unbekannt.** Den Erzeuger hat die ÜZ bestätigt. Ob es weitere Einspeisepunkte gibt, ist
  offen, und die Schätzung aus dem Vorlauf könnte mehrere nicht trennen
  ([Qualität](../datengrundlage/qualitaet.md#netz-und-zuordnung)).
- **Lücken im Netz.** 18 Adressen haben keine Koordinate, deshalb fehlt für 35 Kanten der Rohrweg. 30 Nodes ohne
  Zähler fehlen im Rohrbaum und in den Tests, 8 Stationen haben auch über zwei Kanten keinen Nachbarn mit Zähler
  ([Qualität](../datengrundlage/qualitaet.md#netz-und-zuordnung),
  [Rohrbaum](../netz_einbeziehen/rohrbaum.md#8-grenzen)).
- **Anschlusswert.** Er fehlt bei 6 Stationen
  ([Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md#anschlusswert)). Im Netzplan steht bei 7 der 9
  verkleinerten Verträge schon der neue Wert. Die Kapazitätsregel rechnet deshalb mit der Vertragsleistung aus dem
  Begehungsprotokoll ([Fehlerart und Klasse](../modelle/klassen.md#kapazitat-eine-regel-statt-eines-modells)).
