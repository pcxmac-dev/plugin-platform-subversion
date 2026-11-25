"""svn, svnadmin and svnserve as stand-ins, and working copies and repositories as a few files. `FakeSpawn` is the
runner's spawn (subprocess.run's shape): it answers each program's --version --quiet as it prints it and keeps every
call with its keywords; `runner()` makes a Runner whose `which` finds only the programs given. `working_copy` writes a
wc.db with the tables and columns the plugin reads, as Subversion lays them out; `repository` an FSFS repository's small
files: nothing runs."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from plugin_platform_subversion.tool import Runner

BIN = "C:\\Program Files\\TortoiseSVN\\bin"
VERSIONS = {"svn": "1.14.5\n", "svnadmin": "1.14.5\n", "svnserve": "1.14.5\n"}


@dataclass
class Done:
    returncode: int
    stdout: str
    stderr: str = ""


class FakeSpawn:
    def __init__(self, answers=None):
        self.answers = dict(answers or {})
        self.calls: list[tuple[list, dict]] = []

    def __call__(self, argv, **kw):
        self.calls.append((list(argv), dict(kw)))
        name = argv[0].rsplit("\\", 1)[-1].removesuffix(".exe")
        got = self.answers.get((name, *argv[1:]))
        if isinstance(got, BaseException):
            raise got
        if got is not None:
            return got
        if argv[1:] == ["--version", "--quiet"] and name in VERSIONS:
            return Done(0, VERSIONS[name])
        return Done(1, "", f"unknown: {argv}")


def runner(found=("svn", "svnadmin", "svnserve"), spawn: FakeSpawn | None = None):
    s = spawn or FakeSpawn()
    return Runner(which=lambda name: f"{BIN}\\{name}.exe" if name in found else None, spawn=s), s


def working_copy(root: Path, name: str, url_root="https://svn.example.org/repos/proj", rel="trunk", rev=42,
                 author="ciara") -> Path:
    p = root / name
    (p / ".svn").mkdir(parents=True)
    con = sqlite3.connect(p / ".svn" / "wc.db")
    con.executescript(
        "CREATE TABLE repository (id INTEGER PRIMARY KEY AUTOINCREMENT, root TEXT UNIQUE NOT NULL, uuid TEXT NOT NULL);"
        "CREATE TABLE nodes (wc_id INTEGER NOT NULL, local_relpath TEXT NOT NULL, op_depth INTEGER NOT NULL, "
        "parent_relpath TEXT, repos_id INTEGER, repos_path TEXT, revision INTEGER, presence TEXT NOT NULL, "
        "changed_revision INTEGER, changed_date INTEGER, changed_author TEXT, "
        "PRIMARY KEY (wc_id, local_relpath, op_depth));")
    con.execute("INSERT INTO repository (root, uuid) VALUES (?, ?)", (url_root, "6a7e1b2c-0000-4000-8000-123456789abc"))
    con.execute("INSERT INTO nodes VALUES (1, '', 0, NULL, 1, ?, ?, 'normal', ?, ?, ?)",
                (rel, rev, rev - 2, 1_764_000_000_000_000, author))
    con.commit()
    con.close()
    return p


def repository(root: Path, name: str, youngest=7) -> Path:
    p = root / name
    (p / "db").mkdir(parents=True)
    (p / "conf").mkdir()
    (p / "format").write_text("5\n")
    (p / "db" / "fs-type").write_text("fsfs\n")
    (p / "db" / "uuid").write_text("0e1f2a3b-0000-4000-8000-abcdefabcdef\n1764000000\n")
    (p / "db" / "current").write_text(f"{youngest}\n")
    return p
