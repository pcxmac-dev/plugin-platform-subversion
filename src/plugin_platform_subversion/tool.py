"""The local programs this plugin asks (svn, svnadmin, svnserve), run without a window and only to read: a `Runner` finds a program on PATH
and runs it once, with no console window (the library's proc.no_window: CREATE_NO_WINDOW on Windows), its standard input
closed, a short wait, a neutral working folder (the system's temporary folder: never a repository, whose own
configuration a program would read), its messages in plain English, and what it prints bounded. A test hands its own `which` and
`spawn`: nothing runs."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Mapping

from liminal_libs.proc import no_window

WAIT_S = 5.0  # a program's whole run, at most
MOST = 256 * 1024  # what is kept of its output
QUIET = {"LC_ALL": "C", "LANG": "C"}


@dataclass(frozen=True)
class Ran:
    """One run: its exit code and what it printed (cut at MOST)."""

    code: int
    out: str
    err: str = ""


class ToolError(Exception):
    """A program that is not on PATH, did not end in time, or could not be started, in words."""


class Runner:
    """Finds and runs this machine's programs (the module's docstring). `which(name) -> path | None`; `spawn(argv, **kw)
    -> an object with returncode, stdout, stderr` (subprocess.run's shape)."""

    def __init__(self, which: Callable | None = None, spawn: Callable | None = None, env: Mapping[str, str] | None = None):
        self._which = which or shutil.which
        self._spawn = spawn or subprocess.run
        self._env = dict(QUIET if env is None else env)

    def find(self, name: str) -> str:
        """Where `name` is on PATH ("" when it is not)."""
        try:
            return str(self._which(name) or "")
        except (OSError, ValueError):
            return ""

    def run(self, name: str, *args: str, timeout: float = WAIT_S) -> Ran:
        """`name args...` run once and read; ToolError when it is not found, not started or not done in time."""
        path = self.find(name)
        if not path:
            raise ToolError(f"{name} is not on PATH here")
        env = {**os.environ, **self._env}
        try:
            done = self._spawn([path, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, stdin=subprocess.DEVNULL, check=False, cwd=tempfile.gettempdir(),
                               env=env, **no_window())
        except subprocess.TimeoutExpired:
            raise ToolError(f"{name} did not answer within {timeout:g} s") from None
        except (OSError, subprocess.SubprocessError) as e:
            raise ToolError(f"{name} could not be started: {type(e).__name__}: {e}"[:300]) from None
        return Ran(int(done.returncode), str(done.stdout or "")[:MOST], str(done.stderr or "")[:MOST])


def version_of(text: str) -> str:
    """The version a program prints ("git version 2.47.1.windows.1" -> "2.47.1.windows.1"); "" when none."""
    found = re.search(r"\b(\d+\.\d+(?:\.\d+)?(?:[.+~-][0-9A-Za-z.+~-]*)?)", str(text or ""))
    return found.group(1) if found else ""
