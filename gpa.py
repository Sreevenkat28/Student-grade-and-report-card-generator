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

# Standard US percent -> letter conversion, used when grades are entered as percentages.
PERCENT_SCALE = [(93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"),
                 (73, "C"), (70, "C-"), (67, "D+"), (63, "D"), (60, "D-"), (0, "F")]


def percent_to_letter(pct):
    for low, letter in PERCENT_SCALE:
        if pct >= low:
            return letter


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def compute_gpa(rows):
    """rows: dicts with Course, Credits, Level and either Grade (letter) or Percent (0-100).

    Rows with neither a grade nor a percent are skipped (treated as in progress).
    Returns (result, error).
    """
    used = []
    for r in rows:
        course = str(r.get("Course") or "").strip()
        label = course or "a course"
        grade = str(r.get("Grade") or "").strip().upper()
        if grade == "NONE":
            grade = ""
        pct = _num(r.get("Percent"))
        if not grade and pct is None:
            continue
        if not grade:
            if not 0 <= pct <= 100:
                return None, f"The percentage for {label} must be between 0 and 100."
            grade = percent_to_letter(pct)
        if grade not in GRADE_POINTS:
            return None, f'"{grade}" is not a valid grade for {label}.'
        credits = _num(r.get("Credits"))
        if credits is None or credits <= 0:
            return None, f"Enter credits greater than 0 for {label}."
        level = r.get("Level") or "Regular"
        if level not in LEVEL_BONUS:
            return None, f"Unknown course level for {label}."
        base = GRADE_POINTS[grade]
        weighted = base + (LEVEL_BONUS[level] if base > 0 else 0.0)
        row = {"Course": course or "—", "Grade": grade, "Credits": credits, "Level": level,
               "Unweighted": base, "Weighted": round(weighted, 2)}
        if pct is not None:
            row = {"Course": row["Course"], "Percent": pct, **{k: v for k, v in row.items() if k != "Course"}}
        used.append(row)
    if not used:
        return None, "Enter a grade (or percentage) and credits for at least one course."
    credits_total = sum(u["Credits"] for u in used)
    unweighted = sum(u["Unweighted"] * u["Credits"] for u in used) / credits_total
    weighted = sum(u["Weighted"] * u["Credits"] for u in used) / credits_total
    return {"rows": used, "credits": round(credits_total, 2),
            "unweighted": round(unweighted, 2), "weighted": round(weighted, 2)}, None
