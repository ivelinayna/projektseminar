"""
Render test for the Streamlit dashboard via streamlit.testing.AppTest.

Runs the full script headless and checks that every section renders
without an exception, and that selecting a station fills the detail
panel. Needs the pipeline artifacts in data/processed/ (skips politely
if they are absent).

Note: everything runs on ONE AppTest instance - instantiating a second
AppTest in the same process segfaults in this environment (native-lib
re-initialisation inside Streamlit's test runtime, not an app bug).

    python -m tests.test_dashboard_app
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "dashboard_app.py"


def test_dashboard_renders_and_selects():
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception, f"app raised: {at.exception}"

    # all five areas present
    headers = " | ".join(h.value for h in at.subheader)
    for expected in ["Netzkarte", "Stationsdetail", "Netz-Gesamtschau",
                     "Stationsliste", "Fehlererkennung"]:
        assert expected in headers, f"missing section: {expected}"
    assert len(at.metric) == 4, "expected 4 KPI metrics"
    body_all = " ".join(m.value for m in at.markdown)
    assert "Straßenzüge im Vergleich" in body_all, "street aggregation missing"

    # selecting a station re-renders the detail panel without errors
    assert at.selectbox, "station selectbox missing"
    sb = at.selectbox[0]
    sb.select(sb.options[3]).run()
    assert not at.exception, f"selection raised: {at.exception}"
    body = " ".join(m.value for m in at.markdown)
    assert "Einstufung" in body
    assert "Letzte Begehung" in body
    assert "Leitungsnetz" in body, "snapping info missing in detail panel"

    body = " ".join(m.value for m in at.markdown)
    assert "Top-Handlungsempfehlungen" in body, "priority block missing"
    assert "Priorität" in body, "priority breakdown missing in detail"

    # toggling the pipe-node assignment lines re-renders without errors
    assert at.checkbox, "snap-lines checkbox missing"
    at.checkbox[0].check().run()
    assert not at.exception, f"snap toggle raised: {at.exception}"

    # switching the list sorting re-renders without errors
    assert at.radio, "sort radio missing"
    at.radio[0].set_value("Ampel / Winter-Rücklauf").run()
    assert not at.exception, f"sort switch raised: {at.exception}"


if __name__ == "__main__":
    if not (ROOT / "data" / "processed" / "hast_geocoded.csv").exists():
        print("skip: pipeline artifacts missing (run the pipeline first)")
    else:
        test_dashboard_renders_and_selects()
        print("ok  test_dashboard_renders_and_selects")
