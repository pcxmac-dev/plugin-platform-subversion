"""The versions of svn, svnadmin and svnserve through the stand-in runner, the folders you name and the working copies
and repositories found under them, read from their files alone; its two changes asked from its page alone."""
from __future__ import annotations

import subprocess

import pytest

from liminal_libs.apps import asking
from liminal_libs.instances import Refusal
from liminal_libs.machines import standins

from plugin_platform_subversion import SubversionPlugin, folders as F, repos
from stand_ins import FakeSpawn, repository, runner, working_copy


def plugin(found=("svn", "svnadmin", "svnserve"), spawn=None, pairs=None):
    r, s = runner(found, spawn)
    p = SubversionPlugin(runner=r)
    p.login = standins.login(dict(pairs or {}))
    return p, s


def as_page(p, hook, *args):
    with asking.asking(asking.PAGE):
        return getattr(p, hook)(*args)


def test_its_versions_are_its_programs_run_once_each_without_a_window():
    p, s = plugin()
    st = p.status()
    assert st["programs"] == {"svn": "1.14.5", "svnadmin": "1.14.5", "svnserve": "1.14.5"}
    assert st["summary"].startswith("Subversion 1.14.5")
    assert [argv[1:] for argv, _ in s.calls] == [["--version", "--quiet"]] * 3
    for _, kw in s.calls:
        assert kw["stdin"] is subprocess.DEVNULL and kw["timeout"] <= 5 and kw["cwd"] and kw["env"]["LC_ALL"] == "C"
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            assert kw["creationflags"] & 0x08000000
    p.status()
    assert len(s.calls) == 3  # kept READ_S
    p.refresh()
    assert len(s.calls) == 6


def test_no_subversion_here_is_said_and_nothing_runs():
    p, s = plugin(found=())
    st = p.status()
    assert s.calls == [] and "not on PATH" in st["summary"] and p.present() is False


def test_a_program_that_waits_too_long_is_said_in_words():
    p, _ = plugin(spawn=FakeSpawn({("svnserve", "--version", "--quiet"): subprocess.TimeoutExpired("svnserve", 5)}))
    st = p.status()
    assert "did not answer within" in st["programs"]["svnserve"] and st["programs"]["svn"] == "1.14.5"


def test_folders_are_named_from_its_page_alone(tmp_path):
    p, _ = plugin()
    for who in ("a-harness", None):
        with asking.asking(who), pytest.raises(Refusal, match="from its page alone"):
            p.add_folder(str(tmp_path))
    as_page(p, "add_folder", str(tmp_path))
    assert p._folders().all() == [str(tmp_path)]
    with asking.asking("a-harness"), pytest.raises(Refusal, match="from its page alone"):
        p.remove_folder(str(tmp_path))
    as_page(p, "remove_folder", str(tmp_path))
    assert p._folders().all() == []
    with pytest.raises(Refusal, match="whole disk"):
        as_page(p, "add_folder", tmp_path.anchor)


def test_working_copies_and_repositories_are_found_and_read_from_their_files(tmp_path):
    wc = working_copy(tmp_path, "proj", url_root="https://ciara:hunter2pass@svn.example.org/repos/proj")
    (wc / "sub").mkdir()
    repo = repository(tmp_path / "srv", "main")
    p, s = plugin()
    as_page(p, "add_folder", str(tmp_path))
    st = p.status()
    rows = {r[0]["sub"]: r for r in st["tables"][1]["rows"]}
    assert set(rows) == {str(wc), str(repo)}
    assert rows[str(wc)][1] == "working copy"
    assert rows[str(wc)][2]["text"] == "https://ciara@svn.example.org/repos/proj/trunk"  # its password taken out
    assert rows[str(wc)][3] == "r42" and rows[str(wc)][4]["text"] == "r40 by ciara" and rows[str(wc)][4]["sub"]
    assert "hunter2pass" not in str(st)
    assert rows[str(repo)][1] == "repository" and rows[str(repo)][2]["text"] == "fsfs (format 5)"
    assert rows[str(repo)][3] == "r7"
    assert [argv[1:] for argv, _ in s.calls] == [["--version", "--quiet"]] * 3  # svn was never run in one
    assert "1 working copies and 1 repositories" in st["summary"]


def test_a_working_copy_is_read_without_writing_to_it(tmp_path):
    wc = working_copy(tmp_path, "proj")
    before = sorted(x.name for x in (wc / ".svn").iterdir())
    found = repos.read(str(wc))
    assert found.revision == 42 and found.url.endswith("/proj/trunk")
    assert sorted(x.name for x in (wc / ".svn").iterdir()) == before  # no journal, no wal left


def test_a_broken_wc_db_is_said(tmp_path):
    p = tmp_path / "bad"
    (p / ".svn").mkdir(parents=True)
    (p / ".svn" / "wc.db").write_bytes(b"not a database at all, just bytes" * 10)
    found = repos.read(str(p))
    assert found.kind == "working copy" and "could not be read" in found.why


def test_the_look_is_bounded(tmp_path, monkeypatch):
    for i in range(4):
        repository(tmp_path, f"r{i}")
    monkeypatch.setattr(F, "MAX_FOUND", 2)
    assert len(F.look([str(tmp_path)], repos.kind_of).found) == 2


def test_its_facts_ask_nothing():
    p, s = plugin()
    assert p.api_facts() == {}
    p.status()
    n = len(s.calls)
    facts = p.api_facts()
    assert len(s.calls) == n and facts["Subversion's programs"]["svn"].startswith("1.14.5 at ")


def test_wc_db_is_opened_read_only(tmp_path, monkeypatch):
    wc = working_copy(tmp_path, "proj")
    opened = []
    real = repos.sqlite3.connect
    monkeypatch.setattr(repos.sqlite3, "connect", lambda what, **kw: opened.append((what, kw)) or real(what, **kw))
    repos.read(str(wc))
    [(what, kw)] = opened
    assert what.startswith("file:") and what.endswith("?mode=ro") and kw["uri"] is True
