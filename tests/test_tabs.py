"""Guards against a tab silently losing its content (this once happened: GPA and Grading rules went blank).

Run from the project folder:  python tests/test_tabs.py   (or with pytest)
Uses a throwaway database, never users.db.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402
import classes_db  # noqa: E402
import files_db  # noqa: E402
import prefs_db  # noqa: E402

_tmp = os.path.join(tempfile.mkdtemp(), "test.db")
for _m in (auth, classes_db, files_db, prefs_db):
    _m.DB_PATH = _tmp

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "streamlit_app.py")


def _app():
    try:
        auth.create_member("t@gmail.com", "tester", "pw")
        classes_db.mark_onboarded("tester")
        classes_db.add_classes("tester", ["Math"], "current")
    except Exception:
        pass
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["user"] = "tester"
    return at.run()


def test_no_exceptions_and_all_tabs_present():
    at = _app()
    assert not at.exception, at.exception
    labels = [t.label for t in at.tabs]
    for want in ("My grades", "Report card", "GPA", "Grading rules", "My classes", "Files", "Assistant", "Account"):
        assert any(want in l for l in labels), f"missing tab: {want}"


def test_every_tab_renders_its_key_widgets():
    at = _app()
    buttons = [b.label for b in at.button]
    for want in ("Save grades", "Generate report card", "Calculate GPA", "Save grading rules", "Save GPA scale",
                 "Save files", "Change password"):
        assert any(want in b for b in buttons), f"expected a '{want}' button"
    assert any(m.value for m in at.markdown if "Study assistant" in m.value)
    assert [t for t in at.toggle], "profile-menu effect switches missing"


def test_effect_switches_start_on():
    at = _app()
    assert all(t.value for t in at.toggle if t.label[:4] in ("Anim", "Smoo", "Clic", "Hove", "Typi", "Fade")), \
        [(t.label, t.value) for t in at.toggle]


def test_one_set_of_grades_drives_every_tab():
    """A grade entered once shows up in the summary bar, the report card marks and the GPA table."""
    import overview
    classes_db.add_classes("tester", ["Physics"], "current")
    classes_db.set_final("tester", "Math", percent=92)
    classes_db.set_final("tester", "Physics", letter="B+")
    src = open(APP).read()
    # capture what the report-card and GPA tabs pre-fill with
    src = src.replace("        table = st.data_editor(\n            pd.DataFrame({\"Subject\": subjects, \"Marks\": _marks,",
                      "        st.session_state['_seen_marks'] = dict(zip(subjects, _marks))\n        table = st.data_editor(\n            pd.DataFrame({\"Subject\": subjects, \"Marks\": _marks,")
    at = AppTest.from_string(src, default_timeout=60)
    at.session_state["user"] = "tester"
    at.run()
    assert not at.exception, at.exception
    bar = " ".join(m.value for m in at.markdown if "sumbar" in m.value)
    assert "classes graded" in bar and "GPA" in bar, bar
    assert at.session_state["_seen_marks"] == {"Math": 92.0, "Physics": 87.0}, at.session_state["_seen_marks"]
    s = overview.summary("tester")
    assert s["graded"] == 2 and s["avg_percent"] == 89.5, s


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
