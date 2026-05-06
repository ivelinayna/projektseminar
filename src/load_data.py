"""
Data loading for the Prichsenstadt heating network.

Sources from ÜZ Mainfranken:
- Leitungsverlauf shapefiles: physical pipe network (ETRS89 / UTM 32N)
- Nodes_Edges.ods: logical topology (99 HAST, 110 edges) by street address
- Optimierung xlsx: 67 on-site HAST inspection records

Place data files into data/raw/ - they are gitignored.
"""

from pathlib import Path
from typing import Optional
import re

import geopandas as gpd
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


# Pipe type codes inferred from LINIENTYP attribute
LINIENTYP_MAP = {
    1: "Vorlauf (single)",
    2: "Rücklauf (single)",
    3: "Doppelrohr (combined)",
    4: "Hausanschluss",
    5: "Sonstige",
    6: "Knotenpunkt / Station",
}


def load_pipes(data_dir: Path = DATA_DIR) -> gpd.GeoDataFrame:
    """Load pipe segments (LineString shapefile)."""
    path = data_dir / "Leitungsverlauf_LineString.shp"
    gdf = gpd.read_file(path)
    gdf["pipe_type"] = gdf["LINIENTYP"].map(LINIENTYP_MAP)
    gdf["material"] = gdf["TEXT_LBL"].fillna("unspezifiziert")
    return gdf


def load_gis_points(data_dir: Path = DATA_DIR) -> gpd.GeoDataFrame:
    """Load network point features (junctions, stations) from Point shapefile."""
    path = data_dir / "Leitungsverlauf_Point.shp"
    gdf = gpd.read_file(path)
    gdf["point_type"] = gdf["LINIENTYP"].map(LINIENTYP_MAP)
    return gdf


def load_logical_nodes(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load logical HAST nodes from Nodes_Edges.ods (Nodes sheet)."""
    path = data_dir / "Nodes_Edges.ods"
    df = pd.read_excel(path, sheet_name="Nodes", engine="odf")
    df["address"] = df["Straße"].astype(str).str.strip()
    df["address_norm"] = df["address"].apply(_normalize_address)
    return df


def load_logical_edges(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load logical edges from Nodes_Edges.ods (Edges sheet).

    Edges are address pairs (Node From -> Node To).
    """
    path = data_dir / "Nodes_Edges.ods"
    df = pd.read_excel(path, sheet_name="Edges", engine="odf")
    df["from_norm"] = df["Node From"].apply(_normalize_address)
    df["to_norm"] = df["Node To"].apply(_normalize_address)
    return df


def load_inspections(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load HAST on-site inspection / optimisation records.

    Headers span rows 0 (group) and 1 (subgroup). Row 2 is units. Data
    starts at row 3. We collapse the two header rows by taking the most
    informative cell.
    """
    path = next(data_dir.glob("*Ergebnis_Optimierung_FW*.xlsx"))
    raw = pd.read_excel(path, header=[0, 1])
    # Flatten multi-index by preferring the second row when it's not 'Unnamed'
    flat_cols = []
    for top, sub in raw.columns:
        top_s = "" if str(top).startswith("Unnamed") else str(top).strip()
        sub_s = "" if str(sub).startswith("Unnamed") else str(sub).strip()
        if top_s and sub_s:
            flat_cols.append(f"{top_s} | {sub_s}")
        else:
            flat_cols.append(top_s or sub_s)
    raw.columns = flat_cols
    # Drop the units row (now first data row) and any all-empty rows
    raw = raw.iloc[1:].reset_index(drop=True)
    raw = raw.dropna(how="all").reset_index(drop=True)
    # Keep rows that have a Strassenname (column index 2)
    raw = raw[raw.iloc[:, 2].notna()].reset_index(drop=True)

    # Standardise the typo Fleider -> Flieder
    raw.iloc[:, 2] = raw.iloc[:, 2].astype(str).str.replace(
        "Fleider", "Flieder", regex=False)
    raw["address_norm"] = (raw.iloc[:, 2].astype(str) + " "
                           + raw.iloc[:, 3].astype(str)).apply(_normalize_address)
    return raw


# --- helpers --------------------------------------------------------------

def _normalize_address(s: object) -> str:
    """Map 'Blumenstr. 8', 'Blumenstraße 8', 'Blumenstrasse 8' -> 'blumenstrasse 8'.

    Handles common German street-name variants so the three data sources
    (ODS, optimisation Excel, future address geocoding) can be joined.
    """
    if not isinstance(s, str):
        return ""
    t = s.lower().strip()
    t = t.replace("ß", "ss")
    t = re.sub(r"ä", "ae", t)
    t = re.sub(r"ö", "oe", t)
    t = re.sub(r"ü", "ue", t)
    # Expand all street-name suffix variants to a single canonical form.
    # Handles: 'Blumenstr.', 'Blumenstr', 'Blumenstrasse', 'Blumenstraße'
    # All -> 'blumenstrasse'.
    t = re.sub(r"\.", "", t)                        # drop periods
    t = re.sub(r"str(asse)?\b", "strasse", t)       # str | strasse -> strasse
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 \-]", "", t)
    # Collapse "1 a" -> "1a" (letter suffix glued to number)
    t = re.sub(r"(\d)\s+([a-z])\b", r"\1\2", t)
    # Collapse spaces around hyphens in number ranges: "6 - 8" -> "6-8"
    t = re.sub(r"\s*-\s*", "-", t)
    return t.strip()


if __name__ == "__main__":
    pipes = load_pipes()
    pts = load_gis_points()
    nodes = load_logical_nodes()
    edges = load_logical_edges()
    insp = load_inspections()
    print(f"pipes: {len(pipes)}")
    print(f"gis points: {len(pts)}")
    print(f"logical nodes: {len(nodes)}")
    print(f"logical edges: {len(edges)}")
    print(f"inspections: {len(insp)}")
