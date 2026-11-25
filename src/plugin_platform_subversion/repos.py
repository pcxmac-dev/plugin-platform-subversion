"""Subversion's working copies and repositories found under a folder you named, read from their own files alone: no svn
is run in them (a working copy's runtime configuration is the user's, and a look needs none of it).

- A working copy (Subversion 1.7 and later: one .svn at its root) is read from .svn/wc.db, its SQLite database, opened
  read-only (mode=ro, so nothing is written and no journal is made): the repository's root and UUID, the path checked
  out, its revision, and its last change's revision, author and time.
- A repository (FSFS, as svnadmin create makes it) is read from its files: format, db/fs-type, db/uuid, db/current (its
  youngest revision).
An address is said without a password in it."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MOST_READ = 4096
WORKING_COPY, REPOSITORY = "working copy", "repository"
NODE = ("SELECT r.root, r.uuid, n.repos_path, n.revision, n.changed_revision, n.changed_author, n.changed_date "
        "FROM nodes n JOIN repository r ON r.id = n.repos_id WHERE n.local_relpath = '' AND n.op_depth = 0 LIMIT 1")


def _read(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return f.read(MOST_READ).decode("utf-8", "replace")
    except OSError:
        return ""


def kind_of(path: str) -> str:
    if os.path.isfile(os.path.join(path, ".svn", "wc.db")):
        return WORKING_COPY
    if os.path.isfile(os.path.join(path, "format")) and os.path.isfile(os.path.join(path, "db", "fs-type")):
        return REPOSITORY
    return ""


def bare_address(url: str) -> str:
    """An address without a password in it (svn://user:pw@host/x -> svn://user@host/x)."""
    text = str(url or "").strip()
    try:
        parts = urlsplit(text)
    except ValueError:
        return "an address not read"
    if "@" not in parts.netloc:
        return text
    who, host = parts.netloc.rsplit("@", 1)
    who = who.split(":", 1)[0]
    return urlunsplit((parts.scheme, f"{who}@{host}" if who else host, parts.path, parts.query, parts.fragment))


@dataclass(frozen=True)
class Found:
    path: str
    kind: str
    url: str = ""
    uuid: str = ""
    revision: int | None = None
    changed: str = ""
    store: str = ""
    why: str = ""
    changed_at: float = 0.0  # seconds since 1970 (wc.db keeps microseconds)


def _working_copy(path: str) -> Found:
    db = Path(path, ".svn", "wc.db")
    try:
        con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=1.0)
        try:
            row = con.execute(NODE).fetchone()
        finally:
            con.close()
    except sqlite3.Error as e:
        return Found(path, WORKING_COPY, why=f"its wc.db could not be read ({type(e).__name__}: {e})"[:200])
    if not row:
        return Found(path, WORKING_COPY, why="its wc.db names no node at its root")
    root, uuid, rel, rev, crev, author, date = row
    url = bare_address(f"{str(root).rstrip('/')}/{rel}" if rel else str(root))
    changed = f"r{crev}" + (f" by {author}" if author else "") if crev is not None else ""
    at = float(date) / 1e6 if isinstance(date, (int, float)) and date > 0 else 0.0
    return Found(path, WORKING_COPY, url, str(uuid or ""), int(rev) if rev is not None else None, changed,
                 changed_at=at)


def _repository(path: str) -> Found:
    current = _read(os.path.join(path, "db", "current")).split()
    try:
        youngest = int(current[0]) if current else None
    except ValueError:
        youngest = None
    store = _read(os.path.join(path, "db", "fs-type")).strip()
    fmt = _read(os.path.join(path, "format")).strip()
    return Found(path, REPOSITORY, "", _read(os.path.join(path, "db", "uuid")).split("\n")[0].strip(), youngest,
                 "", f"{store} (format {fmt})" if fmt else store,
                 "" if youngest is not None else "its db/current could not be read")


def read(path: str, kind: str = "") -> Found:
    kind = kind or kind_of(path)
    return _working_copy(path) if kind == WORKING_COPY else _repository(path)
