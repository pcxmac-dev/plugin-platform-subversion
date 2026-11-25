# plugin-platform-subversion

Subversion for Liminal, one of the platform's Source Control plugins (Monday list item 35). `SECTION` "scm", icon
`subversion`. Needs liminal-libs 1.95.0 (a secret the plugin declares among its own keys is handed to its container;
1.93.0 and 1.94.0 refused it).

## What it does

- **The versions of svn, svnadmin and svnserve**: each `--version --quiet`, run once per look without a window, its
  standard input closed, outside any working copy, five seconds at most.
- **The folders you name** on its page (Add a folder…, Remove…), kept through the login as `SUBVERSION_FOLDERS`: an
  absolute path to a folder that is there, never a drive's or the file system's root, 16 at most. It looks four
  folders down at most, follows no link (symbolic link, junction), steps over `node_modules`, `.venv` and the like,
  and never goes into what it found. Nothing is ever looked for across a whole disk.
- **Working copies and repositories read from their own files** (`repos.py`): a working copy's `.svn/wc.db` opened
  read-only (`mode=ro`: nothing written, no journal made): its URL (without a password), revision and last change;
  an FSFS repository's `format`, `db/fs-type`, `db/uuid` and `db/current`. svn is never run in one.
- **svnserve in a container** (`recipe.py`, the library's ContainedService; garethflowers/svn-server 1.8.1): its
  repositories in a volume (/var/opt/svn), a first repository `main` made at its first start. No one gets in
  anonymously (a seeded svnserve.conf, read with --config-file: anon-access none, auth-access write). svnserve keeps
  passwords as they are (CRAM-MD5 needs them), so the admin's password (`SUBVERSION_ADMIN_PASSWORD`, 12 characters at
  least, through the login) goes to the container as a secret, by environment alone (the plan asks
  accept_kept_secret), written at each start into the container's /tmp and unset before svnserve runs: never into the
  volume, onto a command line or into a spec. On this PC alone (127.0.0.1:3690) until you Expose… it.

## Its pin

`docker.io/garethflowers/svn-server:1.8.1` at `sha256:26688af4…20095658`, read from Docker Hub on 2026-11-25 (its
manifest list, then its amd64 config blob; no layer, no image pulled), 7.9 MB for amd64. An unread pin (`UNREAD`) is
refused before any plan.

What its config blob says: no Entrypoint; Cmd `/usr/bin/svnserve --daemon --foreground --root /var/opt/svn`; no User
(root); ExposedPorts `3690/tcp`; Volumes `/var/opt/svn`; WorkingDir `/var/opt/svn`. The recipe matches it: its
command (`/bin/sh -c …`) replaces the image's Cmd whole, as no entrypoint wraps it, and runs as root in the declared
volume. That `/bin/sh` and `svnadmin` are in the image is its Alpine base's word (a layer's, not read).

## Tests

Stand-ins alone: no svn, svnserve, docker or network is run or reached (`tests/conftest.py` refuses every process and
connection while a test runs). Run them with the library on the path:

    PYTHONPATH="src;<liminal-libs>/src" python -m pytest -q -p no:cacheprovider

`LIMINAL_VENDOR_PAGES=1` lets `tests/test_apis.py` ask every address on its API cards once (the only test that reaches
the network). Each gate was taken out once and a test seen to fail.
