"""Tests for godcode.ledger.CovenantLedger (spec section 8)."""

import json

from godcode.ledger import CovenantLedger


def test_seal_creates_blocks_with_chaining_hashes(tmp_path):
    ledger = CovenantLedger(tmp_path / "nested" / "covenant.chain")  # parent dirs created
    b0 = ledger.seal({"sealed": "alpha"})
    b1 = ledger.seal({"sealed": "beta"})

    assert b0["index"] == 0
    assert b0["prev_hash"] == "GENESIS"
    assert len(b0["hash"]) == 64
    assert "timestamp" in b0

    assert b1["index"] == 1
    assert b1["prev_hash"] == b0["hash"]


def test_verify_true_on_intact_chain(tmp_path):
    ledger = CovenantLedger(tmp_path / "covenant.chain")
    ledger.seal({"n": 1})
    ledger.seal({"n": 2})
    ledger.seal({"n": 3})
    ok, message = ledger.verify()
    assert ok is True
    assert "3 covenants intact" in message


def test_verify_false_after_tampering_names_the_block(tmp_path):
    path = tmp_path / "covenant.chain"
    ledger = CovenantLedger(path)
    ledger.seal({"v": "a"})
    ledger.seal({"v": "b"})

    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["record"] = {"v": "EVIL"}
    lines[1] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, message = ledger.verify()
    assert ok is False
    assert "broken" in message.lower()
    assert "1" in message  # names the tampered block


def test_read_all_round_trip(tmp_path):
    ledger = CovenantLedger(tmp_path / "covenant.chain")
    records = [{"n": 1}, {"n": 2, "deep": {"x": [1, 2]}}]
    for record in records:
        ledger.seal(record)
    blocks = ledger.read_all()
    assert [b["record"] for b in blocks] == records
    assert [b["index"] for b in blocks] == [0, 1]


def test_read_all_empty_when_no_chain(tmp_path):
    ledger = CovenantLedger(tmp_path / "missing.chain")
    assert ledger.read_all() == []
    ok, _ = ledger.verify()
    assert ok is True
