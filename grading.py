"""Report-card grading with a user-editable scale and pass rules. No Streamlit imports."""
import math

DEFAULT_SCALE = [
    {"grade": "A+", "min": 90.0, "remark": "Outstanding"},
    {"grade": "A", "min": 80.0, "remark": "Excellent"},
    {"grade": "B+", "min": 70.0, "remark": "Very Good"},
    {"grade": "B", "min": 60.0, "remark": "Good"},
    {"grade": "C", "min": 50.0, "remark": "Satisfactory"},
    {"grade": "D", "min": 40.0, "remark": "Needs Improvement"},
    {"grade": "F", "min": 0.0, "remark": "Fail"},
]
DEFAULT_RULES = {"pass_subject": 40.0, "pass_overall": 40.0, "require_all": True}
MAX_GRADES = 15


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def clean_scale(rows):
    """Validate a grade scale (list of dicts with grade/min/remark).

    Returns (scale_sorted_high_to_low, error). Rules: 2-15 grades, unique non-blank names,
    minimums between 0 and 100 and all different, and exactly one grade starting at 0
    so every percentage gets a grade.
    """
    out, names = [], set()
    for r in rows:
        grade = str(r.get("grade") or "").strip()
        mn = _num(r.get("min"))
        remark = str(r.get("remark") or "").strip()
        if not grade and mn is None and not remark:
            continue  # blank row
        if not grade:
            return None, "Every grade needs a name (for example A or B+)."
        if grade.lower() in names:
            return None, f'The grade "{grade}" appears more than once.'
        if mn is None or not 0 <= mn <= 100:
            return None, f'The minimum % for "{grade}" must be a number from 0 to 100.'
        names.add(grade.lower())
        out.append({"grade": grade[:6], "min": round(mn, 2), "remark": remark[:40]})
    if len(out) < 2:
        return None, "Keep at least two grades."
    if len(out) > MAX_GRADES:
        return None, f"Use at most {MAX_GRADES} grades."
    out.sort(key=lambda g: -g["min"])
    mins = [g["min"] for g in out]
    if len(set(mins)) != len(mins):
        return None, "Two grades have the same minimum %. Each grade needs its own cut-off."
    if mins[-1] != 0:
        return None, "The lowest grade must start at 0% so every score gets a grade."
    return out, None


def clean_rules(pass_subject, pass_overall, require_all):
    ps, po = _num(pass_subject), _num(pass_overall)
    if ps is None or not 0 <= ps <= 100 or po is None or not 0 <= po <= 100:
        return None, "Pass marks must be numbers from 0 to 100."
    return {"pass_subject": round(ps, 2), "pass_overall": round(po, 2),
            "require_all": bool(require_all)}, None


def grade_for(scale, pct):
    for g in scale:  # scale is sorted high -> low
        if pct >= g["min"]:
            return g["grade"], g["remark"]
    last = scale[-1]
    return last["grade"], last["remark"]


def compute_result(rows, scale=None, rules=None):
    """rows: dicts with Subject, Marks, Max. Returns (result, error)."""
    scale = scale or DEFAULT_SCALE
    rules = {**DEFAULT_RULES, **(rules or {})}
    if not rows:
        return None, "Add at least one subject."
    out = []
    for r in rows:
        name = str(r.get("Subject") or "").strip()
        marks, mx = _num(r.get("Marks")), _num(r.get("Max"))
        if not name:
            return None, "Every subject needs a name."
        if mx is None or mx <= 0:
            return None, f'Maximum marks for "{name}" must be greater than 0.'
        if marks is None:
            return None, f'Enter marks for "{name}".'
        if marks < 0:
            return None, f'Marks for "{name}" cannot be negative.'
        if marks > mx:
            return None, f'Marks for "{name}" ({marks:g}) exceed the maximum ({mx:g}).'
        pct = round(marks / mx * 100, 2)
        out.append({
            "Subject": name, "Marks": marks, "Max": mx, "%": pct,
            "Grade": grade_for(scale, pct)[0],
            "Status": "Pass" if pct >= rules["pass_subject"] else "Fail",
        })
    total = round(sum(o["Marks"] for o in out), 2)
    max_total = round(sum(o["Max"] for o in out), 2)
    pct = round(total / max_total * 100, 2)
    failed = [o["Subject"] for o in out if o["Status"] == "Fail"]
    overall_ok = pct >= rules["pass_overall"]
    passed = overall_ok and (not failed or not rules["require_all"])
    grade, remark = grade_for(scale, pct)
    if not passed:
        if not overall_ok:
            remark = f"Overall below the {rules['pass_overall']:g}% pass mark"
        else:
            remark = "Must reappear in failed subject(s)"
    return {"rows": out, "total": total, "max_total": max_total, "pct": pct,
            "grade": grade, "remark": remark, "passed": passed, "failed": failed}, None
