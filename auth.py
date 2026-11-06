"""Username/email + password auth backed by SQLite with PBKDF2-hashed passwords."""
import hashlib
import hmac
import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
MIN_PASSWORD = 6


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS accounts ("
        "username TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, "
        "salt BLOB NOT NULL, hash BLOB NOT NULL)"
    )
    return conn


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def register(email: str, username: str, password: str):
    """Returns (ok, message)."""
    email, username = email.strip().lower(), username.strip().lower()
    if not EMAIL_RE.match(email):
        return False, "Enter a valid email address."
    if not USERNAME_RE.match(username):
        return False, "Username must be 3-30 characters: letters, numbers, _ . -"
    if len(password) < MIN_PASSWORD:
        return False, f"Password must be at least {MIN_PASSWORD} characters."
    salt = os.urandom(16)
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?)",
                (username, email, salt, _hash(password, salt)),
            )
    except sqlite3.IntegrityError:
        with _conn() as c:
            taken_user = c.execute(
                "SELECT 1 FROM accounts WHERE username = ?", (username,)
            ).fetchone()
        return False, (
            "That username is already taken."
            if taken_user
            else "An account with that email already exists."
        )
    return True, "Account created. You can now log in."


def authenticate(identifier: str, password: str):
    """identifier is a username or an email. Returns the username, or None."""
    ident = identifier.strip().lower()
    with _conn() as c:
        row = c.execute(
            "SELECT username, salt, hash FROM accounts WHERE username = ? OR email = ?",
            (ident, ident),
        ).fetchone()
    if row is None:
        _hash(password, b"\0" * 16)  # keep timing similar for unknown users
        return None
    return row[0] if hmac.compare_digest(_hash(password, row[1]), row[2]) else None
