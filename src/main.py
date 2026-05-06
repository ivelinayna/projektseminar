"""
End-to-end pipeline.

Run from the project root:

    python -m src.main                         # network analysis only
    python -m src.main --synth                 # also generate synthetic data
    python -m src.main --synth --detect        # also run fault detection
    python -m src.main --synth --detect --plot # plus the feature plot

Reads everything in `data/raw/`, builds graphs, generates the static PNG
topology, the interactive folium map, the fault-frequency chart, the
tidy inspection CSV, and (optionally) synthetic meter data + fault
detection results.
"""

import argparse
from pathlib import Path

import pandas as pd

from . import load_data as ld
from .build_graph import build_logical_graph, build_spatial_graph, graph_summary
from .visualize import plot_logical_topology, make_folium_map, find_main_cluster
from .inspections import tidy_inspections, fault_summary

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
PROCESSED = ROOT / "data" / "processed"
SYNTH_DIR = ROOT / "data" / "raw" / "synthetic"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--synth", action="store_true",
                   help="generate synthetic meter time series")
    p.add_argument("--detect", action="store_true",
                   help="run fault detection on the meter time series")
    p.add_argument("--plot", action="store_true",
                   help="produce additional analysis plots")
    p.add_argument("--geocode", action="store_true",
                   help="geocode HAST addresses (uses cache if present)")
    p.add_argument("--dashboard", action="store_true",
                   help="render the combined map (implies --geocode)")
    p.add_argument("--fault-share", type=float, default=0.25,
                   help="fraction of HAST to inject faults into (synth only)")
    args = p.parse_args()

    OUTPUTS.mkdir(exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # 1. Logical graph from address topology -----------------------------
    print("→ building logical graph from Nodes_Edges.ods")
    nodes = ld.load_logical_nodes()
    edges = ld.load_logical_edges()
    insp = ld.load_inspections()
    g_log = build_logical_graph(nodes, edges, insp)
    print(graph_summary(g_log, "Logical graph"))
    plot_logical_topology(g_log, OUTPUTS / "logical_topology.png")
    print(f"  → {OUTPUTS / 'logical_topology.png'}")

    # 2. Spatial graph from shapefile ------------------------------------
    print("\n→ building spatial graph from shapefiles")
    pipes = ld.load_pipes()
    points = ld.load_gis_points()
    g_spa = build_spatial_graph(pipes)
    print(graph_summary(g_spa, "Spatial graph (full Mainfranken)"))

    print("\n→ rendering interactive folium maps")
    bounds = find_main_cluster(pipes)
    make_folium_map(pipes, points, OUTPUTS / "network_map_main.html", bounds=bounds)
    make_folium_map(pipes, points, OUTPUTS / "network_map_full.html", bounds=None)
    print(f"  → {OUTPUTS / 'network_map_main.html'}")
    print(f"  → {OUTPUTS / 'network_map_full.html'}")

    # 3. Inspection / fault summary --------------------------------------
    print("\n→ tidying inspection records")
    tidy = tidy_inspections(insp)
    summary = fault_summary(tidy)
    tidy.to_csv(PROCESSED / "inspections_tidy.csv", index=False)
    summary.to_csv(PROCESSED / "fault_summary.csv", index=False)
    print(f"  → {PROCESSED / 'inspections_tidy.csv'}")
    print(f"  → {PROCESSED / 'fault_summary.csv'}")
    print()
    print(summary.to_string(index=False))

    hast = [n for n, d in g_log.nodes(data=True) if d.get("kind") == "HAST"]
    inspected = [n for n in hast if g_log.nodes[n].get("inspected")]
    print(f"\nCoverage: {len(inspected)} of {len(hast)} HAST have inspection "
          f"records ({len(inspected)/len(hast)*100:.0f}%)")

    # 4. Synthetic time series -------------------------------------------
    if args.synth:
        from .synth_data import generate_dataset
        print("\n→ generating synthetic meter time series")
        truth = generate_dataset(nodes, SYNTH_DIR,
                                 fault_share=args.fault_share)
        print(f"  wrote {len(truth)} CSVs → {SYNTH_DIR / 'meters'}")
        print(truth["fault"].value_counts().to_string())

    # 5. Fault detection on time series ----------------------------------
    if args.detect:
        from .features import features_for_directory
        from .fault_detection import classify_dataframe, confusion

        meters = SYNTH_DIR / "meters"
        if not meters.exists():
            raise SystemExit("no meter time series found - run with --synth "
                             "first or place real CSVs into "
                             f"{meters}")
        print("\n→ extracting features and running rule-based detection")
        feats = features_for_directory(meters, nodes)
        feats.to_csv(PROCESSED / "features.csv", index=False)
        res = classify_dataframe(feats)
        res.to_csv(PROCESSED / "predictions.csv", index=False)
        print(f"  → {PROCESSED / 'features.csv'}")
        print(f"  → {PROCESSED / 'predictions.csv'}")
        print()
        print("predicted fault distribution:")
        print(res["predicted_fault"].value_counts().to_string())

        # If we have ground truth (synthetic case), score it
        truth_csv = SYNTH_DIR / "faults_truth.csv"
        if truth_csv.exists():
            truth = pd.read_csv(truth_csv)
            merged = res.merge(truth[["Zählernummer", "fault"]], on="Zählernummer")
            print()
            print("confusion (truth × pred):")
            print(confusion(merged["predicted_fault"], merged["fault"]).to_string())
            acc = (merged["predicted_fault"] == merged["fault"]).mean()
            print(f"\naccuracy: {acc*100:.0f} %")

    # 6. Optional analysis plots -----------------------------------------
    if args.plot and args.detect:
        from .features import features_for_directory

        feats = features_for_directory(SYNTH_DIR / "meters", nodes)
        truth_csv = SYNTH_DIR / "faults_truth.csv"
        if truth_csv.exists():
            truth = pd.read_csv(truth_csv)
            df = feats.merge(truth[["Zählernummer", "fault"]],
                             on="Zählernummer")
            _plot_feature_separation(df, OUTPUTS / "feature_separation.png")
            print(f"  → {OUTPUTS / 'feature_separation.png'}")

    # 7. Geocoding -------------------------------------------------------
    if args.geocode or args.dashboard:
        from .geocode import geocode_nodes, validate_results
        print("\n→ geocoding HAST addresses (Nominatim or cache)")
        geo = validate_results(geocode_nodes(nodes))
        n_hit = geo["lat"].notna().sum()
        n_in = geo["in_expected_area"].sum()
        print(f"  {n_hit}/{len(geo)} matched, {n_in}/{n_hit} in expected area")
        geo.to_csv(PROCESSED / "hast_geocoded.csv", index=False)
        print(f"  → {PROCESSED / 'hast_geocoded.csv'}")

    # 8. Combined dashboard map ------------------------------------------
    if args.dashboard:
        from .dashboard_map import build_combined_map
        print("\n→ rendering combined dashboard map")
        out = build_combined_map(OUTPUTS / "dashboard_map.html")
        print(f"  → {out}")


def _plot_feature_separation(df: pd.DataFrame, out_path: Path) -> None:
    import matplotlib.pyplot as plt
    fault_colors = {
        "healthy": "#bdbdbd", "fouled_filter": "#1f77b4",
        "excess_rt": "#d62728", "continuous_flow": "#2ca02c",
        "oversized_contract": "#ff7f0e", "control_hysteresis": "#9467bd",
    }
    panels = [
        ("rt_mean_winter", "dt_mean_loaded",
         "RT mean (winter) °C", "ΔT mean under load (K)"),
        ("summer_flow_baseline", "summer_idle_flow_median",
         "Summer median flow (l/h)", "Summer idle flow (l/h)"),
        ("flow_ceiling_slope_per_month", "dt_p10_loaded",
         "Monthly flow-ceiling slope", "ΔT 10th pct (K)"),
        ("peak_load_share", "full_load_hours",
         "Peak / contracted", "Full-load-equiv hours"),
        ("flow_short_cycle_power", "dt_std_loaded",
         "4–12h flow oscillation power", "ΔT std under load"),
        ("rt_above_50_share_loaded", "rt_p95",
         "RT > 50 °C share (loaded)", "RT 95th pct °C"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for ax, (xc, yc, xl, yl) in zip(axes.flat, panels):
        for fault, sub in df.groupby("fault"):
            ax.scatter(sub[xc], sub[yc],
                       c=fault_colors.get(fault, "#888"),
                       label=fault,
                       s=60 if fault != "healthy" else 18,
                       alpha=0.85 if fault != "healthy" else 0.4,
                       edgecolors="white", linewidths=0.4)
        ax.set_xlabel(xl, fontsize=10)
        ax.set_ylabel(yl, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=6,
               frameon=False, bbox_to_anchor=(0.5, 0.99), fontsize=10)
    fig.suptitle(f"Feature separation by fault type ({len(df)} HAST)",
                 y=1.04, fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
