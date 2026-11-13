"""Auth: accounts (email + username + password) and emailed one-time codes (used to reset a password).

Storage is a local SQLite file. Codes are stored hashed, expire after 10 minutes,
allow 5 wrong attempts, and can be re-sent at most once every 30 seconds.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from urllib.parse import urlparse

import emailcheck

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
CODE_TTL = 600
MAX_ATTEMPTS = 5
ITERATIONS = 200_000
RESEND_WAIT = 30


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS members ("
        "username TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE)"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(members)")}
    for col in ("salt", "hash"):  # older databases had no password columns
        if col not in cols:
            conn.execute(f"ALTER TABLE members ADD COLUMN {col} BLOB")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS codes ("
        "email TEXT PRIMARY KEY, hash TEXT NOT NULL, expires REAL NOT NULL, "
        "attempts INTEGER NOT NULL DEFAULT 0, sent REAL NOT NULL)"
    )
    return conn


def _hash_code(email: str, code: str) -> str:
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


def _hash_pw(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def check_password(password: str):
    """Returns an error message, or '' if the password is acceptable."""
    if not password:
        return "Enter a password."
    return ""


def check_signup(email: str, username: str):
    """Validate sign-up details. Returns (ok, message, email, username)."""
    email, username = email.strip().lower(), username.strip().lower()
    bad = emailcheck.problem(email)
    if bad:
        return False, bad, email, username
    if not USERNAME_RE.match(username):
        return False, "Username must be 3-30 characters: letters, numbers, _ . -", email, username
    with _conn() as c:
        if c.execute("SELECT 1 FROM members WHERE username = ?", (username,)).fetchone():
            return False, "That username is already taken.", email, username
        if c.execute("SELECT 1 FROM members WHERE email = ?", (email,)).fetchone():
            return False, "An account with that email already exists. Log in instead.", email, username
    return True, "", email, username


def create_member(email: str, username: str, password: str):
    salt = os.urandom(16)
    with _conn() as c:
        c.execute(
            "INSERT INTO members (username, email, salt, hash) VALUES (?, ?, ?, ?)",
            (username, email, salt, _hash_pw(password, salt)),
        )


def set_password(email: str, password: str):
    salt = os.urandom(16)
    with _conn() as c:
        c.execute(
            "UPDATE members SET salt = ?, hash = ? WHERE email = ?",
            (salt, _hash_pw(password, salt), email),
        )


def authenticate(identifier: str, password: str):
    """Username-or-email + password. Returns (username, error); exactly one is None."""
    ident = identifier.strip().lower()
    with _conn() as c:
        row = c.execute(
            "SELECT username, salt, hash FROM members WHERE username = ? OR email = ?", (ident, ident)
        ).fetchone()
    if row and row[1] and row[2]:
        if hmac.compare_digest(_hash_pw(password, row[1]), row[2]):
            return row[0], None
    else:
        _hash_pw(password, b"\0" * 16)  # similar timing for unknown users
    return None, "Invalid username/email or password."


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


def discard_code(email: str):
    """Forget a code that was never delivered, so the user can retry immediately."""
    with _conn() as c:
        c.execute("DELETE FROM codes WHERE email = ?", (email,))


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


class EmailError(Exception):
    """An email problem with a message that is safe to show to the user."""


def smtp_config(raw: dict) -> dict:
    """Normalise the [smtp] secrets. Raises EmailError if something is missing or invalid."""
    raw = dict(raw or {})
    missing = [k for k in ("host", "user", "password") if not str(raw.get(k) or "").strip()]
    if missing:
        raise EmailError("Email settings are incomplete. Missing: " + ", ".join(missing) + ".")
    try:
        port = int(raw.get("port", 587))
    except (TypeError, ValueError):
        raise EmailError("The email port must be a number such as 587 or 465.")
    return {
        "host": str(raw["host"]).strip(),
        "port": port,
        "user": str(raw["user"]).strip(),
        # Google shows app passwords in groups of four with spaces; they must be removed.
        "password": str(raw["password"]).replace(" ", ""),
        "from_addr": str(raw.get("from_addr") or "").strip() or str(raw["user"]).strip(),
        "starttls": bool(raw.get("starttls", True)),
    }


def send_email(smtp: dict, to_email: str, subject: str, body: str):
    """Send one plain-text email. Raises EmailError with a readable reason on failure."""
    cfg = smtp_config(smtp)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = to_email
    msg.set_content(body)
    try:
        if cfg["port"] == 465:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
        with server:
            if cfg["port"] != 465 and cfg["starttls"]:
                server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise EmailError(
            "The email server rejected the login. For Gmail, turn on 2-step verification and use "
            "a 16-character App Password (not your normal password) as the password."
        )
    except smtplib.SMTPRecipientsRefused:
        raise EmailError("The email server refused that recipient address.")
    except smtplib.SMTPSenderRefused:
        raise EmailError("The email server refused the sender address. Check 'user' / 'from_addr'.")
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, OSError):
        raise EmailError(f"Couldn't reach the email server {cfg['host']}:{cfg['port']}. "
                         "Check the host and port.")
    except smtplib.SMTPException as e:
        raise EmailError(f"The email server returned an error ({type(e).__name__}).")


def script_config(raw: dict) -> dict:
    """Normalise the [apps_script] secrets. Raises EmailError if missing or invalid."""
    raw = dict(raw or {})
    url, token = str(raw.get("url") or "").strip(), str(raw.get("token") or "").strip()
    missing = [k for k, v in (("url", url), ("token", token)) if not v]
    if missing:
        raise EmailError("Email settings are incomplete. Missing: " + ", ".join(missing) + ".")
    u = urlparse(url)
    if not raw.get("allow_custom_url") and not (u.scheme == "https" and u.hostname == "script.google.com"):
        raise EmailError("The script url must be the https://script.google.com/.../exec web app URL.")
    return {"url": url, "token": token}


_SCRIPT_ERRORS = {
    "unauthorized": "The email service rejected the secret key. Make sure `token` in Secrets exactly "
                    "matches the SECRET script property.",
    "bad_email": "The email service says that address is invalid.",
    "bad_code": "The email service rejected the code format.",
    "rate_limited": "Too many emails were sent to that address recently. Please try again later.",
}


def send_via_script(cfg: dict, kind: str, to_email: str, code: str = ""):
    """Ask the Google Apps Script web app to send a 'code' or 'test' email."""
    c = script_config(cfg)
    payload = json.dumps({"token": c["token"], "kind": kind, "to": to_email, "code": code}).encode()
    req = urllib.request.Request(c["url"], data=payload, headers={"Content-Type": "application/json"})
    try:
        # Apps Script answers a POST with a redirect to the result; urllib follows it.
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise EmailError(f"The email script returned HTTP {e.code}. Check the deployment URL and access.")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise EmailError("Couldn't reach the email script. Check the url and your connection.")
    try:
        result = json.loads(raw)
    except ValueError:
        raise EmailError(
            "The email script didn't return a valid reply. In Deploy settings, set 'Who has access' "
            "to Anyone and use the /exec URL (not /dev)."
        )
    if not result.get("ok"):
        err = result.get("error", "")
        raise EmailError(_SCRIPT_ERRORS.get(err, f"The email script reported an error ({err or 'unknown'})."))


def send_code_email(cfg: dict, to_email: str, code: str):
    """Send a confirmation code. `cfg` is either {url, token} (Apps Script) or SMTP settings."""
    if "url" in cfg:
        return send_via_script(cfg, "code", to_email, code)
    send_email(
        cfg, to_email, f"Your confirmation code: {code}",
        f"Your Grade & Report Card Generator confirmation code is {code}.\n\n"
        f"Enter it in the app to continue. It expires in {CODE_TTL // 60} minutes. "
        "If you didn't ask for this, you can ignore this email.",
    )


def send_test_email(cfg: dict, to_email: str):
    if "url" in cfg:
        return send_via_script(cfg, "test", to_email)
    send_email(
        cfg, to_email, "Test email from Grade & Report Card Generator",
        "This is a test. Email sending from the app is working, so confirmation codes will arrive.",
    )


# ---------------------------------------------------------------- account changes
def change_password(username: str, current: str, new: str, confirm: str):
    """Returns (ok, message). Requires the current password."""
    u, _ = authenticate(username, current)
    if not u:
        return False, "Your current password is incorrect."
    err = check_password(new) or ("The new passwords do not match." if new != confirm else "")
    if err:
        return False, err
    if new == current:
        return False, "Choose a password different from your current one."
    with _conn() as c:
        email = c.execute("SELECT email FROM members WHERE username = ?", (u,)).fetchone()[0]
    set_password(email, new)
    return True, "Password changed."


def change_email(username: str, password: str, new_email: str):
    """Returns (ok, message). Requires the password."""
    u, _ = authenticate(username, password)
    if not u:
        return False, "Your password is incorrect."
    new_email = new_email.strip().lower()
    bad = emailcheck.problem(new_email)
    if bad:
        return False, bad
    try:
        with _conn() as c:
            c.execute("UPDATE members SET email = ? WHERE username = ?", (new_email, u))
    except sqlite3.IntegrityError:
        return False, "Another account already uses that email."
    return True, "Email updated."


def get_email(username: str):
    with _conn() as c:
        row = c.execute("SELECT email FROM members WHERE username = ?", (username,)).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------- admin (this device only)
ADMIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".admin_device")


def is_admin(username: str) -> bool:
    """True only if this machine has a local `.admin_device` file naming `username`.

    The file is git-ignored, so it never exists on the deployed (Streamlit Cloud) copy:
    admin access is possible only on the device where the file was created.
    """
    try:
        with open(ADMIN_FILE) as f:
            return bool(username) and f.read().strip().lower() == username.strip().lower()
    except OSError:
        return False


def list_members():
    with _conn() as c:
        return c.execute("SELECT username, email FROM members ORDER BY username").fetchall()


def delete_member(username: str):
    """Remove an account and everything tied to it."""
    with _conn() as c:
        row = c.execute("SELECT email FROM members WHERE username = ?", (username,)).fetchone()
        c.execute("DELETE FROM members WHERE username = ?", (username,))
        if row:
            c.execute("DELETE FROM codes WHERE email = ?", (row[0],))
        for table in ("classes", "profile", "prefs"):  # created by classes_db on first use
            try:
                c.execute(f"DELETE FROM {table} WHERE username = ?", (username,))
            except sqlite3.OperationalError:
                pass


def delete_all_members(keep: str = ""):
    """Delete every account except `keep`. Returns how many were removed."""
    names = [u for (u, _e) in list_members() if u != keep.strip().lower()]
    for u in names:
        delete_member(u)
    return len(names)
