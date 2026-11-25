"""Roles: student / teacher / admin (owner's device). Run:  python tests/test_roles.py  (uses a throwaway database)."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import auth  # noqa: E402
import classes_db as cdb  # noqa: E402
import files_db  # noqa: E402
import overview  # noqa: E402
import prefs_db  # noqa: E402
import rooms_db  # noqa: E402
import assistant  # noqa: E402

_dir = tempfile.mkdtemp()
for _m in (auth, cdb, files_db, prefs_db):
    _m.DB_PATH = os.path.join(_dir, "test.db")
auth.ADMIN_FILE = os.path.join(_dir, ".admin_device")     # never touch the real admin file

from streamlit.testing.v1 import AppTest  # noqa: E402

for _u, _r in (("owner", "student"), ("tina", "teacher"), ("tom", "teacher"), ("sam", "student"), ("sue", "student")):
    auth.create_member(f"{_u}@gmail.com", _u, "pw", _r)
    cdb.mark_onboarded(_u)


def _denied(fn, *args):
    try:
        fn(*args)
    except PermissionError:
        return True
    return False


def _room():
    rooms = rooms_db.rooms_of_teacher("tina")
    if rooms:
        return rooms[0]
    assert rooms_db.create_room("tina", "Math 10-B")[0]
    room = rooms_db.rooms_of_teacher("tina")[0]
    assert rooms_db.join("sam", room["code"].lower()) == (True, "Math 10-B")
    cdb.add_classes("sam", ["Math 10-B"], "current")
    return room


def test_only_teachers_create_and_manage_their_own_classrooms():
    assert rooms_db.create_room("sam", "Sneaky")[0] is False
    room = _room()
    rid = room["id"]
    for intruder in ("sam", "sue", "tom"):
        assert _denied(rooms_db.roster, intruder, rid)
        assert _denied(rooms_db.gradebook, intruder, rid)
        assert _denied(rooms_db.add_assignment, intruder, rid, "x", 10)
        assert _denied(rooms_db.delete_room, intruder, rid)
        assert _denied(rooms_db.remove_student, intruder, rid, "sam")
    assert _denied(rooms_db.announcements, "sue", rid)          # not enrolled
    assert _denied(rooms_db.class_average, "sue", rid)
    assert rooms_db.join("sue", "WRONGCDE")[0] is False


def test_teacher_grades_reach_every_part_of_the_student_app():
    room = _room()
    rid = room["id"]
    rooms_db.add_assignment("tina", rid, "Unit test", 50)
    aid = rooms_db.gradebook("tina", rid)["assignments"][0]["id"]
    try:
        rooms_db.set_scores("tina", rid, [(aid, "sam", 99)])
        raise AssertionError("marks above the maximum must be rejected")
    except ValueError:
        pass
    rooms_db.set_scores("tina", rid, [(aid, "sam", 45)])
    cdb.set_final("sam", "Math 10-B", percent=10)               # the student's own entry must not win
    row = next(r for r in overview.class_table("sam") if r["name"] == "Math 10-B")
    assert row["percent"] == 90.0 and row["source"] == "teacher"
    assert overview.summary("sam")["avg_percent"] == 90.0
    assert ("Math 10-B", 90.0) in overview.report_prefill("sam")
    out, is_error, _ = assistant.run_tool("sam", "set_class_grade", {"class_name": "Math 10-B", "grade": "100%"}, {})
    assert is_error and "teacher" in out
    cdb.remove_class("sam", "Math 10-B")                         # removing it from the list can't hide the grade
    assert any(r["name"] == "Math 10-B" and r["percent"] == 90.0 for r in overview.class_table("sam"))
    assert rooms_db.class_average("sam", rid) is None            # hidden unless the teacher allows it
    rooms_db.update_room("tina", rid, 40, True, True)
    assert rooms_db.class_average("sam", rid) == 90.0
    assert rooms_db.my_scores("sam", rid) == [{"title": "Unit test", "max": 50.0, "marks": 45.0}]


def test_admin_exists_only_with_the_device_file():
    assert not auth.is_admin("owner")
    try:
        auth.set_role("owner", "sue", "teacher")
        raise AssertionError("not admin yet")
    except PermissionError:
        pass
    open(auth.ADMIN_FILE, "w").write("owner")
    auth.set_role("owner", "sue", "teacher")
    assert auth.get_role("sue") == "teacher"
    auth.set_role("owner", "sue", "student")
    os.remove(auth.ADMIN_FILE)


def _tabs(user, **state):
    at = AppTest.from_file(os.path.join(ROOT, "streamlit_app.py"), default_timeout=60)
    at.session_state["user"] = user
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at, [t.label for t in at.tabs]


def test_each_role_sees_its_own_tabs():
    _room()
    _, labels = _tabs("sam")
    assert "🎒 Classrooms" in labels and "🏫 Teaching" not in labels and "🛠 Admin" not in labels
    _, labels = _tabs("tina")
    assert "🏫 Teaching" in labels and "🎒 Classrooms" not in labels and "🛠 Admin" not in labels
    assert "✏️ My grades" in labels                              # teachers keep every student feature
    _, labels = _tabs("owner")
    assert "🛠 Admin" not in labels                              # no device file -> no admin


def test_admin_can_preview_roles_and_view_as_others():
    open(auth.ADMIN_FILE, "w").write("owner")
    at, labels = _tabs("owner")
    assert {"🏫 Teaching", "🎒 Classrooms", "🛠 Admin"} <= set(labels)
    at.radio(key="view_role").set_value("Teacher").run()
    labels = [t.label for t in at.tabs]
    assert "🏫 Teaching" in labels and "🎒 Classrooms" not in labels and "🛠 Admin" not in labels
    at.radio(key="view_role").set_value("Student").run()
    labels = [t.label for t in at.tabs]
    assert "🎒 Classrooms" in labels and "🏫 Teaching" not in labels
    at, labels = _tabs("sam", admin_real="owner")               # viewing as a student
    assert "🎒 Classrooms" in labels and "🛠 Admin" not in labels
    assert any("Admin view" in w.value for w in at.warning)
    [b for b in at.button if b.key == "back_to_admin"][0].click().run()
    assert at.session_state["user"] == "owner" and "🛠 Admin" in [t.label for t in at.tabs]
    at, labels = _tabs("sam", admin_real="tom")                 # a non-admin can't claim admin view
    assert not at.warning or not any("Admin view" in w.value for w in at.warning)
    os.remove(auth.ADMIN_FILE)


KEY = "k" * 10 + "Z9" * 10
OWNER_SECRETS = {"admin_email": "owner@gmail.com", "admin_key": KEY}


def _online(user, secrets=OWNER_SECRETS, **state):
    at = AppTest.from_file(os.path.join(ROOT, "streamlit_app.py"), default_timeout=60)
    for k, v in secrets.items():
        at.secrets[k] = v
    if user:
        at.session_state["user"] = user
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def _has_admin(at):
    return "🛠 Admin" in [t.label for t in at.tabs]


def _key_boxes(at):
    return [t for t in at.text_input if t.label == "Owner key"]


def _unlock(at, key):
    _key_boxes(at)[0].set_value(key)
    [b for b in at.button if b.label == "🔐 Unlock"][0].click().run()
    return at


def test_online_owner_needs_the_owner_email_and_the_secret_key():
    assert not os.path.exists(auth.ADMIN_FILE)          # online: no device file
    for other in ("sam", "sue", "tom"):
        at = _online(other)
        assert not _has_admin(at) and not _key_boxes(at), "others must see nothing about admin"
    at = _online("owner")
    assert not _has_admin(at) and _key_boxes(at), "the owner is offered the key box but is not admin yet"
    assert not _has_admin(_unlock(at, "x" * 40))
    at = _online("owner")
    _unlock(at, KEY)
    assert _has_admin(at) and any(r.key == "view_role" for r in at.radio)
    assert not _has_admin(_online("owner")), "another browser session of the same account is not admin without the key"
    assert not _has_admin(_online("sam", admin_unlocked="sam")), "a forged unlock flag on another account does nothing"
    assert not _has_admin(_online("sam", admin_real="owner")), "viewing-as needs the unlock too"
    assert _has_admin(_online("owner", admin_unlocked="owner"))


def test_online_owner_is_not_offered_without_both_secrets():
    for secrets in ({}, {"admin_email": "owner@gmail.com"}, {"admin_email": "owner@gmail.com", "admin_key": "short"}):
        at = _online("owner", secrets)
        assert not _has_admin(at)
        if _key_boxes(at):
            assert not _has_admin(_unlock(at, secrets.get("admin_key", "")))


def test_nobody_can_take_the_owner_email():
    _online("sam")                                       # the app registers the reserved address
    ok, _msg = auth.change_email("sam", "pw", "owner@gmail.com")
    assert not ok
    auth.RESERVED_EMAIL = "free.owner@gmail.com"
    at = _online(None, {"admin_email": "free.owner@gmail.com", "admin_key": KEY, "dev_show_code": True})
    box = lambda label: [t for t in at.text_input if t.label == label][0]
    box("Email").set_value("free.owner@gmail.com")
    box("Username").set_value("squatter")
    box("Password").set_value("pw")
    box("Confirm password").set_value("pw")
    [b for b in at.button if b.label == "Send me a confirmation code"][0].click().run()
    assert "dev_code" not in at.session_state, "test mode must never reveal the code for the owner's address"
    assert any("real email" in e.value for e in at.error)
    assert auth.find_member("squatter") is None
    auth.RESERVED_EMAIL = ""


def test_deleting_accounts_cleans_up_classrooms():
    room = _room()
    auth.delete_member("sam")
    assert "sam" not in rooms_db.roster("tina", room["id"])
    auth.delete_member("tina")
    assert not rooms_db.all_rooms()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
