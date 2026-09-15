"""
Tests for src.load_begehungen using small synthetic frames.

Covers the join logic only - the Excel parsing needs the confidential files
in data/raw and is exercised by running the module itself. Runs standalone
(no raw data needed):

    python -m tests.test_load_begehungen          # plain-assert runner
    python -m pytest tests/test_load_begehungen.py
"""

import pandas as pd

from src.load_begehungen import _key, address_to_meter, meter_changes, visit_hours


def _zuordnung() -> pd.DataFrame:
    """Three addresses; the second one had its meter swapped between years."""
    return pd.DataFrame({
        "key": ["musterweg 1", "musterweg 2", "musterweg 2", "musterweg 3"],
        "meter": [11111111, 22222222, 33333333, 44444444],
        "year": ["2024", "2024", "2025", "2025"],
    })


def test_key_collapses_street_spellings():
    assert _key("Fliederstr. 999") == _key("Fliederstraße 999") == "fliederstrasse 999"


def test_key_fixes_known_typo():
    # the walkthrough sheet spells it "Fleiderstraße" - without the fix the
    # address never matches the directory
    assert _key("Fleiderstraße 999") == "fliederstrasse 999"


def test_meter_changes_lists_only_swapped_addresses():
    assert meter_changes(_zuordnung()) == {"musterweg 2": [22222222, 33333333]}


def test_address_to_meter_prefers_meter_with_data():
    lookup = address_to_meter(available={33333333}, zuordnung=_zuordnung())
    assert lookup["musterweg 2"] == 33333333


def test_address_to_meter_without_data_takes_lowest():
    lookup = address_to_meter(zuordnung=_zuordnung())
    assert lookup["musterweg 2"] == 22222222
    assert lookup["musterweg 1"] == 11111111


def test_visit_hours():
    assert visit_hours(pd.Series({"von": "08:30:00", "bis": "09:55:00"})) == (8, 9)
    # end time missing -> single-hour window
    assert visit_hours(pd.Series({"von": "10:20:00", "bis": float("nan")})) == (10, 10)
    assert visit_hours(pd.Series({"von": float("nan"), "bis": float("nan")})) is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
