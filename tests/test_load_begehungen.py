"""
Tests for src.load_begehungen using small synthetic frames.

Covers the join logic only - the Excel parsing needs the confidential files
in data/raw and is exercised by running the module itself. Runs standalone
(no raw data needed):

    python -m tests.test_load_begehungen          # plain-assert runner
    python -m pytest tests/test_load_begehungen.py
"""

import pandas as pd

from src.load_begehungen import (
    _key,
    address_to_meter,
    meter_changes,
    meter_to_address,
    parallel_meters,
    visit_hours,
)


def _zuordnung() -> pd.DataFrame:
    """Three addresses; the second one had its meter swapped between years."""
    return pd.DataFrame({
        "key": ["musterweg 1", "musterweg 2", "musterweg 2", "musterweg 3"],
        "meter": [11111111, 22222222, 33333333, 44444444],
        "year": ["2024", "2024", "2025", "2025"],
    })


def _zuordnung_with_address() -> pd.DataFrame:
    """Same meter moved address between years - most recent year should win."""
    return pd.DataFrame({
        "address": ["Musterweg 1", "Musterweg 1", "Musterweg 2"],
        "key": ["musterweg 1", "musterweg 1", "musterweg 2"],
        "meter": [11111111, 22222222, 22222222],
        "year": ["2024", "2024", "2025"],
    })


def test_key_collapses_street_spellings():
    assert _key("Fliederstr. 999") == _key("Fliederstraße 999") == "fliederstrasse 999"


def test_key_fixes_known_typo():
    # the walkthrough sheet spells it "Fleiderstraße" - without the fix the
    # address never matches the directory
    assert _key("Fleiderstraße 999") == "fliederstrasse 999"


def test_meter_changes_lists_only_swapped_addresses():
    assert meter_changes(_zuordnung()) == {"musterweg 2": [22222222, 33333333]}


def _zuordnung_parallel() -> pd.DataFrame:
    """Musterweg 5: zwei Stationen auf einem Grundstück, beide jedes Jahr.
    Musterweg 6: 66666666 stand 2024 fälschlich mit dort und wird ab 2025
    unter Musterweg 7 geführt. Musterweg 8 ist ein echter Tausch."""
    return pd.DataFrame({
        "key": ["musterweg 5", "musterweg 5", "musterweg 5", "musterweg 5",
                "musterweg 6", "musterweg 6", "musterweg 6", "musterweg 7",
                "musterweg 8", "musterweg 8"],
        "meter": [51, 52, 51, 52, 61, 66, 61, 66, 81, 82],
        "year": ["2024", "2024", "2025", "2025",
                 "2024", "2024", "2025", "2025", "2024", "2025"],
    })


def test_meter_changes_ignores_meters_listed_in_the_same_year():
    assert meter_changes(_zuordnung_parallel()) == {"musterweg 8": [81, 82]}


def test_parallel_meters_lists_coexisting_meters():
    assert parallel_meters(_zuordnung_parallel()) == {
        "musterweg 5": [51, 52], "musterweg 6": [61, 66]}


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


def test_meter_to_address_picks_most_recent_year():
    lookup = meter_to_address(_zuordnung_with_address())
    # meter 11111111 only appears in 2024 -> keeps its only address
    assert lookup[11111111] == "Musterweg 1"
    # meter 22222222 moved from Musterweg 1 (2024) to Musterweg 2 (2025)
    assert lookup[22222222] == "Musterweg 2"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
