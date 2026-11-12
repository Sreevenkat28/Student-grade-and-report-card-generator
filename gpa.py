"""GPA on the standard US 4.0 scale, unweighted and weighted. No Streamlit imports."""
import math

# Standard unweighted 4.0 scale (plus/minus).
GRADE_POINTS = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}
GRADES = list(GRADE_POINTS)
# Extra points added for harder courses in the weighted GPA (not given for an F).
LEVEL_BONUS = {"Regular": 0.0, "Honors": 0.5, "AP / IB": 1.0, "Dual enrollment": 1.0}
LEVELS = list(LEVEL_BONUS)


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def compute_gpa(rows):
    """rows: dicts with Course, Grade, Credits, Level.

    Rows with no grade are skipped (treated as in progress). Returns (result, error).
    """
    used = []
    for r in rows:
        course = str(r.get("Course") or "").strip()
        grade = str(r.get("Grade") or "").strip().upper()
        if not grade or grade == "NONE":
            continue
        label = course or "a course"
        if grade not in GRADE_POINTS:
            return None, f'"{grade}" is not a valid grade for {label}.'
        credits = _num(r.get("Credits"))
        if credits is None or credits <= 0:
            return None, f"Enter credits greater than 0 for {label}."
        level = r.get("Level") or "Regular"
        if level not in LEVEL_BONUS:
            return None, f'Unknown course level for {label}.'
        base = GRADE_POINTS[grade]
        weighted = base + (LEVEL_BONUS[level] if base > 0 else 0.0)
        used.append({"Course": course or "—", "Grade": grade, "Credits": credits, "Level": level,
                     "Unweighted": base, "Weighted": round(weighted, 2)})
    if not used:
        return None, "Enter a grade and credits for at least one course."
    credits_total = sum(u["Credits"] for u in used)
    unweighted = sum(u["Unweighted"] * u["Credits"] for u in used) / credits_total
    weighted = sum(u["Weighted"] * u["Credits"] for u in used) / credits_total
    return {"rows": used, "credits": round(credits_total, 2),
            "unweighted": round(unweighted, 2), "weighted": round(weighted, 2)}, None
