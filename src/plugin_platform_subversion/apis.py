"""What the Subversion plugin attaches to (plugin API 2.2): Subversion's programs, which it asks for their versions alone;
a working copy's and a repository's own files, which it reads them from; and svnserve, which it runs in a container.

These cards were written on 2026-11-25 from the Subversion book and Apache Subversion's pages as known to their writer;
no page was fetched for this build (its one network use was reading the image's digest). `LIMINAL_VENDOR_PAGES=1
pytest tests/test_apis.py` asks every address on them once."""
from __future__ import annotations

from liminal_libs.sources.apis import Api, Area, Call, Link

VERIFIED = "2026-11-25"
CLI, FILES, SERVER = "Subversion's programs", "A working copy's and a repository's files", "svnserve"
_BOOK = "https://svnbook.red-bean.com/en/1.7/"

SVN_CLI = Api(
    name=CLI, maker="The Apache Software Foundation (Apache Subversion, Apache-2.0)", kind="command",
    about=("svn (the client), svnadmin (a repository's administration) and svnserve (the server of svn://). The plugin "
           "runs each once per look with --version --quiet, without a window and outside any working copy."),
    base="svn, svnadmin and svnserve on PATH",
    version="Subversion 1.7 and later (one .svn at a working copy's root)",
    auth="none: local programs, run as the signed-in user", limits="", costs="nothing: Subversion is free and open source",
    links=(Link("Version Control with Subversion", _BOOK, "docs"),
           Link("svn reference", _BOOK + "svn.ref.svn.html", "reference"),
           Link("svnadmin reference", _BOOK + "svn.ref.svnadmin.html", "reference"),
           Link("Apache Subversion", "https://subversion.apache.org/", "tool"),
           Link("Release notes", "https://subversion.apache.org/docs/release-notes/", "changelog"),
           Link("apache/subversion", "https://github.com/apache/subversion", "source")),
    areas=(Area("Versions", "each program's own version", covered="the versions on the page"),
           Area("Working copies", "svn checkout, update, commit, status, info, log"),
           Area("Repositories", "svnadmin create, dump, load, verify, hotcopy"),
           Area("Server", "svnserve's options")),
    calls=(Call("svn --version --quiet", "svn's version", "Versions", used="svn's version, once per look"),
           Call("svnadmin --version --quiet", "svnadmin's version", "Versions", used="svnadmin's version"),
           Call("svnserve --version --quiet", "svnserve's version", "Versions", used="svnserve's version"),
           Call("svn info", "a working copy's URL and revision (reads its runtime configuration)", "Working copies"),
           Call("svn update", "a working copy brought up to date", "Working copies", writes=True),
           Call("svnadmin create", "a new repository", "Repositories", writes=True)),
    verified=VERIFIED)

SVN_FILES = Api(
    name=FILES, maker="The Apache Software Foundation", kind="file",
    about=("A working copy's administrative area (.svn at its root: wc.db, an SQLite database of its nodes and their "
           "repository) and a repository's FSFS files (format, db/fs-type, db/uuid, db/current). The plugin opens "
           "wc.db read-only and reads the repository's small files: nothing is written."),
    base="<working copy>/.svn/wc.db; <repository>/db",
    version="wc.db of Subversion 1.7 and later; FSFS",
    auth="none: files the signed-in user can read", limits="each small file read up to 4 KB", costs="",
    links=(Link("Repository administration", _BOOK + "svn.reposadmin.html", "guide"),
           Link("Working copy internals (wc-ng)", "https://subversion.apache.org/docs/community-guide/", "docs")),
    areas=(Area("wc.db", "a working copy's nodes, their repository, revision and last change",
                covered="the URL, revision and last change of each working copy"),
           Area("FSFS", "a repository's store: format, type, UUID, youngest revision",
                covered="each repository's store, UUID and youngest revision"),
           Area("Pristine copies", "a working copy's unchanged files")),
    calls=(Call("SELECT root, uuid, repos_path, revision, changed_* FROM nodes JOIN repository", "a working copy's root "
                "node, read-only", "wc.db", used="the working copies' columns"),
           Call("read db/current, db/uuid, db/fs-type, format", "a repository's facts", "FSFS",
                used="the repositories' columns"),
           Call("read .svn/pristine", "a file as last checked out", "Pristine copies")),
    verified=VERIFIED)

SVNSERVE = Api(
    name=SERVER, maker="The Apache Software Foundation, in garethflowers/svn-server's image", kind="socket",
    about=("svnserve, Subversion's own server of the svn:// protocol, run by the plugin in a container: its repositories "
           "in a volume, its configuration seeded (anon-access none, auth-access write), its admin's password from the "
           "login. Its first repository, main, is made at its first start."),
    base="svn://127.0.0.1:3690/main (this PC alone until Expose…)",
    version="the pinned image, garethflowers/svn-server 1.8.1",
    auth="svnserve's own password database (CRAM-MD5): the admin and SUBVERSION_ADMIN_PASSWORD", limits="", costs="nothing",
    links=(Link("svnserve, a custom server", _BOOK + "svn.serverconfig.svnserve.html", "guide"),
           Link("garethflowers/svn-server", "https://hub.docker.com/r/garethflowers/svn-server", "tool"),
           Link("garethflowers/docker-svn-server", "https://github.com/garethflowers/docker-svn-server", "source")),
    areas=(Area("Sign-in", "svnserve.conf's anon-access, auth-access and password-db", covered="seeded"),
           Area("svn://", "checkout, update and commit over svnserve's protocol",
                covered="said on the page: how to check out its first repository"),
           Area("Authorization", "an authz file's per-path rules")),
    calls=(Call("svn checkout svn://<host>:3690/main", "its first repository checked out", "svn://",
                used="said on the page after its install"),
           Call("svn commit", "changes sent to it", "svn://", writes=True)),
    verified=VERIFIED)

APIS = (SVN_CLI, SVN_FILES, SVNSERVE)
