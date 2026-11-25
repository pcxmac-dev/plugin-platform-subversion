"""svnserve in a container, through a container plugin's plans (the library's ContainedService), on the library's
stand-ins alone (machines/servicestandins.py): no docker, no process, no socket. No one gets in anonymously; the admin's
password goes to the container as a secret, by environment alone; it runs on this PC alone until you Expose… it."""
from __future__ import annotations

import re

import pytest

from liminal_libs.instances import Refusal
from liminal_libs.machines.containedservice import UNREAD
from liminal_libs.machines.servicestandins import ServiceWorld, quick_pace

from plugin_platform_subversion import SubversionPlugin, recipe
from stand_ins import runner

PASSWORD = "correct-horse-battery-9"
DIG = "sha256:" + "e" * 64


def pins(digest=DIG):
    return {s: {part: {**pin, "digest": digest} for part, pin in parts.items()} for s, parts in recipe.PINS.items()}


def world(tmp_path, pairs=None, digest=DIG):
    p = SubversionPlugin(runner=runner()[0], pace=quick_pace(), pins=pins(digest))
    w = ServiceWorld(p, pairs={recipe.ADMIN_PASSWORD: PASSWORD} if pairs is None else pairs, folder=tmp_path)
    return w, p


def test_its_shipped_pin_is_read_and_an_unread_one_is_refused(tmp_path):
    # read from Docker Hub on 2026-11-25 (its manifest list alone); an unread pin is still refused
    assert all(re.fullmatch(r"sha256:[0-9a-f]{64}", pin["digest"]) and pin["digest"] != UNREAD and pin["size"] > 0
               for parts in recipe.PINS.values() for pin in parts.values())
    w, p = world(tmp_path, digest=UNREAD)
    w.grant()
    with pytest.raises(Refusal, match="not pinned by digest yet"):
        w.ask("service_install", w.HOST, w.TARGET, "svnserve", "no")


def test_it_is_never_installed_open_its_password_is_needed_first(tmp_path):
    w, p = world(tmp_path, pairs={})
    w.grant()
    with pytest.raises(Refusal, match="set SUBVERSION_ADMIN_PASSWORD"):
        w.ask("service_install", w.HOST, w.TARGET, "svnserve", "no")
    w.login.env[recipe.ADMIN_PASSWORD] = "line\nbreak-password"
    with pytest.raises(Refusal, match="line break"):
        w.ask("service_install", w.HOST, w.TARGET, "svnserve", "no")


def test_it_is_installed_on_this_pc_alone_first(tmp_path):
    w, p = world(tmp_path)
    w.grant()
    with pytest.raises(Refusal, match="this PC alone first"):
        w.ask("service_install", w.HOST, w.TARGET, "svnserve", "yes")


def test_its_install_lets_no_one_in_anonymously_and_hands_the_password_as_a_secret(tmp_path):
    w, p = world(tmp_path)
    w.grant()
    answer = w.ask("service_install", w.HOST, w.TARGET, "svnserve", "no")
    words = w.page(w.HOST, "plan_words", answer["approve"][0]["plan"])
    assert "accept_kept_secret" in {a["name"] for a in words["accepts"]}  # the secret is said and asked
    end = w.through(answer)
    assert end["ok"], end
    conf = w.fake.volumes["liminal-subversion-svnserve-repos"]["files"][recipe.CONF].decode()
    assert "anon-access = none" in conf and "auth-access = write" in conf and "password-db = /tmp/liminal/passwd" in conf
    [made] = w.fake.argv_of("create")
    said = " ".join(made)
    assert PASSWORD not in said and "-p 127.0.0.1:3690:3690/tcp" in said
    assert "--config-file /var/opt/svn/.liminal/svnserve.conf" in said and "svnadmin create /var/opt/svn/main" in said
    [box] = w.fake.containers.values()
    assert box["secret_values"] == {"SVN_ADMIN_PASSWORD": PASSWORD}
    assert all(PASSWORD.encode() not in v for v in w.fake.volumes["liminal-subversion-svnserve-repos"]["files"].values())
    assert PASSWORD not in str(p.placements()) and PASSWORD not in str(end)
    assert any("svn checkout svn://127.0.0.1:3690/main" in line for line in end["lines"])


def test_the_start_script_writes_the_password_outside_the_volume_and_forgets_it():
    s = recipe.START
    assert s.index("umask 077") < s.index("> /tmp/liminal/passwd") < s.index("unset SVN_ADMIN_PASSWORD") < s.index("exec svnserve")
    assert '"$SVN_ADMIN_PASSWORD"' in s and "/var/opt/svn/" not in s.split("> ", 1)[1].split(";", 1)[0]


def test_expose_opens_it_while_the_password_is_set(tmp_path):
    w, p = world(tmp_path)
    assert w.install("svnserve", "no")["ok"]
    w.login.env[recipe.ADMIN_PASSWORD] = "short"
    with pytest.raises(Refusal, match="not opened to your network yet"):
        w.ask("service_change", "expose", "svnserve", "on")
    w.login.env[recipe.ADMIN_PASSWORD] = PASSWORD
    assert w.through(w.ask("service_change", "expose", "svnserve", "on"))["ok"]
    assert "-p 3690:3690/tcp" in " ".join(w.fake.argv_of("create")[-1]) and p.placement("svnserve")["lan"] is True


def test_on_windows_containers_it_has_no_image():
    with pytest.raises(Refusal, match="no windows image"):
        recipe.spec("windows", "svnserve", {}, PASSWORD, pins())
