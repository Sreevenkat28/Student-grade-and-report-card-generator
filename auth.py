"""Minimal username/password auth backed by SQLite with PBKDF2-hashed passwords."""
import hashlib
import hmac
import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD = 6


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "username TEXT PRIMARY KEY, salt BLOB NOT NULL, hash BLOB NOT NULL)"
    )
    return conn


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def register(username: str, password: str):
    """Returns (ok, message)."""
    username = username.strip()
    if not USERNAME_RE.match(username):
        return False, "Username must be 3-30 characters: letters, numbers, _ . -"
    if len(password) < MIN_PASSWORD:
        return False, f"Password must be at least {MIN_PASSWORD} characters."
    salt = os.urandom(16)
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO users VALUES (?, ?, ?)",
                (username.lower(), salt, _hash(password, salt)),
            )
    except sqlite3.IntegrityError:
        return False, "That username is already taken."
    return True, "Account created. You can now log in."


def authenticate(username: str, password: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT salt, hash FROM users WHERE username = ?", (username.strip().lower(),)
        ).fetchone()
    if row is None:
        _hash(password, b"\0" * 16)  # keep timing similar for unknown users
        return False
    return hmac.compare_digest(_hash(password, row[0]), row[1])
