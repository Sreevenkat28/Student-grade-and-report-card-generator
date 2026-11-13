"""Per-user file storage (any file type) next to the accounts, plus text extraction for the assistant."""
import io
import mimetypes
import os
import re
import sqlite3
import time

from auth import DB_PATH

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_FILES = 50
TEXT_EXTS = {".txt", ".md", ".csv", ".tsv", ".json", ".html", ".htm", ".xml", ".log", ".py", ".js", ".yaml", ".yml", ".rtf"}


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, "
        "name TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL, data BLOB NOT NULL, created REAL NOT NULL)"
    )
    return conn


def safe_name(name: str) -> str:
    """Keep only the file name (no folders), drop control characters, cap the length."""
    base = os.path.basename(str(name or "").replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip().strip(".")
    if len(base) > 120:
        stem, ext = os.path.splitext(base)
        base = stem[: 120 - len(ext)] + ext
    return base or "file"


def usage(username: str):
    with _conn() as c:
        n, total = c.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM files WHERE username = ?", (username,)).fetchone()
    return n, total


def add_file(username: str, name: str, data: bytes):
    """Store a file. Returns (ok, message)."""
    name = safe_name(name)
    if not data:
        return False, f'"{name}" is empty.'
    if len(data) > MAX_FILE_BYTES:
        return False, f'"{name}" is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.'
    n, total = usage(username)
    if n >= MAX_FILES:
        return False, f"You can store at most {MAX_FILES} files. Delete some first."
    if total + len(data) > MAX_TOTAL_BYTES:
        return False, f"Not enough space ({MAX_TOTAL_BYTES // (1024 * 1024)} MB total). Delete some files first."
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with _conn() as c:
        cur = c.execute("INSERT INTO files (username, name, mime, size, data, created) VALUES (?, ?, ?, ?, ?, ?)",
                        (username, name, mime, len(data), data, time.time()))
    return True, cur.lastrowid


def list_files(username: str):
    with _conn() as c:
        rows = c.execute("SELECT id, name, mime, size, created FROM files WHERE username = ? ORDER BY created DESC, id DESC",
                         (username,)).fetchall()
    return [{"id": r[0], "name": r[1], "mime": r[2], "size": r[3], "created": r[4]} for r in rows]


def get_file(username: str, file_id: int):
    """Returns (name, mime, data) only if the file belongs to `username`, else None."""
    with _conn() as c:
        row = c.execute("SELECT name, mime, data FROM files WHERE username = ? AND id = ?", (username, int(file_id))).fetchone()
    return (row[0], row[1], bytes(row[2])) if row else None


def delete_file(username: str, file_id: int):
    with _conn() as c:
        c.execute("DELETE FROM files WHERE username = ? AND id = ?", (username, int(file_id)))


def find_by_name(username: str, name: str):
    """Newest file whose name matches (case-insensitive). Returns its id or None."""
    with _conn() as c:
        row = c.execute("SELECT id FROM files WHERE username = ? AND name = ? COLLATE NOCASE ORDER BY id DESC LIMIT 1",
                        (username, safe_name(name))).fetchone()
    return row[0] if row else None


def extract_text(name: str, data: bytes, limit: int = 20000):
    """Best-effort text from a stored file. Returns (text, error); one of them is None."""
    ext = os.path.splitext(name.lower())[1]
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, "PDF reading isn't available on this server."
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                return None, "This PDF is password-protected."
            parts, total = [], 0
            for page in reader.pages[:60]:
                t = (page.extract_text() or "").strip()
                parts.append(t)
                total += len(t)
                if total >= limit:
                    break
            text = "\n\n".join(p for p in parts if p)
        except Exception:
            return None, "Couldn't read this PDF."
        if not text.strip():
            return None, "No readable text in this PDF (it may be a scan or images)."
        return text[:limit], None
    if ext in TEXT_EXTS or ext == "":
        for enc in ("utf-8", "latin-1"):
            try:
                return data.decode(enc)[:limit], None
            except UnicodeDecodeError:
                continue
    return None, f"Can't read text from {ext or 'this'} files."


def save_note(username: str, title: str, content: str):
    """Save text as a .md file (used for study plans). Returns (ok, message_or_id)."""
    title = re.sub(r"[^\w\- ]+", "", str(title or "")).strip()[:60] or "Note"
    content = str(content or "").strip()
    if not content:
        return False, "Nothing to save."
    return add_file(username, f"{title}.md", content[:100_000].encode("utf-8"))
