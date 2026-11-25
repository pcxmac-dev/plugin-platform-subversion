"""Nothing in these tests runs a real svn, starts a process or reaches the network: svn is the stand-in runner's
(stand_ins.py), the container plugin and the firewall are the library's stand-ins (machines/servicestandins.py),
and a repository is a few files a test writes in its own temporary folder. While a test runs, an audit hook refuses every
way Python has to start a process or to reach the network (REFUSED: each raises its audit event first, whatever name
its caller bound): it raises `Reached`, a BaseException no `except Exception` of the plugin's or the library's swallows,
and the test fails at its end as well, whatever caught it. No program is found on PATH, and SUBVERSION_ variables are taken
out of this process's environment, so a test reads only the settings its own login gives."""
from __future__ import annotations

import os
import shutil
import sys

import pytest

try:
    import requests  # noqa: F401 - imported before any test: urllib3 looks at this machine's IPv6 as it loads (a bind)
except ImportError:  # (not every test run has it)
    pass

REFUSED = frozenset({
    "subprocess.Popen", "os.system", "os.startfile", "os.startfile/2", "os.spawn", "os.posix_spawn", "os.exec",
    "os.fork", "os.forkpty", "_winapi.CreateProcess",
    "socket.connect", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo", "socket.gethostbyname",
    "socket.gethostbyaddr", "socket.getnameinfo",
})


class Reached(BaseException):
    """A test reached for real what it must stand in for: a process, a connection, a name looked up."""


class Guard:
    """The audit hook's switch: on while a test runs (set through monkeypatch, whose undo() lifts it)."""

    on = False
    reached: list[str] = []


def _audit(event: str, args) -> None:
    if Guard.on and event in REFUSED:
        Guard.reached.append(event)
        raise Reached(f"a test reached {event} for real: give the plugin a stand-in")


sys.addaudithook(_audit)  # for the whole run: a hook is never taken away, and off between tests


@pytest.fixture(autouse=True)
def nothing_runs(monkeypatch):
    reached: list[str] = []
    monkeypatch.setattr(Guard, "reached", reached)
    monkeypatch.setattr(Guard, "on", True)
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None)
    for name in list(os.environ):
        if name.upper().startswith("SUBVERSION_"):
            monkeypatch.delenv(name, raising=False)
    yield reached
    Guard.on = False
    assert not reached, f"the test reached {', '.join(reached)} for real"
