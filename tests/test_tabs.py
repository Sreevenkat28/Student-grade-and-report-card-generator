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
    for want in ("Report card", "GPA", "Grading rules", "My classes", "Files", "Assistant", "Account"):
        assert any(want in l for l in labels), f"missing tab: {want}"


def test_every_tab_renders_its_key_widgets():
    at = _app()
    buttons = [b.label for b in at.button]
    for want in ("Generate report card", "Calculate GPA", "Save grading rules", "Save GPA scale",
                 "Save files", "Change password"):
        assert any(want in b for b in buttons), f"expected a '{want}' button"
    assert any(m.value for m in at.markdown if "Study assistant" in m.value)
    assert [t for t in at.toggle], "profile-menu effect switches missing"


def test_effect_switches_start_on():
    at = _app()
    assert all(t.value for t in at.toggle if t.label[:4] in ("Anim", "Smoo", "Clic", "Hove", "Typi", "Fade")), \
        [(t.label, t.value) for t in at.toggle]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
