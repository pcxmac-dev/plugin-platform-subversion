"""The tests' own guard (conftest.py): while a test runs, every way out (a process started, a connection made, a name
looked up) is refused with `Reached`, and a test that reached for one fails at its end, whatever caught it. Nothing here
starts a process: each refused event is raised by hand (sys.audit), and the one real path tried, the runner given no
stand-in, is refused before any program starts."""
from __future__ import annotations

import sys

import pytest

from conftest import REFUSED, Reached
from plugin_platform_subversion.tool import Runner


@pytest.mark.parametrize("event", sorted(REFUSED))
def test_every_way_out_is_refused_while_a_test_runs(event, nothing_runs):
    with pytest.raises(Reached):
        sys.audit(event, "a stand-in's argument")
    assert nothing_runs == [event]
    nothing_runs.clear()


def test_a_runner_given_no_stand_in_is_refused_whatever_it_catches(nothing_runs):
    """A Runner made with a real which (a path) and no spawn starts a process through subprocess: the guard refuses it
    with a BaseException the runner's `except OSError` cannot turn into an answer."""
    r = Runner(which=lambda name: sys.executable)
    with pytest.raises(Reached):
        r.run("svn", "--version")
    assert nothing_runs[:1] == ["subprocess.Popen"]
    nothing_runs.clear()
