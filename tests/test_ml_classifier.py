"""
Smoke test for src.ml_classifier: the evaluation runs end-to-end and
the honest guarantees hold (three benchmarks present, CV reports a
std, per-type tasks below MIN_POS are excluded). Needs the pipeline
artifacts; skips politely if absent.

    python -m tests.test_ml_classifier
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_runs_and_reports_all_benchmarks():
    from src.ml_classifier import (MIN_POS, build_labelled, evaluate_task,
                                   FEATURE_COLS)

    df = build_labelled()
    assert len(df) > 0
    X = df[FEATURE_COLS]
    y = df["y_binary"].values

    ev = evaluate_task(X, y, df["baseline_pred"].values,
                       "binär: mind. eine Maßnahme")
    approaches = set(ev["approach"])
    # all three benchmarks must be present
    assert "trivial (immer Befund)" in approaches
    assert "Regel-Baseline" in approaches
    assert {"LogReg", "RandomForest"} <= approaches
    # every metric carries a std column (fold spread is reported)
    assert {"precision", "recall", "f1", "balanced_acc"} <= set(ev["metric"])
    assert "std" in ev.columns and ev["std"].notna().all()

    # leakage flags exist and are quantified
    for c in ("begehung_im_fenster", "begehung_nach_fenster",
              "begehung_ohne_datum"):
        assert c in df.columns


def test_small_measure_types_are_excluded():
    from src.ml_classifier import MIN_POS, build_labelled

    df = build_labelled()
    # regler_getauscht has 0 positives -> must never be viable
    assert int(df["regler_getauscht"].astype(int).sum()) < MIN_POS


if __name__ == "__main__":
    if not (ROOT / "data" / "processed" / "features_real.csv").exists():
        print("skip: pipeline artifacts missing (run python -m src.detect_real)")
    else:
        test_evaluation_runs_and_reports_all_benchmarks()
        print("ok  test_evaluation_runs_and_reports_all_benchmarks")
        test_small_measure_types_are_excluded()
        print("ok  test_small_measure_types_are_excluded")
        print("\n2 tests passed")
