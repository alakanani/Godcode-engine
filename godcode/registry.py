"""Pillar 2 — the Scroll Registry: installable, versioned God Code scrolls.

A scroll is a directory holding a ``scroll.toml`` manifest beside its entry
``.god`` file.  The local registry (``registry/`` at the repo root) is the
source of truth: ``publish`` copies a scroll into
``registry/scrolls/<name>/<version>/`` and records it in
``registry/index.json``; ``install`` copies from there into
``~/.godcode/scrolls/<name>/<version>/`` (user-global) or
``.godcode/scrolls/`` (project-local, wins over user-global).

requires-python is >=3.10, so ``tomllib`` (3.11+) is off the table: the
manifest parser below is a hand-rolled TOML subset covering exactly the
keys this registry defines.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:  # the package version is the engine version; tolerate odd import orders
    from godcode import __version__ as ENGINE_VERSION
except Exception:  # pragma: no cover - defensive
    ENGINE_VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# errors


class ScrollError(Exception):
    """Raised when a manifest, publish, install, or lookup fails."""


class ScrollNotFoundError(ScrollError):
    """Raised when a scroll cannot be found in a registry.

    Kept distinct from ScrollError so the CLI can fall back from the local
    registry to the remote one on exactly this failure.
    """


# ---------------------------------------------------------------------------
# manifest parsing (TOML subset: key = "value" pairs, # comments)


MANIFEST_KEYS = frozenset(
    {"name", "version", "author", "description", "entry", "godcode",
     "dependencies"}
)
REQUIRED_KEYS = frozenset(
    {"name", "version", "author", "description", "entry", "godcode"}
)  # dependencies is optional
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$")
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_REQ_CLAUSE_RE = re.compile(r"^(>=|<=|==|!=|>|<)\s*(\d+(?:\.\d+){0,2})$")

# Human-readable blurbs shown in errors; keep them short.
_KEY_HINTS = {
    "name": 'e.g. name = "json-tools"',
    "version": 'e.g. version = "1.0.0"',
    "author": 'e.g. author = "Ama Seretse"',
    "description": 'e.g. description = "JSON helpers written in God Code"',
    "entry": 'e.g. entry = "json-tools.god"',
    "godcode": 'e.g. godcode = ">=2.0"',
    "dependencies": 'e.g. dependencies = "json-tools >= 1.0.0, dates"',
}


def _strip_comment(line: str) -> str:
    """Cut a trailing ``#`` comment, ignoring ``#`` inside quoted strings."""
    in_quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quote:
            if ch == "\\" and in_quote == '"':
                i += 2
                continue
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
        elif ch == "#":
            return line[:i]
        i += 1
    return line


def _parse_toml_value(raw: str, source: str, lineno: int) -> str:
    """Parse a quoted TOML string value (double- or single-quoted)."""
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        out: list[str] = []
        i = 1
        while i < len(raw) - 1:
            ch = raw[i]
            if ch == "\\":
                i += 1
                if i >= len(raw) - 1:
                    raise ScrollError(
                        f"{source}:{lineno}: dangling backslash in manifest value"
                    )
                esc = raw[i]
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(esc, esc))
            else:
                out.append(ch)
            i += 1
        return "".join(out)
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return raw[1:-1]  # literal string: no escapes
    raise ScrollError(
        f"{source}:{lineno}: manifest values must be quoted strings "
        f"(got {raw!r})"
    )


def parse_manifest(text: str, source: str = "<scroll.toml>") -> dict[str, str]:
    """Parse and validate a ``scroll.toml`` manifest. Returns a plain dict."""
    data: dict[str, str] = {}
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        if "=" not in line:
            raise ScrollError(
                f"{source}:{lineno}: expected `key = \"value\"`, got {line!r}"
            )
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise ScrollError(f"{source}:{lineno}: bad manifest key {key!r}")
        if key in data:
            raise ScrollError(
                f"{source}:{lineno}: duplicate manifest key {key!r}"
            )
        data[key] = _parse_toml_value(value, source, lineno)

    unknown = sorted(set(data) - MANIFEST_KEYS)
    if unknown:
        raise ScrollError(
            f"{source}: unknown manifest key(s) {', '.join(unknown)}; "
            "known keys: " + ", ".join(sorted(MANIFEST_KEYS))
        )
    missing = sorted(REQUIRED_KEYS - set(data))
    if missing:
        hints = "; ".join(_KEY_HINTS[k] for k in missing)
        raise ScrollError(
            f"{source}: missing required manifest key(s) "
            f"{', '.join(missing)} ({hints})"
        )

    name = data["name"]
    if not _NAME_RE.match(name):
        raise ScrollError(
            f"{source}: name {name!r} must be lowercase letters, digits and "
            "hyphens, starting with a letter"
        )
    parse_semver(data["version"], source=source)  # validates
    entry = data["entry"]
    if not entry or "/" in entry or "\\" in entry or entry.startswith("."):
        raise ScrollError(
            f"{source}: entry must be a plain filename, got {entry!r}"
        )
    req = data["godcode"]
    if not requirement_satisfied(req):
        raise ScrollError(
            f"{source}: this scroll needs God Code {req}, "
            f"but the engine is {ENGINE_VERSION}"
        )
    if "dependencies" in data:
        parse_dependencies(data["dependencies"], source=source)
    return data


def read_manifest(path: str | os.PathLike) -> dict[str, str]:
    """Read, parse, and validate the manifest at ``path``."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScrollError(f"cannot read manifest {path}: {exc}") from exc
    return parse_manifest(text, source=str(path))


# ---------------------------------------------------------------------------
# semver-ish versions (X.Y.Z only)


def parse_semver(text: str, source: str = "<manifest>") -> tuple[int, int, int]:
    """Parse ``X.Y.Z``; raise ScrollError on anything else."""
    match = _SEMVER_RE.match(text.strip())
    if not match:
        raise ScrollError(
            f"{source}: version must look like X.Y.Z, got {text!r}"
        )
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def compare_versions(a: str, b: str) -> int:
    """-1 if a < b, 0 if equal, 1 if a > b (numeric per component)."""
    ta, tb = parse_semver(a), parse_semver(b)
    return (ta > tb) - (ta < tb)


def latest_version(versions: list[str]) -> str:
    """The highest version; ties are impossible (versions are unique)."""
    if not versions:
        raise ScrollError("no versions to choose from")
    best = versions[0]
    for v in versions[1:]:
        if compare_versions(v, best) > 0:
            best = v
    return best


# ---------------------------------------------------------------------------
# godcode version requirements, e.g. ">=2.0, <4"


def _parse_requirement(req: str) -> list[tuple[str, tuple[int, ...]]]:
    clauses: list[tuple[str, tuple[int, ...]]] = []
    for part in req.split(","):
        part = part.strip()
        if not part:
            raise ScrollError(f"bad godcode requirement {req!r}: empty clause")
        match = _REQ_CLAUSE_RE.match(part)
        if not match:
            raise ScrollError(
                f"bad godcode requirement {req!r}: expected e.g. "
                f"'>=2.0', got {part!r}"
            )
        op, ver = match.group(1), match.group(2)
        clauses.append((op, tuple(int(x) for x in ver.split("."))))
    return clauses


def _pad(parts: tuple[int, ...], length: int) -> tuple[int, ...]:
    return parts + (0,) * (length - len(parts))


def _clauses_satisfied(
    req: str, engine: str, clauses: list[tuple[str, tuple[int, ...]]]
) -> bool:
    engine_parts = _pad(tuple(int(x) for x in engine.split(".")), 3)
    for op, want in clauses:
        want = _pad(want, 3)
        if op == ">=" and not (engine_parts >= want):
            return False
        if op == "<=" and not (engine_parts <= want):
            return False
        if op == "==" and not (engine_parts == want):
            return False
        if op == "!=" and not (engine_parts != want):
            return False
        if op == ">" and not (engine_parts > want):
            return False
        if op == "<" and not (engine_parts < want):
            return False
    return True


def requirement_satisfied(req: str, engine: str = ENGINE_VERSION) -> bool:
    """True when ``engine`` satisfies a requirement like ``>=2.0``."""
    return _clauses_satisfied(req, engine, _parse_requirement(req))


# ---------------------------------------------------------------------------
# scroll dependencies, e.g. dependencies = "json-tools >= 1.0.0, dates"


def parse_dependencies(
    spec: str, source: str = "<scroll.toml>"
) -> list[tuple[str, str | None]]:
    """Parse a manifest ``dependencies`` value.

    Returns ``[(name, requirement)]``; requirement is None when the clause
    names the scroll with no version constraint.  A clause carries at most
    one requirement clause (``>= 1.0.0``); commas separate dependencies.
    """
    if not spec.strip():
        return []
    deps: list[tuple[str, str | None]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise ScrollError(
                f"{source}: bad dependencies {spec!r}: empty clause"
            )
        tokens = part.split()
        name = tokens[0]
        if not _NAME_RE.match(name):
            raise ScrollError(
                f"{source}: bad dependency name {name!r} in "
                f"dependencies {spec!r}"
            )
        requirement = " ".join(tokens[1:]) or None
        if requirement is not None:
            _parse_requirement(requirement)  # validates the clause shape
        if name in {n for n, _ in deps}:
            raise ScrollError(
                f"{source}: duplicate dependency {name!r} in "
                f"dependencies {spec!r}"
            )
        deps.append((name, requirement))
    return deps


def render_manifest(manifest: dict[str, str]) -> str:
    """Render a manifest dict as ``scroll.toml`` text."""
    lines: list[str] = []
    for key in ("name", "version", "author", "description", "entry",
                "godcode", "dependencies"):
        if key in manifest:
            value = manifest[key].replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{value}"')
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# the registry


def _default_registry_root() -> Path:
    return Path(__file__).resolve().parent.parent / "registry"


def _sha256_file(path: Path) -> str:
    """Hex sha256 of a file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checksum_tree(root: Path) -> dict[str, str]:
    """sha256 for every file under ``root``, keyed by relative path."""
    checksums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            checksums[path.relative_to(root).as_posix()] = _sha256_file(path)
    return checksums


class ScrollRegistry:
    """Local scroll registry: publish into ``registry/``, install from it."""

    def __init__(
        self,
        registry_root: str | os.PathLike | None = None,
        home: str | os.PathLike | None = None,
        project_dir: str | os.PathLike | None = None,
    ) -> None:
        self.registry_root = Path(registry_root or _default_registry_root())
        self.scrolls_root = self.registry_root / "scrolls"
        self.index_path = self.registry_root / "index.json"
        self.home = Path(home or Path.home())  # honors $HOME, monkeypatchable
        self.user_dir = self.home / ".godcode" / "scrolls"
        self.project_dir = Path(project_dir or Path.cwd())
        self.project_scrolls_dir = self.project_dir / ".godcode" / "scrolls"

    # ------------------------------------------------------------- index ---

    def load_index(self) -> dict[str, Any]:
        """The published index; {} when nothing has been published yet."""
        if not self.index_path.is_file():
            return {}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScrollError(
                f"cannot read registry index {self.index_path}: {exc}"
            ) from exc

    def _save_index(self, index: dict[str, Any]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    # ----------------------------------------------------------- publish ---

    def publish(self, scroll_dir: str | os.PathLike) -> dict[str, str]:
        """Validate a scroll directory and publish it into the registry.

        Copies ``scroll_dir`` to ``registry/scrolls/<name>/<version>/`` and
        updates ``index.json``. Refuses when that exact version is already
        published. Returns the validated manifest.
        """
        src = Path(scroll_dir)
        if not src.is_dir():
            raise ScrollError(f"publish: {src} is not a directory")
        manifest_path = src / "scroll.toml"
        if not manifest_path.is_file():
            raise ScrollError(f"publish: {src} holds no scroll.toml manifest")
        manifest = read_manifest(manifest_path)

        name, version = manifest["name"], manifest["version"]
        if src.name != name:
            raise ScrollError(
                f"publish: manifest name {name!r} does not match directory "
                f"name {src.name!r}"
            )
        entry_path = src / manifest["entry"]
        if not entry_path.is_file():
            raise ScrollError(
                f"publish: entry file {manifest['entry']!r} not found in {src}"
            )

        index = self.load_index()
        published = index.get(name, {}).get("versions", [])
        if version in published:
            raise ScrollError(
                f"publish: {name} {version} is already in the registry — "
                "bump the version to publish again"
            )

        dest = self.scrolls_root / name / version
        if dest.exists():
            raise ScrollError(
                f"publish: {dest} already exists on disk but is not indexed; "
                "remove it or repair the index first"
            )
        shutil.copytree(src, dest)

        versions = sorted(set(published) | {version},
                          key=lambda v: parse_semver(v))
        index[name] = {
            "name": name,
            "versions": versions,
            "latest": latest_version(versions),
            "manifest": manifest,
            "checksums": {
                **index.get(name, {}).get("checksums", {}),
                version: _checksum_tree(dest),
            },
        }
        self._save_index(index)
        return manifest

    # ----------------------------------------------------------- install ---

    def _remote_client(self, remote: bool | Any) -> Any | None:
        """A RemoteRegistry when ``remote`` asks for one, else None.

        ``remote`` may be True (build a default client), a RemoteRegistry
        instance (use it), or False/None (local only).
        """
        if remote is True:
            from godcode.remote_registry import RemoteRegistry

            return RemoteRegistry()
        return remote or None

    def resolve_version(self, name: str, version: str | None = None) -> str:
        """The version to install: ``version`` if given, else the latest."""
        index = self.load_index()
        entry = index.get(name)
        if entry is None:
            raise ScrollNotFoundError(
                f"install: {name!r} is not in the registry "
                f"({self.registry_root})"
            )
        versions: list[str] = entry["versions"]
        if version is None:
            return entry["latest"]
        if version not in versions:
            raise ScrollError(
                f"install: {name} has no version {version!r}; "
                f"published: {', '.join(versions)}"
            )
        return version

    def _choose_source(
        self,
        name: str,
        requirement: str | None,
        remote_client: Any | None,
        stack: tuple[str, ...],
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Pick (version, source, info) for ``name`` under ``requirement``.

        ``requirement`` is None (any version), ``==X.Y.Z`` (exact, from
        ``--version`` or a pinned dependency), or a dep clause like
        ``>= 1.0.0``.  The local index always wins; the remote registry is
        consulted only when a client was passed and the local index cannot
        serve the requirement.
        """
        context = f" (needed by {' -> '.join(stack)})" if stack else ""
        index = self.load_index()
        entry = index.get(name)

        if requirement is not None and requirement.startswith("=="):
            exact = requirement[2:].strip()
            if entry is not None:
                if exact in entry["versions"]:
                    return exact, "local", None
                if remote_client is None:
                    raise ScrollError(
                        f"install: {name} has no version {exact!r}; "
                        f"published: {', '.join(entry['versions'])}"
                    )
                # else: fall through to the remote lookup below
        elif entry is not None:
            matching = [
                v
                for v in entry["versions"]
                if requirement is None
                or requirement_satisfied(requirement, v)
            ]
            if matching:
                return latest_version(matching), "local", None

        if remote_client is not None:
            try:
                info, matching = remote_client.versions_satisfying(
                    name, requirement
                )
            except ScrollError as exc:
                raise ScrollNotFoundError(
                    f"install: {name!r} is not in the local registry and the "
                    f"remote registry cannot serve it: {exc}{context}"
                ) from exc
            if matching:
                return matching[0], "remote", info
            raise ScrollNotFoundError(
                f"install: {name!r} is not in the local registry and the "
                f"remote registry has no version matching "
                f"{requirement or 'any'!r}{context}"
            )
        if entry is None:
            raise ScrollNotFoundError(
                f"install: {name!r} is not in the registry "
                f"({self.registry_root}){context}"
            )
        raise ScrollNotFoundError(
            f"install: {name!r} has no published version matching "
            f"{requirement!r}{context}"
        )

    def _manifest_for(
        self,
        name: str,
        version: str,
        source: str,
        info: dict[str, Any] | None,
    ) -> dict[str, str]:
        """The validated manifest for a chosen (name, version)."""
        if source == "local":
            return read_manifest(self.scrolls_root / name / version / "scroll.toml")
        from godcode.remote_registry import synthesized_manifest

        manifest = synthesized_manifest(name, info or {}, version)
        return parse_manifest(
            render_manifest(manifest), source=f"<remote {name} {version}>"
        )

    def _plan_install(
        self,
        name: str,
        requirement: str | None,
        stack: tuple[str, ...],
        remote_client: Any | None,
        plan: dict[str, dict[str, Any]],
    ) -> None:
        """Fill ``plan`` (insertion-ordered, dependencies first) with the
        scrolls this install needs, resolving versions and detecting cycles.
        """
        if name in stack:
            cycle = " -> ".join([*stack, name])
            raise ScrollError(
                f"dependency cycle detected: {cycle}. A scroll cannot depend "
                "on itself through a circle of dependencies; break the "
                "circle and publish again."
            )
        if name in plan:
            chosen = plan[name]["version"]
            if requirement is None or requirement_satisfied(requirement, chosen):
                return
            raise ScrollError(
                f"install: version conflict for {name!r}: this install "
                f"already resolved {chosen}, which does not satisfy "
                f"{requirement!r}"
            )
        version, source, info = self._choose_source(
            name, requirement, remote_client, stack
        )
        manifest = self._manifest_for(name, version, source, info)
        for dep_name, dep_req in parse_dependencies(
            manifest.get("dependencies", ""), source=f"<{name} {version}>"
        ):
            self._plan_install(dep_name, dep_req, stack + (name,),
                               remote_client, plan)
        plan[name] = {
            "name": name,
            "version": version,
            "source": source,
            "info": info,
            "manifest": manifest,
        }

    def _dependency_tree(
        self, manifest: dict[str, str], plan: dict[str, dict[str, Any]]
    ) -> dict[str, str]:
        """Resolved {dependency name: version} for a receipt."""
        tree: dict[str, str] = {}
        for dep_name, _ in parse_dependencies(manifest.get("dependencies", "")):
            if dep_name in plan:
                tree[dep_name] = plan[dep_name]["version"]
        return tree

    def _verify_checksums(self, name: str, version: str, src: Path) -> dict[str, str]:
        """Check published files against the checksums recorded on publish.

        Returns the recorded checksums (for the receipt).  Index entries
        written before checksums existed carry none and are trusted as-is.
        """
        index = self.load_index()
        recorded: dict[str, str] = (
            index.get(name, {}).get("checksums", {}) or {}
        ).get(version, {})
        for rel, expected in recorded.items():
            path = src / rel
            if not path.is_file():
                raise ScrollError(
                    f"install: {name} {version} is missing published file "
                    f"{rel!r} in the registry; republish the scroll"
                )
            actual = _sha256_file(path)
            if actual != expected:
                raise ScrollError(
                    f"install: checksum mismatch for {name} {version} file "
                    f"{rel!r}: the registry copy changed after publish "
                    f"(expected {expected[:12]}..., got {actual[:12]}...). "
                    "Republish the scroll to heal the registry."
                )
        return recorded

    def _write_install(
        self,
        name: str,
        version: str,
        project: bool,
        manifest: dict[str, str],
        *,
        source: str,
        checksums: dict[str, str],
        dependencies: dict[str, str],
        copy_from: Path | None = None,
        files: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Materialize one installed scroll directory and its receipt."""
        base = self.project_scrolls_dir if project else self.user_dir
        dest = base / name / version
        if dest.exists():
            shutil.rmtree(dest)
        if copy_from is not None:
            shutil.copytree(copy_from, dest)
        else:
            dest.mkdir(parents=True)
            for rel, content in (files or {}).items():
                (dest / rel).write_text(content, encoding="utf-8")

        receipt = {
            "name": name,
            "version": version,
            "source": source,
            "location": "project" if project else "user",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "checksums": checksums,
            "dependencies": dependencies,
            "manifest": manifest,
        }
        (dest / "install.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return receipt

    def _install_local(
        self,
        name: str,
        version: str,
        manifest: dict[str, str],
        project: bool,
        dependency_tree: dict[str, str],
    ) -> dict[str, Any]:
        """Install one planned scroll from the local registry directory."""
        src = self.scrolls_root / name / version
        if not src.is_dir():
            raise ScrollError(
                f"install: registry is missing files for {name} {version} "
                f"(expected {src})"
            )
        checksums = self._verify_checksums(name, version, src)
        return self._write_install(
            name, version, project, manifest,
            source="local", checksums=checksums,
            dependencies=dependency_tree, copy_from=src,
        )

    def _install_remote(
        self,
        name: str,
        version: str,
        manifest: dict[str, str],
        project: bool,
        remote_client: Any,
        dependency_tree: dict[str, str],
    ) -> dict[str, Any]:
        """Install one planned scroll by downloading it from the remote."""
        code, resolved = remote_client.fetch_code(name, version)
        entry_name = manifest["entry"]
        manifest_text = render_manifest({**manifest, "version": resolved})
        checksums = {
            entry_name: hashlib.sha256(code.encode("utf-8")).hexdigest(),
            "scroll.toml": hashlib.sha256(
                manifest_text.encode("utf-8")).hexdigest(),
        }
        return self._write_install(
            name, resolved, project, {**manifest, "version": resolved},
            source="remote", checksums=checksums,
            dependencies=dependency_tree,
            files={entry_name: code, "scroll.toml": manifest_text},
        )

    def install(
        self,
        name: str,
        version: str | None = None,
        project: bool = False,
        remote: bool | Any = False,
    ) -> dict[str, Any]:
        """Install a scroll and its dependencies into an install directory.

        ``project=True`` installs under ``.godcode/scrolls/`` in the current
        (or given) project directory; otherwise under ``~/.godcode/scrolls/``.
        Dependencies declared in the manifest are resolved recursively, the
        local index first and then the remote registry when ``remote`` is a
        client (or True for a default client); cycles are refused with a
        clear error.  Returns the top-level install receipt.
        """
        remote_client = self._remote_client(remote)
        plan: dict[str, dict[str, Any]] = {}
        self._plan_install(
            name,
            f"=={version}" if version is not None else None,
            (),
            remote_client,
            plan,
        )
        receipts: list[dict[str, Any]] = []
        for item in plan.values():
            tree = self._dependency_tree(item["manifest"], plan)
            if item["source"] == "local":
                receipts.append(
                    self._install_local(
                        item["name"], item["version"], item["manifest"],
                        project, tree,
                    )
                )
            else:
                assert remote_client is not None  # chosen by _choose_source
                receipts.append(
                    self._install_remote(
                        item["name"], item["version"], item["manifest"],
                        project, remote_client, tree,
                    )
                )
        return receipts[-1]

    # --------------------------------------------------------- uninstall ---

    def uninstall(
        self, name: str, version: str | None = None
    ) -> list[dict[str, str]]:
        """Remove an installed scroll (one version, or every installed
        version when ``version`` is None) from both install scopes."""
        removed: list[dict[str, str]] = []
        for base, location in (
            (self.project_scrolls_dir, "project"),
            (self.user_dir, "user"),
        ):
            name_dir = base / name
            if not name_dir.is_dir():
                continue
            if version is None:
                targets = sorted(d for d in name_dir.iterdir() if d.is_dir())
            else:
                single = name_dir / version
                targets = [single] if single.is_dir() else []
            for target in targets:
                shutil.rmtree(target)
                removed.append(
                    {"name": name, "version": target.name,
                     "location": location}
                )
            if version is None and name_dir.is_dir() and not any(
                name_dir.iterdir()
            ):
                name_dir.rmdir()
        if not removed:
            raise ScrollError(
                f"uninstall: {name!r}"
                + (f" {version}" if version else "")
                + " is not installed"
            )
        return removed

    # ------------------------------------------------------------ update ---

    def _newest_available(
        self, name: str, remote_client: Any | None
    ) -> tuple[str | None, str]:
        """(newest version known anywhere, source) for ``name``."""
        best: str | None = None
        source = "local"
        entry = self.load_index().get(name)
        if entry:
            best = entry["latest"]
        if remote_client is not None:
            try:
                info, matching = remote_client.versions_satisfying(name, None)
            except ScrollError:
                matching = []
                info = {}
            if matching and (
                best is None or compare_versions(matching[0], best) > 0
            ):
                best, source = matching[0], "remote"
        return best, source

    def update(
        self,
        name: str | None = None,
        project: bool = False,
        remote: bool | Any = False,
    ) -> list[dict[str, Any]]:
        """Update one installed scroll (or all, when ``name`` is None) to the
        newest version known to the local index or the remote registry."""
        remote_client = self._remote_client(remote)
        rows = {r["name"]: r for r in self.list_installed()}
        names = [name] if name is not None else sorted(rows)
        if name is not None and name not in rows:
            raise ScrollError(f"update: {name!r} is not installed")
        results: list[dict[str, Any]] = []
        for scroll_name in names:
            installed = rows[scroll_name]["latest"]
            available, _source = self._newest_available(scroll_name,
                                                       remote_client)
            if available is not None and compare_versions(available,
                                                          installed) > 0:
                receipt = self.install(
                    scroll_name, version=available, project=project,
                    remote=remote,
                )
                results.append(
                    {"name": scroll_name, "from": installed,
                     "to": available, "source": receipt["source"]}
                )
            else:
                results.append(
                    {"name": scroll_name, "from": installed,
                     "to": installed, "up_to_date": True}
                )
        return results

    # -------------------------------------------------------------- read ---

    def _installed_versions(self, base: Path) -> dict[str, list[str]]:
        """name -> sorted installed versions found under ``base``."""
        found: dict[str, list[str]] = {}
        if not base.is_dir():
            return found
        for name_dir in sorted(base.iterdir()):
            if not name_dir.is_dir():
                continue
            for ver_dir in sorted(name_dir.iterdir()):
                if not ver_dir.is_dir():
                    continue
                if not (ver_dir / "scroll.toml").is_file():
                    continue
                try:
                    parse_semver(ver_dir.name)
                except ScrollError:
                    continue
                found.setdefault(name_dir.name, []).append(ver_dir.name)
        return found

    def list_installed(self) -> list[dict[str, Any]]:
        """Every installed scroll; project-local entries win over user ones."""
        user = self._installed_versions(self.user_dir)
        project = self._installed_versions(self.project_scrolls_dir)
        rows: list[dict[str, Any]] = []
        for name in sorted(set(user) | set(project)):
            versions = sorted(
                set(user.get(name, [])) | set(project.get(name, [])),
                key=lambda v: parse_semver(v),
            )
            rows.append(
                {
                    "name": name,
                    "versions": versions,
                    "latest": latest_version(versions),
                    "locations": sorted(
                        {
                            *(("user",) if name in user else ()),
                            *(("project",) if name in project else ()),
                        }
                    ),
                }
            )
        return rows

    def info(self, name: str) -> dict[str, Any]:
        """Manifest, published versions, and install state for ``name``."""
        index = self.load_index()
        entry = index.get(name)
        user = self._installed_versions(self.user_dir).get(name, [])
        project = self._installed_versions(self.project_scrolls_dir).get(name, [])
        installed = sorted(set(user) | set(project),
                           key=lambda v: parse_semver(v))
        return {
            "name": name,
            "published": entry["versions"] if entry else [],
            "latest": entry["latest"] if entry else None,
            "manifest": entry["manifest"] if entry else None,
            "installed": installed,
            "installed_project": sorted(project, key=lambda v: parse_semver(v)),
            "installed_user": sorted(user, key=lambda v: parse_semver(v)),
        }

    # ------------------------------------------- interpreter resolution ----

    def resolve_entry(self, name: str) -> Optional[Path]:
        """Path to the installed entry ``.god`` file for ``name``, if any.

        Project-local installs win; otherwise the latest user-global
        version wins. Returns None when the scroll is not installed.
        """
        for base in (self.project_scrolls_dir, self.user_dir):
            name_dir = base / name
            if not name_dir.is_dir():
                continue
            versions: list[str] = []
            for ver_dir in name_dir.iterdir():
                if ver_dir.is_dir() and (ver_dir / "scroll.toml").is_file():
                    try:
                        parse_semver(ver_dir.name)
                    except ScrollError:
                        continue
                    versions.append(ver_dir.name)
            if not versions:
                continue
            latest = latest_version(versions)
            scroll_dir = name_dir / latest
            try:
                manifest = read_manifest(scroll_dir / "scroll.toml")
            except ScrollError:
                continue
            entry = scroll_dir / manifest["entry"]
            if entry.is_file():
                return entry.resolve()
            # project-local dir exists but is broken: fall through to user
        return None
