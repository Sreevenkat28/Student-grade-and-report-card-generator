"""GPA, unweighted and weighted, with an editable grade scale. No Streamlit imports."""
import math

# Default scale: the standard US 4.0 scale. `min` is the lowest percentage that earns the
# grade when a course is entered as a percentage (None = can't be reached by percentage).
DEFAULT_SCALE = [
    {"grade": "A+", "points": 4.0, "min": 97.0}, {"grade": "A", "points": 4.0, "min": 93.0},
    {"grade": "A-", "points": 3.7, "min": 90.0}, {"grade": "B+", "points": 3.3, "min": 87.0},
    {"grade": "B", "points": 3.0, "min": 83.0}, {"grade": "B-", "points": 2.7, "min": 80.0},
    {"grade": "C+", "points": 2.3, "min": 77.0}, {"grade": "C", "points": 2.0, "min": 73.0},
    {"grade": "C-", "points": 1.7, "min": 70.0}, {"grade": "D+", "points": 1.3, "min": 67.0},
    {"grade": "D", "points": 1.0, "min": 63.0}, {"grade": "D-", "points": 0.7, "min": 60.0},
    {"grade": "F", "points": 0.0, "min": 0.0},
]
# Extra points added for harder courses in the weighted GPA (never added to a 0-point grade).
DEFAULT_LEVELS = [
    {"level": "Regular", "bonus": 0.0}, {"level": "Honors", "bonus": 0.5},
    {"level": "AP / IB", "bonus": 1.0}, {"level": "Dual enrollment", "bonus": 1.0},
]
MAX_ROWS = 30

# Handy views of the defaults (used by tests and simple callers).
GRADE_POINTS = {g["grade"]: g["points"] for g in DEFAULT_SCALE}
GRADES = list(GRADE_POINTS)
LEVEL_BONUS = {l["level"]: l["bonus"] for l in DEFAULT_LEVELS}
LEVELS = list(LEVEL_BONUS)


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _text(v):
    """Cell text, with None and NaN (what an empty table cell becomes) treated as empty."""
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


def clean_scale(rows):
    """Validate an editable GPA scale. Returns (scale, error).

    Rules: unique grade names, points 0-10, optional minimum % (0-100, all different), and one
    grade at 0% so every percentage maps to a grade.
    """
    out, names = [], set()
    for r in rows:
        grade = _text(r.get("grade"))
        pts, mn = _num(r.get("points")), _num(r.get("min"))
        if not grade and pts is None and mn is None:
            continue  # blank row
        if not grade:
            return None, "Every grade needs a name (for example A or B+)."
        if grade.lower() in names:
            return None, f'The grade "{grade}" appears more than once.'
        if pts is None or not 0 <= pts <= 10:
            return None, f'The points for "{grade}" must be a number from 0 to 10.'
        if mn is not None and not 0 <= mn <= 100:
            return None, f'The minimum % for "{grade}" must be from 0 to 100 (or empty).'
        names.add(grade.lower())
        out.append({"grade": grade[:6], "points": round(pts, 2), "min": None if mn is None else round(mn, 2)})
    if len(out) < 2:
        return None, "Keep at least two grades."
    if len(out) > MAX_ROWS:
        return None, f"Use at most {MAX_ROWS} grades."
    mins = [g["min"] for g in out if g["min"] is not None]
    if len(set(mins)) != len(mins):
        return None, "Two grades have the same minimum %. Each cut-off must be different."
    if 0 not in mins:
        return None, "One grade must have a minimum of 0% so every percentage gets a grade."
    return out, None


def clean_levels(rows):
    """Validate editable course levels (name + weighted bonus). Returns (levels, error)."""
    out, names = [], set()
    for r in rows:
        level = _text(r.get("level"))
        bonus = _num(r.get("bonus"))
        if not level and bonus is None:
            continue
        if not level:
            return None, "Every course level needs a name."
        if level.lower() in names:
            return None, f'The level "{level}" appears more than once.'
        if bonus is None or not 0 <= bonus <= 5:
            return None, f'The bonus for "{level}" must be a number from 0 to 5.'
        names.add(level.lower())
        out.append({"level": level[:24], "bonus": round(bonus, 2)})
    if not out:
        return None, "Keep at least one course level."
    if len(out) > MAX_ROWS:
        return None, f"Use at most {MAX_ROWS} levels."
    return out, None


def percent_to_letter(pct, scale=None):
    """Highest grade whose minimum % the score reaches."""
    scale = scale or DEFAULT_SCALE
    ranked = sorted((g for g in scale if g["min"] is not None), key=lambda g: -g["min"])
    for g in ranked:
        if pct >= g["min"]:
            return g["grade"]
    return ranked[-1]["grade"] if ranked else None


def compute_gpa(rows, scale=None, levels=None):
    """rows: dicts with Course, Credits, Level and either Grade (letter) or Percent (0-100).

    Rows with neither a grade nor a percent are skipped (treated as in progress).
    Returns (result, error).
    """
    scale = scale or DEFAULT_SCALE
    levels = levels or DEFAULT_LEVELS
    points = {g["grade"].upper(): g["points"] for g in scale}
    shown = {g["grade"].upper(): g["grade"] for g in scale}
    bonuses = {l["level"]: l["bonus"] for l in levels}
    default_level = levels[0]["level"]

    used = []
    for r in rows:
        course = _text(r.get("Course"))
        label = course or "a course"
        grade = _text(r.get("Grade"))
        if grade.upper() == "NONE":
            grade = ""
        pct = _num(r.get("Percent"))
        if not grade and pct is None:
            continue
        if not grade:
            if not 0 <= pct <= 100:
                return None, f"The percentage for {label} must be between 0 and 100."
            grade = percent_to_letter(pct, scale)
        if grade.upper() not in points:
            return None, f'"{grade}" is not a grade in your GPA scale (used for {label}).'
        credits = _num(r.get("Credits"))
        if credits is None or credits <= 0:
            return None, f"Enter credits greater than 0 for {label}."
        level = _text(r.get("Level")) or default_level
        if level not in bonuses:
            return None, f"Unknown course level for {label}."
        base = points[grade.upper()]
        weighted = base + (bonuses[level] if base > 0 else 0.0)
        row = {"Course": course or "—"}
        if pct is not None:
            row["Percent"] = pct
        row.update({"Grade": shown[grade.upper()], "Credits": credits, "Level": level,
                    "Unweighted": base, "Weighted": round(weighted, 2)})
        used.append(row)
    if not used:
        return None, "Enter a grade (or percentage) and credits for at least one course."
    credits_total = sum(u["Credits"] for u in used)
    unweighted = sum(u["Unweighted"] * u["Credits"] for u in used) / credits_total
    weighted = sum(u["Weighted"] * u["Credits"] for u in used) / credits_total
    return {"rows": used, "credits": round(credits_total, 2),
            "unweighted": round(unweighted, 2), "weighted": round(weighted, 2)}, None
