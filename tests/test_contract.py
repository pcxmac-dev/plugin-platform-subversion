"""The plugin conforms to the class contract (plugin API 2.2: liminal_libs.sources.conformance, read from the plugin
alone, nothing run): a machine plugin of the platform, drawn under its Source Control plugins, its hooks the machine
kind's, the base's and its own, its settings declared as the login keeps them, its version, floor and entry point as
pyproject says them, and what it says of the interface it shares sound by the Internal API tab's rules."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import plugin_platform_subversion as module
from liminal_libs.apps import asking
from liminal_libs.sources.conformance import assert_module_conforms
from liminal_libs.sources.keys import refusal
from liminal_libs.ui import STATIC

PYPROJECT = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
OWN = ("refresh", "add_folder", "remove_folder")
BASE = {"hosts", "service_install", "service_change", "service_carry", "service_log", "service_forget"}


def test_the_plugin_conforms_to_the_class_contract():
    found = assert_module_conforms(module)
    assert [p.name for p in found] == ["subversion"] and all(p.api == "2.2" and not p.is_record for p in found)
    p = found[0]
    assert (p.SYSTEM, p.KIND, p.title, p.order, p.SECTION) == ("platform", "machine", "Subversion", 783, "scm")
    assert p.interface()["apis"] == [a.name for a in p.apis]


def test_its_hooks_are_the_machine_kinds_the_bases_and_its_own():
    p = module.MACHINE
    assert set(p.interface()["hooks"]) == {"present", "status", *OWN, *BASE}
    assert p.HOOKS[-3:] == OWN and p.JOB_HOOKS == ("service_carry",)
    assert not p.gives("setup") and not p.gives("run") and not p.gives("instances")


def test_its_changes_are_asked_from_its_page_alone():
    p = module.MACHINE
    assert {"add_folder", "remove_folder"} <= set(p.PAGE_ONLY_HOOKS)
    for change in ("add_folder", "remove_folder", "service_install", "service_change", "service_carry"):
        assert asking.refusal(p, change, "a-harness") and asking.refusal(p, change, None)
        assert asking.refusal(p, change, asking.PAGE) == ""
    assert asking.refusal(p, "refresh", "a-harness") == asking.refusal(p, "status", "a-harness") == ""


def test_its_settings_are_declared_as_the_login_keeps_them():
    names = [k.name for k in module.MACHINE.keys]
    assert names == ["SUBVERSION_ADMIN_PASSWORD"] and all(refusal(n) is None for n in names)
    assert module.MACHINE.keys[0].secret is True  # handed to svnserve as a secret, never said
    kept = dict(module.MACHINE.KEEPS)
    assert set(kept) == {"SUBVERSION_SERVICES", "SUBVERSION_FOLDERS"}


def test_its_icon_is_one_the_platforms_page_draws():
    assert module.MACHINE.ICON == "subversion"
    drawn = set(re.findall(r"^\s*([a-z]+):\s*'", (STATIC / "icons.js").read_text(encoding="utf-8"), re.M))
    if "subversion" not in drawn:
        pytest.skip("the library's icons.js draws no subversion mark yet: the tray shows none for the plugin until it does")


def test_its_version_floor_and_entry_point_are_pyprojects():
    assert re.search(r'^version = "([^"]+)"', PYPROJECT, re.M).group(1) == module.__version__ == "0.1.0"
    assert re.search(r'"liminal-libs>=([0-9.]+)"', PYPROJECT).group(1) == "1.95.0"  # its own secret handed over
    assert '[project.entry-points."liminal.providers"]\nsubversion = "plugin_platform_subversion"' in PYPROJECT


def test_what_it_says_of_its_interface_is_sound():
    internal = pytest.importorskip("liminal_libs.internal")
    assert internal.problems(module.MACHINE) == []
    assert 1 <= len(module.MACHINE.INTERNAL_NOTES) <= 40 and all(len(n) <= 400 for n in module.MACHINE.INTERNAL_NOTES)
