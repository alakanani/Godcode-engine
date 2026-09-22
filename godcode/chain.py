"""Blockchain-anchored seals for God Code v4.0 -- "Intent & Chain".

A ChainAdapter anchors a payload hash into a tamper-evident chain and
later verifies the receipt it handed back. The bundled
SimulatedChainAdapter keeps the anchor chain as local JSONL
(``anchors.chain``), mirroring :class:`godcode.ledger.CovenantLedger`;
real chain adapters (Ethereum, and the like) can be registered later
with :func:`register_adapter` -- that work belongs to the founder, not
to this module. There are no network calls here, no wallets, no keys.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

GENESIS_PREV_HASH = "GENESIS"
DEFAULT_CHAIN_NAME = "simulated"


def _canonical(payload: dict) -> bytes:
    """Canonical JSON bytes used for hashing (stable key order, no whitespace)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _block_hash(index: int, timestamp: str, record: dict, prev_hash: str) -> str:
    return hashlib.sha256(
        _canonical(
            {"index": index, "timestamp": timestamp,
             "record": record, "prev_hash": prev_hash}
        )
    ).hexdigest()


class ChainAdapter:
    """The contract every chain adapter honors.

    ``anchor(payload_hash)`` writes the hash into the chain and returns a
    receipt dict; ``verify(receipt)`` returns True only when the receipt
    matches a block that is still intact.
    """

    name = "adapter"

    def anchor(self, payload_hash: str) -> dict:
        raise NotImplementedError

    def verify(self, receipt: dict) -> bool:
        raise NotImplementedError


class SimulatedChainAdapter(ChainAdapter):
    """A local tamper-evident anchor chain (JSONL), standing in for a chain.

    Blocks look like ``{index, timestamp, record: {payload_hash},
    prev_hash, hash}``; the chain begins at ``"GENESIS"``. Receipts look
    like ``{chain, anchor_hash, height, timestamp, payload_hash}``.
    """

    name = "simulated"

    def __init__(self, path: str | Path | None = "anchors.chain") -> None:
        self.path = Path(path) if path is not None else None
        self._memory: list[dict] = []
        if self.path is not None and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- persistence

    def read_all(self) -> list[dict]:
        """Every anchor block in chain order (empty when no chain yet)."""
        if self.path is None:
            return list(self._memory)
        if not self.path.exists():
            return []
        blocks: list[dict] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    blocks.append(json.loads(line))
        return blocks

    def _append(self, block: dict) -> None:
        if self.path is None:
            self._memory.append(block)
        else:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(block, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------- adapter

    def anchor(self, payload_hash: str) -> dict:
        """Anchor a payload hash; return the receipt dict."""
        blocks = self.read_all()
        index = len(blocks)
        prev_hash = blocks[-1]["hash"] if blocks else GENESIS_PREV_HASH
        timestamp = datetime.now(timezone.utc).isoformat()
        record = {"payload_hash": payload_hash}
        block = {
            "index": index,
            "timestamp": timestamp,
            "record": record,
            "prev_hash": prev_hash,
            "hash": _block_hash(index, timestamp, record, prev_hash),
        }
        self._append(block)
        return {
            "chain": self.name,
            "anchor_hash": block["hash"],
            "height": block["index"],
            "timestamp": block["timestamp"],
            "payload_hash": payload_hash,
        }

    def verify(self, receipt: dict) -> bool:
        """True when the receipt names a block that is present and intact."""
        try:
            height = receipt["height"]
            anchor_hash = receipt["anchor_hash"]
            payload_hash = receipt["payload_hash"]
        except (KeyError, TypeError, AttributeError):
            return False
        if not isinstance(height, int) or isinstance(height, bool):
            return False
        blocks = self.read_all()
        if height < 0 or height >= len(blocks):
            return False
        block = blocks[height]
        if block.get("hash") != anchor_hash:
            return False
        if block.get("record", {}).get("payload_hash") != payload_hash:
            return False
        return _block_hash(
            block.get("index"),
            block.get("timestamp"),
            block.get("record"),
            block.get("prev_hash"),
        ) == block.get("hash")

    def verify_chain(self) -> tuple[bool, str]:
        """Recompute the whole anchor chain.

        (True, 'N anchors intact') or (False, 'anchor chain broken at
        block K').
        """
        blocks = self.read_all()
        prev_hash = GENESIS_PREV_HASH
        for expected, block in enumerate(blocks):
            payload_ok = (
                block.get("index") == expected
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
                return False, f"anchor chain broken at block {block.get('index')} ⚓💔"
            prev_hash = block["hash"]
        return True, f"{len(blocks)} anchors intact ⚓"


class MemoryChainAdapter(SimulatedChainAdapter):
    """An ephemeral in-memory anchor chain: the sandbox's answer to ANCHOR.

    Same interface as the simulated chain, but nothing is written to
    disk. Anchors made here vanish when the run ends -- which is exactly
    what a deny-by-default sandbox requires.
    """

    name = "simulated"

    def __init__(self) -> None:
        super().__init__(path=None)


# ------------------------------------------------------------- registry

_ADAPTERS: dict[str, ChainAdapter] = {}


def register_adapter(name: str, adapter: ChainAdapter) -> None:
    """Register a chain adapter under *name* (e.g. a future real chain)."""
    if not isinstance(name, str) or not name:
        raise ValueError("a chain adapter needs a non-empty string name")
    if not isinstance(adapter, ChainAdapter):
        raise ValueError(f"'{name}' is not a ChainAdapter")
    _ADAPTERS[name] = adapter


def get_adapter(name: str) -> ChainAdapter | None:
    """The adapter registered under *name*, or None."""
    return _ADAPTERS.get(name)


def default_adapters() -> dict[str, ChainAdapter]:
    """A fresh per-interpreter registry holding the bundled adapters."""
    adapters = dict(_ADAPTERS)
    adapters.setdefault(DEFAULT_CHAIN_NAME, SimulatedChainAdapter())
    return adapters


register_adapter(DEFAULT_CHAIN_NAME, SimulatedChainAdapter())
