"""
Validierung der Clusterergebnisse aus den Notebooks 01, 04 und 05.

Notebook 05 clustert jede einzelne Betriebsstunde statt eines
Stationsprofils und findet fünf fachlich benennbare Zustände bei einer
Silhouette von 0,40. Das ist der beste Clusterbefund des Projekts, er
ist aber nie gegen die naheliegendste Alternativerklärung geprüft
worden: ein Stundencluster kann statt eines Betriebszustands auch
einfach die Jahreszeit oder die Tageszeit abbilden. Im Winter ist die
Leistung hoch und der Vorlauf warm, im Sommer ist beides niedrig - eine
Partition, die nur das nachzeichnet, trägt keine Fehlererkennung.

Das Modul stellt die Bausteine dafür bereit:

Stundenpanel
    `lade_stundenpanel` baut aus den Zähler-CSVs von Notebook 00
    (``data/processed/real_meters``) die Matrix, auf der Notebook 05 clustert (Leistung und Volumenstrom je
    Station auf das eigene 95. Perzentil normiert, dazu Spreizung,
    Vor- und Rücklauf). Ausgeschlossene Stationen kommen als Tabelle
    mit Grund zurück und verschwinden nicht still.

Saison- und Tageszeitkontrolle
    `kontext_erklaerbarkeit` fragt, wie weit sich die Clusterzugehörig-
    keit allein aus Kontextgrößen vorhersagen lässt - Außentemperatur,
    Monat, Stunde. Reicht ein flacher Baum auf der Außentemperatur, um
    die Partition zu reproduzieren, ist der Befund ein Saisoneffekt und
    kein Betriebszustand. Verglichen wird gegen die Trivialrate (immer
    das häufigste Cluster), nicht gegen Null.

Stabilität
    `bootstrap_ari` rechnet dieselbe Kennzahl wie Notebook 04 (Refit auf
    einer Bootstrap-Stichprobe, Rückübertragung über das nächste
    Zentroid, ARI gegen die Referenzpartition), damit die Zahlen der
    Stunden- und der Stationsebene vergleichbar sind.

Feature-Gewichtung
    `redundanz_auswahl` und `gewichtungsvarianten` arbeiten die
    Betreuerkritik ab, dass K-Means alle Features gleich gewichtet.
    Stark korrelierte Features zählen in der euklidischen Distanz
    faktisch mehrfach; der Redundanzabbau macht aus mehreren Messungen
    derselben Richtung wieder eine.

Stationstypen
    `leistungsklasse` bildet die im Meeting genannten Klassen über den
    Anschlusswert. Der Anschlusswert steht nur in `Nodes_Edges.ods`,
    die Zähler-zu-Adresse-Zuordnung dagegen in `Zuordnung.xlsx` - beide
    Quellen werden kombiniert und nicht gegeneinander ausgetauscht.

Alle Funktionen hier sind reine Transformationen auf DataFrames bzw.
Arrays; nur `lade_stundenpanel` greift auf das Dateisystem zu. Die
Tests in `tests/test_clustervalidierung.py` laufen deshalb ohne
Rohdaten und ohne Netz.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (adjusted_mutual_info_score, adjusted_rand_score,
                             silhouette_score)
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from . import nb00_daten as nb00

#Spaltennamen der NB-00-Ausgabe
SPALTEN_MAP = nb00.SPALTEN_MAP

#Merkmalsraum aus Notebook 05: Leistung und Durchfluss stationsnormiert,
#die drei Temperaturgroessen in Kelvin bzw. Grad Celsius
BETRIEBS_FEATURES = ["power_norm", "flow_norm", "dt", "vl", "rt"]

ROHSPALTEN = ["power", "flow", "dt", "vl", "rt"]

#Leistungsklassen nach Anschlusswert, Grenzen aus dem Team-Meeting
LEISTUNGSKLASSEN_GRENZEN = (5.0, 10.0)

SEED = 42


#--------------------------------------------------------------------------
#Stundenpanel
#--------------------------------------------------------------------------

def normiere_station(df: pd.DataFrame,
                     spalten: Sequence[str] = ("power", "flow"),
                     quantil: float = 0.95,
                     min_nenner: float = 1e-9) -> pd.DataFrame:
    """Kopie von `df` mit `<spalte>_norm` je Station.

    Normiert wird auf das eigene `quantil` der Station, nicht auf den
    Anschlusswert: der fehlt für 15 von 100 Zählern, und ein Zähler ohne
    Anschlusswert soll nicht aus der Stundenanalyse fallen. Die
    Normierung macht aus der absoluten Last eine relative Auslastung,
    sonst dominiert die Objektgröße jede Distanz.

    Stationen, deren Quantil 0 oder nicht endlich ist, bekommen NaN
    statt einer Division durch Null - sie werden in
    `lade_stundenpanel` ohnehin als Dauerstillstand ausgeschlossen.
    """
    out = df.copy()
    for spalte in spalten:
        nenner = out.groupby("Zählernummer")[spalte].transform(
            lambda s: s.quantile(quantil))
        nenner = nenner.where(nenner > min_nenner)
        out[f"{spalte}_norm"] = out[spalte] / nenner
    return out


def _lies_zaehler_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Timestamp"])
    df = df.rename(columns=SPALTEN_MAP)
    fehlend = [c for c in ROHSPALTEN if c not in df.columns]
    if fehlend:
        raise ValueError(
            f"{path.name}: Spalten {fehlend} fehlen - vorhanden: {list(df.columns)}")
    df = df.rename(columns={"Timestamp": "timestamp"})
    return df[["timestamp"] + ROHSPALTEN]


def lade_stundenpanel(meter_dir: Path,
                      zaehler: Optional[Iterable[int]] = None,
                      quantil: float = 0.95,
                      min_stunden: int = 100,
                      ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stundenpanel über alle Zähler plus Ausschlussbilanz.

    Rückgabe ist ein Tupel aus

        panel        Zählernummer, timestamp, power, flow, dt, vl, rt und
                     die normierten Spalten, nur vollständige Stunden
        ausschluss   eine Zeile je nicht verwendetem Zähler mit Grund und
                     Stundenzahl

    Ausgeschlossen wird in zwei Fällen. Stationen mit weniger als
    `min_stunden` vollständigen Stunden tragen zu wenig, um ein
    Clusterprofil zu stützen. Stationen, deren 95. Perzentil der
    Leistung 0 ist, stehen praktisch durchgehend still - sie würden ein
    eigenes Cluster aus Nullzeilen erzeugen, das nichts erklärt. Beides
    steht in der Ausschlusstabelle mit Grund, es wird nichts still
    verworfen.
    """
    meter_dir = Path(meter_dir)
    nb00.pruefe_ausgabe(meter_dir)
    frames = []
    ausschluss = []
    for csv in sorted(meter_dir.glob("*.csv")):
        try:
            zid = int(csv.stem)
        except ValueError:
            continue
        if zaehler is not None and zid not in set(zaehler):
            continue
        df = _lies_zaehler_csv(csv)
        n_roh = len(df)
        df = df.dropna(subset=ROHSPALTEN)
        if len(df) < min_stunden:
            ausschluss.append({"Zählernummer": zid, "n_stunden": len(df),
                               "n_zeilen_roh": n_roh,
                               "grund": f"weniger als {min_stunden} vollständige Stunden"})
            continue
        if float(df["power"].quantile(quantil)) <= 0.0:
            ausschluss.append({"Zählernummer": zid, "n_stunden": len(df),
                               "n_zeilen_roh": n_roh,
                               "grund": f"p{int(quantil * 100)}(Leistung) = 0, Dauerstillstand"})
            continue
        df.insert(0, "Zählernummer", zid)
        frames.append(df)

    spalten = ["Zählernummer", "n_stunden", "n_zeilen_roh", "grund"]
    ausschluss_df = pd.DataFrame(ausschluss, columns=spalten)
    if not frames:
        leer = pd.DataFrame(columns=["Zählernummer", "timestamp"] + ROHSPALTEN
                            + ["power_norm", "flow_norm"])
        return leer, ausschluss_df

    panel = pd.concat(frames, ignore_index=True)
    panel = normiere_station(panel, quantil=quantil)
    panel = panel.dropna(subset=BETRIEBS_FEATURES)
    return panel.reset_index(drop=True), ausschluss_df


def mit_kontext(panel: pd.DataFrame,
                temperatur: Optional[pd.DataFrame] = None,
                month_map: Optional[Mapping[int, str]] = None) -> pd.DataFrame:
    """Panel um Monat, Stunde, Saisonsegment und Außentemperatur ergänzen.

    Die Kontextspalten sind bewusst **keine** Clusterfeatures. Sie
    dienen allein der Gegenprobe: wenn sich die Partition aus ihnen
    vorhersagen lässt, misst das Clustering Witterung statt Betrieb.
    """
    from . import season

    out = panel.copy()
    ts = pd.DatetimeIndex(out["timestamp"])
    out["monat"] = ts.month
    out["stunde"] = ts.hour
    out = season.add_season_segment(out, timestamp_col="timestamp",
                                    month_map=month_map)
    if temperatur is not None:
        temp = temperatur[["timestamp", "t_out"]].drop_duplicates("timestamp")
        out = out.merge(temp, on="timestamp", how="left")
    return out


#--------------------------------------------------------------------------
#Clustern und Stabilität
#--------------------------------------------------------------------------

def fit_minibatch_kmeans(X: np.ndarray, k: int, seed: int = SEED,
                         n_init: int = 10,
                         batch_size: int = 2048) -> np.ndarray:
    """Labels eines MiniBatchKMeans-Laufs, wie in Notebook 05."""
    km = MiniBatchKMeans(n_clusters=k, n_init=n_init, random_state=seed,
                         batch_size=batch_size)
    return km.fit_predict(np.asarray(X))


def bootstrap_ari(fit_fn: Callable[[np.ndarray, int], np.ndarray],
                  X: np.ndarray,
                  k: int,
                  n_boot: int = 25,
                  seed: int = SEED,
                  stichprobe: Optional[int] = None) -> pd.Series:
    """Stabilität einer Partition als mittlerer ARI über Bootstrap-Refits.

    Gleiches Verfahren wie in Notebook 04, damit Stunden- und
    Stationsebene vergleichbar bleiben: auf jeder Bootstrap-Stichprobe
    wird neu gefittet, die Labels werden über das nächste Zentroid auf
    die Referenzpunkte übertragen und mit der Referenzpartition
    verglichen.

    `stichprobe` zieht vorab eine Teilmenge der Zeilen. Auf Stundenebene
    stehen Millionen Punkte an; der ARI wird dadurch nicht
    systematisch besser oder schlechter, nur rechenbar.
    """
    X = np.asarray(X, dtype=float)
    rng = np.random.default_rng(seed)
    if stichprobe is not None and stichprobe < len(X):
        X = X[rng.choice(len(X), stichprobe, replace=False)]

    ref = np.asarray(fit_fn(X, k))
    n = len(X)
    aris = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        lab_b = np.asarray(fit_fn(X[idx], k))
        if len(np.unique(lab_b)) < 2:
            #Bootstrap ohne Struktur liefert keinen verwertbaren Vergleich
            continue
        klassen = np.unique(lab_b)
        zentroide = np.vstack([X[idx][lab_b == c].mean(axis=0) for c in klassen])
        dist = ((X[:, None, :] - zentroide[None, :, :]) ** 2).sum(axis=2)
        transfer = klassen[dist.argmin(axis=1)]
        aris.append(adjusted_rand_score(ref, transfer))

    if not aris:
        return pd.Series({"ari_mean": np.nan, "ari_std": np.nan,
                          "ari_min": np.nan, "n_laeufe": 0})
    return pd.Series({"ari_mean": float(np.mean(aris)),
                      "ari_std": float(np.std(aris)),
                      "ari_min": float(np.min(aris)),
                      "n_laeufe": len(aris)})


def silhouette_stichprobe(X: np.ndarray, labels: Sequence[int],
                          stichprobe: int = 5000,
                          seed: int = SEED) -> float:
    """Silhouette auf einer Zufallsstichprobe, NaN bei weniger als zwei Clustern."""
    lab = np.asarray(labels)
    if len(np.unique(lab)) < 2:
        return float("nan")
    n = min(stichprobe, len(lab))
    return float(silhouette_score(np.asarray(X), lab, sample_size=n,
                                  random_state=seed))


def zentroid_profil(X: np.ndarray, labels: Sequence[int],
                    spalten: Sequence[str]) -> pd.DataFrame:
    """Clustermittelwerte in Originaleinheiten plus Besetzung.

    Für die fachliche Lesart ist nicht der skalierte Zentroid
    interessant, sondern der Mittelwert der Rohgrößen - ein Rücklauf von
    33 °C lässt sich einordnen, ein z-Wert von -1,2 nicht.
    """
    df = pd.DataFrame(np.asarray(X), columns=list(spalten))
    df["cluster"] = np.asarray(labels)
    profil = df.groupby("cluster")[list(spalten)].mean()
    besetzung = df["cluster"].value_counts().sort_index()
    profil["n_stunden"] = besetzung
    profil["anteil_%"] = (besetzung / len(df) * 100).round(1)
    return profil


def zentroid_zuordnung(profil_a: pd.DataFrame, profil_b: pd.DataFrame,
                       spalten: Sequence[str]) -> pd.DataFrame:
    """Jedes Cluster aus `profil_a` seinem nächsten Gegenstück in `profil_b`.

    Zwei K-Means-Läufe auf unterschiedlichen Teilmengen vergeben die
    Clusternummern beliebig. Für den Vergleich "ist dasselbe Muster
    wieder da" braucht es deshalb eine Zuordnung über die Profile statt
    über die Nummern. Die Distanz wird auf z-Werten der gemeinsamen
    Spalten gerechnet, sonst entscheidet allein die Temperaturskala.
    """
    a = profil_a[list(spalten)].to_numpy(dtype=float)
    b = profil_b[list(spalten)].to_numpy(dtype=float)
    gemeinsam = np.vstack([a, b])
    mu = gemeinsam.mean(axis=0)
    sd = gemeinsam.std(axis=0)
    sd[sd == 0] = 1.0
    az = (a - mu) / sd
    bz = (b - mu) / sd
    dist = np.sqrt(((az[:, None, :] - bz[None, :, :]) ** 2).sum(axis=2))
    treffer = dist.argmin(axis=1)
    return pd.DataFrame({
        "cluster_a": list(profil_a.index),
        "cluster_b": [profil_b.index[i] for i in treffer],
        "distanz": dist[np.arange(len(a)), treffer],
    })


#--------------------------------------------------------------------------
#Saison- und Tageszeitkontrolle
#--------------------------------------------------------------------------

def cramers_v(tabelle: pd.DataFrame) -> float:
    """Cramérs V einer Kontingenztafel, 0 = unabhängig, 1 = deterministisch."""
    beobachtet = np.asarray(tabelle, dtype=float)
    n = beobachtet.sum()
    if n <= 0:
        return float("nan")
    zeilen = beobachtet.sum(axis=1, keepdims=True)
    spalten = beobachtet.sum(axis=0, keepdims=True)
    erwartet = zeilen @ spalten / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.nansum(np.where(erwartet > 0,
                                  (beobachtet - erwartet) ** 2 / erwartet, 0.0))
    k = min(beobachtet.shape) - 1
    if k <= 0:
        return float("nan")
    return float(np.sqrt(chi2 / (n * k)))


def kontext_erklaerbarkeit(labels: Sequence[int],
                           kontext: pd.DataFrame,
                           merkmalsgruppen: Mapping[str, Sequence[str]],
                           max_depth: int = 4,
                           cv: int = 5,
                           stichprobe: Optional[int] = 100_000,
                           seed: int = SEED) -> pd.DataFrame:
    """Wie gut lässt sich die Clusterzugehörigkeit aus Kontext vorhersagen?

    Je Merkmalsgruppe wird ein flacher Entscheidungsbaum
    kreuzvalidiert. Flach ist Absicht: ein tiefer Baum könnte jede
    Partition auswendig lernen, gefragt ist aber, ob ein *trivialer*
    Zusammenhang reicht. Berichtet wird die Genauigkeit zusammen mit der
    Trivialrate (Anteil des häufigsten Clusters) und dem Abstand dazu.

    Lesart: liegt die Genauigkeit auf der Außentemperatur allein nahe an
    der Genauigkeit auf allen Clusterfeatures, bildet die Partition im
    Wesentlichen Witterung ab. Bleibt sie dagegen dicht an der
    Trivialrate, steckt im Clustering Information, die der Kontext nicht
    liefert.
    """
    y = np.asarray(labels)
    daten = kontext.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    if stichprobe is not None and stichprobe < len(y):
        idx = rng.choice(len(y), stichprobe, replace=False)
        y = y[idx]
        daten = daten.iloc[idx].reset_index(drop=True)

    trivial = float(pd.Series(y).value_counts(normalize=True).max())
    zeilen = []
    for name, spalten in merkmalsgruppen.items():
        X = daten[list(spalten)].apply(pd.to_numeric, errors="coerce")
        gueltig = X.notna().all(axis=1)
        X = X[gueltig]
        y_g = y[gueltig.to_numpy()]
        if len(X) == 0 or len(np.unique(y_g)) < 2:
            zeilen.append({"merkmale": name, "n": len(X), "genauigkeit": np.nan,
                           "trivialrate": trivial, "abstand": np.nan,
                           "ami": np.nan})
            continue
        baum = DecisionTreeClassifier(max_depth=max_depth, random_state=seed)
        score = float(cross_val_score(baum, X, y_g, cv=cv,
                                      scoring="accuracy").mean())
        vorhersage = baum.fit(X, y_g).predict(X)
        zeilen.append({
            "merkmale": name,
            "n": int(len(X)),
            "genauigkeit": score,
            "trivialrate": float(pd.Series(y_g).value_counts(normalize=True).max()),
            "abstand": score - float(pd.Series(y_g).value_counts(normalize=True).max()),
            "ami": float(adjusted_mutual_info_score(y_g, vorhersage)),
        })
    return pd.DataFrame(zeilen)


def kontext_kreuztabelle(labels: Sequence[int],
                         kontext: pd.Series,
                         normalisieren: str = "index") -> pd.DataFrame:
    """Kreuztabelle Cluster gegen eine Kontextgröße, zeilenweise normiert."""
    tab = pd.crosstab(pd.Series(np.asarray(labels), name="cluster"),
                      pd.Series(np.asarray(kontext), name=kontext.name
                                if hasattr(kontext, "name") else "kontext"))
    if normalisieren is None:
        return tab
    return tab.div(tab.sum(axis=1 if normalisieren == "index" else 0),
                   axis=0 if normalisieren == "index" else 1)


#--------------------------------------------------------------------------
#Feature-Gewichtung
#--------------------------------------------------------------------------

def redundanz_auswahl(df: pd.DataFrame,
                      spalten: Optional[Sequence[str]] = None,
                      schwelle: float = 0.8,
                      prioritaet: Optional[Sequence[str]] = None
                      ) -> tuple[list[str], pd.DataFrame]:
    """Greedy-Abbau korrelierter Features.

    Hintergrund der Betreuerkritik: K-Means misst euklidische Distanz
    auf standardisierten Spalten. Stehen drei Spalten für dieselbe
    zugrundeliegende Richtung, geht diese Richtung dreifach in die
    Distanz ein - das ist eine implizite Gewichtung, die niemand
    entschieden hat. Der Abbau behält je Korrelationsgruppe eine Spalte.

    Durchlaufen wird in der Reihenfolge `prioritaet` (fachlich wichtige
    Features zuerst), danach die restlichen Spalten in der
    Ausgangsreihenfolge. Eine Spalte fliegt, wenn ihr Betrag der
    Pearson-Korrelation mit einer bereits behaltenen Spalte `schwelle`
    erreicht. Rückgabe ist die Auswahl plus eine Tabelle, die zu jeder
    verworfenen Spalte den Grund nennt.
    """
    spalten = list(df.columns if spalten is None else spalten)
    korr = df[spalten].corr().abs()
    reihenfolge = [c for c in (prioritaet or []) if c in spalten]
    reihenfolge += [c for c in spalten if c not in reihenfolge]

    behalten: list[str] = []
    verworfen = []
    for spalte in reihenfolge:
        partner = None
        for b in behalten:
            wert = korr.loc[spalte, b]
            if pd.notna(wert) and wert >= schwelle:
                partner = (b, float(wert))
                break
        if partner is None:
            behalten.append(spalte)
        else:
            verworfen.append({"feature": spalte, "redundant_zu": partner[0],
                              "korrelation": partner[1]})
    bilanz = pd.DataFrame(verworfen,
                          columns=["feature", "redundant_zu", "korrelation"])
    return behalten, bilanz


def gewichtungsvarianten(df: pd.DataFrame,
                         spalten: Sequence[str],
                         auswahl: Optional[Sequence[str]] = None,
                         pca_varianz: float = 0.9,
                         gewichte: Optional[Mapping[str, float]] = None,
                         seed: int = SEED) -> dict[str, np.ndarray]:
    """Die Vorverarbeitungswege, die gegeneinander antreten.

    `alle gleich`      StandardScaler auf allen Features, der bisherige
                       Weg aus Notebook 01, 04 und 05
    `auswahl`          StandardScaler auf der redundanzbereinigten
                       Teilmenge
    `pca`              StandardScaler, danach PCA auf `pca_varianz`
                       erklärte Varianz
    `fachgewichtet`    StandardScaler, danach Multiplikation mit festen
                       Gewichten - nur gebildet, wenn `gewichte` gesetzt
                       ist

    Eine Gewichtung mit Faktor w skaliert den Beitrag der Spalte zur
    quadrierten Distanz mit w²; die Gewichte sind also keine Anteile,
    sondern Streckungen der Achse.
    """
    X = df[list(spalten)].to_numpy(dtype=float)
    skaliert = StandardScaler().fit_transform(X)
    varianten = {"alle gleich": skaliert}

    if auswahl:
        idx = [list(spalten).index(c) for c in auswahl]
        varianten["auswahl"] = StandardScaler().fit_transform(X[:, idx])

    pca = PCA(n_components=pca_varianz, random_state=seed)
    varianten["pca"] = pca.fit_transform(skaliert)

    if gewichte:
        w = np.array([float(gewichte.get(c, 1.0)) for c in spalten])
        varianten["fachgewichtet"] = skaliert * w

    return varianten


#--------------------------------------------------------------------------
#Stationstypen und Leistungsklassen
#--------------------------------------------------------------------------

def leistungsklasse(anschlusswert_kw: object,
                    grenzen: Sequence[float] = LEISTUNGSKLASSEN_GRENZEN) -> str:
    """Leistungsklasse eines Anschlusswerts in kW.

    Grenzen aus dem Team-Meeting (0-5 kW, 5-10 kW, darüber), als
    Parameter gehalten, weil die Klassengrenzen eine fachliche
    Festlegung und kein Datenbefund sind. Die Grenze gehört jeweils zur
    unteren Klasse. Fehlender Anschlusswert ergibt `unbekannt` statt
    stillschweigend in die kleinste Klasse zu fallen - der Wert steht
    nur in `Nodes_Edges.ods` und fehlt dort für einen Teil der Zähler.
    """
    try:
        kw = float(anschlusswert_kw)
    except (TypeError, ValueError):
        return "unbekannt"
    if not np.isfinite(kw):
        return "unbekannt"
    g = list(grenzen)
    if kw <= g[0]:
        return f"bis {g[0]:g} kW"
    for unten, oben in zip(g, g[1:]):
        if kw <= oben:
            return f"{unten:g}-{oben:g} kW"
    return f"über {g[-1]:g} kW"


def mit_leistungsklasse(df: pd.DataFrame,
                        spalte: str = "anschlusswert_kw",
                        grenzen: Sequence[float] = LEISTUNGSKLASSEN_GRENZEN,
                        ziel: str = "leistungsklasse") -> pd.DataFrame:
    """Kopie von `df` mit Leistungsklasse als geordneter kategorialer Spalte."""
    out = df.copy()
    out[ziel] = out[spalte].map(lambda v: leistungsklasse(v, grenzen))
    g = list(grenzen)
    ordnung = [f"bis {g[0]:g} kW"]
    ordnung += [f"{u:g}-{o:g} kW" for u, o in zip(g, g[1:])]
    ordnung += [f"über {g[-1]:g} kW", "unbekannt"]
    out[ziel] = pd.Categorical(out[ziel], categories=ordnung, ordered=True)
    return out
