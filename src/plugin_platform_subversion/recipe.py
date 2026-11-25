"""svnserve's recipe for a container (0.1.0; Monday list item 35, with the user's answers of 2026-11-23 and 2026-11-25:
every server in a container through the container plugin you pick, a seeded sign-in, this PC alone first, then
Expose…, images pinned by digest).

One part, `server` (garethflowers/svn-server: Alpine's Subversion, svnserve on 3690), its repositories in the `repos`
volume (/var/opt/svn). Its sign-in is on before its first start: a configuration seeded into the new volume
(.liminal/svnserve.conf, read with --config-file in place of each repository's own) lets no one in anonymously
(anon-access none) and the admin in to write, from a password database outside the volume. svnserve's password
database holds each password as it is (it signs in by CRAM-MD5, which needs the password itself), so the password you
set (SUBVERSION_ADMIN_PASSWORD, through the login) is handed to the container as a secret, by environment alone
(accept_kept_secret: its container plugin says who can read it), and written at each start into /tmp of the container,
never into the volume nor onto a command line. A first repository, `main`, is made at the first start (svnadmin
create), and more are made the same way, by the repository's own tools. Installed on this PC alone (127.0.0.1:3690);
Expose… opens it to your network.

The pin: read from Docker Hub on 2026-11-25 (its manifest list, then its amd64 config blob; no layer, no image
pulled). The config says: no Entrypoint, Cmd /usr/bin/svnserve --daemon --foreground --root /var/opt/svn, no User (root),
port 3690/tcp, Volume /var/opt/svn, WorkingDir /var/opt/svn: so this recipe's command replaces the whole of what runs,
as root, in the volume the image declares. That /bin/sh and svnadmin are in it is its Alpine base's and its Dockerfile's
word (a layer's, not read)."""
from __future__ import annotations

from collections.abc import Mapping

from liminal_libs.instances import Refusal
from liminal_libs.machines.containers import ServiceSpec

OWNER = "subversion"
ADMIN = "admin"
ADMIN_PASSWORD = "SUBVERSION_ADMIN_PASSWORD"  # the password you set, a pair through the login, handed as a secret
PASSWORD_LEAST = 12
SVN_PORT = 3690
MEMORY_MB = 256
CONF = ".liminal/svnserve.conf"  # inside the repos volume
HUB = "https://hub.docker.com/r/"
PINS = {
    "linux": {
        "server": dict(ref="docker.io/garethflowers/svn-server:1.8.1",
                       digest="sha256:26688af47713ff4fea4c654ccdbfd86e50b2fe6e6d902c0e4b36249820095658",
                       size=7896393, system="linux", platforms=["linux/amd64", "linux/arm64"], version="1.8.1",
                       licence="MIT (the image); Apache-2.0 (Subversion)", page=HUB + "garethflowers/svn-server",
                       tar=True),
    },
}
SVNSERVE_CONF = f"""# seeded by Liminal (plugin-platform-subversion 0.1.0) into a new volume, once: yours from then on
[general]
anon-access = none
auth-access = write
password-db = /tmp/liminal/passwd
realm = Liminal Subversion
"""
START = "; ".join((  # one line: a command's words hold no line break
    "set -eu", "umask 077", "mkdir -p /tmp/liminal",
    f"printf '[users]\\n{ADMIN} = %s\\n' \"$SVN_ADMIN_PASSWORD\" > /tmp/liminal/passwd",
    "unset SVN_ADMIN_PASSWORD",
    "[ -e /var/opt/svn/main/format ] || svnadmin create /var/opt/svn/main",
    f"exec svnserve --daemon --foreground --root /var/opt/svn --config-file /var/opt/svn/{CONF} --listen-port {SVN_PORT}"))


def password_problem(password: str) -> str:
    """Why a password cannot be the admin's ("" when it can)."""
    if len(password) < PASSWORD_LEAST:
        return (f"set {ADMIN_PASSWORD} ({PASSWORD_LEAST} characters at least) in the login first: svnserve's sign-in is "
                "on before its first start, so it never runs open")
    if any(ord(c) < 32 or ord(c) == 127 for c in password) or password != password.strip():
        return f"{ADMIN_PASSWORD} holds a line break, a control character or a space at an end: set it again"
    return ""


def spec(system: str, name: str, options: Mapping, password: str, pins: Mapping | None = None) -> ServiceSpec:
    """svnserve's spec for a system (Linux alone). `password`: the admin's, only checked here ("" only for reading a
    fit): it goes to the container as a secret, never in the spec."""
    pins = pins if pins is not None else PINS
    if system not in pins:
        raise Refusal(f"svnserve has no {system} image")
    fit = bool(options.get("fit"))
    if not fit:
        problem = password_problem(password)
        if problem:
            raise Refusal(problem)
    ports = list(options.get("ports") or [])
    host = int(ports[0]) if ports else SVN_PORT
    server = {
        "name": "server", "image": dict(pins[system]["server"]),
        "ports": [{"name": "svn", "container": SVN_PORT, "host": host, "lan": bool(options.get("lan")),
                   "about": "svnserve's svn:// protocol"}],
        "volumes": [{"name": "repos", "path": "/var/opt/svn", "holds": "its repositories and its configuration",
                     "owner": None}],
        "secrets": [{"variable": ADMIN_PASSWORD, "env": "SVN_ADMIN_PASSWORD"}],
        "seeds": [] if fit else [{"volume": "repos", "path": CONF, "text": SVNSERVE_CONF, "mode": 0o644}],
        "command": ["/bin/sh", "-c", START],
        "memory": (int(options.get("memory_mb") or 0) or MEMORY_MB) << 20,
        "health": {"port": "svn", "path": "", "ready_s": 60}, "stop_s": 10}
    return ServiceSpec.of({"owner": OWNER, "name": name, "title": "svnserve", "system": system, "parts": [server]})
