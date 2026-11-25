"""The folders you name on the page, where repositories are looked for, and the look itself.

Repositories are found under these folders alone, never by scanning the whole disk: a folder is an absolute path to a
folder that is there, never a drive's or the file system's root, 16 folders at most, kept through the login (the
plugin's `<NAME>_FOLDERS`, as JSON). The look goes MAX_DEPTH folders down at most, visits MAX_DIRS folders of each at
most and keeps MAX_FOUND repositories in all; it follows no link (a symbolic link, a junction), steps over SKIP's
folders (dependencies and build output), and never goes into a repository it found. It reads names alone: what a
repository holds is read by `repos.py`, from its own files."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Callable

from liminal_libs.instances import Refusal, Store

MOST_FOLDERS = 16
MAX_DEPTH = 4
MAX_DIRS = 4000
MAX_FOUND = 500
SKIP = frozenset({"node_modules", ".venv", "venv", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", "$RECYCLE.BIN",
                  "System Volume Information"})


def is_root(path: PurePath) -> bool:
    """Whether a path is a drive's or the file system's root (C:\\, \\\\server\\share\\, /)."""
    return path == path.parent or str(path).rstrip("\\/") == path.anchor.rstrip("\\/")


def checked(text) -> str:
    """A folder as typed, made absolute and checked (Refusal in words)."""
    raw = str(text or "").strip().strip('"')
    if not raw or any(ord(c) < 32 for c in raw) or len(raw) > 1024:
        raise Refusal("a folder is a path of 1,024 characters at most, with no line break")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        raise Refusal(f"{raw[:120]} is no absolute path: name the whole path (C:\\Users\\you\\source, /home/you/src)")
    p = Path(os.path.normpath(p))
    if is_root(p):
        raise Refusal(f"{p} is a whole disk: repositories are looked for under the folders you name, never across a "
                      "disk")
    if not p.is_dir():
        raise Refusal(f"{p} is not a folder here")
    return str(p)


class Folders:
    """The folders kept through the plugin's login under `variable`."""

    def __init__(self, variable: str, login_of: Callable[[], object]):
        self.variable = variable
        self._store = Store(variable, login_of)

    def all(self) -> list[str]:
        try:
            data = json.loads(self._store.text() or "[]")
        except Exception:  # noqa: BLE001 - nothing kept, or not readable: none
            return []
        return [str(x) for x in data if isinstance(x, str)][:MOST_FOLDERS] if isinstance(data, list) else []

    def add(self, text) -> tuple[str, str]:
        """A folder added (its checked path, where it is kept)."""
        path = checked(text)
        kept = self.all()
        if any(os.path.normcase(path) == os.path.normcase(k) for k in kept):
            raise Refusal(f"{path} is named already")
        if len(kept) >= MOST_FOLDERS:
            raise Refusal(f"{MOST_FOLDERS} folders are named already: remove one first")
        return path, self._store.put(json.dumps([*kept, path]))

    def remove(self, text) -> tuple[str, str]:
        """A folder taken off the list (nothing on the disk is touched)."""
        raw = str(text or "").strip().strip('"')
        kept = self.all()
        left = [k for k in kept if os.path.normcase(k) != os.path.normcase(os.path.normpath(raw) if raw else raw)]
        if len(left) == len(kept):
            raise Refusal(f"{raw[:120]!r} is not among the folders named")
        return raw, self._store.put(json.dumps(left) if left else None)


@dataclass
class Look:
    """What a look under the folders found (by `found(path) -> kind | ""`): the repositories (path, kind), and what it
    left out, in words."""

    found: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _linked(entry: os.DirEntry) -> bool:
    try:
        if entry.is_symlink():
            return True
        junction = getattr(entry, "is_junction", None)
        return bool(junction()) if callable(junction) else False
    except OSError:
        return True


def look(folders: list[str], kind_of: Callable[[str], str]) -> Look:
    """Each folder walked (the module's docstring); `kind_of(path)` says whether a folder is a repository and of which
    kind ("" when it is not)."""
    out = Look()
    for top in folders:
        if not os.path.isdir(top):
            out.notes.append(f"{top} is not there now")
            continue
        seen, stack = 0, [(top, 0)]
        while stack:
            path, depth = stack.pop()
            kind = kind_of(path)
            if kind:
                out.found.append((path, kind))
                if len(out.found) >= MAX_FOUND:
                    out.notes.append(f"the first {MAX_FOUND} repositories: the look ended there")
                    return out
                continue
            seen += 1
            if seen > MAX_DIRS:
                out.notes.append(f"{top}: {MAX_DIRS:,} folders looked at, the rest left (name a folder further in)")
                break
            if depth >= MAX_DEPTH:
                continue
            try:
                with os.scandir(path) as it:
                    subs = sorted((e.path for e in it if e.name not in SKIP and not _linked(e) and e.is_dir()),
                                  reverse=True)
            except OSError as e:
                out.notes.append(f"{path}: not read ({type(e).__name__})")
                continue
            stack.extend((s, depth + 1) for s in subs)
    out.found.sort(key=lambda x: x[0].lower())
    return out
