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
