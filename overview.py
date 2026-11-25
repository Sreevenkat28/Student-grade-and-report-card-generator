"""One place that turns each class's grade into everything the app shows (report card, GPA, summary...).

A student types ONE grade per class, either a letter ("B+") or a percentage ("87" / "87.5%"). A letter is
converted to a percentage with the GPA scale (the lowest % that earns it); a percentage is converted to a
letter the same way. If a class has no typed grade, the average of its recorded test scores is used.
No Streamlit imports.
"""
import re

import classes_db as cdb
import gpa as gpa_lib
import prefs_db
import rooms_db

NUM_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:%|percent)?$", re.I)


def parse_grade(text, gpa_scale):
    """'B+' | '87' | '87.5%' -> (percent, letter, error). Empty text -> (None, None, None)."""
    t = str(text if text is not None else "").strip()
    if not t or t.lower() in ("nan", "none"):
        return None, None, None
    m = NUM_RE.match(t)
    if m:
        v = float(m.group(1))
        if not 0 <= v <= 100:
            return None, None, f'"{t}" is outside 0-100%.'
        return v, None, None
    letters = {g["grade"].upper(): g["grade"] for g in gpa_scale}
    if t.upper() in letters:
        return None, letters[t.upper()], None
    return None, None, (f'"{t}" is not a percentage (0-100) or one of your grades '
                        f'({", ".join(g["grade"] for g in gpa_scale)}).')


def letter_to_percent(letter, gpa_scale):
    for g in gpa_scale:
        if g["grade"].upper() == str(letter).upper() and g["min"] is not None:
            return float(g["min"])
    return None


def _test_averages(user):
    per = {}
    for g in cdb.list_grades(user):
        per.setdefault(g["class"].lower(), []).append(g["percent"])
    return {k: (round(sum(v) / len(v), 1), len(v)) for k, v in per.items()}


def class_table(user):
    """One dict per class (current first, then previous) with everything derived from its grade."""
    my, finals = cdb.list_classes(user), cdb.get_finals(user)
    gs, lv = prefs_db.load_gpa(user)
    tests = _test_averages(user)
    default_level = lv[0]["level"]
    level_names = {l["level"] for l in lv}
    rooms = rooms_db.teacher_grades(user)
    listed = {n.lower() for n in my["current"] + my["previous"]}
    # a joined classroom always shows up, even if the student removed or renamed it in their own list
    my = {"current": my["current"] + [v["name"] for k, v in rooms.items() if k not in listed], "previous": my["previous"]}
    rows = []
    for status in ("current", "previous"):
        for name in my[status]:
            f, t = finals.get(name.lower()), tests.get(name.lower())
            room = rooms.get(name.lower())
            percent, letter, source, n = None, None, None, 0
            if room and room["percent"] is not None:  # the teacher's grade wins and the student can't change it
                percent, source, n = room["percent"], "teacher", 1
            elif f and (f["percent"] is not None or f["letter"]):
                source, n = "entered", 1
                if f["percent"] is not None:
                    percent = float(f["percent"])
                else:
                    letter = f["letter"]
                    percent = letter_to_percent(letter, gs)
            elif t:
                percent, n, source = t[0], t[1], "tests"
            gpa_letter = letter or (gpa_lib.percent_to_letter(percent, gs) if percent is not None else None)
            level = f["level"] if f and f["level"] in level_names else default_level
            rows.append({"name": name, "status": status, "percent": percent, "entered_letter": letter,
                         "entered_text": (letter if letter else (f"{percent:g}%" if source in ("entered", "teacher") else "")),
                         "teacher": room["teacher"] if room else None,
                         "gpa_letter": gpa_letter, "credits": float(f["credits"]) if f else 1.0, "level": level,
                         "source": source, "n": n})
    return rows


def graded(user):
    return [r for r in class_table(user) if r["percent"] is not None or r["gpa_letter"]]


def summary(user):
    """Overall numbers shown across the app. Keys are None when there is nothing to compute."""
    rows = class_table(user)
    got = [r for r in rows if r["percent"] is not None or r["gpa_letter"]]
    out = {"total": len(rows), "graded": len(got), "avg_percent": None, "gpa": None, "gpa_weighted": None}
    pcts = [r["percent"] for r in got if r["percent"] is not None]
    if pcts:
        out["avg_percent"] = round(sum(pcts) / len(pcts), 1)
    gs, lv = prefs_db.load_gpa(user)
    res, err = gpa_lib.compute_gpa(
        [{"Course": r["name"], "Grade": r["gpa_letter"], "Credits": r["credits"], "Level": r["level"]}
         for r in got if r["gpa_letter"]], gs, lv)
    if not err:
        out["gpa"], out["gpa_weighted"] = res["unweighted"], res["weighted"]
    return out


def report_prefill(user):
    """[(subject, percent or None)] for the report card: your current classes."""
    return [(r["name"], r["percent"]) for r in class_table(user) if r["status"] == "current"]


def gpa_prefill(user):
    """Rows for the GPA table: every graded class (current and previous), then ungraded current classes."""
    rows = class_table(user)
    ordered = [r for r in rows if r["gpa_letter"]] + [r for r in rows if not r["gpa_letter"] and r["status"] == "current"]
    return [{"Course": r["name"], "Grade": r["gpa_letter"], "Percent": r["percent"],
             "Credits": r["credits"], "Level": r["level"]} for r in ordered]


def apply_entered_letters(user, res):
    """On the report card, show a letter exactly as the student typed it (only where the marks are unchanged)."""
    typed = {r["name"].lower(): r for r in class_table(user) if r["entered_letter"]}
    for row in res["rows"]:
        r = typed.get(row["Subject"].lower())
        if r and r["percent"] is not None and abs(row["Marks"] - r["percent"]) < 0.01 and row["Max"] == 100:
            row["Grade"] = r["entered_letter"]
    return res
