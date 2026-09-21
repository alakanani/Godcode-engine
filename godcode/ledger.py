"""CovenantLedger -- an append-only, hash-chained record of sealed covenants. 🔒

Each sealed record becomes a block in a JSONL chain file. A block's hash is
the sha256 of the canonical JSON of {index, timestamp, record, prev_hash};
the genesis block's prev_hash is "GENESIS". verify() recomputes every link.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS_PREV_HASH = "GENESIS"


def _canonical(payload: dict) -> bytes:
    """Canonical JSON bytes used for hashing (stable key order, no whitespace)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _block_hash(index: int, timestamp: str, record: dict, prev_hash: str) -> str:
    return hashlib.sha256(
        _canonical(
            {"index": index, "timestamp": timestamp, "record": record, "prev_hash": prev_hash}
        )
    ).hexdigest()


class CovenantLedger:
    """Append-only covenant chain persisted as JSONL."""

    def __init__(self, path: str | Path = "covenant.chain") -> None:
        self.path = Path(path)
        if str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def seal(self, record: dict) -> dict:
        """Append a record as a new block; return the block dict."""
        blocks = self.read_all()
        index = len(blocks)
        prev_hash = blocks[-1]["hash"] if blocks else GENESIS_PREV_HASH
        timestamp = datetime.now(timezone.utc).isoformat()
        block = {
            "index": index,
            "timestamp": timestamp,
            "record": record,
            "prev_hash": prev_hash,
            "hash": _block_hash(index, timestamp, record, prev_hash),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(block, ensure_ascii=False) + "\n")
        return block

    def read_all(self) -> list[dict]:
        """Return every block in chain order (empty list if no chain file yet)."""
        if not self.path.exists():
            return []
        blocks: list[dict] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    blocks.append(json.loads(line))
        return blocks

    def verify(self) -> tuple[bool, str]:
        """Recompute the chain. (True, 'N covenants intact 🔒') or (False, 'chain broken at block K')."""
        blocks = self.read_all()
        prev_hash = GENESIS_PREV_HASH
        for expected, block in enumerate(blocks):
            index = block.get("index")
            payload_ok = (
                index == expected
                and block.get("prev_hash") == prev_hash
                and _block_hash(
                    block.get("index"),
                    block.get("timestamp"),
                    block.get("record"),
                    block.get("prev_hash"),
                )
                == block.get("hash")
            )
            if not payload_ok:
                return False, f"chain broken at block {index} 🔗💔"
            prev_hash = block["hash"]
        return True, f"{len(blocks)} covenants intact 🔒"
