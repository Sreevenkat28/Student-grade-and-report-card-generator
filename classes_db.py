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
