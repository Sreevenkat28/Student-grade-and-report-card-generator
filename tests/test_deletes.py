"""Deleting: bulk delete, admin powers over other people's classrooms, and the report card. Run: python tests/test_deletes.py"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import auth  # noqa: E402
import classes_db  # noqa: E402
import files_db  # noqa: E402
import prefs_db  # noqa: E402

_dir = tempfile.mkdtemp()
for _m in (auth, classes_db, files_db, prefs_db):
    _m.DB_PATH = os.path.join(_dir, "test.db")
auth.ADMIN_FILE = os.path.join(_dir, "admin_device")

from streamlit.testing.v1 import AppTest  # noqa: E402

import cleanup  # noqa: E402
import rooms_db  # noqa: E402


def _setup():
    for name, role in (("owner", "student"), ("tina", "teacher"), ("sam", "student")):
        if not any(u == name for u, _e in auth.list_members()):
            auth.create_member(f"{name}@gmail.com", name, "pw", role)
            classes_db.mark_onboarded(name)
    classes_db.add_classes("sam", ["Math"], "current")
    classes_db.set_final("sam", "Math", percent=80)
    classes_db.add_grade("sam", "Math", 8, 10)
    files_db.add_file("sam", "a.txt", b"hello")
    if not rooms_db.rooms_of_teacher("tina"):
        rooms_db.create_room("tina", "Biology")
    room = rooms_db.rooms_of_teacher("tina")[0]
    rooms_db.join("sam", room["code"])
    classes_db.add_classes("sam", ["Biology"], "current")
    classes_db.set_final("sam", "Biology", percent=70)
    return room["id"]


def _denied(fn, *args):
    try:
        fn(*args)
    except PermissionError:
        return True
    return False


def test_bulk_delete_only_removes_what_was_picked():
    _setup()
    assert cleanup.choices("sam") == ["grades", "classes", "files", "joined"]
    cleanup.delete("sam", ["grades"])
    assert not classes_db.get_finals("sam") and not classes_db.list_grades("sam")
    assert classes_db.list_classes("sam")["current"] and files_db.list_files("sam")
    cleanup.delete("sam", ["classes", "files", "joined"])
    assert not classes_db.list_classes("sam")["current"] and not files_db.list_files("sam")
    assert not rooms_db.rooms_of_student("sam")
    cleanup.delete("tina", ["teaching"])
    assert not rooms_db.rooms_of_teacher("tina")


def test_only_the_admin_can_delete_in_other_peoples_classrooms():
    rid = _setup()
    rooms_db.add_announcement("tina", rid, "hello")
    note = rooms_db.announcements("tina", rid)[0]["id"]
    for who in ("sam", "owner"):  # owner is not admin yet
        assert _denied(rooms_db.delete_announcement, who, rid, note)
        assert _denied(rooms_db.delete_room, who, rid)
    assert _denied(auth.clear_events, "sam")
    with open(auth.ADMIN_FILE, "w") as f:
        f.write("owner")
    rooms_db.delete_announcement("owner", rid, note)
    rooms_db.remove_student("owner", rid, "sam")
    assert not rooms_db.announcements("owner", rid) and not rooms_db.roster("owner", rid)
    assert _denied(rooms_db.delete_room, "sam", rid)
    auth.clear_events("owner")
    assert not auth.recent_events()
    at = AppTest.from_file(os.path.join(ROOT, "streamlit_app.py"), default_timeout=60)
    at.session_state["user"] = "owner"
    at.run()
    at.selectbox(key="adm_target").select("sam").run()
    at.selectbox(key="adm_inside_room").select(rid).run()
    assert not at.exception, at.exception
    assert any(m.key == "adm_wipe_sam" for m in at.multiselect)
    os.remove(auth.ADMIN_FILE)


def test_report_card_can_be_deleted():
    _setup()
    at = AppTest.from_file(os.path.join(ROOT, "streamlit_app.py"), default_timeout=60)
    at.session_state["user"] = "sam"
    at.run()
    next(t for t in at.text_input if t.label == "Student name").input("Sam")
    next(b for b in at.button if b.label == "Generate report card").click().run()
    assert not at.error, [e.value for e in at.error]
    at.button(key="del_report").click().run()
    assert not at.exception, at.exception
    assert not any(b.key == "del_report" for b in at.button)
    import helper
    out = helper.handle("sam", "delete my report card", {}, {})
    assert out["set_state"] == {"last_report": None}
    assert classes_db.get_finals("sam")  # grades are untouched


def test_settings_offers_delete_things():
    _setup()
    at = AppTest.from_file(os.path.join(ROOT, "streamlit_app.py"), default_timeout=60)
    at.session_state["user"] = "sam"
    at.session_state["open_settings"] = True
    at.run()
    assert not at.exception, at.exception
    assert any(m.key == "s_wipe" for m in at.multiselect)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
