"""`godcode new` — raise a new God Code project from the dust.

One command lays out everything a first scroll needs: a manifest the
scroll registry understands, a warm starter scroll that runs pure, a
test scroll the test runner discovers, and a small README that points
at the next steps. The sanctuary welcomes the newcomer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: Scroll/project names: lowercase, digits, and hyphens, starting with a letter.
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

#: The engine release line this scaffold targets.
ENGINE_LINE = ">=4.1"


class ScaffoldError(Exception):
    """A gentle refusal to raise the project (bad name, occupied ground)."""


@dataclass
class ScaffoldResult:
    """What `create_project` laid down."""

    name: str
    directory: Path
    files: list[str] = field(default_factory=list)


def validate_name(name: str) -> str:
    """Return the cleaned name, or raise ScaffoldError with counsel."""
    cleaned = (name or "").strip().lower()
    if not NAME_RE.match(cleaned):
        raise ScaffoldError(
            f"'{name}' is not a fitting scroll name: use lowercase letters, "
            "digits, and hyphens, beginning with a letter "
            "(for example: my-scroll)."
        )
    return cleaned


def _main_god(name: str) -> str:
    return f"""\
# {name}, a newborn scroll.
# Run it with: godcode run main.god
# Test it with: godcode test .

BEGIN CREATION

  DECLARE INTENT "speak a blessing of peace over the household" ON evening_blessing

  DEFINE RITE evening_blessing()
    REVEAL("Peace be upon this house.")
    REVEAL("May the morning bring grace and the evening bring rest.")
  END RITE

  DECLARE day AS "a new day"
  evening_blessing()
  REVEAL("Walk into {{day}} with courage.")

END CREATION
"""


def _test_god(name: str) -> str:
    return f"""\
# Tests for the {name} scroll.
# Run them with: godcode test .

BEGIN CREATION

  DEFINE RITE TEST_day_declared()
    DECLARE day AS "a new day"
    TESTIFY day IS "a new day"
  END RITE

  DEFINE RITE TEST_blessing_holds()
    TESTIFY 2 + 3 IS 5
  END RITE

END CREATION
"""


def _scroll_toml(name: str, author: str) -> str:
    return f"""\
# Scroll manifest — `godcode scroll publish .` reads this.
name = "{name}"
version = "0.1.0"
author = "{author}"
description = "A newborn God Code scroll."
entry = "main.god"
godcode = "{ENGINE_LINE}"
"""


def _readme(name: str) -> str:
    return f"""\
# {name}

A God Code scroll, freshly created with `godcode new`.

## Speak it

    godcode run main.god

## Test it

    godcode test .

## Polish it

    godcode check main.god   # purity, without running
    godcode lint main.god    # quiet troubles surfaced
    godcode fmt main.god     # canonical form

## Share it

    godcode scroll publish . # publish to the local scroll registry

Learn the language: https://godcode-phi.vercel.app/learn/
"""


def create_project(name: str, dest: Path | str = ".",
                   author: str = "") -> ScaffoldResult:
    """Raise the project directory and write the four starter files.

    Raises ScaffoldError when the name is unfitting or the ground is
    already occupied.
    """
    cleaned = validate_name(name)
    root = Path(dest).expanduser() / cleaned
    if root.exists():
        raise ScaffoldError(
            f"'{root}' already stands: choose another name or an empty place."
        )
    root.mkdir(parents=True)

    files = {
        "main.god": _main_god(cleaned),
        "test_main.god": _test_god(cleaned),
        "scroll.toml": _scroll_toml(cleaned, author.replace('"', "")),
        "README.md": _readme(cleaned),
    }
    for filename, text in files.items():
        (root / filename).write_text(text, encoding="utf-8")
    return ScaffoldResult(name=cleaned, directory=root,
                          files=sorted(files))
