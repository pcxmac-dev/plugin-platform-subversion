"""Subversion for Liminal, one of the platform's Source Control plugins (Monday list item 35; the user, 2026-11-22:
"add github, gitlab and Subversion, Mercurial open source installable popular version control software"). Its SECTION is
"scm": a platform that draws that section (0.39.0) shows it under Source Control plugins, an older one under Machine
plugins.

What it reads, when the platform asks and never on its own:
- the versions of svn, svnadmin and svnserve (each `--version --quiet`, run without a window, outside any working copy:
  tool.py);
- the working copies and repositories under the folders you name on its page (folders.py: never across a whole disk),
  each read from its own files alone (repos.py: a working copy's wc.db opened read-only; a repository's db files).
  What was read is kept READ_S; Read again looks now.

What it changes, from its page alone (PAGE_ONLY_HOOKS, and checked again inside each): the folders it looks under
(kept through the login as SUBVERSION_FOLDERS); and svnserve, installed, started, stopped, updated and removed only as a
container, through the container plugin you pick, in that plugin's plans you approve (the library's ContainedService):
no anonymous access, the admin's password yours (SUBVERSION_ADMIN_PASSWORD, handed as a secret), on this PC alone until
you Expose… it. No working copy or repository here is touched."""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from liminal_libs.apps import asking
from liminal_libs.instances import Refusal
from liminal_libs.machines.containedservice import ContainedService, Pace
from liminal_libs.sources.keys import KeyVar

from . import apis as cards
from . import folders as F
from . import recipe, repos
from .tool import Runner, ToolError, version_of

__version__ = "0.1.0"
READ_S = 30.0
ROWS = 200
FOLDERS = "SUBVERSION_FOLDERS"
PROGRAMS = ("svn", "svnadmin", "svnserve")
KEYS = (KeyVar(recipe.ADMIN_PASSWORD, label="svnserve's admin password",
               hint=(f"optional: the password of svnserve's admin ({recipe.ADMIN}), {recipe.PASSWORD_LEAST} characters at "
                     "least, set before Install…: handed to its container as a secret, by environment alone (svnserve "
                     "keeps passwords as they are)")),)


def local(seconds: float) -> str:
    if not seconds:
        return "–"
    try:
        return datetime.fromtimestamp(seconds, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "–"


@dataclass(frozen=True)
class Reading:
    at: float
    when: float
    folders: tuple[str, ...]
    versions: dict = field(default_factory=dict)  # program -> (path, version, trouble)
    found: tuple = field(default=())
    notes: tuple[str, ...] = ()

    @property
    def svn(self) -> str:
        return self.versions.get("svn", ("", "", ""))[1]


class SubversionPlugin(ContainedService):
    """Subversion here: its programs' versions, the working copies and repositories under your folders, and svnserve in
    a container."""

    name = "subversion"
    title = "Subversion"
    about = ("Subversion on this machine: the versions of svn, svnadmin and svnserve, and the working copies and "
             "repositories under the folders you name, each read from its own files; svnserve run in a container "
             "through the plugin you pick")
    api = "2.2"
    apis = cards.APIS
    order = 783
    ICON = "subversion"
    SECTION = "scm"
    SERVICE = "svnserve"
    LAN_FIRST = False  # its sign-in on first, this PC alone first (the user, 2026-11-25)
    DEFAULT_MEMORY_MB = recipe.MEMORY_MB
    HOOKS = (*ContainedService.HOOKS, "refresh", "add_folder", "remove_folder")
    READ_HOOKS = ("refresh",)
    PAGE_ONLY_HOOKS = ("add_folder", "remove_folder")
    INTERNAL_NOTES = (
        "svn, svnadmin and svnserve are run for their versions alone (--version --quiet), without a window and outside "
        "any working copy; a working copy is read from its wc.db opened read-only, a repository from its db files.",
        f"Working copies and repositories are looked for under the folders you name alone ({FOLDERS}, through the "
        f"login): never across a whole disk, {F.MAX_DEPTH} folders down at most, no link followed.",
        "Its folders and svnserve's changes are its page's alone (PAGE_ONLY_HOOKS); svnserve runs only as a container, "
        "in a container plugin's plans you approve; its admin's password goes to it as a secret, by environment alone.",
    )
    keys = KEYS

    def __init__(self, runner: Runner | None = None, pace: Pace | None = None, pins=None, clock=None, wall=None):
        ContainedService.__init__(self, pace)
        self._runner = runner or Runner()
        self._pins = pins
        self._clock = clock or time.monotonic
        self._wall = wall or time.time
        self._lock = threading.Lock()
        self._reading: Reading | None = None

    @property
    def KEEPS(self):  # noqa: N802 - read as a declared word
        return (*ContainedService.KEEPS.fget(self), (FOLDERS, "the folders its working copies are looked for under"))

    # -- reading -------------------------------------------------------------------------------------------------------
    def _folders(self) -> F.Folders:
        return F.Folders(FOLDERS, lambda: self.login)

    def _version(self, program: str) -> tuple[str, str, str]:
        path = self._runner.find(program)
        if not path:
            return "", "", ""
        try:
            ran = self._runner.run(program, "--version", "--quiet")
        except ToolError as e:
            return path, "", str(e)
        v = version_of(ran.out) if ran.code == 0 else ""
        return path, v, "" if v else f"{program} --version said nothing of a version ({(ran.err or ran.out)[:120]})"

    def _read(self, fresh: bool = False) -> Reading:
        folders = tuple(self._folders().all())
        with self._lock:
            kept = self._reading
        if kept is not None and not fresh and kept.folders == folders and self._clock() - kept.at < READ_S:
            return kept
        versions = {p: self._version(p) for p in PROGRAMS}
        look = F.look(list(folders), repos.kind_of)
        found = tuple(repos.read(p, k) for p, k in look.found)
        r = Reading(self._clock(), self._wall(), folders, versions, found, tuple(look.notes))
        with self._lock:
            self._reading = r
        return r

    def _forget(self) -> None:
        with self._lock:
            self._reading = None

    def _password(self) -> str:
        try:
            got = (self.login.variables([recipe.ADMIN_PASSWORD]) or {}) if self.login is not None else {}
        except Exception:  # noqa: BLE001 - a login that cannot be asked: none set
            return ""
        return str(got.get(recipe.ADMIN_PASSWORD) or "")

    # -- svnserve (ContainedService) -----------------------------------------------------------------------------------
    def spec_for(self, system, name, options):
        """svnserve's recipe (recipe.py): no anonymous access, the admin's password handed as a secret."""
        return recipe.spec(system, name, options, "" if options.get("fit") else self._password(), self._pins)

    def lan_ready(self, hosted):
        """Its sign-in is on from its first start (anon-access none): opened to your network while the admin's password
        is set."""
        problem = recipe.password_problem(self._password())
        return (False, problem) if problem else (True, "")

    def after(self, action, hosted, line):
        """After its install: how its first repository is checked out."""
        if action != "install":
            return []
        at = re.sub(r"^[a-z]+://", "", self.address(hosted)).rstrip("/") or f"127.0.0.1:{recipe.SVN_PORT}"
        return [f"check out its first repository: svn checkout svn://{at}/main --username {recipe.ADMIN}"]

    def detach(self) -> None:
        self._forget()
        super().detach()

    # -- the hooks -------------------------------------------------------------------------------------------------------
    def present(self) -> bool:
        """Whether svn (or svnadmin, svnserve) is on PATH here, or svnserve is placed in a container."""
        return self.service_present() or any(self._runner.find(p) for p in PROGRAMS)

    def refresh(self) -> dict:
        """The programs and the folders looked at again now."""
        r = self._read(fresh=True)
        return {"said": self._summary(r), "ok": True, "lines": list(r.notes) or [f"{len(r.found)} found"]}

    def _page(self, hook: str) -> None:
        who = asking.asker()
        if who != asking.PAGE:
            raise Refusal(f"subversion's {hook} is yours, from its page alone: {who or 'no one'} asked it")

    def add_folder(self, path) -> dict:
        """A folder its working copies are looked for under, added from its page alone (kept through the login)."""
        self._page("add_folder")
        added, where = self._folders().add(path)
        self._forget()
        return {"said": f"{added} is looked under now", "ok": True, "lines": [f"kept in {where}"]}

    def remove_folder(self, path) -> dict:
        """A folder taken off its list, from its page alone: nothing on the disk is touched."""
        self._page("remove_folder")
        gone, where = self._folders().remove(path)
        self._forget()
        return {"said": f"{gone} is no longer looked under (nothing on the disk was touched)", "ok": True,
                "lines": [f"kept in {where}"]}

    def api_facts(self) -> dict:
        """What it learned while it ran, asking nothing."""
        with self._lock:
            r = self._reading
        if r is None:
            return {}
        progs = {p: (f"{v} at {path}" if v else (why or "not on PATH here")) for p, (path, v, why) in r.versions.items()}
        return {cards.CLI: {**progs, "Read": local(r.when)},
                cards.FILES: {"Folders": str(len(r.folders)), "Found": str(len(r.found))}}

    # -- the page --------------------------------------------------------------------------------------------------------
    @staticmethod
    def _summary(r: Reading) -> str:
        svn = f"Subversion {r.svn}" if r.svn else "svn is not on PATH here"
        if not r.folders:
            return f"{svn} · no folder named to look for working copies under"
        wc = sum(1 for x in r.found if x.kind == repos.WORKING_COPY)
        return f"{svn} · {wc} working copies and {len(r.found) - wc} repositories under {len(r.folders)} folders"

    def status(self) -> dict:
        """The programs' versions, the folders, their working copies and repositories, and svnserve's containers."""
        r = self._read()
        any_here = any(path for path, _, _ in r.versions.values())
        troubles = [why for _, _, why in r.versions.values() if why]
        out: dict = {"present": any_here or self.service_present(), "summary": self._summary(r),
                     "valid": self.service_valid() or any_here, "why": "",
                     "programs": {p: v or why or "not on PATH here" for p, (_, v, why) in r.versions.items()},
                     "folders": len(r.folders), "found": len(r.found),
                     "readAt": f"{local(r.when)} (kept {READ_S:g} s; Read again looks now)"}
        if troubles:
            out["note"] = "; ".join(troubles)
        out["tables"] = [self._folders_table(r), self._found_table(r)]
        out["forms"] = self._forms(r)
        out["actions"] = [{"hook": "refresh", "args": [], "title": "Read again", "note": "looks at svn and the folders now"},
                          {"form": "add_folder", "title": "Add a folder…"}]
        if self.app is not None:
            svc = self.service_status()
            out["tables"] += svc.get("tables") or []
            out["forms"] += svc.get("forms") or []
        return out

    @staticmethod
    def _folders_table(r: Reading) -> dict:
        rows = [[f, {"form": "remove_folder", "title": "Remove…", "values": {"path": f}}] for f in r.folders]
        return {"title": "Folders looked under", "columns": [{"title": "Folder"}, {"title": "Remove"}], "rows": rows,
                "empty": "No folder yet: Add a folder… names one (nothing is looked for across a disk).",
                "note": f"{F.MAX_DEPTH} folders down at most; no link followed; "
                        + ("; ".join(r.notes) if r.notes else "everything under them looked at")}

    @staticmethod
    def _found_table(r: Reading) -> dict:
        rows = []
        for x in r.found[:ROWS]:
            rev = f"r{x.revision}" if x.revision is not None else "–"
            what = x.url or x.store or "–"
            rows.append([{"text": os.path.basename(x.path) or x.path, "sub": x.path}, x.kind,
                         {"text": what, "sub": x.why or (f"UUID {x.uuid}" if x.uuid else None)},
                         rev, {"text": x.changed or "–", "sub": local(x.changed_at) if x.changed_at else None}])
        note = "read from each one's own files: svn is never run in one"
        if len(r.found) > ROWS:
            note += f" · the first {ROWS} of {len(r.found):,}"
        return {"title": "Working copies and repositories", "rows": rows, "note": note,
                "columns": [{"title": "Where"}, {"title": "Kind"}, {"title": "Checked out from / store"},
                            {"title": "Revision"}, {"title": "Last change"}],
                "empty": "None found under the folders named."}

    @staticmethod
    def _forms(r: Reading) -> list[dict]:
        forms = [{"id": "add_folder", "hook": "add_folder", "title": "Add a folder to look under", "submit": "Review",
                  "fields": [{"name": "path", "label": "Folder", "type": "text", "value": "",
                              "placeholder": r"C:\Users\you\source"}],
                  "confirm": {"title": "Look under {path}?",
                              "words": "Its folders are looked at, four down at most, each time the page reads; nothing "
                                       "in them is changed.", "yes": "Add it"}}]
        if r.folders:
            forms.append({"id": "remove_folder", "hook": "remove_folder", "title": "Stop looking under a folder",
                          "fields": [{"name": "path", "label": "Folder", "type": "fixed"}],
                          "confirm": {"title": "Stop looking under {path}?", "words": "Nothing on the disk is touched.",
                                      "yes": "Remove it"}})
        return forms


MACHINE = SubversionPlugin()
