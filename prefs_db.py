"""Per-user grading scale and pass rules, stored as JSON next to the accounts."""
import json
import sqlite3

from auth import DB_PATH
import grading


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS prefs (username TEXT PRIMARY KEY, data TEXT NOT NULL)")
    return conn


def load(username: str):
    """Returns (scale, rules); falls back to the defaults if nothing valid is saved."""
    with _conn() as c:
        row = c.execute("SELECT data FROM prefs WHERE username = ?", (username,)).fetchone()
    scale, rules = [dict(g) for g in grading.DEFAULT_SCALE], dict(grading.DEFAULT_RULES)
    if row:
        try:
            data = json.loads(row[0])
            s, err = grading.clean_scale(data.get("scale", []))
            if not err:
                scale = s
            r, err = grading.clean_rules(data.get("pass_subject"), data.get("pass_overall"),
                                         data.get("require_all", True))
            if not err:
                rules = r
        except (ValueError, TypeError):
            pass
    return scale, rules


def save(username: str, scale, rules):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO prefs VALUES (?, ?)",
                  (username, json.dumps({"scale": scale, **rules})))


def reset(username: str):
    with _conn() as c:
        c.execute("DELETE FROM prefs WHERE username = ?", (username,))
