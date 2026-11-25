"""Classrooms: teachers create them, students join with a code. Every teacher action checks ownership here,
so the screens can't be used to read or change somebody else's classroom.
"""
import mimetypes
import secrets
import sqlite3
import time

import auth
import files_db

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
CODE_LENGTH = 8
MAX_ROOMS = 20
MAX_STUDENTS = 200
MAX_ASSIGNMENTS = 100
MAX_MATERIALS = 30
MAX_NAME = 60


def _conn():
    c = sqlite3.connect(auth.DB_PATH)
    c.executescript(
        "CREATE TABLE IF NOT EXISTS rooms (id INTEGER PRIMARY KEY AUTOINCREMENT, teacher TEXT NOT NULL, name TEXT NOT NULL,"
        " code TEXT NOT NULL UNIQUE, pass_mark REAL NOT NULL DEFAULT 40, show_average INTEGER NOT NULL DEFAULT 0,"
        " open INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);"
        "CREATE TABLE IF NOT EXISTS enrollments (room_id INTEGER NOT NULL, student TEXT NOT NULL, joined REAL NOT NULL,"
        " PRIMARY KEY (room_id, student));"
        "CREATE TABLE IF NOT EXISTS assignments (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL,"
        " title TEXT NOT NULL, max REAL NOT NULL, created REAL NOT NULL);"
        "CREATE TABLE IF NOT EXISTS scores (assignment_id INTEGER NOT NULL, student TEXT NOT NULL, marks REAL NOT NULL,"
        " PRIMARY KEY (assignment_id, student));"
        "CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL,"
        " text TEXT NOT NULL, created REAL NOT NULL);"
        "CREATE TABLE IF NOT EXISTS materials (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL,"
        " name TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL, data BLOB NOT NULL, created REAL NOT NULL);"
    )
    return c


def may_teach(username: str) -> bool:
    return auth.get_role(username) == "teacher" or auth.is_admin(username)


def _room_dict(r):
    return {"id": r[0], "teacher": r[1], "name": r[2], "code": r[3], "pass_mark": r[4], "show_average": bool(r[5]),
            "open": bool(r[6]), "created": r[7]}


def _own(c, actor: str, room_id: int):
    """The room, only if `actor` is its teacher."""
    r = c.execute("SELECT * FROM rooms WHERE id = ? AND teacher = ?", (int(room_id), actor)).fetchone()
    if r is None or not may_teach(actor):
        raise PermissionError("You don't manage that classroom.")
    return _room_dict(r)


def _member(c, username: str, room_id: int):
    """The room, if `username` teaches it or is enrolled in it."""
    r = c.execute("SELECT * FROM rooms WHERE id = ?", (int(room_id),)).fetchone()
    if r is None:
        raise PermissionError("That classroom doesn't exist.")
    if r[1] != username and not c.execute("SELECT 1 FROM enrollments WHERE room_id = ? AND student = ?",
                                          (int(room_id), username)).fetchone():
        raise PermissionError("You're not in that classroom.")
    return _room_dict(r)


def _new_code(c):
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not c.execute("SELECT 1 FROM rooms WHERE code = ?", (code,)).fetchone():
            return code


def _clean(text, limit=MAX_NAME):
    return " ".join(str(text or "").split())[:limit]


# ------------------------------------------------------------------ teacher
def create_room(teacher: str, name: str):
    """Returns (ok, room_id or message)."""
    if not may_teach(teacher):
        return False, "Only teachers can create classrooms."
    name = _clean(name)
    if not name:
        return False, "Give the classroom a name."
    with _conn() as c:
        if c.execute("SELECT COUNT(*) FROM rooms WHERE teacher = ?", (teacher,)).fetchone()[0] >= MAX_ROOMS:
            return False, f"You can have at most {MAX_ROOMS} classrooms."
        if c.execute("SELECT 1 FROM rooms WHERE teacher = ? AND name = ? COLLATE NOCASE", (teacher, name)).fetchone():
            return False, "You already have a classroom with that name."
        cur = c.execute("INSERT INTO rooms (teacher, name, code, created) VALUES (?, ?, ?, ?)",
                        (teacher, name, _new_code(c), time.time()))
        rid = cur.lastrowid
    auth.log_event(teacher, f"created classroom {name}")
    return True, rid


def rooms_of_teacher(teacher: str):
    with _conn() as c:
        return [_room_dict(r) for r in c.execute("SELECT * FROM rooms WHERE teacher = ? ORDER BY name COLLATE NOCASE", (teacher,))]


def update_room(actor: str, room_id: int, pass_mark: float, show_average: bool, is_open: bool):
    pass_mark = float(pass_mark)
    if not 0 <= pass_mark <= 100:
        raise ValueError("The pass mark must be from 0 to 100.")
    with _conn() as c:
        _own(c, actor, room_id)
        c.execute("UPDATE rooms SET pass_mark = ?, show_average = ?, open = ? WHERE id = ?",
                  (pass_mark, int(bool(show_average)), int(bool(is_open)), int(room_id)))


def new_code(actor: str, room_id: int):
    with _conn() as c:
        _own(c, actor, room_id)
        code = _new_code(c)
        c.execute("UPDATE rooms SET code = ? WHERE id = ?", (code, int(room_id)))
        return code


def _delete_room(c, room_id: int):
    c.execute("DELETE FROM scores WHERE assignment_id IN (SELECT id FROM assignments WHERE room_id = ?)", (room_id,))
    for table in ("assignments", "enrollments", "announcements", "materials"):
        c.execute(f"DELETE FROM {table} WHERE room_id = ?", (room_id,))
    c.execute("DELETE FROM rooms WHERE id = ?", (room_id,))


def delete_room(actor: str, room_id: int):
    with _conn() as c:
        room = _own(c, actor, room_id)
        _delete_room(c, int(room_id))
    auth.log_event(actor, f"deleted classroom {room['name']}")


def _remove(c, room_id: int, student: str):
    c.execute("DELETE FROM scores WHERE student = ? AND assignment_id IN (SELECT id FROM assignments WHERE room_id = ?)",
              (student, room_id))
    c.execute("DELETE FROM enrollments WHERE room_id = ? AND student = ?", (room_id, student))


def remove_student(actor: str, room_id: int, student: str):
    with _conn() as c:
        _own(c, actor, room_id)
        _remove(c, int(room_id), student)


def roster(actor: str, room_id: int):
    with _conn() as c:
        _own(c, actor, room_id)
        return [r[0] for r in c.execute("SELECT student FROM enrollments WHERE room_id = ? ORDER BY student", (int(room_id),))]


def add_assignment(actor: str, room_id: int, title: str, max_marks):
    title = _clean(title)
    try:
        max_marks = float(max_marks)
    except (TypeError, ValueError):
        return False, "Maximum marks must be a number."
    if not title:
        return False, "Give the assignment a title."
    if not 0 < max_marks <= 100000:
        return False, "Maximum marks must be greater than 0."
    with _conn() as c:
        _own(c, actor, room_id)
        if c.execute("SELECT COUNT(*) FROM assignments WHERE room_id = ?", (int(room_id),)).fetchone()[0] >= MAX_ASSIGNMENTS:
            return False, f"At most {MAX_ASSIGNMENTS} assignments per classroom."
        c.execute("INSERT INTO assignments (room_id, title, max, created) VALUES (?, ?, ?, ?)",
                  (int(room_id), title, max_marks, time.time()))
    return True, "Assignment added."


def delete_assignment(actor: str, room_id: int, assignment_id: int):
    with _conn() as c:
        _own(c, actor, room_id)
        if c.execute("DELETE FROM assignments WHERE id = ? AND room_id = ?", (int(assignment_id), int(room_id))).rowcount:
            c.execute("DELETE FROM scores WHERE assignment_id = ?", (int(assignment_id),))


def set_scores(actor: str, room_id: int, changes):
    """changes: iterable of (assignment_id, student, marks or None). All are validated before any is saved."""
    changes = list(changes)
    with _conn() as c:
        _own(c, actor, room_id)
        maxima = {r[0]: (r[1], r[2]) for r in c.execute("SELECT id, title, max FROM assignments WHERE room_id = ?", (int(room_id),))}
        enrolled = {r[0] for r in c.execute("SELECT student FROM enrollments WHERE room_id = ?", (int(room_id),))}
        for aid, student, marks in changes:
            if aid not in maxima or student not in enrolled:
                raise ValueError("That assignment or student isn't in this classroom.")
            if marks is not None and not 0 <= float(marks) <= maxima[aid][1]:
                raise ValueError(f"{student}: {maxima[aid][0]} must be between 0 and {maxima[aid][1]:g}.")
        for aid, student, marks in changes:
            if marks is None:
                c.execute("DELETE FROM scores WHERE assignment_id = ? AND student = ?", (aid, student))
            else:
                c.execute("INSERT OR REPLACE INTO scores VALUES (?, ?, ?)", (aid, student, float(marks)))
    if changes:
        auth.log_event(actor, f"saved {len(changes)} score(s)")


def gradebook(actor: str, room_id: int):
    """Returns {"assignments": [...], "students": [...], "scores": {(aid, student): marks}}."""
    with _conn() as c:
        _own(c, actor, room_id)
        assignments = [{"id": r[0], "title": r[1], "max": r[2]} for r in c.execute(
            "SELECT id, title, max FROM assignments WHERE room_id = ? ORDER BY id", (int(room_id),))]
        students = [r[0] for r in c.execute("SELECT student FROM enrollments WHERE room_id = ? ORDER BY student", (int(room_id),))]
        scores = {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT s.assignment_id, s.student, s.marks FROM scores s JOIN assignments a ON a.id = s.assignment_id "
            "WHERE a.room_id = ?", (int(room_id),))}
    return {"assignments": assignments, "students": students, "scores": scores}


def _percent(c, room_id: int, student: str):
    """Marks earned out of the maximum of the assignments this student has a score for."""
    r = c.execute("SELECT SUM(s.marks), SUM(a.max) FROM scores s JOIN assignments a ON a.id = s.assignment_id "
                  "WHERE a.room_id = ? AND s.student = ?", (room_id, student)).fetchone()
    return round(r[0] / r[1] * 100, 2) if r and r[1] else None


def percents(actor: str, room_id: int):
    """{student: percent or None} for everyone in the classroom."""
    with _conn() as c:
        _own(c, actor, room_id)
        return {r[0]: _percent(c, int(room_id), r[0]) for r in c.execute(
            "SELECT student FROM enrollments WHERE room_id = ? ORDER BY student", (int(room_id),))}


# ------------------------------------------------------------------ announcements and materials
def add_announcement(actor: str, room_id: int, text: str):
    text = str(text or "").strip()[:2000]
    if not text:
        return False, "Write something first."
    with _conn() as c:
        _own(c, actor, room_id)
        c.execute("INSERT INTO announcements (room_id, text, created) VALUES (?, ?, ?)", (int(room_id), text, time.time()))
    return True, "Posted."


def announcements(username: str, room_id: int):
    with _conn() as c:
        _member(c, username, room_id)
        return [{"id": r[0], "text": r[1], "created": r[2]} for r in c.execute(
            "SELECT id, text, created FROM announcements WHERE room_id = ? ORDER BY id DESC", (int(room_id),))]


def delete_announcement(actor: str, room_id: int, announcement_id: int):
    with _conn() as c:
        _own(c, actor, room_id)
        c.execute("DELETE FROM announcements WHERE id = ? AND room_id = ?", (int(announcement_id), int(room_id)))


def add_material(actor: str, room_id: int, name: str, data: bytes):
    name = files_db.safe_name(name)
    if not data:
        return False, f'"{name}" is empty.'
    if len(data) > files_db.MAX_FILE_BYTES:
        return False, f'"{name}" is too large.'
    with _conn() as c:
        _own(c, actor, room_id)
        if c.execute("SELECT COUNT(*) FROM materials WHERE room_id = ?", (int(room_id),)).fetchone()[0] >= MAX_MATERIALS:
            return False, f"At most {MAX_MATERIALS} files per classroom."
        c.execute("INSERT INTO materials (room_id, name, mime, size, data, created) VALUES (?, ?, ?, ?, ?, ?)",
                  (int(room_id), name, mimetypes.guess_type(name)[0] or "application/octet-stream", len(data), data, time.time()))
    return True, "Shared."


def materials(username: str, room_id: int):
    with _conn() as c:
        _member(c, username, room_id)
        return [{"id": r[0], "name": r[1], "size": r[2]} for r in c.execute(
            "SELECT id, name, size FROM materials WHERE room_id = ? ORDER BY id DESC", (int(room_id),))]


def get_material(username: str, room_id: int, material_id: int):
    with _conn() as c:
        _member(c, username, room_id)
        r = c.execute("SELECT name, mime, data FROM materials WHERE id = ? AND room_id = ?", (int(material_id), int(room_id))).fetchone()
    return (r[0], r[1], bytes(r[2])) if r else None


def delete_material(actor: str, room_id: int, material_id: int):
    with _conn() as c:
        _own(c, actor, room_id)
        c.execute("DELETE FROM materials WHERE id = ? AND room_id = ?", (int(material_id), int(room_id)))


# ------------------------------------------------------------------ student
def join(student: str, code: str):
    """Returns (ok, message)."""
    code = "".join(str(code or "").split()).upper()
    with _conn() as c:
        r = c.execute("SELECT * FROM rooms WHERE code = ?", (code,)).fetchone()
        if r is None:
            return False, "No classroom has that code. Check it with your teacher."
        room = _room_dict(r)
        if room["teacher"] == student:
            return False, "That's your own classroom."
        if not room["open"]:
            return False, "This classroom isn't accepting new students right now."
        if c.execute("SELECT 1 FROM enrollments WHERE room_id = ? AND student = ?", (room["id"], student)).fetchone():
            return False, "You're already in that classroom."
        if c.execute("SELECT 1 FROM enrollments e JOIN rooms r ON r.id = e.room_id WHERE e.student = ? AND r.name = ? COLLATE NOCASE",
                     (student, room["name"])).fetchone():
            return False, f'You\'re already in another classroom called "{room["name"]}". Leave it first.'
        if c.execute("SELECT COUNT(*) FROM enrollments WHERE room_id = ?", (room["id"],)).fetchone()[0] >= MAX_STUDENTS:
            return False, "This classroom is full."
        c.execute("INSERT INTO enrollments VALUES (?, ?, ?)", (room["id"], student, time.time()))
    auth.log_event(student, f"joined classroom {room['name']} (teacher {room['teacher']})")
    return True, room["name"]


def leave(student: str, room_id: int):
    with _conn() as c:
        _remove(c, int(room_id), student)
    auth.log_event(student, "left a classroom")


def rooms_of_student(student: str):
    with _conn() as c:
        return [_room_dict(r) for r in c.execute(
            "SELECT r.* FROM rooms r JOIN enrollments e ON e.room_id = r.id WHERE e.student = ? ORDER BY r.name COLLATE NOCASE",
            (student,))]


def my_scores(student: str, room_id: int):
    """Only this student's own scores."""
    with _conn() as c:
        _member(c, student, room_id)
        return [{"title": r[0], "max": r[1], "marks": r[2]} for r in c.execute(
            "SELECT a.title, a.max, s.marks FROM assignments a LEFT JOIN scores s ON s.assignment_id = a.id AND s.student = ? "
            "WHERE a.room_id = ? ORDER BY a.id", (student, int(room_id)))]


def my_percent(student: str, room_id: int):
    with _conn() as c:
        _member(c, student, room_id)
        return _percent(c, int(room_id), student)


def class_average(username: str, room_id: int):
    """Average of everyone's percentage. Students only get it if the teacher allows it."""
    with _conn() as c:
        room = _member(c, username, room_id)
        if room["teacher"] != username and not room["show_average"]:
            return None
        values = [_percent(c, int(room_id), r[0]) for r in c.execute("SELECT student FROM enrollments WHERE room_id = ?", (int(room_id),))]
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def teacher_grades(student: str):
    """{lowercase class name: {"name", "percent", "teacher"}} for classrooms the student has joined."""
    with _conn() as c:
        rows = c.execute("SELECT r.id, r.name, r.teacher FROM rooms r JOIN enrollments e ON e.room_id = r.id WHERE e.student = ?",
                         (student,)).fetchall()
        return {name.lower(): {"name": name, "percent": _percent(c, rid, student), "teacher": teacher}
                for rid, name, teacher in rows}


# ------------------------------------------------------------------ admin and clean-up
def all_rooms():
    with _conn() as c:
        return [{**_room_dict(r), "students": c.execute("SELECT COUNT(*) FROM enrollments WHERE room_id = ?", (r[0],)).fetchone()[0]}
                for r in c.execute("SELECT * FROM rooms ORDER BY teacher, name").fetchall()]


def admin_delete_room(admin_user: str, room_id: int):
    if not auth.is_admin(admin_user):
        raise PermissionError("Admin only.")
    with _conn() as c:
        _delete_room(c, int(room_id))


def delete_user_data(username: str):
    """Called when an account is deleted."""
    with _conn() as c:
        for (rid,) in c.execute("SELECT id FROM rooms WHERE teacher = ?", (username,)).fetchall():
            _delete_room(c, rid)
        c.execute("DELETE FROM scores WHERE student = ?", (username,))
        c.execute("DELETE FROM enrollments WHERE student = ?", (username,))


def delete_teaching(username: str):
    """Called when a teacher is changed back to a student: their classrooms go."""
    with _conn() as c:
        for (rid,) in c.execute("SELECT id FROM rooms WHERE teacher = ?", (username,)).fetchall():
            _delete_room(c, rid)
