# Offene Fragen an die ÜZ

Einige Fragen lassen sich aus den Daten nicht beantworten, nur die ÜZ kann sie klären. Jede Frage verweist auf die
Stelle, an der sie aufgekommen ist.

## Zählerwechsel

- Wann wurde welcher Zähler getauscht? Ohne Tauschdatum erscheint eine Station mit neuem Zähler als zwei Zähler, und
  ein Teil der großen Ausschläge könnte ein Tausch sein
  ([Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md#zahlertausch-und-doppelte-eintrage),
  [Stationsbilder](../stationsbilder/index.md#was-offen-bleibt)).
- Gab es vor November 2022 einen Wechsel der Messauflösung? Bis dahin liefern 45 Zähler nur einen Wert am Tag
  ([Zählerdaten](../datengrundlage/zaehlerdaten.md#zeitraum-und-abdeckung)).

## Begehungen

- Welche Reparaturen fehlen in der Begehungstabelle? Beim Ventilfall 68956351 stehen Ventil- und Stellmotortausch nur
  im Freitext ([Begehungen](../datengrundlage/begehungen.md#freitexte),
  [Datenanalyse](../ergebnisse/datenanalyse.md#fazit-zu-den-daten)).
- Welche Daten gehören zu den 7 Begehungen ohne Datum ([Begehungen](../datengrundlage/begehungen.md#umfang))?
- Gibt es Begehungen nach Juli 2025, möglichst mit Zählerständen
  ([Begehungen](../datengrundlage/begehungen.md#grenzen-der-begehungsdaten))?
- Können die chronisch auffälligen, nie begangenen Stationen 68956360, 72135453, 72135480 und 72167793 begangen werden
  ([Netzvergleich](../monitoring/netzvergleich.md#teil-a-chronisch-auffallige-stationen))?
- Was steckt hinter den Stationen 72135442, 80912173 und 68956359, die nach der Begehung mehr Wasser brauchen
  ([Netzvergleich](../monitoring/netzvergleich.md#einordnung))?
- Was ist bei Zähler 72167783 passiert? Der Rücklauf stieg nach der Begehung von 18,6 auf 71,0 °C
  ([Wirkung im 21-Tage-Fenster](../begehungen/wirkung.md#was-offen-bleibt)).
- Was erklärt die großen Sprünge im Herbst 2024 ohne Begehung bei 72167777, 69513891 und 80956410
  ([ARIMA](../begehungen/arima.md#einordnung))?
- Kann das Protokoll künftig festhalten, ob etwas kaputt war, und nicht nur, was gemacht wurde? Sollwert und Filter
  wurden bei 62 % und 47 % der Begehungen gemacht, eine Spur im Zähler hinterlassen sie nicht
  ([Verworfene Ansätze](verworfene_ansaetze.md#fehlerarten-ohne-messspur),
  [Datenanalyse](../ergebnisse/datenanalyse.md#fazit-zu-den-daten)).

## Betrieb

- Welche Alarmlast ist im Betrieb tragbar? Soll die CUSUM-Schwelle bei h = 5 bleiben oder auf h = 8 steigen? Bei h = 8
  fallen die Alarme auf etwa zwei Drittel ([Alarme bewerten](../monitoring/alarme.md#schwelle-h)).
- Wo sollen die Grenzen der Dringlichkeitsstufen liegen
  ([Handlungsempfehlungen](../ergebnisse/handlungsempfehlungen.md#dringlichkeit))?
- Welche Maßnahme gehört zu welchem Fehlerbild ([Alarme bewerten](../monitoring/alarme.md#einordnung),
  [Von der Anomalie zur Empfehlung](../monitoring/empfehlung.md#einordnung))?

## Fehlerkategorien

- Passen die neun Fehlerkategorien, nach denen die Notizen kodiert sind? Sollen Zirkulation und Pumpe getrennt geführt
  werden ([Stationsbilder](../stationsbilder/index.md#4-liegt-es-an-den-labels-notebook-14))?
- Ist Dämmung ein Befund an der Hausanschlussstation? Sie ist bei 41 % der begangenen Stationen eingetragen
  ([Dashboard](../ergebnisse/dashboard.md#grenzen)).
- Kann die ÜZ die Fehler-Symptom-Matrix und den Anteil gesunder Stationen abstimmen? Bisher sind 0 von 132 Feldern
  abgestimmt ([Bayes-Diagnose](../weitere_versuche/bayes.md#matrix-und-vorwissen)).

## Sonderzähler

- Was sind die Zähler 58202380 und 66761022? K-Means und Ward trennen sie als Ausreißer ab, und 58202380 ist für ein
  Haus sehr groß ([Vier Verfahren im Vergleich](../clustering/benchmark.md),
  [Qualität](../datengrundlage/qualitaet.md#zahlerdaten)).

## Netz und Hydraulik

- Gibt es außer dem Erzeuger weitere Einspeisepunkte
  ([Qualität](../datengrundlage/qualitaet.md#netz-und-zuordnung))?
- Was bedeuten die Kantenrichtungen in `Nodes_Edges.ods`
  ([Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md#kantendatei))?
- Gibt es ein hydraulisches Netzmodell, Rohrdaten (Nennweite, Länge) oder Differenzdrücke
  ([Vergleichsgruppen und Nachbarn](../monitoring/nachbarn.md#einordnung),
  [Qualität](../datengrundlage/qualitaet.md#was-an-daten-fehlt))?
- Gibt es die Vorlauftemperatur am Ausgang der Heizzentrale
  ([Qualität](../datengrundlage/qualitaet.md#was-an-daten-fehlt))?
- Gibt es Koordinaten für die 18 Adressen ohne Position? Für 35 Kanten fehlt deshalb der Rohrweg
  ([Qualität](../datengrundlage/qualitaet.md#netz-und-zuordnung)).
- Wie sollen Hausanschlussstationen ohne Kante im Netz behandelt werden? 5 Adressen mit Zähler hängen an keiner Kante
  ([Qualität](../datengrundlage/qualitaet.md#netz-und-zuordnung)).

## Weitere Daten

- Gibt es Minutenwerte oder Reglerdaten mit Stellsignal? Ohne sie bleibt die Regelhysterese unsichtbar
  ([Datenanalyse](../ergebnisse/datenanalyse.md#schwingende-regelung),
  [Netzvergleich](../monitoring/netzvergleich.md#einordnung)).
- Gibt es das Baujahr je Gebäude? Es ist der letzte ungeprüfte Störfaktor für das Dämmungsmuster des gelernten Modells
  ([Alarme bewerten](../monitoring/alarme.md#baujahr-als-kontext),
  [Weiterentwicklung](../ausblick/weiterentwicklung.md)).
