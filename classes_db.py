"""Per-user classes (current / previous) and onboarding flag, stored next to the accounts."""
import re
import sqlite3

from auth import DB_PATH

MAX_NAME = 60
MAX_PER_USER = 60
STATUSES = ("current", "previous")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS classes ("
        "username TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL, "
        "PRIMARY KEY (username, name COLLATE NOCASE))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS profile (username TEXT PRIMARY KEY, onboarded INTEGER NOT NULL)"
    )
    return conn


def parse_names(text: str):
    """Split on newlines/commas/semicolons, trim, drop blanks and duplicates (case-insensitive)."""
    seen, out = set(), []
    for part in re.split(r"[\n,;]+", text or ""):
        name = " ".join(part.split())[:MAX_NAME]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def add_classes(username: str, names, status: str):
    """Add classes with the given status. Existing names are left unchanged. Returns count added."""
    if status not in STATUSES:
        raise ValueError("bad status")
    added = 0
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM classes WHERE username = ?", (username,)).fetchone()[0]
        for n in names:
            if total + added >= MAX_PER_USER:
                break
            cur = c.execute(
                "INSERT OR IGNORE INTO classes VALUES (?, ?, ?)", (username, n[:MAX_NAME], status)
            )
            added += cur.rowcount
    return added


def list_classes(username: str):
    with _conn() as c:
        rows = c.execute(
            "SELECT name, status FROM classes WHERE username = ? ORDER BY name COLLATE NOCASE",
            (username,),
        ).fetchall()
    out = {"current": [], "previous": []}
    for name, status in rows:
        out[status].append(name)
    return out


def set_status(username: str, name: str, status: str):
    if status not in STATUSES:
        raise ValueError("bad status")
    with _conn() as c:
        c.execute(
            "UPDATE classes SET status = ? WHERE username = ? AND name = ? COLLATE NOCASE",
            (status, username, name),
        )


def remove_class(username: str, name: str):
    with _conn() as c:
        c.execute(
            "DELETE FROM classes WHERE username = ? AND name = ? COLLATE NOCASE", (username, name)
        )


def is_onboarded(username: str) -> bool:
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM profile WHERE username = ? AND onboarded = 1", (username,)
        ).fetchone() is not None


def mark_onboarded(username: str):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO profile VALUES (?, 1)", (username,))


# ---------------------------------------------------------------- recorded grades
MAX_GRADES_PER_USER = 500


def _grades_conn():
    conn = _conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS grades (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, "
        "class TEXT NOT NULL, marks REAL NOT NULL, max REAL NOT NULL, label TEXT NOT NULL DEFAULT '', "
        "created REAL NOT NULL)"
    )
    return conn


def add_grade(username: str, class_name: str, marks, max_marks=100, label: str = ""):
    """Record one score (e.g. a test). Returns (ok, message)."""
    name = " ".join(str(class_name or "").split())[:MAX_NAME]
    if not name:
        return False, "Pick a class."
    try:
        marks, max_marks = float(marks), float(max_marks)
    except (TypeError, ValueError):
        return False, "Marks and maximum must be numbers."
    if max_marks != max_marks or marks != marks or max_marks <= 0:
        return False, "Maximum marks must be greater than 0."
    if marks < 0 or marks > max_marks:
        return False, f"Marks must be between 0 and {max_marks:g}."
    label = " ".join(str(label or "").split())[:60]
    import time
    with _grades_conn() as c:
        if c.execute("SELECT COUNT(*) FROM grades WHERE username = ?", (username,)).fetchone()[0] >= MAX_GRADES_PER_USER:
            return False, f"You can record at most {MAX_GRADES_PER_USER} grades."
        c.execute("INSERT INTO grades (username, class, marks, max, label, created) VALUES (?, ?, ?, ?, ?, ?)",
                  (username, name, marks, max_marks, label, time.time()))
    return True, "Grade recorded."


def list_grades(username: str):
    with _grades_conn() as c:
        rows = c.execute(
            "SELECT id, class, marks, max, label, created FROM grades WHERE username = ? ORDER BY created DESC, id DESC",
            (username,),
        ).fetchall()
    return [{"id": r[0], "class": r[1], "marks": r[2], "max": r[3], "label": r[4],
             "percent": round(r[2] / r[3] * 100, 2), "created": r[5]} for r in rows]


def delete_grade(username: str, grade_id: int):
    with _grades_conn() as c:
        c.execute("DELETE FROM grades WHERE username = ? AND id = ?", (username, int(grade_id)))


# ---------------------------------------------------------------- one final grade per class
def _final_conn():
    conn = _conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS final_grades (username TEXT NOT NULL, class TEXT NOT NULL COLLATE NOCASE, "
        "percent REAL, letter TEXT, credits REAL NOT NULL DEFAULT 1, level TEXT, "
        "PRIMARY KEY (username, class))"
    )
    return conn


def set_final(username: str, class_name: str, percent=None, letter=None, credits=1.0, level=None):
    """Save the grade for one class: a percentage OR a letter (the caller validates). Returns (ok, message)."""
    name = " ".join(str(class_name or "").split())[:MAX_NAME]
    if not name:
        return False, "Pick a class."
    if percent is None and not letter:
        return False, "Enter a letter or a percentage."
    try:
        credits = float(credits if credits is not None else 1.0)
    except (TypeError, ValueError):
        return False, "Credits must be a number."
    if not 0 < credits <= 20:
        return False, "Credits must be greater than 0 and at most 20."
    with _final_conn() as c:
        c.execute("INSERT OR REPLACE INTO final_grades VALUES (?, ?, ?, ?, ?, ?)",
                  (username, name, None if percent is None else float(percent), letter or None, credits,
                   (level or None)))
    return True, "Grade saved."


def get_finals(username: str):
    """{lowercase class name: {class, percent, letter, credits, level}}"""
    with _final_conn() as c:
        rows = c.execute("SELECT class, percent, letter, credits, level FROM final_grades WHERE username = ?",
                         (username,)).fetchall()
    return {r[0].lower(): {"class": r[0], "percent": r[1], "letter": r[2], "credits": r[3], "level": r[4]} for r in rows}


def delete_final(username: str, class_name: str):
    with _final_conn() as c:
        c.execute("DELETE FROM final_grades WHERE username = ? AND class = ? COLLATE NOCASE", (username, class_name))


# ---------------------------------------------------------------- undo support, renaming, per-class credits/level
def snapshot(username: str):
    """Everything about this user's classes and grades, as plain data (for undo)."""
    _grades_conn().close()
    with _final_conn() as c:
        classes = c.execute("SELECT name, status FROM classes WHERE username = ? ORDER BY name", (username,)).fetchall()
        finals = c.execute("SELECT class, percent, letter, credits, level FROM final_grades WHERE username = ? ORDER BY class",
                           (username,)).fetchall()
        scores = c.execute("SELECT class, marks, max, label, created FROM grades WHERE username = ? ORDER BY id",
                           (username,)).fetchall()
    return {"classes": [list(r) for r in classes], "finals": [list(r) for r in finals], "scores": [list(r) for r in scores]}


def restore(username: str, snap: dict):
    """Put this user's classes and grades back exactly as in `snap`."""
    _grades_conn().close()
    with _final_conn() as c:
        for table in ("classes", "final_grades", "grades"):
            c.execute(f"DELETE FROM {table} WHERE username = ?", (username,))
        for name, status in snap["classes"]:
            c.execute("INSERT OR IGNORE INTO classes VALUES (?, ?, ?)", (username, name, status))
        for cls, pct, letter, credits, level in snap["finals"]:
            c.execute("INSERT OR REPLACE INTO final_grades VALUES (?, ?, ?, ?, ?, ?)", (username, cls, pct, letter, credits, level))
        for cls, marks, mx, label, created in snap["scores"]:
            c.execute("INSERT INTO grades (username, class, marks, max, label, created) VALUES (?, ?, ?, ?, ?, ?)",
                      (username, cls, marks, mx, label, created))


def rename_class(username: str, old: str, new: str):
    """Rename a class everywhere (list, test scores, grade). Returns (ok, message)."""
    new = " ".join(str(new or "").split())[:MAX_NAME]
    if not new:
        return False, "Give the new name."
    _grades_conn().close()
    with _final_conn() as c:
        if old.lower() != new.lower() and c.execute(
                "SELECT 1 FROM classes WHERE username = ? AND name = ? COLLATE NOCASE", (username, new)).fetchone():
            return False, f'You already have a class called "{new}".'
        c.execute("UPDATE classes SET name = ? WHERE username = ? AND name = ? COLLATE NOCASE", (new, username, old))
        c.execute("UPDATE grades SET class = ? WHERE username = ? AND class = ? COLLATE NOCASE", (new, username, old))
        c.execute("UPDATE final_grades SET class = ? WHERE username = ? AND class = ? COLLATE NOCASE", (new, username, old))
    return True, "Renamed."


def set_final_attrs(username: str, class_name: str, credits=None, level=None):
    """Change a class's credits and/or course level without touching its grade."""
    cur = get_finals(username).get(class_name.lower())
    cr = float(credits) if credits is not None else (cur["credits"] if cur else 1.0)
    if not 0 < cr <= 20:
        return False, "Credits must be greater than 0 and at most 20."
    lv = level if level is not None else (cur["level"] if cur else None)
    with _final_conn() as c:
        c.execute("INSERT OR REPLACE INTO final_grades VALUES (?, ?, ?, ?, ?, ?)",
                  (username, cur["class"] if cur else class_name, cur["percent"] if cur else None,
                   cur["letter"] if cur else None, cr, lv))
    return True, "Saved."


def clear_final_grade(username: str, class_name: str):
    """Remove the typed grade for a class but keep its credits and level."""
    cur = get_finals(username).get(class_name.lower())
    if not cur:
        return
    if cur["credits"] == 1.0 and not cur["level"]:
        delete_final(username, class_name)
    else:
        with _final_conn() as c:
            c.execute("UPDATE final_grades SET percent = NULL, letter = NULL WHERE username = ? AND class = ? COLLATE NOCASE",
                      (username, class_name))
