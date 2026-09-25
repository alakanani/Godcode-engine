"""Tests for Pillar 2 — the Scroll Registry (installable God Code scrolls).

Covers: manifest parsing (valid + invalid), publish (success, duplicate
refusal, missing entry), install + latest-version resolution, list/info,
and end-to-end IMPORT of an installed scroll through the interpreter.

Everything runs against tmp registries/homes; the real ~/.godcode and the
repo's registry/ are never written to. GODCODE_NO_PLUGINS=1 keeps the
sibling plugin pillar from auto-loading during these tests.
"""

import json
import os
from pathlib import Path

import pytest

from godcode.registry import (
    ScrollError,
    ScrollRegistry,
    compare_versions,
    latest_version,
    parse_manifest,
    parse_semver,
    read_manifest,
    requirement_satisfied,
)

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def no_plugins(monkeypatch):
    monkeypatch.setenv("GODCODE_NO_PLUGINS", "1")


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
                 extra_keys: str = "") -> Path:
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
    (d / "scroll.toml").write_text(
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        'author = "Test Scribe"\n'
        f'description = "A test scroll called {name}."\n'
        f'entry = "{entry}"\n'
        f'godcode = "{godcode}"\n'
        f"{extra_keys}",
        encoding="utf-8",
    )
    return d


# ------------------------------------------------------- manifest parsing ---


def test_manifest_valid():
    m = parse_manifest(
        'name = "json-tools"\n'
        'version = "1.2.3"\n'
        'author = "Ama"\n'
        'description = "Does things. # not a comment inside quotes"\n'
        'entry = "json-tools.god"\n'
        'godcode = ">=2.0"\n'
    )
    assert m["name"] == "json-tools"
    assert m["version"] == "1.2.3"
    assert m["description"] == "Does things. # not a comment inside quotes"


def test_manifest_comments_and_blank_lines_ignored():
    m = parse_manifest(
        "# a scroll\n"
        '\n'
        'name = "x" # trailing comment\n'
        'version = "1.0.0"\n'
        'author = "a"\n'
        'description = "d"\n'
        'entry = "x.god"\n'
        'godcode = ">=2.0"\n'
    )
    assert m["name"] == "x"


def test_manifest_single_quotes_literal():
    m = parse_manifest(
        "name = 'blessings'\n"
        'version = "1.0.0"\n'
        'author = "a"\n'
        "description = 'back\\\\slash stays'\n"
        'entry = "blessings.god"\n'
        'godcode = ">=2.0"\n'
    )
    assert m["name"] == "blessings"
    assert m["description"] == "back\\\\slash stays"


def test_manifest_escapes():
    m = parse_manifest(
        'name = "x"\n'
        'version = "1.0.0"\n'
        'author = "a"\n'
        'description = "line1\\nline2\\"quoted\\""\n'
        'entry = "x.god"\n'
        'godcode = ">=2.0"\n'
    )
    assert m["description"] == 'line1\nline2"quoted"'


@pytest.mark.parametrize(
    "text",
    [
        # missing version
        'name = "x"\nauthor = "a"\ndescription = "d"\n'
        'entry = "x.god"\ngodcode = ">=2.0"\n',
        # unknown key
        'name = "x"\nversion = "1.0.0"\nauthor = "a"\ndescription = "d"\n'
        'entry = "x.god"\ngodcode = ">=2.0"\nlicense = "MIT"\n',
        # bad version
        'name = "x"\nversion = "1.0"\nauthor = "a"\ndescription = "d"\n'
        'entry = "x.god"\ngodcode = ">=2.0"\n',
        # bad name
        'name = "Bad Name!"\nversion = "1.0.0"\nauthor = "a"\n'
        'description = "d"\nentry = "x.god"\ngodcode = ">=2.0"\n',
        # unquoted value
        'name = "x"\nversion = 1.0.0\nauthor = "a"\ndescription = "d"\n'
        'entry = "x.god"\ngodcode = ">=2.0"\n',
        # duplicate key
        'name = "x"\nname = "y"\nversion = "1.0.0"\nauthor = "a"\n'
        'description = "d"\nentry = "x.god"\ngodcode = ">=2.0"\n',
        # entry is a path
        'name = "x"\nversion = "1.0.0"\nauthor = "a"\ndescription = "d"\n'
        'entry = "sub/x.god"\ngodcode = ">=2.0"\n',
        # unsatisfiable engine requirement
        'name = "x"\nversion = "1.0.0"\nauthor = "a"\ndescription = "d"\n'
        'entry = "x.god"\ngodcode = ">=99.0"\n',
        # malformed requirement
        'name = "x"\nversion = "1.0.0"\nauthor = "a"\ndescription = "d"\n'
        'entry = "x.god"\ngodcode = "sometime-later"\n',
    ],
)
def test_manifest_invalid(text):
    with pytest.raises(ScrollError):
        parse_manifest(text)


def test_read_manifest_missing_file(tmp_path):
    with pytest.raises(ScrollError):
        read_manifest(tmp_path / "nope.toml")


# ------------------------------------------------------------- versions -----


def test_semver_compare_numeric_not_lexicographic():
    assert compare_versions("1.10.0", "1.9.0") == 1
    assert compare_versions("1.9.0", "1.10.0") == -1
    assert compare_versions("2.0.0", "2.0.0") == 0
    assert compare_versions("1.0.0", "1.0.1") == -1


def test_semver_rejects_non_xyz():
    for bad in ["1.0", "v1.0.0", "1.0.0-beta", "a.b.c", ""]:
        with pytest.raises(ScrollError):
            parse_semver(bad)


def test_latest_version():
    assert latest_version(["1.9.0", "1.10.0", "1.2.3"]) == "1.10.0"
    assert latest_version(["2.0.0"]) == "2.0.0"
    with pytest.raises(ScrollError):
        latest_version([])


def test_requirement_satisfied():
    assert requirement_satisfied(">=2.0", "2.0.0")
    assert requirement_satisfied(">=2.0", "3.1.0")
    assert requirement_satisfied(">=2.0, <4", "3.0.0")
    assert not requirement_satisfied(">=2.0, <4", "4.0.0")
    assert requirement_satisfied("==2.0.0", "2.0.0")
    assert not requirement_satisfied("==2.0.0", "2.0.1")
    assert requirement_satisfied("!=2.0.0", "2.0.1")
    assert not requirement_satisfied(">2.0", "2.0.0")
    with pytest.raises(ScrollError):
        requirement_satisfied("eventually", "2.0.0")


# -------------------------------------------------------------- publish -----


def test_publish_success(reg, tmp_path):
    src = write_scroll(tmp_path / "src", "greet")
    manifest = reg.publish(src)
    assert manifest["name"] == "greet"
    dest = tmp_path / "registry" / "scrolls" / "greet" / "1.0.0"
    assert (dest / "greet.god").is_file()
    assert (dest / "scroll.toml").is_file()
    index = json.loads((tmp_path / "registry" / "index.json").read_text())
    assert index["greet"]["versions"] == ["1.0.0"]
    assert index["greet"]["latest"] == "1.0.0"
    assert index["greet"]["manifest"]["description"].startswith("A test scroll")


def test_publish_second_version_updates_latest(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "greet", "1.0.0"))
    reg.publish(write_scroll(tmp_path / "s2", "greet", "1.10.0"))
    reg.publish(write_scroll(tmp_path / "s3", "greet", "1.9.0"))
    index = reg.load_index()
    assert index["greet"]["versions"] == ["1.0.0", "1.9.0", "1.10.0"]
    assert index["greet"]["latest"] == "1.10.0"  # numeric, not lexicographic


def test_publish_duplicate_version_refused(reg, tmp_path):
    reg.publish(write_scroll(tmp_path / "s1", "greet", "1.0.0"))
    with pytest.raises(ScrollError, match="already in the registry"):
        reg.publish(write_scroll(tmp_path / "s2", "greet", "1.0.0"))


def test_publish_missing_entry_refused(reg, tmp_path):
    d = tmp_path / "src" / "greet"
    d.mkdir(parents=True)
    (d / "scroll.toml").write_text(
        'name = "greet"\nversion = "1.0.0"\nauthor = "a"\n'
        'description = "d"\nentry = "missing.god"\ngodcode = ">=2.0"\n'
    )
    with pytest.raises(ScrollError, match="entry file"):
        reg.publish(d)


def test_publish_name_must_match_dir(reg, tmp_path):
    src = write_scroll(tmp_path / "src", "greet")
    src.rename(tmp_path / "src" / "other")
    with pytest.raises(ScrollError, match="does not match directory"):
        reg.publish(tmp_path / "src" / "other")


def test_publish_no_manifest_refused(reg, tmp_path):
    d = tmp_path / "src" / "bare"
    d.mkdir(parents=True)
    (d / "bare.god").write_text("REVEAL(1)\n")
    with pytest.raises(ScrollError, match="no scroll.toml"):
        reg.publish(d)


def test_publish_unsatisfied_engine_refused(reg, tmp_path):
    src = write_scroll(tmp_path / "src", "future", godcode=">=99.0")
    with pytest.raises(ScrollError):
        reg.publish(src)


# -------------------------------------------------------------- install -----


def _publish(reg, tmp_path, name, version):
    return reg.publish(write_scroll(tmp_path / f"src-{name}-{version}",
                                    name, version))


def test_install_latest_by_default(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    _publish(reg, tmp_path, "greet", "1.1.0")
    receipt = reg.install("greet")
    assert receipt["version"] == "1.1.0"
    assert receipt["location"] == "user"
    dest = tmp_path / "home" / ".godcode" / "scrolls" / "greet" / "1.1.0"
    assert (dest / "greet.god").is_file()
    assert (dest / "install.json").is_file()
    saved = json.loads((dest / "install.json").read_text())
    assert saved["name"] == "greet" and saved["version"] == "1.1.0"


def test_install_exact_version(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    _publish(reg, tmp_path, "greet", "2.0.0")
    receipt = reg.install("greet", version="1.0.0")
    assert receipt["version"] == "1.0.0"


def test_install_unknown_version_refused(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    with pytest.raises(ScrollError, match="no version"):
        reg.install("greet", version="9.9.9")


def test_install_unknown_scroll_refused(reg):
    with pytest.raises(ScrollError, match="not in the registry"):
        reg.install("nope")


def test_install_project_local(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    receipt = reg.install("greet", project=True)
    assert receipt["location"] == "project"
    dest = tmp_path / "proj" / ".godcode" / "scrolls" / "greet" / "1.0.0"
    assert (dest / "greet.god").is_file()


def test_list_installed(reg, tmp_path):
    assert reg.list_installed() == []
    _publish(reg, tmp_path, "aaa", "1.0.0")
    _publish(reg, tmp_path, "bbb", "1.0.0")
    _publish(reg, tmp_path, "bbb", "2.0.0")
    reg.install("aaa")
    reg.install("bbb", version="1.0.0", project=True)
    reg.install("bbb", version="2.0.0", project=True)
    rows = {r["name"]: r for r in reg.list_installed()}
    assert rows["aaa"]["versions"] == ["1.0.0"]
    assert rows["aaa"]["locations"] == ["user"]
    assert rows["bbb"]["versions"] == ["1.0.0", "2.0.0"]
    assert rows["bbb"]["latest"] == "2.0.0"
    assert rows["bbb"]["locations"] == ["project"]


def test_info(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    _publish(reg, tmp_path, "greet", "1.1.0")
    reg.install("greet", version="1.0.0")
    info = reg.info("greet")
    assert info["published"] == ["1.0.0", "1.1.0"]
    assert info["latest"] == "1.1.0"
    assert info["manifest"]["author"] == "Test Scribe"
    assert info["installed"] == ["1.0.0"]
    assert info["installed_user"] == ["1.0.0"]
    assert info["installed_project"] == []


def test_info_unknown_scroll(reg):
    info = reg.info("never-published")
    assert info["published"] == []
    assert info["latest"] is None
    assert info["manifest"] is None
    assert info["installed"] == []


def test_resolve_entry_project_wins_and_latest_wins(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    _publish(reg, tmp_path, "greet", "2.0.0")
    reg.install("greet", version="1.0.0")  # user-global, older
    reg.install("greet", version="1.0.0", project=True)
    entry = reg.resolve_entry("greet")
    assert entry is not None
    assert ".godcode" in entry.parts
    # project-local wins over user-global even at the same version
    assert str(tmp_path / "proj") in str(entry)

    reg.install("greet", version="2.0.0")  # user-global, newer
    entry = reg.resolve_entry("greet")
    assert "1.0.0" in str(entry)  # project-local 1.0.0 still wins


def test_resolve_entry_missing_returns_none(reg):
    assert reg.resolve_entry("nope") is None


# ------------------------------------------------------ interpreter IMPORT --


def _run(interp_source: str, tmp_path: Path):
    from godcode.interpreter import Interpreter
    from godcode.lexer import Lexer
    from godcode.parser import Parser

    interp = Interpreter(log_path=str(tmp_path / "t.log"))
    program = Parser(Lexer(interp_source).lex()).parse()
    interp.run(program, source_name=str(tmp_path / "main.god"))
    return interp


def test_import_installed_scroll_end_to_end(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    reg.install("greet", project=True)
    interp = _run('IMPORT "greet"\nREVEAL(HELLO_GREET())\n', tmp_path)
    assert interp.output == ["greet 1.0.0"]


def test_import_prefers_latest_installed_version(reg, tmp_path):
    _publish(reg, tmp_path, "greet", "1.0.0")
    _publish(reg, tmp_path, "greet", "1.5.0")
    reg.install("greet", project=True)  # latest
    interp = _run('IMPORT "greet"\nREVEAL(HELLO_GREET())\n', tmp_path)
    assert interp.output == ["greet 1.5.0"]


def test_import_unknown_scroll_still_fails(reg, tmp_path):
    from godcode.errors import GodRuntimeError

    with pytest.raises(GodRuntimeError, match="could not be found"):
        _run('IMPORT "no-such-scroll"\n', tmp_path)


def test_stdlib_import_unchanged(reg, tmp_path):
    interp = _run('IMPORT "math"\nREVEAL(POW(2, 10))\n', tmp_path)
    assert interp.output == ["1024"]


def test_stdlib_shadows_registry_install(reg, tmp_path):
    # A registry scroll named like a stdlib scroll must NOT take precedence.
    src = write_scroll(tmp_path / "src", "math", "9.9.9")
    (src / "math.god").write_text(
        "DEFINE RITE POW(b, e)\nRETURN 0 - 1\nEND RITE\n", encoding="utf-8"
    )
    reg.publish(src)
    reg.install("math", project=True)
    interp = _run('IMPORT "math"\nREVEAL(POW(2, 10))\n', tmp_path)
    assert interp.output == ["1024"]  # stdlib math, not the registry one


# ------------------------------------------------------------- CLI smoke ----


def test_cli_scroll_commands_against_real_registry(tmp_path, monkeypatch,
                                                  capsys):
    """list/install/info via the CLI with an isolated HOME (read-only on
    the real registry; installs land in the tmp HOME)."""
    from godcode.cli import main

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    assert main(["scroll", "list"]) == 0
    assert "No scrolls installed" in capsys.readouterr().out

    assert main(["scroll", "install", "json-tools"]) == 0
    out = capsys.readouterr().out
    assert "json-tools 1.0.0" in out

    assert main(["scroll", "list"]) == 0
    out = capsys.readouterr().out
    assert "json-tools 1.0.0 [user]" in out

    assert main(["scroll", "info", "blessings"]) == 0
    out = capsys.readouterr().out
    assert "blessings" in out and "1.0.0" in out

    installed = tmp_path / "home" / ".godcode" / "scrolls" / "json-tools"
    assert (installed / "1.0.0" / "json-tools.god").is_file()


def test_cli_install_unknown_scroll_falls_back_to_remote(tmp_path, monkeypatch,
                                                         capsys):
    """A local miss falls back to the remote registry; when the remote has
    no answer either, the error names the scroll and says so."""
    from godcode import remote_registry
    from godcode.cli import main

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)

    class _DeadRemote(remote_registry.RemoteRegistry):
        def versions_satisfying(self, name, requirement):
            raise remote_registry.RegistryClientError("the test net is down")

    monkeypatch.setattr(remote_registry, "RemoteRegistry", _DeadRemote)
    with pytest.raises(SystemExit) as exc:
        main(["scroll", "install", "no-such-scroll"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no-such-scroll" in err
    assert "remote registry" in err


# ------------------------------------------------- shipped registry sanity --


def test_shipped_stdlib_manifests_valid():
    for name in ["math", "strings", "lists", "time", "prophecy", "covenant"]:
        m = read_manifest(REPO / "godcode" / "scrolls" / f"{name}.toml")
        assert m["name"] == name
        assert m["entry"] == f"{name}.god"
        assert (REPO / "godcode" / "scrolls" / m["entry"]).is_file()


def test_shipped_registry_index_covers_stdlib_and_community():
    index = json.loads((REPO / "registry" / "index.json").read_text())
    for name in ["math", "strings", "lists", "time", "prophecy", "covenant",
                 "json-tools", "blessings"]:
        assert name in index, name
        assert index[name]["latest"] == "1.0.0"
        scroll_dir = REPO / "registry" / "scrolls" / name / "1.0.0"
        assert (scroll_dir / "scroll.toml").is_file()
        manifest = read_manifest(scroll_dir / "scroll.toml")
        assert manifest["name"] == name
        assert (scroll_dir / manifest["entry"]).is_file()
