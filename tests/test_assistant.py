"""Tests for the built-in assistant's commands, multi-command messages, confirmations and undo.

Run from the project folder:  python tests/test_assistant.py   (or with pytest). Uses a throwaway database.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth  # noqa: E402
import classes_db as cdb  # noqa: E402
import files_db  # noqa: E402
import helper  # noqa: E402
import overview  # noqa: E402
import prefs_db  # noqa: E402

_tmp = os.path.join(tempfile.mkdtemp(), "test.db")
for _m in (auth, cdb, files_db, prefs_db):
    _m.DB_PATH = _tmp

TABS = {"My grades": "✏️ My grades", "Report card": "📝 Report card", "GPA": "🎯 GPA", "Grading rules": "⚙️ Grading rules",
        "My classes": "📚 My classes", "Files": "📁 Files", "Assistant": "🤖 Assistant"}
_n = [0]


def fresh():
    """A new user with a few classes and an empty chat state."""
    _n[0] += 1
    u = f"user{_n[0]}"
    auth.create_member(f"{u}@gmail.com", u, "pw")
    cdb.add_classes(u, ["Math", "Physics", "Art"], "current")
    cdb.add_classes(u, ["Biology"], "previous")
    return u, {}


def say(u, st, text):
    return helper.handle(u, text, TABS, st)


def grades(u):
    return {r["name"]: r["entered_text"] for r in overview.class_table(u)}


def test_set_grades_letters_and_percentages():
    u, st = fresh()
    say(u, st, "my math grade is B+")
    say(u, st, "set physics to 87%")
    say(u, st, "I have an A in art")
    assert grades(u) == {"Art": "A", "Math": "B+", "Physics": "87%", "Biology": ""}
    say(u, st, "clear my art grade")
    assert grades(u)["Art"] == ""


def test_credits_levels_rename():
    u, st = fresh()
    say(u, st, "set math credits to 0.5")
    say(u, st, "make physics honors")
    say(u, st, "make all classes regular")
    say(u, st, "rename math to maths")
    names = cdb.list_classes(u)
    assert "Maths" in names["current"] and "Math" not in names["current"]
    row = {r["name"]: r for r in overview.class_table(u)}["Maths"]
    assert row["credits"] == 0.5 and row["level"] == "Regular"
    assert "couldn't find" in say(u, st, "rename zzz to q")["text"]


def test_grading_rules_and_scales():
    u, st = fresh()
    say(u, st, "set pass mark to 50")
    assert prefs_db.load(u)[1]["pass_subject"] == 50
    say(u, st, "add grade A++ at 95")
    assert any(g["grade"] == "A++" for g in prefs_db.load(u)[0])
    say(u, st, "set a++ to 96")
    assert [g["min"] for g in prefs_db.load(u)[0] if g["grade"] == "A++"] == [96.0]
    say(u, st, "remove grade D")
    assert all(g["grade"] != "D" for g in prefs_db.load(u)[0])
    assert "can't remove" in say(u, st, "remove grade F")["text"]
    say(u, st, "set gpa cutoff for A- to 91")
    assert [g["min"] for g in prefs_db.load_gpa(u)[0] if g["grade"] == "A-"] == [91.0]
    say(u, st, "add level IB bonus 1.25")
    assert any(l["level"] == "IB" for l in prefs_db.load_gpa(u)[1])


def test_several_requests_in_one_message():
    u, st = fresh()
    r = say(u, st, "my math grade is B+ and my physics grade is 87% and turn on dark mode")
    assert grades(u)["Math"] == "B+" and grades(u)["Physics"] == "87%"
    assert prefs_db.load_theme(u) == "Dark" and r["set_state"]["theme_mode"] == "Dark"
    r = say(u, st, "add classes chemistry and english then set chemistry grade to a-")
    assert {"Chemistry", "English"} <= set(cdb.list_classes(u)["current"]) and grades(u)["Chemistry"] == "A-"
    say(u, st, "turn animations off and light mode")
    assert prefs_db.load_ui(u)["animations"] is False and prefs_db.load_theme(u) == "Light"


def test_typos_are_forgiven_but_class_names_are_not_changed():
    u, st = fresh()
    say(u, st, "chnage my math grade to B")
    assert grades(u)["Math"] == "B"
    say(u, st, "show grades as precentages")
    assert prefs_db.load_display(u) == "Percentages"


def test_undo_covers_settings_grades_and_confirmed_deletions():
    u, st = fresh()
    before = grades(u)
    say(u, st, "my math grade is 55%")
    say(u, st, "make physics honors")
    say(u, st, "show grades as both")
    for _ in range(3):
        say(u, st, "undo")
    assert grades(u) == before and prefs_db.load_display(u) == "Letter grades"
    assert "nothing to undo" in say(u, st, "undo")["text"].lower()
    say(u, st, "remove class art")
    say(u, st, "yes")
    assert "Art" not in cdb.list_classes(u)["current"]
    say(u, st, "undo")
    assert "Art" in cdb.list_classes(u)["current"]
    cdb.set_final(u, "Math", percent=80)
    cdb.add_grade(u, "Art", 30, 50, "q")
    snap = (grades(u), len(cdb.list_grades(u)))
    say(u, st, "delete all my grades")
    say(u, st, "yes")
    assert len(cdb.list_grades(u)) == 0 and grades(u)["Math"] == ""
    say(u, st, "undo")
    assert (grades(u), len(cdb.list_grades(u))) == snap


def test_one_undo_reverses_a_whole_message():
    u, st = fresh()
    before = (grades(u), prefs_db.load_theme(u), prefs_db.load(u)[1]["pass_subject"])
    say(u, st, "my math grade is B+ and my physics grade is 87% and set pass mark to 55 and dark mode")
    assert grades(u)["Math"] == "B+" and prefs_db.load_theme(u) == "Dark"
    r = say(u, st, "undo")
    assert (grades(u), prefs_db.load_theme(u), prefs_db.load(u)[1]["pass_subject"]) == before
    assert r["set_state"]["theme_mode"] == "Light"
    assert "nothing to undo" in say(u, st, "undo")["text"].lower()


def test_confirmations_and_compound_safety():
    u, st = fresh()
    r = say(u, st, "remove class art")
    assert "yes" in r["text"].lower() and "Art" in cdb.list_classes(u)["current"]
    say(u, st, "no")
    assert "Art" in cdb.list_classes(u)["current"]
    # a delete in the middle of a multi-request message is skipped, never run
    say(u, st, "remove class art and turn animations off and dark mode")
    assert "Art" in cdb.list_classes(u)["current"] and "pending" not in st
    assert prefs_db.load_ui(u)["animations"] is False and prefs_db.load_theme(u) == "Dark"
    # as the last step it asks first
    r = say(u, st, "turn animations on and remove class art")
    assert st.get("pending", {}).get("kind") == "remove_class"
    say(u, st, "yes")
    assert "Art" not in cdb.list_classes(u)["current"]


def test_settings_notes_report_details_and_navigation():
    u, st = fresh()
    r = say(u, st, "open appearance settings")
    assert r["open_settings"] and r["settings_tab"] == helper.ST_APPEARANCE
    assert say(u, st, "change my password")["settings_tab"] == helper.ST_ACCOUNT
    assert say(u, st, "download my data")["settings_tab"] == helper.ST_DATA
    assert "Theme" in say(u, st, "show my settings")["text"]
    say(u, st, "save a note called Study Ideas: do more practice tests, sleep early")
    assert [f["name"] for f in files_db.list_files(u)] == ["Study Ideas.md"]
    r = say(u, st, "make a report card for Sam Lee, roll 12, class 10-B, exam Finals: math 80/100, science 45/50")
    assert r["report"][0]["name"] == "Sam Lee" and r["report"][0]["roll"] == "12" and r["report"][0]["cls"] == "10-B" \
        and r["report"][0]["exam"] == "Finals"
    assert say(u, st, "go to GPA")["nav"] == "🎯 GPA"


def test_things_that_must_not_be_misread():
    u, st = fresh()
    before = (prefs_db.load(u), grades(u), cdb.list_classes(u))
    for t in ("set volume to 5", "what is the weather", "make a study plan so i pass 3 exams", "set the theme to 5", "how do i add a class"):
        say(u, st, t)
    assert (prefs_db.load(u), grades(u), cdb.list_classes(u)) == before
    assert "not sure" in say(u, st, "how do i add a class")["text"] or "add classes" in say(u, st, "how do i add a class")["text"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
