"""Tests for the remote scroll registry: RemoteRegistry client, the new
`scroll search/install --remote/publish --remote/uninstall/update` CLI
commands, manifest `dependencies` resolution (recursive, cycles, version
requirements), and sha256 checksums on publish/install.

All network use goes through a local fake HTTP server speaking the real
registry's REST shapes; the live api.getgodcode.com is never touched.
GODCODE_NO_PLUGINS=1 keeps the sibling plugin pillar from auto-loading.
"""

import hashlib
import http.server
import json
import threading
import urllib.parse
from pathlib import Path

import pytest

from godcode.registry import (
    ScrollError,
    ScrollNotFoundError,
    ScrollRegistry,
    compare_versions,
    parse_dependencies,
    parse_manifest,
)
from godcode.remote_registry import (
    RegistryClientError,
    RemoteRegistry,
    registry_base_url,
    synthesized_manifest,
)


@pytest.fixture(autouse=True)
def no_plugins(monkeypatch):
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")


# ------------------------------------------------- fake registry server ----


class FakeRegistryHandler(http.server.BaseHTTPRequestHandler):
    """Speaks the real registry REST shapes from an in-memory catalog."""

    catalog: dict = {}  # name -> {"info": {...}, "codes": {version: str}}
    posts: list = []  # recorded POST /v1/scrolls requests

    def log_message(self, *args):  # keep the test output quiet
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, query = parsed.path, urllib.parse.parse_qs(parsed.query)

        if path == "/v1/scrolls":
            q = query.get("q", [""])[0].lower()
            rows = [
                entry["info"]
                for name, entry in self.catalog.items()
                if q in name.lower()
                or q in entry["info"].get("description", "").lower()
            ]
            limit = int(query.get("limit", ["20"])[0])
            offset = int(query.get("offset", ["0"])[0])
            self._send_json({"ok": True,
                             "scrolls": rows[offset:offset + limit]})
            return

        if path.startswith("/v1/scrolls/"):
            rest = path[len("/v1/scrolls/"):]
            if rest.endswith("/download"):
                name = rest[: -len("/download")]
                entry = self.catalog.get(name)
                if entry is None:
                    self._send_json({"ok": False,
                                     "error": "Scroll not found"}, 404)
                    return
                latest = entry["info"]["latest"]
                self._send_text(entry["codes"][latest])
                return
            if "/versions/" in rest:
                name, _, version = rest.partition("/versions/")
                entry = self.catalog.get(name)
                code = entry["codes"].get(version) if entry else None
                if code is None:
                    self._send_json({"ok": False,
                                     "error": "Version not found"}, 404)
                    return
                self._send_json({"ok": True, "name": name, "version": version,
                                 "code": code, "created_at": "2026-09-25T00:00:00Z"})
                return
            entry = self.catalog.get(rest)
            if entry is None:
                self._send_json({"ok": False, "error": "Scroll not found"},
                                404)
                return
            self._send_json({"ok": True, **entry["info"]})
            return

        self._send_json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/v1/scrolls":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            self.posts.append(
                {"auth": self.headers.get("Authorization"), "body": body}
            )
            self._send_json({"ok": True, "name": body["name"],
                             "version": body["version"]})
            return
        self._send_json({"ok": False, "error": "not found"}, 404)


class FakeRegistry:
    """Test helper: seeds the fake catalog and exposes its base URL."""

    def __init__(self, base_url):
        self.base_url = base_url

    def seed(self, name, versions, description="", author="Test Scribe"):
        versions = list(versions)
        best = versions[0]
        for v in versions[1:]:
            if compare_versions(v, best) > 0:
                best = v
        codes = {
            v: f'BEGIN CREATION\nREVEAL("{name} {v}")\nEND CREATION\n'
            for v in versions
        }
        FakeRegistryHandler.catalog[name] = {
            "info": {
                "name": name,
                "description": description or f"A remote {name}.",
                "author": author,
                "downloads": 3,
                "versions": sorted(
                    versions, key=lambda v: [int(x) for x in v.split(".")]),
                "latest": best,
                "updated_at": "2026-09-25T00:00:00Z",
            },
            "codes": codes,
        }

    @property
    def posts(self):
        return FakeRegistryHandler.posts


@pytest.fixture()
def fake_registry(monkeypatch):
    FakeRegistryHandler.catalog = {}
    FakeRegistryHandler.posts = []
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), FakeRegistryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("GODCODE_REGISTRY_URL", url)
    yield FakeRegistry(url)
    server.shutdown()
    server.server_close()


@pytest.fixture()
def reg(tmp_path, monkeypatch):
    """A ScrollRegistry rooted entirely in tmp dirs."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)
    return ScrollRegistry(
        registry_root=tmp_path / "registry",
        home=home,
        project_dir=project,
    )


def write_scroll(base: Path, name: str, version: str = "1.0.0",
                 entry: str | None = None, godcode: str = ">=2.0",
                 dependencies: str | None = None) -> Path:
    """Create a scroll dir with a manifest and a tiny entry scroll."""
    entry = entry or f"{name}.god"
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / entry).write_text(
        f'DEFINE RITE HELLO_{name.upper().replace("-", "_")}()\n'
        f'RETURN "{name} {version}"\n'
        "END RITE\n",
        encoding="utf-8",
    )
    dep_line = (f'dependencies = "{dependencies}"\n'
                if dependencies is not None else "")
    (d / "scroll.toml").write_text(
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        'author = "Test Scribe"\n'
        f'description = "A test scroll called {name}."\n'
        f'entry = "{entry}"\n'
        f'godcode = "{godcode}"\n'
        f"{dep_line}",
        encoding="utf-8",
    )
    return d


# ------------------------------------------------------ base URL config ----


def test_base_url_defaults_to_live(monkeypatch):
    monkeypatch.delenv("GODCODE_REGISTRY_URL", raising=False)
    assert registry_base_url() == "https://api.getgodcode.com"


def test_base_url_env_override(monkeypatch):
    monkeypatch.setenv("GODCODE_REGISTRY_URL", "http://localhost:9999/")
    assert RemoteRegistry().base_url == "http://localhost:9999"


# ------------------------------------------------------ client: search ------


def test_search_returns_rows(fake_registry):
    fake_registry.seed("sky-scroll", ["1.0.0"], description="Reads the sky.")
    rows = RemoteRegistry().search("sky")
    assert len(rows) == 1
    assert rows[0]["name"] == "sky-scroll"
    assert rows[0]["latest"] == "1.0.0"
    assert rows[0]["description"] == "Reads the sky."


def test_search_no_match_returns_empty(fake_registry):
    assert RemoteRegistry().search("nothing-like-this") == []


# -------------------------------------------------------- client: info -----


def test_info_returns_catalog_record(fake_registry):
    fake_registry.seed("sky-scroll", ["1.0.0", "1.2.0"])
    info = RemoteRegistry().info("sky-scroll")
    assert info["name"] == "sky-scroll"
    assert info["versions"] == ["1.0.0", "1.2.0"]
    assert info["latest"] == "1.2.0"
    assert info["author"] == "Test Scribe"


def test_info_unknown_scroll_raises(fake_registry):
    with pytest.raises(RegistryClientError, match="not found"):
        RemoteRegistry().info("never-there")


def test_info_unreachable_server_raises(monkeypatch):
    monkeypatch.setenv("GODCODE_REGISTRY_URL", "http://127.0.0.1:1/")
    with pytest.raises(RegistryClientError, match="cannot reach"):
        RemoteRegistry().search("x")


# -------------------------------------------------- client: fetch code -----


def test_fetch_code_latest(fake_registry):
    fake_registry.seed("sky-scroll", ["1.0.0", "2.0.0"])
    code, version = RemoteRegistry().fetch_code("sky-scroll")
    assert version == "2.0.0"
    assert "sky-scroll 2.0.0" in code


def test_fetch_code_exact_version(fake_registry):
    fake_registry.seed("sky-scroll", ["1.0.0", "2.0.0"])
    code, version = RemoteRegistry().fetch_code("sky-scroll", "1.0.0")
    assert version == "1.0.0"
    assert "sky-scroll 1.0.0" in code


def test_fetch_code_unknown_version_raises(fake_registry):
    fake_registry.seed("sky-scroll", ["1.0.0"])
    with pytest.raises(RegistryClientError):
        RemoteRegistry().fetch_code("sky-scroll", "9.9.9")


# ------------------------------------------------- client: publish --------


def test_publish_sends_bearer_token_and_body(fake_registry):
    client = RemoteRegistry()
    result = client.publish_scroll(
        name="sky-scroll", version="1.0.0", code="BEGIN CREATION\nEND CREATION\n",
        description="Reads the sky.", author="Test Scribe", token="secret-tok")
    assert result["ok"] is True
    post = fake_registry.posts[0]
    assert post["auth"] == "Bearer secret-tok"
    assert post["body"]["name"] == "sky-scroll"
    assert post["body"]["version"] == "1.0.0"
    assert post["body"]["code"].startswith("BEGIN CREATION")
    assert post["body"]["description"] == "Reads the sky."
    assert post["body"]["author"] == "Test Scribe"


def test_publish_without_token_refused(fake_registry):
    with pytest.raises(RegistryClientError, match="needs a token"):
        RemoteRegistry().publish_scroll(
            name="x", version="1.0.0", code="c",
            description="d", author="a", token="")


# ----------------------------------------------- manifest dependencies ----


def test_parse_dependencies():
    assert parse_dependencies("json-tools >= 1.0.0, dates") == [
        ("json-tools", ">= 1.0.0"), ("dates", None)]
    assert parse_dependencies("") == []
    assert parse_dependencies("  ") == []
    assert parse_dependencies("solo") == [("solo", None)]
    assert parse_dependencies("pinned == 2.3.4") == [("pinned", "== 2.3.4")]


def test_parse_dependencies_rejects_bad_specs():
    for bad in ["Bad Name", "x >= sometime", "x,", ",x", "x >= 1.0.0, x"]:
        with pytest.raises(ScrollError):
            parse_dependencies(bad)


def test_manifest_accepts_dependencies():
    m = parse_manifest(
        'name = "app"\nversion = "1.0.0"\nauthor = "a"\ndescription = "d"\n'
        'entry = "app.god"\ngodcode = ">=2.0"\n'
        'dependencies = "json-tools >= 1.0.0, dates"\n'
    )
    assert m["dependencies"] == "json-tools >= 1.0.0, dates"


def test_manifest_rejects_bad_dependencies():
    with pytest.raises(ScrollError):
        parse_manifest(
            'name = "app"\nversion = "1.0.0"\nauthor = "a"\n'
            'description = "d"\nentry = "app.god"\ngodcode = ">=2.0"\n'
            'dependencies = "Bad Name!"\n'
        )


# --------------------------------------- install: dependency resolution --


def test_install_resolves_dependencies_recursively(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "dates", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "dates", "1.5.0"))
    reg.publish(write_scroll(tmp_path / "s3", "json-tools", "1.0.0",
                             dependencies="dates >= 1.0.0"))
    reg.publish(write_scroll(tmp_path / "s4", "app", "1.0.0",
                             dependencies="json-tools >= 1.0.0, dates"))

    receipt = reg.install("app")
    assert receipt["name"] == "app"
    assert receipt["dependencies"] == {"json-tools": "1.0.0",
                                       "dates": "1.5.0"}

    dest = tmp_path / "home" / ".godcode" / "scrolls"
    for name, version in [("app", "1.0.0"), ("json-tools", "1.0.0"),
                          ("dates", "1.5.0")]:
        assert (dest / name / version / f"{name}.god").is_file(), name
        saved = json.loads((dest / name / version / "install.json")
                           .read_text())
        assert saved["source"] == "local"

    # the dependency's own receipt records its own tree
    tools_receipt = json.loads(
        (dest / "json-tools" / "1.0.0" / "install.json").read_text())
    assert tools_receipt["dependencies"] == {"dates": "1.5.0"}


def test_install_picks_highest_satisfying_dependency(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "dates", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "dates", "1.9.0"))
    reg.publish(write_scroll(tmp_path / "s3", "dates", "2.0.0"))
    reg.publish(write_scroll(tmp_path / "s4", "app", "1.0.0",
                             dependencies="dates < 2.0.0"))
    receipt = reg.install("app")
    assert receipt["dependencies"] == {"dates": "1.9.0"}


def test_install_dependency_cycle_refused(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "alpha", "1.0.0",
                             dependencies="beta"))
    reg.publish(write_scroll(tmp_path / "s2", "beta", "1.0.0",
                             dependencies="alpha"))
    with pytest.raises(ScrollError, match="dependency cycle detected"):
        reg.install("alpha")


def test_install_self_dependency_cycle_refused(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "ouroboros", "1.0.0",
                             dependencies="ouroboros"))
    with pytest.raises(ScrollError, match="dependency cycle detected"):
        reg.install("ouroboros")


def test_install_unsatisfied_dependency_version_refused(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "dates", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "app", "1.0.0",
                             dependencies="dates >= 2.0.0"))
    with pytest.raises(ScrollNotFoundError, match="dates"):
        reg.install("app")


def test_install_missing_dependency_names_the_chain(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "app", "1.0.0",
                             dependencies="ghost-scroll"))
    with pytest.raises(ScrollNotFoundError, match="needed by app"):
        reg.install("app")


def test_install_dependency_version_conflict_refused(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "dates", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "dates", "2.0.0"))
    reg.publish(write_scroll(tmp_path / "s3", "left", "1.0.0",
                             dependencies="dates == 1.0.0"))
    reg.publish(write_scroll(tmp_path / "s4", "right", "1.0.0",
                             dependencies="dates == 2.0.0"))
    reg.publish(write_scroll(tmp_path / "s5", "app", "1.0.0",
                             dependencies="left, right"))
    with pytest.raises(ScrollError, match="version conflict"):
        reg.install("app")


def test_install_remote_fallback_installs_synthesized_manifest(
        reg, fake_registry, tmp_path):
    fake_registry.seed("sky-scroll", ["1.0.0"])
    receipt = reg.install("sky-scroll", remote=True)
    assert receipt["source"] == "remote"
    assert receipt["version"] == "1.0.0"
    dest = tmp_path / "home" / ".godcode" / "scrolls" / "sky-scroll" / "1.0.0"
    assert (dest / "sky-scroll.god").is_file()
    assert (dest / "scroll.toml").is_file()
    manifest = (dest / "scroll.toml").read_text()
    assert 'name = "sky-scroll"' in manifest
    assert 'version = "1.0.0"' in manifest
    assert receipt["checksums"]["sky-scroll.god"] == hashlib.sha256(
        (dest / "sky-scroll.god").read_bytes()).hexdigest()


def test_install_local_wins_over_remote(reg, fake_registry, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "sky-scroll", "9.9.9"))
    fake_registry.seed("sky-scroll", ["1.0.0"])
    receipt = reg.install("sky-scroll", remote=True)
    assert receipt["source"] == "local"
    assert receipt["version"] == "9.9.9"


def test_install_dependency_falls_back_to_remote(reg, fake_registry, tmp_path):
    fake_registry.seed("dates", ["1.0.0"])
    reg.publish(write_scroll(tmp_path / "s1", "app", "1.0.0",
                             dependencies="dates"))
    receipt = reg.install("app", remote=True)
    assert receipt["dependencies"] == {"dates": "1.0.0"}
    dest = tmp_path / "home" / ".godcode" / "scrolls" / "dates" / "1.0.0"
    assert (dest / "dates.god").is_file()


# ------------------------------------------------------------ checksums ---


def test_publish_records_checksums(reg, tmp_path):
    src = write_scroll(tmp_path / "src", "greet")
    reg.publish(src)
    index = reg.load_index()
    checks = index["greet"]["checksums"]["1.0.0"]
    assert checks["greet.god"] == hashlib.sha256(
        (src / "greet.god").read_bytes()).hexdigest()
    assert checks["scroll.toml"] == hashlib.sha256(
        (src / "scroll.toml").read_bytes()).hexdigest()


def test_install_refuses_tampered_registry_copy(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "src", "greet"))
    tampered = (tmp_path / "registry" / "scrolls" / "greet" / "1.0.0"
                / "greet.god")
    tampered.write_text(tampered.read_text() + "\n# evil\n",
                        encoding="utf-8")
    with pytest.raises(ScrollError, match="checksum mismatch"):
        reg.install("greet")


def test_install_ok_after_republish_heals_checksums(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "src", "greet"))
    tampered = (tmp_path / "registry" / "scrolls" / "greet" / "1.0.0"
                / "greet.god")
    tampered.write_text(tampered.read_text() + "\n# evil\n",
                        encoding="utf-8")
    reg.publish(write_scroll(tmp_path / "src2", "greet", "1.0.1"))
    receipt = reg.install("greet")
    assert receipt["version"] == "1.0.1"


# ------------------------------------------------------------ uninstall ---


def test_uninstall_removes_all_versions(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "greet", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "greet", "2.0.0"))
    reg.install("greet", version="1.0.0")
    reg.install("greet", version="2.0.0")
    removed = reg.uninstall("greet")
    assert {r["version"] for r in removed} == {"1.0.0", "2.0.0"}
    assert reg.list_installed() == []


def test_uninstall_single_version(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "greet", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "greet", "2.0.0"))
    reg.install("greet", version="1.0.0")
    reg.install("greet", version="2.0.0")
    removed = reg.uninstall("greet", version="1.0.0")
    assert removed == [{"name": "greet", "version": "1.0.0",
                        "location": "user"}]
    rows = {r["name"]: r for r in reg.list_installed()}
    assert rows["greet"]["versions"] == ["2.0.0"]


def test_uninstall_unknown_scroll_refused(reg):
    with pytest.raises(ScrollError, match="not installed"):
        reg.uninstall("never-there")


# --------------------------------------------------------------- update ---


def test_update_installs_newer_version(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "greet", "1.0.0"))
    reg.install("greet")
    reg.publish(write_scroll(tmp_path / "s2", "greet", "1.1.0"))

    results = reg.update("greet")
    assert results == [{"name": "greet", "from": "1.0.0", "to": "1.1.0",
                        "source": "local"}]
    rows = {r["name"]: r for r in reg.list_installed()}
    assert rows["greet"]["versions"] == ["1.0.0", "1.1.0"]

    again = reg.update("greet")
    assert again[0]["up_to_date"] is True


def test_update_all_scrolls(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "aaa", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "bbb", "1.0.0"))
    reg.install("aaa")
    reg.install("bbb")
    reg.publish(write_scroll(tmp_path / "s3", "aaa", "2.0.0"))

    results = {r["name"]: r for r in reg.update()}
    assert results["aaa"]["to"] == "2.0.0"
    assert results["bbb"]["up_to_date"] is True


def test_update_unknown_name_refused(reg):
    with pytest.raises(ScrollError, match="not installed"):
        reg.update("never-there")


def test_update_consults_remote_for_newer_version(reg, fake_registry,
                                                  tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "sky-scroll", "1.0.0"))
    reg.install("sky-scroll")
    fake_registry.seed("sky-scroll", ["1.0.0", "1.4.0"])

    results = reg.update("sky-scroll", remote=True)
    assert results[0]["to"] == "1.4.0"
    assert results[0]["source"] == "remote"


# ------------------------------------------------------------ CLI: search --


def test_cli_search_against_fake_registry(fake_registry, tmp_path, monkeypatch,
                                          capsys):
    from godcode.cli import main

    fake_registry.seed("sky-scroll", ["1.0.0"], description="Reads the sky.")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    assert main(["scroll", "search", "sky"]) == 0
    out = capsys.readouterr().out
    assert "sky-scroll" in out and "1.0.0" in out and "Reads the sky." in out


def test_cli_search_no_results(fake_registry, tmp_path, monkeypatch, capsys):
    from godcode.cli import main

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    assert main(["scroll", "search", "nothing-like-this"]) == 0
    assert "No scrolls found" in capsys.readouterr().out


# --------------------------------------- CLI: install against the fake ------


def test_cli_install_falls_back_to_remote(fake_registry, tmp_path, monkeypatch,
                                          capsys):
    from godcode.cli import main

    fake_registry.seed("sky-scroll", ["1.0.0"], description="Reads the sky.")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    assert main(["scroll", "install", "sky-scroll"]) == 0
    out = capsys.readouterr().out
    assert "sky-scroll 1.0.0" in out and "from remote" in out
    installed = (tmp_path / "home" / ".godcode" / "scrolls" / "sky-scroll"
                 / "1.0.0")
    assert (installed / "sky-scroll.god").is_file()
    assert (installed / "scroll.toml").is_file()


def test_cli_install_remote_imports_end_to_end(fake_registry, tmp_path,
                                               monkeypatch):
    """A remote-installed scroll IMPORTs through the interpreter."""
    from godcode.interpreter import Interpreter
    from godcode.lexer import Lexer
    from godcode.parser import Parser
    from godcode.cli import main

    fake_registry.seed("sky-scroll", ["1.0.0"])
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)
    assert main(["scroll", "install", "sky-scroll", "--project",
                 "--remote"]) == 0

    interp = Interpreter(log_path=str(tmp_path / "t.log"))
    program = Parser(Lexer('IMPORT "sky-scroll"\n').lex()).parse()
    interp.run(program, source_name=str(tmp_path / "main.god"))
    assert interp.output == ["sky-scroll 1.0.0"]


# --------------------------------------- CLI: publish --remote -------------


def test_cli_publish_remote_needs_token(tmp_path, monkeypatch, capsys):
    from godcode.cli import main

    src = write_scroll(tmp_path / "src", "sky-scroll")
    monkeypatch.delenv("GODCODE_PUBLISH_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["scroll", "publish", str(src), "--remote"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "GODCODE_PUBLISH_TOKEN" in err


def test_cli_publish_remote_with_token(fake_registry, tmp_path, monkeypatch,
                                       capsys):
    from godcode.cli import main

    src = write_scroll(tmp_path / "src", "sky-scroll")
    monkeypatch.setenv("GODCODE_PUBLISH_TOKEN", "tok-123")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    assert main(["scroll", "publish", str(src), "--remote"]) == 0
    out = capsys.readouterr().out
    assert "sky-scroll 1.0.0" in out and "remote registry" in out
    post = fake_registry.posts[0]
    assert post["auth"] == "Bearer tok-123"
    assert post["body"]["name"] == "sky-scroll"


# --------------------------------------- CLI: uninstall / update -----------


def test_cli_uninstall_and_update(reg, tmp_path, monkeypatch, capsys):
    from godcode.cli import main

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path / "proj")
    reg.publish(write_scroll(tmp_path / "s1", "greet", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "greet", "1.1.0"))

    # CLI builds its own registry from the repo root; point it at ours
    from godcode import cli
    monkeypatch.setattr(cli, "_scroll_registry", lambda: reg)

    assert main(["scroll", "install", "greet", "--version", "1.0.0"]) == 0
    capsys.readouterr()
    assert main(["scroll", "update", "greet"]) == 0
    out = capsys.readouterr().out
    assert "Updated greet 1.0.0 -> 1.1.0" in out

    assert main(["scroll", "update", "greet"]) == 0
    assert "already at the newest version" in capsys.readouterr().out

    assert main(["scroll", "uninstall", "greet"]) == 0
    out = capsys.readouterr().out
    assert "Uninstalled greet" in out
    assert reg.list_installed() == []

    with pytest.raises(SystemExit) as exc:
        main(["scroll", "uninstall", "greet"])
    assert exc.value.code == 1
    assert "not installed" in capsys.readouterr().err


# --------------------------------------- synthesized manifest -------------


def test_synthesized_manifest_shape():
    info = {"name": "sky-scroll", "description": "Reads the sky.",
            "author": "Ama", "latest": "1.0.0", "versions": ["1.0.0"]}
    manifest = synthesized_manifest("sky-scroll", info, "1.0.0")
    assert manifest["name"] == "sky-scroll"
    assert manifest["entry"] == "sky-scroll.god"
    assert manifest["version"] == "1.0.0"
    parsed = parse_manifest(
        "\n".join(f'{k} = "{v}"' for k, v in manifest.items()) + "\n")
    assert parsed["name"] == "sky-scroll"
