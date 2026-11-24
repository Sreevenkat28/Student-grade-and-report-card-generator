"""Per-user grading scale, pass rules and display choice, stored as JSON next to the accounts."""
import json
import sqlite3

from auth import DB_PATH
import gpa as gpa_lib
import grading

DISPLAY_MODES = ["Letter grades", "Percentages", "Both"]


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS prefs (username TEXT PRIMARY KEY, data TEXT NOT NULL)")
    return conn


def _read(username: str) -> dict:
    with _conn() as c:
        row = c.execute("SELECT data FROM prefs WHERE username = ?", (username,)).fetchone()
    try:
        data = json.loads(row[0]) if row else {}
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _write(username: str, data: dict):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO prefs VALUES (?, ?)", (username, json.dumps(data)))


def load(username: str):
    """Returns (scale, rules); falls back to the defaults if nothing valid is saved."""
    data = _read(username)
    scale, rules = [dict(g) for g in grading.DEFAULT_SCALE], dict(grading.DEFAULT_RULES)
    s, err = grading.clean_scale(data.get("scale", []))
    if not err:
        scale = s
    r, err = grading.clean_rules(data.get("pass_subject"), data.get("pass_overall"),
                                 data.get("require_all", True))
    if not err:
        rules = r
    return scale, rules


def save(username: str, scale, rules):
    data = _read(username)
    data.update({"scale": scale, **rules})
    _write(username, data)


def reset(username: str):
    """Restore the default scale and pass rules (keeps the display choice)."""
    data = _read(username)
    for k in ("scale", "pass_subject", "pass_overall", "require_all"):
        data.pop(k, None)
    _write(username, data)


def load_display(username: str) -> str:
    mode = _read(username).get("display")
    return mode if mode in DISPLAY_MODES else DISPLAY_MODES[0]


def save_display(username: str, mode: str):
    if mode in DISPLAY_MODES:
        data = _read(username)
        data["display"] = mode
        _write(username, data)


def load_gpa(username: str):
    """Returns (gpa_scale, levels); the defaults if nothing valid is saved."""
    data = _read(username)
    scale, levels = [dict(g) for g in gpa_lib.DEFAULT_SCALE], [dict(l) for l in gpa_lib.DEFAULT_LEVELS]
    s, err = gpa_lib.clean_scale(data.get("gpa_scale", []))
    if not err:
        scale = s
    l, err = gpa_lib.clean_levels(data.get("gpa_levels", []))
    if not err:
        levels = l
    return scale, levels


def save_gpa(username: str, scale, levels):
    data = _read(username)
    data.update({"gpa_scale": scale, "gpa_levels": levels})
    _write(username, data)


def reset_gpa(username: str):
    data = _read(username)
    for k in ("gpa_scale", "gpa_levels"):
        data.pop(k, None)
    _write(username, data)


# ---------------------------------------------------------------- interface / animation settings
UI_KEYS = ["animations", "transitions", "click_fx", "hover_fx", "typing_fx", "cards_fx"]
UI_DEFAULTS = {k: True for k in UI_KEYS}
UI_LABELS = {"animations": "Animations (master switch)", "transitions": "Smooth tab transitions",
             "click_fx": "Click & press effects", "hover_fx": "Hover lift effects",
             "typing_fx": "Typing effect in the assistant", "cards_fx": "Fade-in cards & results"}


def load_ui(username: str) -> dict:
    saved = _read(username).get("ui", {})
    saved = saved if isinstance(saved, dict) else {}
    return {k: bool(saved.get(k, UI_DEFAULTS[k])) for k in UI_KEYS}


def save_ui(username: str, ui: dict):
    data = _read(username)
    data["ui"] = {k: bool(ui.get(k, UI_DEFAULTS[k])) for k in UI_KEYS}
    _write(username, data)


THEMES = ["Light", "Dark", "Auto"]


def load_theme(username: str) -> str:
    t = _read(username).get("theme")
    return t if t in THEMES else "Light"


def save_theme(username: str, theme: str):
    if theme in THEMES:
        data = _read(username)
        data["theme"] = theme
        _write(username, data)


# ---------------------------------------------------------------- whole-settings export/import (used by undo)
def export_all(username: str) -> dict:
    return json.loads(json.dumps(_read(username)))


def import_all(username: str, data: dict):
    if data:
        _write(username, data)
    else:
        with _conn() as c:
            c.execute("DELETE FROM prefs WHERE username = ?", (username,))
