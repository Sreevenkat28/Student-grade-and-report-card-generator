"""Free study helper: understands simple commands with plain pattern matching. No AI service, no cost.

Reuses the same scoped actions as the AI assistant (assistant.run_tool), so it can only touch the
signed-in user's own data.
"""
import json
import math
import re

import assistant
import classes_db as cdb
import files_db
import gpa as gpa_lib
import grading
import prefs_db

HELP = """I'm the built-in helper (no AI, no cost). Try things like:

- **Record a grade:** `I got 45/50 in math`, `record 85% in english`, `log 18 out of 20 in biology quiz`
- **Classes:** `add classes physics, art` · `add class history to previous` · `move art to previous` · `finished math`
- **How am I doing:** `how am I doing?` · `my averages` · `weakest class`
- **GPA:** `what's my GPA?`
- **Study plan:** `make a study plan` · `study plan 12 hours` · `study plan and save it`
- **Improve:** `how can I improve?` · `study tips`
- **Files:** `list my files`
- **Navigate:** `go to GPA` · `open files` · `show my classes`"""

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


def _band(avg):
    return "low" if avg < 60 else "mid" if avg < 75 else "good" if avg < 88 else "top"


def _averages(user):
    """[(class, avg_percent, count)] for classes with recorded grades, weakest first."""
    per = {}
    for g in cdb.list_grades(user):
        per.setdefault(g["class"].lower(), [g["class"], []])[1].append(g["percent"])
    out = [(name, round(sum(p) / len(p), 1), len(p)) for name, p in per.values()]
    return sorted(out, key=lambda t: t[1])


def _match_class(user, raw):
    """Resolve what the user typed to an existing class if there is a clear match."""
    raw = " ".join(raw.split()).lower()
    all_c = cdb.list_classes(user)
    names = all_c["current"] + all_c["previous"]
    for n in names:
        if n.lower() == raw:
            return n
    hits = [n for n in names if n.lower().startswith(raw) or raw in n.lower()]
    return hits[0] if len(hits) == 1 else None


def _run(user, tool, args, tabs, actions, state):
    content, is_err, summary = assistant.run_tool(user, tool, args, {"tabs": tabs, "nav": None, "state": state})
    actions.append(("⚠️ " if is_err else "✅ ") + summary)
    return json.loads(content), is_err


# ----------------------------------------------------------------- intents
def _record(user, m, tabs, actions):
    marks = float(m.group("m"))
    if m.group("pct"):
        mx = 100.0
    else:
        mx = float(m.group("mx") or 100)
    cls_raw = m.group("c").strip(" .,!?")
    cls = _match_class(user, cls_raw) or " ".join(w.capitalize() for w in cls_raw.split())
    label = (m.group("t") or "").strip().capitalize()
    data, err = _run(user, "record_grade", {"class_name": cls, "marks": marks, "max_marks": mx, "label": label},
                     tabs, actions, None)
    if err:
        return f"I couldn't record that: {data.get('error')}"
    extra = " I added that class to your current classes." if data.get("class_was_created") else ""
    return f"Recorded **{cls}**: {marks:g}/{mx:g} (**{data['percent']:g}%**).{extra}"


def _progress(user):
    avgs = _averages(user)
    if not avgs:
        return "You haven't recorded any grades yet. Try `I got 45/50 in math`, or use the form in the My classes tab."
    scale, _ = prefs_db.load(user)
    rows = "\n".join(f"| {n} | {a:g}% | {grading.grade_for(scale, a)[0]} | {c} |" for n, a, c in avgs)
    weakest, strongest = avgs[0], avgs[-1]
    msg = f"| Class | Average | Grade | Scores |\n|---|---|---|---|\n{rows}\n\n"
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
    out = []
    for name, avg, _n in avgs[:2]:
        band = _band(avg)
        out.append(f"**{name}** ({avg:g}%):\n" + "\n".join(f"- {t}" for t in TIPS[band][:3]))
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
    need = []
    for c in classes:
        a = avg.get(c.lower())
        need.append(max(100 - a, 15) + 10 if a is not None else 40)
    total = float(sum(need))
    alloc = [max(0.5, round(hours * n / total * 2) / 2) for n in need]
    # trim or pad to the requested hours without dropping below 0.5h each
    diff = round(sum(alloc) - hours, 1)
    order = sorted(range(len(classes)), key=lambda i: -need[i])
    guard = 0
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
    for c, h, n in zip(classes, alloc, need):
        a = avg.get(c.lower())
        focus = "Add grades" if a is None else "Priority" if a < 60 else "Build up" if a < 80 else "Maintain"
        rows.append((c, a, focus, h))
    table = "| Class | Average | Focus | Hours / week |\n|---|---|---|---|\n" + "\n".join(
        f"| {c} | {'—' if a is None else f'{a:g}%'} | {f} | {h:g} |" for c, a, f, h in rows)
    # spread 1-hour (or shorter) sessions across Mon-Sat, hardest classes first
    chunks = []
    for c, _a, _f, h in sorted(rows, key=lambda r: -r[3]):
        left = h
        while left > 0:
            step = min(1.0, left)
            chunks.append((c, step)); left = round(left - step, 1)
    per_day = [[] for _ in DAYS]
    loads = [0.0] * len(DAYS)
    for c, step in chunks:
        d = min(range(len(DAYS)), key=lambda i: (loads[i], i))
        per_day[d].append(f"{c} ({step:g}h)"); loads[d] += step
    sched = "\n".join(f"- **{d}:** {', '.join(s) if s else 'Rest'}" for d, s in zip(DAYS, per_day))
    real = sum(alloc)
    note = "" if abs(real - hours) < 0.01 else f"\n\n_Each class gets at least 30 minutes, so this comes to {real:g} hours._"
    plan = (f"# Weekly study plan ({real:g} hours){note}\n\n{table}\n\n## Schedule\n{sched}\n- **Sun:** Review the week's mistakes "
            f"and plan next week (30 min)\n\n## Habits\n" + "\n".join(f"- {t}" for t in GENERAL))
    return plan, None


def _plan(user, text, tabs, actions):
    hm = re.search(r"(\d+(?:\.\d+)?)\s*(?:h\b|hrs?\b|hours?\b)", text)
    hours = min(max(float(hm.group(1)), 2.0), 40.0) if hm else 8.0
    plan, err = make_plan(user, hours)
    if err:
        return err
    msg = plan
    if re.search(r"\bsave\b", text):
        _data, e = _run(user, "save_note", {"title": "Study plan", "content": plan}, tabs, actions, None)
        msg += "\n\n" + ("I couldn't save it." if e else "Saved to your **Files** tab as *Study plan.md*.")
    else:
        msg += "\n\nSay `study plan and save it` to keep a copy in your Files tab. Add `12 hours` to change the weekly time."
    return msg


def _gpa(user):
    avgs = _averages(user)
    if not avgs:
        return "Record some grades first (for example `I got 45/50 in math`) and I'll work out your GPA."
    gs, lv = prefs_db.load_gpa(user)
    rows = [{"Course": n, "Percent": a, "Credits": 1.0, "Level": lv[0]["level"]} for n, a, _c in avgs]
    res, err = gpa_lib.compute_gpa(rows, gs, lv)
    if err:
        return f"I couldn't work that out: {err}"
    lines = "\n".join(f"| {r['Course']} | {r['Percent']:g}% | {r['Grade']} | {r['Unweighted']:g} |" for r in res["rows"])
    return (f"**Unweighted GPA: {res['unweighted']:.2f}**\n\n| Class | Average | Grade | Points |\n|---|---|---|---|\n{lines}\n\n"
            "I used each class's average percent, 1 credit each, on your GPA scale. For weighted GPA or different credits, use the GPA tab.")


def _files(user):
    fs = files_db.list_files(user)
    if not fs:
        return "You have no files yet. Add some in the **Files** tab."
    return "Your files:\n\n" + "\n".join(f"- {f['name']} ({f['size'] // 1024 or 1} KB)" for f in fs)


def _add_classes(user, m, tabs, actions):
    body = m.group("b").strip()
    status = "current"
    sm = re.search(r"\s+(?:to|as|in)\s+(?:my\s+)?(previous|past|completed|finished|current)(?:\s+classes)?$", body)
    if sm:
        status = "previous" if sm.group(1) != "current" else "current"
        body = body[: sm.start()]
    names = [n.strip() for n in re.split(r"[,;]|\band\b", body) if n.strip()]
    names = [n if n != n.lower() else " ".join(w.capitalize() for w in n.split()) for n in names]
    if not names:
        return "Which classes? For example `add classes math, physics, art`."
    data, err = _run(user, "add_classes", {"names": names, "status": status}, tabs, actions, None)
    if err:
        return f"I couldn't add those: {data.get('error')}"
    return f"Added **{data['added']}** class(es) to your {status} classes." + (
        "" if data["added"] else " (They were already in your lists.)")


def _move(user, name, status, tabs, actions):
    cls = _match_class(user, name)
    if not cls:
        return f'I couldn\'t find a class called "{name.strip()}". Check the My classes tab for the exact name.'
    data, err = _run(user, "move_class", {"name": cls, "status": status}, tabs, actions, None)
    return f"I couldn't move it: {data.get('error')}" if err else f"Moved **{cls}** to your {status} classes."


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


NUM = r"\d+(?:\.\d+)?"
RECORD = re.compile(
    rf"^(?:please\s+)?(?:(?:i\s+)?(?:got|scored|made|earned)|record|log|add|enter|save)?\s*(?:a\s+|an\s+)?(?:score\s+of\s+|grade\s+of\s+)?"
    rf"(?P<m>{NUM})\s*(?:(?:/|out of)\s*(?P<mx>{NUM})|(?P<pct>%|percent))?\s*(?:in|for|on)\s+(?:my\s+)?"
    rf"(?P<c>[a-z][\w &.'-]{{0,50}}?)(?:\s+(?P<t>test|quiz|exam|assignment|homework|project|midterm|final|lab))?\s*[.!]?$")
ADD_CLASS = re.compile(r"^(?:please\s+)?(?:add|create|new)\s+(?:a\s+|my\s+)?(?:classes|class|subjects?|courses?)\s*:?\s*(?P<b>.+)$", re.I)
MOVE = re.compile(r"^(?:move|mark|put)\s+(?P<n>.+?)\s+(?:to|as|in)\s+(?:my\s+)?(?P<s>previous|past|completed|finished|done|current)(?:\s+classes)?$")
FINISHED = re.compile(r"^(?:i\s+)?(?:finished|completed|passed)\s+(?P<n>.+?)$")
GOTO = re.compile(r"^(?:please\s+)?(?:go to|open|show|take me to|switch to|navigate to|view)\s+(?P<t>.+)$")


def handle(user, text, tabs):
    """Returns {"text", "actions", "nav", "error"} for one message to the free helper."""
    out = {"text": "", "actions": [], "nav": None, "error": None}
    raw = (text or "").strip()[:assistant.MAX_USER_CHARS]
    if not raw:
        out["error"] = "Type a message first."
        return out
    t = " ".join(raw.lower().split())
    actions = out["actions"]

    m = GOTO.match(t)
    if m and _tab_for(m.group("t"), tabs):
        key = _tab_for(m.group("t"), tabs)
        out["nav"] = tabs[key]
        actions.append(f"✅ Opened the {key} tab")
        out["text"] = f"Opening **{key}**."
        return out
    if re.fullmatch(r"(?:help|\?|what can you do\??|commands|hi|hello|hey)", t):
        out["text"] = HELP
    elif (m := RECORD.match(t)):
        out["text"] = _record(user, m, tabs, actions)
    elif (m := ADD_CLASS.match(raw)):
        out["text"] = _add_classes(user, m, tabs, actions)
    elif (m := MOVE.match(t)):
        out["text"] = _move(user, m.group("n"), "current" if m.group("s") == "current" else "previous", tabs, actions)
    elif (m := FINISHED.match(t)):
        out["text"] = _move(user, m.group("n"), "previous", tabs, actions)
    elif re.search(r"\b(study )?(plan|schedule|timetable)\b", t):
        out["text"] = _plan(user, t, tabs, actions)
    elif re.search(r"\bgpa\b", t):
        out["text"] = _gpa(user)
    elif re.search(r"\b(improve|improvement|tips?|advice|get better|study better|help me study)\b", t):
        out["text"] = _improve(user)
    elif re.search(r"\b(files?|documents?|pdfs?)\b", t):
        out["text"] = _files(user)
    elif re.search(r"\b(how am i doing|progress|summary|overview|averages?|weak(?:est)?|strong(?:est)?|stats?|my grades|performance|how are my)\b", t):
        out["text"] = _progress(user)
    else:
        out["text"] = ("I didn't understand that. I'm a simple built-in helper, so I work best with short commands.\n\n" + HELP)
    return out
