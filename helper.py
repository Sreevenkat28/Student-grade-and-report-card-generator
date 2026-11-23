"""The study assistant's command engine: plain pattern matching over the signed-in user's own data.

It can change most settings in the app when asked. Anything destructive (removing a class or file, deleting
all grades) asks for a "yes" first. Account security (password, email, deleting the account) is never done
from chat; it points the user to the Account tab instead.
"""
import json
import re
from datetime import date

import assistant
import classes_db as cdb
import files_db
import gpa as gpa_lib
import grading
import overview
import prefs_db

HELP = """Here's what I can do. Just tell me in plain words:

**Your grades (feed every tab)**
- `my math grade is B+` · `set physics grade to 87%` · `I have an A in art` · `clear my art grade`

**Test scores & classes**
- `I got 45/50 in math` · `record 85% in english` · `undo my last grade` · `list my grades`
- `add classes physics, art` · `add class history to previous` · `move art to previous` · `finished math`
- `remove class art` · `delete all my grades` *(I'll ask you to confirm)*

**Reports & GPA**
- `how am I doing?` · `weakest class` · `what's my GPA?` · `gpa A, B+, 92%`
- `make a report card for Sam: math 80/100, science 45/50` (or just `make a report card` to use your recorded grades)
- `study plan 12 hours and save it` · `how can I improve?`

**Settings**
- `set pass mark to 50` · `overall pass mark 45` · `must pass every subject off`
- `set A to 85` · `set honors bonus to 0.5` · `set B+ points to 3.4` · `reset grading rules`
- `show grades as percentages` (or letters / both)
- `dark mode` · `light mode` · `auto theme` (match your device)
- `turn animations off` · `turn on click effects` · `typing effect off`

**Files & navigation**
- `list my files` · `show file notes.txt` · `delete file notes.txt`
- `go to GPA` · `open files` · `take me to the report card` · `log out` · `new chat`"""

TIPS = {
    "low": ["Re-learn the basics: go back to the first topics you lost track of and redo easy questions until they feel automatic.",
            "Study this class in short daily sessions (25-30 minutes) rather than one long session a week.",
            "Ask your teacher for the 2-3 topics that cost you the most marks, and start with those.",
            "Bring your errors to class or a study group and have someone explain them."],
    "mid": ["Do practice questions without notes, then check every wrong answer and write down why you got it wrong.",
            "Make a one-page summary of each unit and rewrite it from memory a few days later.",
            "Redo your last test's mistakes until you can solve them cold."],
    "good": ["Move from reviewing to testing yourself: past papers under timed conditions.",
             "Aim at the last few marks: check units, working and presentation on every answer.",
             "Teach a topic to a friend; gaps show up quickly."],
    "top": ["Keep it up with light weekly retrieval practice so nothing fades.",
            "Stretch yourself with harder problems or extension material."],
}
GENERAL = ["Study the hardest class first, when you're freshest.",
           "Use spaced repetition: review a topic after 1 day, 3 days, then a week.",
           "Sleep matters: a tired brain remembers far less."]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
NUM = r"\d+(?:\.\d+)?"
YES = {"yes", "y", "yep", "yeah", "sure", "ok", "okay", "confirm", "do it", "go ahead", "yes please"}
NO = {"no", "n", "nope", "cancel", "stop", "never mind", "nevermind", "dont", "don't"}


# ----------------------------------------------------------------- shared helpers
def _band(avg):
    return "low" if avg < 60 else "mid" if avg < 75 else "good" if avg < 88 else "top"


def _averages(user):
    """[(class, percent, count)] for classes that have a grade, weakest first (typed grade, else test average)."""
    out = [(r["name"], round(r["percent"], 1), r["n"]) for r in overview.class_table(user) if r["percent"] is not None]
    return sorted(out, key=lambda t: t[1])


def _match_class(user, raw):
    raw = " ".join(raw.split()).lower()
    all_c = cdb.list_classes(user)
    names = all_c["current"] + all_c["previous"]
    for n in names:
        if n.lower() == raw:
            return n
    hits = [n for n in names if n.lower().startswith(raw) or raw in n.lower()]
    return hits[0] if len(hits) == 1 else None


def _run(user, tool, args, tabs, actions):
    content, is_err, summary = assistant.run_tool(user, tool, args, {"tabs": tabs, "nav": None})
    actions.append(("⚠️ " if is_err else "✅ ") + summary)
    return json.loads(content), is_err


def _cap(name):
    """Keep what the user typed, but capitalise it if they typed all lowercase."""
    name = " ".join(name.split()).strip(" .,!?")
    return name if name != name.lower() else " ".join(w.capitalize() for w in name.split())


def _table(rows, head):
    return "| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n" + "\n".join(
        "| " + " | ".join(str(c) for c in r) + " |" for r in rows)


# ----------------------------------------------------------------- grades & classes
RECORD = re.compile(
    rf"^(?:please\s+)?(?:(?:i\s+)?(?:got|scored|made|earned)|record|log|add|enter|save)?\s*(?:a\s+|an\s+)?(?:score\s+of\s+|grade\s+of\s+)?"
    rf"(?P<m>{NUM})\s*(?:(?:/|out of)\s*(?P<mx>{NUM})|(?P<pct>%|percent))?\s*(?:in|for|on)\s+(?:my\s+)?"
    rf"(?P<c>[a-z][\w &.'-]{{0,50}}?)(?:\s+(?P<t>test|quiz|exam|assignment|homework|project|midterm|final|lab))?\s*[.!]?$")
ADD_CLASS = re.compile(r"^(?:please\s+)?(?:add|create|new)\s+(?:a\s+|my\s+)?(?:classes|class|subjects?|courses?)\s*:?\s*(?P<b>.+)$", re.I)
MOVE = re.compile(r"^(?:move|mark|put)\s+(?P<n>.+?)\s+(?:to|as|in)\s+(?:my\s+)?(?P<s>previous|past|completed|finished|done|current)(?:\s+classes)?$")
FINISHED = re.compile(r"^(?:i\s+)?(?:finished|completed|passed)\s+(?P<n>.+?)$")


def _record(user, m, tabs, actions):
    marks = float(m.group("m"))
    mx = 100.0 if m.group("pct") else float(m.group("mx") or 100)
    cls_raw = m.group("c").strip(" .,!?")
    cls = _match_class(user, cls_raw) or _cap(cls_raw)
    label = (m.group("t") or "").strip().capitalize()
    data, err = _run(user, "record_grade", {"class_name": cls, "marks": marks, "max_marks": mx, "label": label}, tabs, actions)
    if err:
        return f"I couldn't record that: {data.get('error')}"
    extra = " I added that class to your current classes." if data.get("class_was_created") else ""
    return f"Recorded **{cls}**: {marks:g}/{mx:g} (**{data['percent']:g}%**).{extra}"


def _add_classes(user, m, tabs, actions):
    body = m.group("b").strip()
    status = "current"
    sm = re.search(r"\s+(?:to|as|in)\s+(?:my\s+)?(previous|past|completed|finished|current)(?:\s+classes)?$", body, re.I)
    if sm:
        status = "current" if sm.group(1).lower() == "current" else "previous"
        body = body[: sm.start()]
    names = [_cap(n) for n in re.split(r"[,;]|\band\b", body) if n.strip()]
    if not names:
        return "Which classes? For example `add classes math, physics, art`."
    data, err = _run(user, "add_classes", {"names": names, "status": status}, tabs, actions)
    if err:
        return f"I couldn't add those: {data.get('error')}"
    return f"Added **{data['added']}** class(es) to your {status} classes." + ("" if data["added"] else " (They were already in your lists.)")


def _move(user, name, status, tabs, actions):
    cls = _match_class(user, name)
    if not cls:
        return f'I couldn\'t find a class called "{name.strip()}". Check the My classes tab for the exact name.'
    data, err = _run(user, "move_class", {"name": cls, "status": status}, tabs, actions)
    return f"I couldn't move it: {data.get('error')}" if err else f"Moved **{cls}** to your {status} classes."


def _set_class_grade(user, cls_raw, grade_text, tabs, actions):
    cls_raw = cls_raw.strip(" .,!?")
    cls = _match_class(user, cls_raw) or _cap(cls_raw)
    data, err = _run(user, "set_class_grade", {"class_name": cls, "grade": grade_text.strip(" .,!?")}, tabs, actions)
    if err:
        return f"I couldn't set that: {data.get('error')}"
    ov, shown = data["overall"], data["entered"]
    about = f" (about {data['percent']:g}%)" if data.get("percent") is not None and not shown.endswith("%") else ""
    extra = " I added that class to your current classes." if data.get("class_was_created") else ""
    gpa = f", GPA **{ov['gpa']:.2f}**" if ov.get("gpa") is not None else ""
    avg = f" Overall average is now **{ov['avg_percent']:g}%**{gpa}." if ov.get("avg_percent") is not None else ""
    return f"Set **{cls}** to **{shown}**{about}.{extra}{avg} Your Report card, GPA and summary are updated."


def _clear_class_grade(user, cls_raw, tabs, actions):
    cls = _match_class(user, cls_raw.strip(" .,!?"))
    if not cls:
        return f'I couldn\'t find a class called "{cls_raw.strip()}".'
    cdb.delete_final(user, cls)
    actions.append(f"✅ Cleared the grade for {cls}")
    return f"Cleared the grade for **{cls}**."


def _list_classes(user):
    my = cdb.list_classes(user)
    if not (my["current"] or my["previous"]):
        return "You haven't added any classes yet. Try `add classes math, physics, art`."
    return ("**Current:** " + (", ".join(my["current"]) or "none") + "\n\n**Previous:** " + (", ".join(my["previous"]) or "none"))


def _list_grades(user):
    gs = cdb.list_grades(user)
    if not gs:
        return "No grades recorded yet. Try `I got 45/50 in math`."
    rows = [(g["class"], g["label"] or "—", f"{g['marks']:g}/{g['max']:g}", f"{g['percent']:g}%") for g in gs[:25]]
    more = f"\n\n…and {len(gs) - 25} older ones." if len(gs) > 25 else ""
    return _table(rows, ["Class", "Label", "Score", "Percent"]) + more


def _undo_grade(user, actions):
    gs = cdb.list_grades(user)
    if not gs:
        return "There's no recorded grade to undo."
    g = gs[0]
    cdb.delete_grade(user, g["id"])
    actions.append(f"✅ Removed your latest grade ({g['class']} {g['percent']:g}%)")
    return f"Removed your most recent grade: **{g['class']}** {g['marks']:g}/{g['max']:g} ({g['percent']:g}%)."


# ----------------------------------------------------------------- progress, advice, GPA
def _progress(user):
    avgs = _averages(user)
    if not avgs:
        return "You haven't recorded any grades yet. Try `I got 45/50 in math`, or use the form in the My classes tab."
    scale, _ = prefs_db.load(user)
    msg = _table([(n, f"{a:g}%", grading.grade_for(scale, a)[0], c) for n, a, c in avgs], ["Class", "Average", "Grade", "Scores"]) + "\n\n"
    weakest, strongest = avgs[0], avgs[-1]
    if len(avgs) > 1:
        msg += f"Strongest: **{strongest[0]}** ({strongest[1]:g}%). Needs the most work: **{weakest[0]}** ({weakest[1]:g}%)."
    else:
        msg += f"Your only class with grades so far is **{weakest[0]}** ({weakest[1]:g}%)."
    return msg


def _improve(user):
    avgs = _averages(user)
    if not avgs:
        return ("Record some grades first so I can tailor advice to you (for example `I got 45/50 in math`). "
                "In the meantime:\n\n" + "\n".join(f"- {t}" for t in GENERAL))
    out = [f"**{n}** ({a:g}%):\n" + "\n".join(f"- {t}" for t in TIPS[_band(a)][:3]) for n, a, _c in avgs[:2]]
    out.append("**For every class:**\n" + "\n".join(f"- {t}" for t in GENERAL))
    out.append("Say `study plan` and I'll turn this into a weekly schedule.")
    return "\n\n".join(out)


def make_plan(user, hours):
    """Returns (markdown, error). Hours are split by how much each class needs."""
    my = cdb.list_classes(user)
    avg = {n.lower(): a for n, a, _c in _averages(user)}
    classes = list(my["current"]) or [n for n, _a, _c in _averages(user)]
    if not classes:
        return None, "Add your classes first (for example `add classes math, physics, art`), and record some grades."
    need = [max(100 - avg[c.lower()], 15) + 10 if c.lower() in avg else 40 for c in classes]
    total = float(sum(need))
    alloc = [max(0.5, round(hours * n / total * 2) / 2) for n in need]
    diff, guard = round(sum(alloc) - hours, 1), 0
    order = sorted(range(len(classes)), key=lambda i: -need[i])
    while abs(diff) >= 0.5 and guard < 200:
        guard += 1
        for i in (order if diff < 0 else reversed(order)):
            if diff < 0:
                alloc[i] += 0.5; diff += 0.5
            elif alloc[i] > 0.5:
                alloc[i] -= 0.5; diff -= 0.5
            if abs(diff) < 0.5:
                break
    rows = []
    for c, h in zip(classes, alloc):
        a = avg.get(c.lower())
        rows.append((c, a, "Add grades" if a is None else "Priority" if a < 60 else "Build up" if a < 80 else "Maintain", h))
    table = _table([(c, "—" if a is None else f"{a:g}%", f, f"{h:g}") for c, a, f, h in rows], ["Class", "Average", "Focus", "Hours / week"])
    chunks = []
    for c, _a, _f, h in sorted(rows, key=lambda r: -r[3]):
        left = h
        while left > 0:
            step = min(1.0, left)
            chunks.append((c, step)); left = round(left - step, 1)
    per_day, loads = [[] for _ in DAYS], [0.0] * len(DAYS)
    for c, step in chunks:
        d = min(range(len(DAYS)), key=lambda i: (loads[i], i))
        per_day[d].append(f"{c} ({step:g}h)"); loads[d] += step
    sched = "\n".join(f"- **{d}:** {', '.join(s) if s else 'Rest'}" for d, s in zip(DAYS, per_day))
    real = sum(alloc)
    note = "" if abs(real - hours) < 0.01 else f"\n\n_Each class gets at least 30 minutes, so this comes to {real:g} hours._"
    return (f"# Weekly study plan ({real:g} hours){note}\n\n{table}\n\n## Schedule\n{sched}\n- **Sun:** Review the week's mistakes "
            f"and plan next week (30 min)\n\n## Habits\n" + "\n".join(f"- {t}" for t in GENERAL)), None


def _plan(user, t, tabs, actions):
    hm = re.search(r"(\d+(?:\.\d+)?)\s*(?:h\b|hrs?\b|hours?\b)", t)
    hours = min(max(float(hm.group(1)), 2.0), 40.0) if hm else 8.0
    plan, err = make_plan(user, hours)
    if err:
        return err
    if re.search(r"\bsave\b", t):
        _d, e = _run(user, "save_note", {"title": "Study plan", "content": plan}, tabs, actions)
        return plan + "\n\n" + ("I couldn't save it." if e else "Saved to your **Files** tab as *Study plan.md*.")
    return plan + "\n\nSay `study plan and save it` to keep a copy in your Files tab. Add `12 hours` to change the weekly time."


def _gpa_from_tokens(user, body):
    """`gpa A, B+, 92%`: each chunk is a letter or a percent (1 credit each). Returns text or None."""
    chunks = [c.strip() for c in re.split(r"[,;]|\band\b", body) if c.strip()]
    if not chunks or not all(re.fullmatch(rf"(?:[a-f][+-]?|{NUM}\s*%)", c) for c in chunks):
        return None
    gs, lv = prefs_db.load_gpa(user)
    rows = [{"Course": f"Course {i + 1}", "Credits": 1.0, "Level": lv[0]["level"],
             **({"Percent": float(c.rstrip("% "))} if c.endswith("%") else {"Grade": c.upper()})} for i, c in enumerate(chunks)]
    res, err = gpa_lib.compute_gpa(rows, gs, lv)
    if err:
        return f"I couldn't work that out: {err}"
    return f"**GPA: {res['unweighted']:.2f}** (unweighted, {len(rows)} course(s), 1 credit each, using your GPA scale)."


def _gpa(user):
    rows = [r for r in overview.class_table(user) if r["gpa_letter"]]
    if not rows:
        return ("You haven't entered any grades yet. Type them in the **My grades** tab, or say `my math grade is B+`.")
    sm = overview.summary(user)
    gs, _lv = prefs_db.load_gpa(user)
    pts = {g["grade"].upper(): g["points"] for g in gs}
    table = _table([(r["name"], r["entered_text"] or (f"{r['percent']:g}%" if r["percent"] is not None else "—"),
                     r["gpa_letter"], f"{pts.get(r['gpa_letter'].upper(), 0):g}", f"{r['credits']:g}") for r in rows],
                   ["Class", "Grade", "Letter", "Points", "Credits"])
    return (f"**Unweighted GPA: {sm['gpa']:.2f}** · weighted {sm['gpa_weighted']:.2f}\n\n{table}\n\n"
            "Calculated from the grades in your **My grades** tab on your GPA scale.")


def _report(user, m, raw, out):
    """Build a report card from the typed subjects (or recorded averages) and show it in the Report card tab."""
    body = (m.group("b") or "").strip()
    name = _cap(m.group("name") or "") or user.title()
    items = []
    for chunk in [c for c in re.split(r"[,;]|\band\b", body) if c.strip()]:
        im = re.fullmatch(rf"\s*(?P<s>[a-z][a-z &.'-]*?)\s*[:=-]?\s*(?P<m>{NUM})\s*(?:(?:/|out of)\s*(?P<x>{NUM}))?\s*%?\s*", chunk)
        if not im:
            return "I couldn't read the subjects. Try: `make a report card for Sam: math 80/100, science 45/50`."
        items.append({"Subject": _cap(im.group("s")), "Marks": float(im.group("m")), "Max": float(im.group("x") or 100)})
    from_saved = False
    if not items:
        items = [{"Subject": n, "Marks": p, "Max": 100.0} for n, p in overview.report_prefill(user) if p is not None]
        from_saved = True
        if not items:
            return ("Give me some subjects, like `make a report card: math 80/100, science 45/50`, "
                    "or enter your grades in the **My grades** tab first.")
    scale, rules = prefs_db.load(user)
    res, err = grading.compute_result(items, scale, rules)
    if err:
        return f"I couldn't make the report card: {err}"
    if from_saved:
        res = overview.apply_entered_letters(user, res)
    out["report"] = ({"name": name, "roll": "", "cls": "", "exam": "Report card", "date": f"{date.today():%d %b %Y}"}, res)
    out["nav"] = out["tabs"]["Report card"]
    out["actions"].append("✅ Built a report card and opened it")
    verdict = "**PASS**" if res["passed"] else "**FAIL**"
    return (f"Here's the report card for **{name}**: {res['total']:g}/{res['max_total']:g} = **{res['pct']:g}%**, grade **{res['grade']}**, "
            f"{verdict}. I've opened it in the Report card tab.")


# ----------------------------------------------------------------- settings
def _num(m, key="n"):
    return float(m.group(key))


PASS_CMD = re.compile(
    rf"^(?:please\s+)?(?:(?:set|change|make|update|use)\s+)?(?:the\s+|my\s+)?(?:(?:overall|total|per[- ]subject|each subject|subject)\s+)?"
    rf"pass(?:ing)?\s*(?:mark|marks|grade|score|percent|percentage|requirement)?\s*"
    rf"(?:(?:overall|total|per[- ]subject|for each subject|for every subject)\s*)?(?:to|at|is|=|:)?\s*(?P<n>{NUM})\s*%?$")
REQUIRE_CMD = re.compile(
    r"^(?:please\s+)?(?:must pass|have to pass|need to pass|do i need to pass|require passing|require|don'?t require|do not require|"
    r"no longer require|turn (?:on|off)|stop requiring|(?:set|make) (?:it )?(?:so )?(?:that )?(?:i )?(?:must |have to |need to )?pass)\b.*\b(?:every|each|all) subjects?\b.*$")


def _pass_rules(user, t, actions):
    """Handle pass-mark commands. Returns text or None if t isn't one."""
    scale, rules = prefs_db.load(user)
    new, msg = dict(rules), None
    m = PASS_CMD.match(t)
    if m:
        v = float(m.group("n"))
        if "overall" in t or "total" in t:
            new["pass_overall"] = v; msg = f"overall pass mark to **{v:g}%**"
        elif "subject" in t:
            new["pass_subject"] = v; msg = f"per-subject pass mark to **{v:g}%**"
        else:
            new["pass_subject"] = new["pass_overall"] = v; msg = f"pass marks (per subject and overall) to **{v:g}%**"
    elif REQUIRE_CMD.match(t):
        off = bool(re.search(r"\b(don'?t|dont|do not|no longer|not|off|disable|without|stop)\b", t))
        new["require_all"] = not off
        msg = "passing every subject to " + ("**not required**" if off else "**required**")
    else:
        return None
    new, err = grading.clean_rules(new["pass_subject"], new["pass_overall"], new["require_all"])
    if err:
        return f"I couldn't change that: {err}"
    prefs_db.save(user, scale, new)
    actions.append("✅ Updated your pass rules")
    return "Done. I set " + msg + "."


def _set_grade_cutoff(user, g, n, actions):
    scale, rules = prefs_db.load(user)
    rows, found = [], False
    for r in scale:
        if r["grade"].lower() == g.lower():
            rows.append({"grade": r["grade"], "min": n, "remark": r["remark"]}); found = True
        else:
            rows.append(dict(r))
    if not found:
        rows.append({"grade": g.upper(), "min": n, "remark": ""})
    new, err = grading.clean_scale(rows)
    if err:
        return f"I couldn't change that: {err}"
    prefs_db.save(user, new, rules)
    actions.append(f"✅ Set grade {g.upper()} to start at {n:g}%")
    return f"Done. **{g.upper()}** now starts at **{n:g}%**. Your scale: " + ", ".join(f"{r['grade']} ≥{r['min']:g}" for r in new) + "."


def _set_gpa_points(user, g, n, actions):
    gs, lv = prefs_db.load_gpa(user)
    rows, found = [], False
    for r in gs:
        if r["grade"].lower() == g.lower():
            rows.append({**r, "points": n}); found = True
        else:
            rows.append(dict(r))
    if not found:
        return f'"{g.upper()}" isn\'t a grade in your GPA scale. Edit it in the Grading rules tab.'
    new, err = gpa_lib.clean_scale(rows)
    if err:
        return f"I couldn't change that: {err}"
    prefs_db.save_gpa(user, new, lv)
    actions.append(f"✅ Set {g.upper()} to {n:g} GPA points")
    return f"Done. **{g.upper()}** is now worth **{n:g}** GPA points."


def _set_level_bonus(user, lvl, n, actions):
    gs, lv = prefs_db.load_gpa(user)
    key = lvl.lower().replace("honours", "honors")
    hits = [r for r in lv if key in r["level"].lower() or r["level"].lower() in key]
    if len(hits) != 1:
        return "I couldn't tell which course level you mean. Your levels: " + ", ".join(r["level"] for r in lv) + "."
    new, err = gpa_lib.clean_levels([{**r, "bonus": n} if r is hits[0] else dict(r) for r in lv])
    if err:
        return f"I couldn't change that: {err}"
    prefs_db.save_gpa(user, gs, new)
    actions.append(f"✅ Set the {hits[0]['level']} bonus to {n:g}")
    return f"Done. **{hits[0]['level']}** courses now add **{n:g}** to the weighted GPA."


UI_WORDS = [("transitions", r"transition|tabs?\b"), ("click_fx", r"click|ripple|press|buttons?\b"), ("hover_fx", r"hover|lift"),
            ("typing_fx", r"typing|typewriter|type effect"), ("cards_fx", r"cards?\b|fade|pop")]


def _ui_command(user, t, out):
    """`turn animations off`, `typing effect on`... Returns text or None."""
    if not re.search(r"\b(animations?|motion|effects?|transitions?|ripple|hover|typing|typewriter|fade)\b", t):
        return None
    on = re.search(r"\b(on|enable|enabled|start|show|add|bring back)\b", t)
    off = re.search(r"\b(off|disable|disabled|stop|hide|remove|without|no)\b", t)
    if not (on or off) or (on and off):
        return None
    value = bool(on) and not off
    key = next((k for k, pat in UI_WORDS if re.search(pat, t)), "animations")
    ui = prefs_db.load_ui(user)
    ui[key] = value
    if key != "animations" and value:
        ui["animations"] = True  # turning a single effect on implies the master switch is on
    prefs_db.save_ui(user, ui)
    out["set_state"].update({f"ui_{k}": v for k, v in ui.items()})
    out["actions"].append(f"✅ {prefs_db.UI_LABELS[key]}: {'on' if value else 'off'}")
    return f"Okay, **{prefs_db.UI_LABELS[key].lower()}** is now **{'on' if value else 'off'}**."


def _theme_command(user, t, out):
    """`dark mode`, `turn off dark mode`, `switch to light theme`, `auto theme`. Returns text or None."""
    if len(t.split()) > 8 or not re.search(r"\b(mode|theme|appearance)\b", t):
        return None
    word = re.search(r"\b(dark|night|light|auto|automatic|system)\b", t)
    if not word and not re.search(r"match (?:my )?(?:device|system)", t):
        return None
    w = word.group(1) if word else "auto"
    off = bool(re.search(r"\b(off|disable|stop|no)\b", t))
    if w in ("auto", "automatic", "system"):
        theme = "Auto"
    elif w in ("dark", "night"):
        theme = "Light" if off else "Dark"
    else:
        theme = "Dark" if off else "Light"
    prefs_db.save_theme(user, theme)
    out["set_state"]["theme_mode"] = theme
    out["actions"].append(f"✅ Theme: {theme.lower()}")
    return {"Dark": "Dark mode is on. 🌙", "Light": "Light mode is on. ☀️",
            "Auto": "Theme set to **auto**: it will follow your device's light/dark setting."}[theme]


def _display_command(user, t, out):
    m = re.search(r"\b(?:show|display|use|see)\b.*?\b(?:grades?\s+)?(?:as|in)\s+(?P<m>letters?|percent(?:age)?s?|both)\b", t) or \
        re.search(r"\b(?:use|show)\s+(?P<m>letter|percentage|percent)\s+grades?\b", t)
    if not m:
        return None
    w = m.group("m")
    mode = "Both" if w == "both" else "Letter grades" if w.startswith("letter") else "Percentages"
    prefs_db.save_display(user, mode)
    out["set_state"]["display_mode"] = mode
    out["actions"].append(f"✅ Showing grades as {mode.lower()}")
    return f"Done. Grades will now show as **{mode.lower()}**."


# ----------------------------------------------------------------- files, navigation
def _files(user):
    fs = files_db.list_files(user)
    if not fs:
        return "You have no files yet. Add some in the **Files** tab."
    return "Your files:\n\n" + "\n".join(f"- {f['name']} ({f['size'] // 1024 or 1} KB)" for f in fs)


def _show_file(user, name):
    fid = files_db.find_by_name(user, name.strip())
    got = files_db.get_file(user, fid) if fid else None
    if not got:
        return f'I couldn\'t find a file called "{name.strip()}". Say `list my files` to see them.'
    text, err = files_db.extract_text(got[0], got[2], limit=1500)
    return f"**{got[0]}**\n\n```\n{text}\n```" if text else f"I can't show **{got[0]}** here: {err}"


def _tab_for(text, tabs):
    t = re.sub(r"[^a-z ]", "", text.lower()).strip()
    t = re.sub(r"^(?:the|my)\s+", "", t)
    t = re.sub(r"\s+(?:tab|page|section)$", "", t)
    for key in tabs:
        if t == key.lower():
            return key
    for key in tabs:
        if key.lower() in t.split() or t in key.lower().split():
            return key
    return None


LETTER = r"[a-f][+-]?"
SET_GRADE_A = re.compile(r"^(?:please\s+)?(?:set|change|update|make)\s+(?:my\s+)?(?P<c>.+?)\s+grade\s+(?:to|as|=)\s+(?P<g>.+)$")
SET_GRADE_B = re.compile(r"^(?:my\s+)?(?P<c>.+?)\s+grade\s+(?:is|=|now)\s+(?:an?\s+)?(?P<g>.+)$")
SET_GRADE_C = re.compile(rf"^i\s+(?:have|got|get|am getting|'m getting)\s+(?:an?\s+)?(?P<g>{LETTER})\s+(?:in|for|on)\s+(?:my\s+)?(?P<c>.+)$")
SET_GRADE_D = re.compile(rf"^i\s+(?:have|got|am at|'m at)\s+(?:an?\s+)?(?P<g>{NUM}\s*%)\s+(?:in|for|on)\s+(?:my\s+)?(?P<c>.+?)\s+(?:overall|right now|currently|now)$")
CLEAR_GRADE = re.compile(r"^(?:please\s+)?(?:clear|remove|reset)\s+(?:my\s+)?(?P<c>.+?)\s+grade$")

GOTO = re.compile(r"^(?:please\s+)?(?:go to|open|show|take me to|switch to|navigate to|view)\s+(?P<t>.+)$")
REPORT = re.compile(r"^(?:please\s+)?(?:make|create|generate|build|calculate|do)\s+(?:me\s+)?(?:a\s+|my\s+)?report\s*card"
                    r"(?:\s+for\s+(?P<name>[^:]{1,40}?)\s*:)?\s*[:\-]?\s*(?P<b>.*)$", re.I)


# ----------------------------------------------------------------- confirmations
def _confirm(user, pending, out):
    kind = pending["kind"]
    if kind == "remove_class":
        _d, err = _run(user, "remove_class", {"name": pending["name"], "confirmed": True}, out["tabs"], out["actions"])
        return "I couldn't remove it." if err else f"Removed the class **{pending['name']}**."
    if kind == "delete_file":
        files_db.delete_file(user, pending["id"])
        out["actions"].append(f"✅ Deleted {pending['name']}")
        return f"Deleted **{pending['name']}**."
    if kind == "delete_all_grades":
        for g in cdb.list_grades(user):
            cdb.delete_grade(user, g["id"])
        out["actions"].append("✅ Deleted all recorded grades")
        return "All your recorded grades are deleted."
    return "Okay."


# ----------------------------------------------------------------- entry point
def handle(user, text, tabs, state=None):
    """One message to the assistant.

    Returns {"text","actions","nav","error","report","set_state","clear","logout","tabs"}. `state` is a dict the
    caller keeps between messages (used to remember a pending confirmation).
    """
    state = state if state is not None else {}
    out = {"text": "", "actions": [], "nav": None, "error": None, "report": None, "set_state": {},
           "clear": False, "logout": False, "tabs": tabs}
    raw = (text or "").strip()[:assistant.MAX_USER_CHARS]
    if not raw:
        out["error"] = "Type a message first."
        return out
    t = " ".join(raw.lower().split())
    actions = out["actions"]

    pending = state.pop("pending", None)
    if pending:
        if t in YES:
            out["text"] = _confirm(user, pending, out)
            return out
        if t in NO:
            out["text"] = "Okay, I won't do that."
            return out
        # anything else cancels the pending action and is handled as a new command

    m = GOTO.match(t)
    if m and _tab_for(m.group("t"), tabs):
        key = _tab_for(m.group("t"), tabs)
        out["nav"] = tabs[key]
        actions.append(f"✅ Opened the {key} tab")
        out["text"] = f"Opening **{key}**."
        return out

    if re.fullmatch(r"(?:help|\?|what can you do\??|commands|hi|hello|hey|hi there)", t):
        out["text"] = HELP
    elif re.fullmatch(r"(?:new chat|clear chat|clear|start over|reset chat)", t):
        out["clear"] = True
        out["text"] = "Chat cleared."
    elif re.fullmatch(r"(?:log ?out|sign ?out)", t):
        out["logout"] = True
        out["text"] = "Logging you out…"
    elif re.search(r"\b(change|reset|update|forgot)\b.*\b(password|email)\b|\bdelete\b.*\baccount\b", t):
        out["nav"] = tabs["Account"]
        out["text"] = ("For your security I don't change passwords, emails or accounts from chat. "
                       "I've opened the **Account** tab, where you can do that safely.")
    elif re.search(r"\b(undo|remove|delete)\b.*\blast grade\b", t):
        out["text"] = _undo_grade(user, actions)
    elif re.search(r"\b(delete|remove|clear)\b.*\b(all|every)\b.*\bgrades\b", t):
        state["pending"] = {"kind": "delete_all_grades"}
        out["text"] = "This will delete **all** your recorded grades. Reply **yes** to confirm or **no** to cancel."
    elif (m := re.match(r"^(?:please\s+)?(?:remove|delete|drop)\s+(?:the\s+)?class\s+(?P<n>.+)$", t)):
        cls = _match_class(user, m.group("n"))
        if not cls:
            out["text"] = f'I couldn\'t find a class called "{m.group("n").strip()}".'
        else:
            state["pending"] = {"kind": "remove_class", "name": cls}
            out["text"] = f"Remove the class **{cls}**? Its recorded grades stay. Reply **yes** to confirm or **no** to cancel."
    elif (m := re.match(r"^(?:please\s+)?(?:delete|remove)\s+(?:the\s+)?file\s+(?P<n>.+)$", raw.lower())):
        fid = files_db.find_by_name(user, m.group("n").strip())
        if not fid:
            out["text"] = f'I couldn\'t find a file called "{m.group("n").strip()}".'
        else:
            name = next(f["name"] for f in files_db.list_files(user) if f["id"] == fid)
            state["pending"] = {"kind": "delete_file", "id": fid, "name": name}
            out["text"] = f"Delete the file **{name}** permanently? Reply **yes** to confirm or **no** to cancel."
    elif (m := re.match(r"^(?:show|read|open|preview|view)\s+(?:the\s+)?file\s+(?P<n>.+)$", raw.lower())):
        out["text"] = _show_file(user, m.group("n"))
    elif (m := REPORT.match(raw)):
        out["text"] = _report(user, m, raw, out)
    elif (txt := _theme_command(user, t, out)):
        out["text"] = txt
    elif (txt := _display_command(user, t, out)):
        out["text"] = txt
    elif (txt := _ui_command(user, t, out)):
        out["text"] = txt
    elif re.search(r"\breset\b.*\bgpa\b", t):
        prefs_db.reset_gpa(user)
        actions.append("✅ Reset your GPA scale")
        out["text"] = "Your GPA scale is back to the defaults."
    elif re.search(r"\breset\b.*\b(grading rules|grade scale|scale|pass marks?)\b", t):
        prefs_db.reset(user)
        actions.append("✅ Reset your grading rules")
        out["text"] = "Your grading rules are back to the defaults."
    elif (m := re.match(rf"^(?:please\s+)?(?:set|change|make|update)\s+(?P<l>honou?rs|ap(?:\s*/\s*ib)?|ib|dual(?:\s+enrollment)?|regular)\s+"
                        rf"(?:bonus|weight|boost)\s*(?:to|at|=)?\s*(?P<n>{NUM})$", t)):
        out["text"] = _set_level_bonus(user, m.group("l"), _num(m), actions)
    elif (m := re.match(rf"^(?:please\s+)?(?:set|change|make|update)\s+(?P<g>[a-f][+-]?)\s+(?:gpa\s+)?points?\s*(?:to|at|=)?\s*(?P<n>{NUM})$", t)):
        out["text"] = _set_gpa_points(user, m.group("g"), _num(m), actions)
    elif (m := re.match(rf"^(?:please\s+)?(?:set|change|make|update)\s+(?:grade\s+)?(?P<g>[a-f][+-]?)\s+(?:to|at|=|start(?:s)?(?:\s+at)?|minimum|min|needs?|requires?)\s*(?P<n>{NUM})\s*%?$", t)) \
            or (m := re.match(rf"^(?:grade\s+)?(?P<g>[a-f][+-]?)\s+(?:needs?|requires?|starts?\s+at)\s+(?P<n>{NUM})\s*%?$", t)):
        out["text"] = _set_grade_cutoff(user, m.group("g"), _num(m), actions)
    elif (txt := _pass_rules(user, t, actions)):
        out["text"] = txt
    elif (m := CLEAR_GRADE.match(t)):
        out["text"] = _clear_class_grade(user, m.group("c"), tabs, actions)
    elif (m := SET_GRADE_A.match(t)) or (m := SET_GRADE_D.match(t)) or (m := SET_GRADE_C.match(t)) \
            or ((m := SET_GRADE_B.match(t)) and not re.search(r"\b(?:pass|cut|minimum|point)", t)):
        out["text"] = _set_class_grade(user, m.group("c"), m.group("g"), tabs, actions)
    elif (m := RECORD.match(t)):
        out["text"] = _record(user, m, tabs, actions)
    elif (m := ADD_CLASS.match(raw)):
        out["text"] = _add_classes(user, m, tabs, actions)
    elif (m := MOVE.match(t)):
        out["text"] = _move(user, m.group("n"), "current" if m.group("s") == "current" else "previous", tabs, actions)
    elif (m := FINISHED.match(t)):
        out["text"] = _move(user, m.group("n"), "previous", tabs, actions)
    elif re.search(r"\b(list|show|what are)\b.*\bclasses\b", t):
        out["text"] = _list_classes(user)
    elif re.search(r"\b(list|show)\b.*\b(recorded |my )?grades\b", t):
        out["text"] = _list_grades(user)
    elif re.search(r"\b(study )?(plan|schedule|timetable)\b", t):
        out["text"] = _plan(user, t, tabs, actions)
    elif (m := re.match(r"^(?:what(?:'s| is)\s+)?(?:the\s+|my\s+)?gpa\s*(?:of|for|from|if i (?:get|got|have))?\s*:?\s*(?P<b>.*)$", t)) and m.group("b") \
            and (txt := _gpa_from_tokens(user, m.group("b"))):
        out["text"] = txt
    elif re.search(r"\bgpa\b", t):
        out["text"] = _gpa(user)
    elif re.search(r"\b(improve|improvement|tips?|advice|get better|study better|help me study)\b", t):
        out["text"] = _improve(user)
    elif re.search(r"\b(files?|documents?|pdfs?)\b", t):
        out["text"] = _files(user)
    elif re.search(r"\b(how am i doing|progress|summary|overview|averages?|weak(?:est)?|strong(?:est)?|stats?|my grades|performance|how are my)\b", t):
        out["text"] = _progress(user)
    else:
        out["text"] = "Sorry, I didn't catch that.\n\n" + HELP
    return out
