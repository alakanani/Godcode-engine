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


# ---------------------------------------------------------------------------
# manifest parsing (TOML subset: key = "value" pairs, # comments)


MANIFEST_KEYS = frozenset(
    {"name", "version", "author", "description", "entry", "godcode"}
)
REQUIRED_KEYS = MANIFEST_KEYS  # every key is required for now
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
# the registry


def _default_registry_root() -> Path:
    return Path(__file__).resolve().parent.parent / "registry"


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
        }
        self._save_index(index)
        return manifest

    # ----------------------------------------------------------- install ---

    def resolve_version(self, name: str, version: str | None = None) -> str:
        """The version to install: ``version`` if given, else the latest."""
        index = self.load_index()
        entry = index.get(name)
        if entry is None:
            raise ScrollError(
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

    def install(
        self,
        name: str,
        version: str | None = None,
        project: bool = False,
    ) -> dict[str, Any]:
        """Install a scroll from the registry into an install directory.

        ``project=True`` installs under ``.godcode/scrolls/`` in the current
        (or given) project directory; otherwise under ``~/.godcode/scrolls/``.
        Returns the install receipt.
        """
        resolved = self.resolve_version(name, version)
        src = self.scrolls_root / name / resolved
        if not src.is_dir():
            raise ScrollError(
                f"install: registry is missing files for {name} {resolved} "
                f"(expected {src})"
            )
        manifest = read_manifest(src / "scroll.toml")

        base = self.project_scrolls_dir if project else self.user_dir
        dest = base / name / resolved
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

        receipt = {
            "name": name,
            "version": resolved,
            "location": "project" if project else "user",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "manifest": manifest,
        }
        (dest / "install.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return receipt

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
