"""Tests for God Code v4.0 -- blockchain-anchored seals (godcode/chain.py)."""

import json
import os

import pytest

from godcode import cli
from godcode.chain import (
    ChainAdapter,
    MemoryChainAdapter,
    SimulatedChainAdapter,
    default_adapters,
    get_adapter,
    register_adapter,
)
from godcode.errors import GodRuntimeError
from godcode.interpreter import Interpreter
from godcode.sandbox import run_sandboxed


def _interp(chain_adapters=None):
    kwargs = {"log_path": None}
    if chain_adapters is not None:
        kwargs["chain_adapters"] = chain_adapters
    return Interpreter(**kwargs)


ANCHOR_SCROLL = """\
BEGIN CREATION
  DECLARE covenant AS contract("everlasting")
  BREATHE LIFE INTO covenant
  DECLARE receipt AS ANCHOR(covenant)
  REVEAL(receipt["chain"])
  REVEAL(receipt["height"])
END CREATION
"""


# ------------------------------------------------------------------ adapter


class TestSimulatedChainAdapter:
    def test_anchor_returns_receipt_shape(self, tmp_path):
        adapter = SimulatedChainAdapter(tmp_path / "anchors.chain")
        receipt = adapter.anchor("abc123")
        assert receipt["chain"] == "simulated"
        assert receipt["height"] == 0
        assert len(receipt["anchor_hash"]) == 64
        assert receipt["payload_hash"] == "abc123"
        assert "timestamp" in receipt

    def test_heights_increase(self, tmp_path):
        adapter = SimulatedChainAdapter(tmp_path / "anchors.chain")
        r0 = adapter.anchor("a")
        r1 = adapter.anchor("b")
        assert (r0["height"], r1["height"]) == (0, 1)
        assert r0["anchor_hash"] != r1["anchor_hash"]

    def test_verify_round_trip(self, tmp_path):
        adapter = SimulatedChainAdapter(tmp_path / "anchors.chain")
        receipt = adapter.anchor("abc123")
        assert adapter.verify(receipt) is True

    def test_verify_rejects_tampered_receipt(self, tmp_path):
        adapter = SimulatedChainAdapter(tmp_path / "anchors.chain")
        receipt = adapter.anchor("abc123")
        bad = dict(receipt, anchor_hash="0" * 64)
        assert adapter.verify(bad) is False
        bad2 = dict(receipt, payload_hash="evil")
        assert adapter.verify(bad2) is False
        assert adapter.verify(dict(receipt, height=99)) is False

    def test_verify_rejects_garbage(self, tmp_path):
        adapter = SimulatedChainAdapter(tmp_path / "anchors.chain")
        assert adapter.verify({}) is False
        assert adapter.verify("not a receipt") is False
        assert adapter.verify(None) is False

    def test_verify_chain_intact(self, tmp_path):
        adapter = SimulatedChainAdapter(tmp_path / "anchors.chain")
        adapter.anchor("a")
        adapter.anchor("b")
        ok, message = adapter.verify_chain()
        assert ok is True
        assert "2 anchors intact" in message

    def test_verify_chain_names_broken_block(self, tmp_path):
        path = tmp_path / "anchors.chain"
        adapter = SimulatedChainAdapter(path)
        adapter.anchor("a")
        adapter.anchor("b")
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[1])
        tampered["record"] = {"payload_hash": "EVIL"}
        lines[1] = json.dumps(tampered)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, message = SimulatedChainAdapter(path).verify_chain()
        assert ok is False
        assert "1" in message

    def test_verify_chain_empty(self, tmp_path):
        ok, message = SimulatedChainAdapter(tmp_path / "missing.chain").verify_chain()
        assert ok is True
        assert "0 anchors intact" in message


class TestMemoryChainAdapter:
    def test_anchor_and_verify_without_touching_disk(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        adapter = MemoryChainAdapter()
        receipt = adapter.anchor("abc123")
        assert receipt["chain"] == "simulated"
        assert adapter.verify(receipt) is True
        assert list(tmp_path.iterdir()) == []  # nothing written

    def test_is_a_chain_adapter(self):
        assert isinstance(MemoryChainAdapter(), ChainAdapter)


class TestRegistry:
    def test_default_adapters_holds_simulated(self):
        adapters = default_adapters()
        assert isinstance(adapters["simulated"], SimulatedChainAdapter)

    def test_register_and_get_adapter(self):
        adapter = MemoryChainAdapter()
        register_adapter("test-memory", adapter)
        try:
            assert get_adapter("test-memory") is adapter
        finally:
            from godcode.chain import _ADAPTERS

            _ADAPTERS.pop("test-memory", None)

    def test_get_unknown_adapter_is_none(self):
        assert get_adapter("no-such-chain") is None


# ------------------------------------------------------------------ builtin


class TestAnchorBuiltin:
    def test_anchor_receipt_is_a_map(self, tmp_path, capsys):
        interp = _interp({"simulated": SimulatedChainAdapter(tmp_path / "a.chain")})
        interp.run_source(ANCHOR_SCROLL)
        out = capsys.readouterr().out
        assert "[ANCHOR] Anchored on simulated" in out
        assert interp.output[0] == "simulated"
        assert interp.output[1] == "0"

    def test_receipt_reveals_as_map(self, tmp_path, capsys):
        interp = _interp({"simulated": SimulatedChainAdapter(tmp_path / "a.chain")})
        interp.run_source(
            'BEGIN CREATION\n  DECLARE r AS ANCHOR("manna")\n  REVEAL(r)\nEND CREATION\n'
        )
        (line,) = interp.output
        assert line.startswith("{chain: simulated, anchor_hash: ")
        assert "payload_hash: " in line

    def test_type_of_receipt_is_map(self, tmp_path):
        interp = _interp({"simulated": SimulatedChainAdapter(tmp_path / "a.chain")})
        interp.run_source(
            'BEGIN CREATION\n  DECLARE r AS ANCHOR("manna")\n  REVEAL(TYPE(r))\nEND CREATION\n'
        )
        assert interp.output == ["map"]

    def test_named_chain_as_symbol(self, tmp_path):
        interp = _interp({"simulated": SimulatedChainAdapter(tmp_path / "a.chain")})
        interp.run_source(
            "BEGIN CREATION\n  DECLARE r AS ANCHOR(\"manna\", simulated)\n  REVEAL(r[\"chain\"])\nEND CREATION\n"
        )
        assert interp.output == ["simulated"]

    def test_unknown_chain_is_a_clean_error_naming_adapters(self):
        interp = _interp({"simulated": MemoryChainAdapter()})
        with pytest.raises(GodRuntimeError) as exc:
            interp.run_source(
                'BEGIN CREATION\n  DECLARE r AS ANCHOR("manna", "ethereum")\nEND CREATION\n'
            )
        assert "ethereum" in str(exc.value)
        assert "simulated" in str(exc.value)

    def test_anchor_writes_chain_file_outside_sandbox(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        interp = _interp()  # default file-backed simulated adapter
        interp.run_source(ANCHOR_SCROLL)
        assert (tmp_path / "anchors.chain").exists()

    def test_anchor_in_sandbox_writes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output = run_sandboxed(ANCHOR_SCROLL)
        assert output == ["simulated", "0"]
        assert list(tmp_path.iterdir()) == []

    def test_anchor_demo_example_runs_clean_in_sandbox(self):
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source = open(os.path.join(repo, "examples", "anchor_demo.god"),
                      encoding="utf-8").read()
        output = run_sandboxed(source)
        assert any("anchor hash: " in line for line in output)


# ------------------------------------------------------------------ CLI


class TestLedgerVerifyBothChains:
    def test_verify_reports_covenants_and_anchors(self, tmp_path, monkeypatch, capsys):
        from godcode.chain import SimulatedChainAdapter
        from godcode.ledger import CovenantLedger

        monkeypatch.chdir(tmp_path)
        CovenantLedger("covenant.chain").seal({"sealed": "light"})
        SimulatedChainAdapter("anchors.chain").anchor("abc")
        rc = cli.main(["ledger", "verify"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 covenants intact" in out
        assert "1 anchors intact" in out

    def test_verify_broken_anchor_chain_fails(self, tmp_path, monkeypatch, capsys):
        from godcode.chain import SimulatedChainAdapter

        monkeypatch.chdir(tmp_path)
        path = tmp_path / "anchors.chain"
        SimulatedChainAdapter(str(path)).anchor("a")
        lines = path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["record"] = {"payload_hash": "EVIL"}
        path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            cli.main(["ledger", "verify"])
        assert exc.value.code == 1
        assert "broken" in capsys.readouterr().out
