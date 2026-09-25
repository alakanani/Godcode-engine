"""Pillar 2b. The remote Scroll Registry client.

Talks to the live scroll registry over HTTPS (default
``https://api.getgodcode.com``) using only the standard library, so no new
dependencies are needed.  The base URL comes from the
``GODCODE_REGISTRY_URL`` environment variable, which lets tests point the
client at a local fake server instead of the live registry.

Endpoints used (all read-only unless noted):

- ``GET /v1/scrolls?q=&limit=&offset=``. Search.
- ``GET /v1/scrolls/:name``. Scroll info (name, description, author,
  downloads, versions[], latest, updated_at).
- ``GET /v1/scrolls/:name/download``. The latest entry ``.god`` code.
- ``GET /v1/scrolls/:name/versions/:version``. JSON {name, version, code,
  created_at} for one version.
- ``POST /v1/scrolls``. Publish (needs ``Authorization: Bearer <token>``).

The remote catalog does not carry engine requirements or dependency lists
for individual versions, so installs from remote synthesize a permissive
``scroll.toml`` from the info endpoint and record their checksum in the
install receipt instead of verifying one from the index.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from godcode.registry import ENGINE_VERSION, ScrollError, requirement_satisfied

DEFAULT_BASE_URL = "https://api.getgodcode.com"
_REQUEST_TIMEOUT = 20


class RegistryClientError(ScrollError):
    """The remote registry could not be reached or refused the request."""


def registry_base_url() -> str:
    """Base URL for the remote registry (env-overridable, for tests)."""
    return (
        os.environ.get("GODCODE_REGISTRY_URL") or DEFAULT_BASE_URL
    ).rstrip("/")


def synthesized_manifest(name: str, info: dict[str, Any], version: str) -> dict[str, str]:
    """Build a ``scroll.toml``-shaped manifest for a remote scroll.

    The info endpoint carries no engine requirement or dependency list, so
    the synthesis is permissive: it admits any modern engine and declares
    no dependencies.  A future info field (``godcode`` / ``dependencies``)
    is passed straight through when present.
    """
    manifest: dict[str, str] = {
        "name": name,
        "version": version,
        "author": str(info.get("author", "unknown")),
        "description": str(info.get("description", "") or ""),
        "entry": f"{name}.god",
        "godcode": ">=2.0",
    }
    if info.get("godcode"):
        manifest["godcode"] = str(info["godcode"])
    if info.get("dependencies"):
        manifest["dependencies"] = str(info["dependencies"])
    # guard the synthesis itself against a broken requirement shape
    requirement_satisfied(manifest["godcode"], ENGINE_VERSION)
    return manifest


class RemoteRegistry:
    """Thin HTTPS client for the remote scroll registry."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or registry_base_url()).rstrip("/")

    # ------------------------------------------------------------ http -----

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> tuple[int, Any]:
        """Issue one request; return (status, parsed body)."""
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            url, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                payload = {"ok": False, "error": exc.reason}
            raise RegistryClientError(
                f"remote registry: {method} {path} failed with HTTP "
                f"{exc.code}: {payload.get('error', exc.reason)}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RegistryClientError(
                f"remote registry: cannot reach {self.base_url} "
                f"({exc}); is the network up and GODCODE_REGISTRY_URL set?"
            ) from exc
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            # download endpoints return plain .god source, not JSON
            return status, raw

    # ------------------------------------------------------------ reads ----

    def search(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Search the remote catalog; rows carry name, description, author,
        latest version, downloads, and updated_at."""
        _, payload = self._request(
            "GET",
            "/v1/scrolls",
            params={"q": query, "limit": str(limit), "offset": str(offset)},
        )
        if isinstance(payload, dict) and payload.get("ok"):
            return list(payload.get("scrolls", []))
        raise RegistryClientError(
            f"remote registry: unexpected search response for {query!r}"
        )

    def info(self, name: str) -> dict[str, Any]:
        """Full catalog record for ``name`` (versions[], latest, ...)."""
        _, payload = self._request(
            "GET", f"/v1/scrolls/{urllib.parse.quote(name, safe='')}"
        )
        if isinstance(payload, dict) and payload.get("ok"):
            record = dict(payload)
            record.setdefault("versions", [])
            return record
        error = payload.get("error") if isinstance(payload, dict) else None
        raise RegistryClientError(
            f"remote registry: scroll {name!r} not found ({error or 'no record'})"
        )

    def fetch_code(self, name: str, version: str | None = None) -> tuple[str, str]:
        """The entry ``.god`` source for ``name``; returns (code, version).

        ``version`` selects an exact release; without it the latest entry
        is downloaded.
        """
        quoted = urllib.parse.quote(name, safe="")
        if version is None:
            _, payload = self._request("GET", f"/v1/scrolls/{quoted}/download")
            if not isinstance(payload, str):
                raise RegistryClientError(
                    f"remote registry: download for {name!r} did not "
                    "return scroll source"
                )
            resolved = self.info(name)["latest"]
            return payload, resolved
        _, payload = self._request(
            "GET",
            f"/v1/scrolls/{quoted}/versions/{urllib.parse.quote(version, safe='')}",
        )
        if isinstance(payload, dict) and payload.get("code") is not None:
            return str(payload["code"]), str(payload.get("version", version))
        raise RegistryClientError(
            f"remote registry: no code for {name!r} version {version!r}"
        )

    def versions_satisfying(
        self, name: str, requirement: str | None
    ) -> tuple[dict[str, Any], list[str]]:
        """The info record plus the versions matching ``requirement``
        (None means any version), highest first."""
        from functools import cmp_to_key

        from godcode.registry import compare_versions, requirement_satisfied

        record = self.info(name)
        versions: list[str] = list(record.get("versions") or [])
        matching = [
            v
            for v in versions
            if requirement is None
            or requirement_satisfied(requirement, v)
        ]
        matching.sort(key=cmp_to_key(compare_versions), reverse=True)
        return record, matching

    # ----------------------------------------------------------- publish ---

    def publish_scroll(
        self,
        *,
        name: str,
        version: str,
        code: str,
        description: str,
        author: str,
        token: str,
    ) -> dict[str, Any]:
        """Publish one scroll version to the remote registry.

        The token travels as ``Authorization: Bearer <token>``.  The body
        mirrors the version-fetch shape: {name, version, code, description,
        author}.  Returns the registry's acknowledgement.
        """
        if not token:
            raise RegistryClientError(
                "remote publish needs a token; refusing to publish unsigned"
            )
        _, payload = self._request(
            "POST",
            "/v1/scrolls",
            body={
                "name": name,
                "version": version,
                "code": code,
                "description": description,
                "author": author,
            },
            token=token,
        )
        if isinstance(payload, dict) and payload.get("ok") is not False:
            return payload
        raise RegistryClientError(
            f"remote registry refused the publish of {name} {version}: "
            f"{payload!r}"
        )
