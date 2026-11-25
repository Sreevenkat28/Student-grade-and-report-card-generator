"""Bulk deletion of one account's saved things. Used by Settings (your own) and the Admin tab (anyone's).

Callers decide who is allowed: Settings only passes the logged-in account, the Admin tab checks for admin.
The report card and the assistant chat live only in the browser session, so Settings clears those itself.
"""
import auth
import classes_db as cdb
import files_db
import rooms_db

LABELS = {
    "grades": "Typed grades and test scores",
    "classes": "Classes (and their grades)",
    "files": "Files",
    "joined": "Classrooms joined (leaves them)",
    "teaching": "Classrooms taught (and everything in them)",
}


def choices(username: str):
    """The kinds that make sense for this account."""
    out = ["grades", "classes", "files"]
    if rooms_db.rooms_of_student(username):
        out.append("joined")
    if rooms_db.rooms_of_teacher(username):
        out.append("teaching")
    return out


def _delete_grades(username):
    for g in cdb.get_finals(username).values():
        cdb.delete_final(username, g["class"])
    for g in cdb.list_grades(username):
        cdb.delete_grade(username, g["id"])


def delete(username: str, kinds, actor: str = None):
    for kind in [k for k in LABELS if k in kinds]:
        if kind == "grades":
            _delete_grades(username)
        elif kind == "classes":
            _delete_grades(username)
            for names in cdb.list_classes(username).values():
                for name in names:
                    cdb.remove_class(username, name)
        elif kind == "files":
            for f in files_db.list_files(username):
                files_db.delete_file(username, f["id"])
        elif kind == "joined":
            for room in rooms_db.rooms_of_student(username):
                rooms_db.leave(username, room["id"])
        elif kind == "teaching":
            rooms_db.delete_teaching(username)
        by = f" (by {actor})" if actor and actor != username else ""
        auth.log_event(username, f"deleted: {LABELS[kind].lower()}{by}")
