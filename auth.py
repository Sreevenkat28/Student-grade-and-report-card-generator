"""Passwordless auth: accounts (email + username) and emailed one-time codes.

Storage is a local SQLite file. Codes are stored hashed, expire after 10 minutes,
allow 5 wrong attempts, and can be re-sent at most once every 30 seconds.
"""
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import sqlite3
import time
from email.message import EmailMessage

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
CODE_TTL = 600
MAX_ATTEMPTS = 5
RESEND_WAIT = 30


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS members ("
        "username TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS codes ("
        "email TEXT PRIMARY KEY, hash TEXT NOT NULL, expires REAL NOT NULL, "
        "attempts INTEGER NOT NULL DEFAULT 0, sent REAL NOT NULL)"
    )
    return conn


def _hash_code(email: str, code: str) -> str:
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


def check_signup(email: str, username: str):
    """Validate sign-up details. Returns (ok, message, email, username)."""
    email, username = email.strip().lower(), username.strip().lower()
    if not EMAIL_RE.match(email):
        return False, "Enter a valid email address.", email, username
    if not USERNAME_RE.match(username):
        return False, "Username must be 3-30 characters: letters, numbers, _ . -", email, username
    with _conn() as c:
        if c.execute("SELECT 1 FROM members WHERE username = ?", (username,)).fetchone():
            return False, "That username is already taken.", email, username
        if c.execute("SELECT 1 FROM members WHERE email = ?", (email,)).fetchone():
            return False, "An account with that email already exists. Log in instead.", email, username
    return True, "", email, username


def create_member(email: str, username: str):
    with _conn() as c:
        c.execute("INSERT INTO members VALUES (?, ?)", (username, email))


def find_member(identifier: str):
    """Look up by username or email. Returns (username, email) or None."""
    ident = identifier.strip().lower()
    with _conn() as c:
        return c.execute(
            "SELECT username, email FROM members WHERE username = ? OR email = ?", (ident, ident)
        ).fetchone()


def issue_code(email: str):
    """Create a fresh code for `email`. Returns (code, error). Enforces resend wait."""
    now = time.time()
    with _conn() as c:
        row = c.execute("SELECT sent FROM codes WHERE email = ?", (email,)).fetchone()
        if row and now - row[0] < RESEND_WAIT:
            wait = int(RESEND_WAIT - (now - row[0])) + 1
            return None, f"Please wait {wait}s before requesting another code."
        code = f"{secrets.randbelow(10**6):06d}"
        c.execute(
            "INSERT OR REPLACE INTO codes VALUES (?, ?, ?, 0, ?)",
            (email, _hash_code(email, code), now + CODE_TTL, now),
        )
    return code, None


def verify_code(email: str, code: str):
    """Returns (ok, message). A correct code is single-use."""
    code = code.strip()
    with _conn() as c:
        row = c.execute(
            "SELECT hash, expires, attempts FROM codes WHERE email = ?", (email,)
        ).fetchone()
        if row is None:
            return False, "No code requested. Please request a new one."
        h, expires, attempts = row
        if time.time() > expires:
            c.execute("DELETE FROM codes WHERE email = ?", (email,))
            return False, "That code has expired. Please request a new one."
        if attempts >= MAX_ATTEMPTS:
            c.execute("DELETE FROM codes WHERE email = ?", (email,))
            return False, "Too many wrong attempts. Please request a new code."
        if hmac.compare_digest(h, _hash_code(email, code)):
            c.execute("DELETE FROM codes WHERE email = ?", (email,))
            return True, ""
        c.execute("UPDATE codes SET attempts = attempts + 1 WHERE email = ?", (email,))
        left = MAX_ATTEMPTS - attempts - 1
        return False, f"Incorrect code. {left} attempt(s) left."


def send_code_email(smtp: dict, to_email: str, code: str):
    """Send the code via SMTP. `smtp` = {host, port, user, password, from_addr(optional)}."""
    msg = EmailMessage()
    msg["Subject"] = f"Your login code: {code}"
    msg["From"] = smtp.get("from_addr") or smtp["user"]
    msg["To"] = to_email
    msg.set_content(
        f"Your Grade & Report Card Generator login code is {code}.\n\n"
        f"It expires in {CODE_TTL // 60} minutes. If you didn't request it, ignore this email."
    )
    port = int(smtp.get("port", 587))
    if port == 465:
        server = smtplib.SMTP_SSL(smtp["host"], port, timeout=15)
    else:
        server = smtplib.SMTP(smtp["host"], port, timeout=15)
        server.starttls()
    with server:
        server.login(smtp["user"], smtp["password"])
        server.send_message(msg)
