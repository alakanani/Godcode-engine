"""Tests for God Code v4.0 -- the agent tool bridge (godcode/tools.py)."""

import io
import json
import sys

import pytest

from godcode import cli
from godcode.tools import TOOL_SCHEMAS, call_tool, cmd_bridge


PURE = "BEGIN CREATION\n  DECLARE answer AS 40 + 2\n  REVEAL(answer)\nEND CREATION\n"
BROKEN = "DECLARE AS\n"


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


# ------------------------------------------------------------------ schemas


class TestToolSchemas:
    NAMES = {"check", "run", "consult", "intent", "anchor_verify", "ledger_verify"}

    def test_six_mcp_compatible_tools(self):
        assert {t["name"] for t in TOOL_SCHEMAS} == self.NAMES
        for tool in TOOL_SCHEMAS:
            assert tool["description"]
            schema = tool["inputSchema"]
            assert schema["type"] == "object"
            assert isinstance(schema["properties"], dict)
            assert isinstance(schema.get("required", []), list)

    def test_tools_json_lists_all_schemas(self, capsys):
        try:
            rc = cli.main(["tools", "--json"])
        except SystemExit as exc:
            rc = exc.code
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert {t["name"] for t in payload["tools"]} == self.NAMES

    def test_tools_human_lists_names(self, capsys):
        rc = cli.main(["tools"])
        assert rc == 0
        out = capsys.readouterr().out
        for name in self.NAMES:
            assert name in out


# ------------------------------------------------------------------ direct calls


class TestCallTool:
    def test_check_ok(self, tmp_path):
        scroll = _write(tmp_path, "pure.god", PURE)
        result = call_tool("check", {"file": scroll})
        assert result == {"ok": True, "diagnostics": []}

    def test_check_broken(self, tmp_path):
        scroll = _write(tmp_path, "broken.god", BROKEN)
        result = call_tool("check", {"file": scroll})
        assert result["ok"] is False
        assert result["diagnostics"][0]["code"] == "PARSE_ERROR"

    def test_run_sandboxed(self, tmp_path):
        scroll = _write(tmp_path, "pure.god", PURE)
        result = call_tool("run", {"file": scroll})
        assert result["ok"] is True
        assert result["output"] == ["42"]

    def test_run_missing_file(self):
        result = call_tool("run", {"file": "no-such-scroll.god"})
        assert result["ok"] is False

    def test_consult(self):
        result = call_tool("consult", {"question": "How should I proceed?"})
        assert result["ok"] is True
        assert "counsel of heaven" in result["counsel"]

    def test_intent(self):
        result = call_tool("intent", {"text": "bring peace to the household"})
        assert result["ok"] is True
        assert result["result"]["intent"] == "Blessing of peace"

    def test_anchor_verify_round_trip(self, tmp_path, monkeypatch):
        from godcode.chain import SimulatedChainAdapter

        monkeypatch.chdir(tmp_path)  # the tool reads ./anchors.chain
        receipt = SimulatedChainAdapter("anchors.chain").anchor("abc123")
        result = call_tool("anchor_verify", {"receipt": receipt})
        assert result == {"ok": True, "valid": True,
                          "message": "the anchor stands"}

    def test_anchor_verify_tampered(self, tmp_path, monkeypatch):
        from godcode.chain import SimulatedChainAdapter

        monkeypatch.chdir(tmp_path)
        receipt = SimulatedChainAdapter("anchors.chain").anchor("abc123")
        bad = dict(receipt, anchor_hash="0" * 64)
        result = call_tool("anchor_verify", {"receipt": bad})
        assert result["valid"] is False

    def test_ledger_verify(self, tmp_path, monkeypatch):
        from godcode.chain import SimulatedChainAdapter
        from godcode.ledger import CovenantLedger

        monkeypatch.chdir(tmp_path)
        CovenantLedger("covenant.chain").seal({"sealed": "light"})
        SimulatedChainAdapter("anchors.chain").anchor("abc")
        result = call_tool("ledger_verify", {})
        assert result["ok"] is True
        assert result["covenants"]["ok"] is True
        assert result["anchors"]["ok"] is True

    def test_unknown_tool(self):
        result = call_tool("nope", {})
        assert result["ok"] is False
        assert "known_tools" in result


# ------------------------------------------------------------------ bridge


def _bridge(requests, monkeypatch, capsys):
    """Feed JSON-RPC request dicts to the bridge; return response dicts."""
    lines = "\n".join(json.dumps(r) for r in requests) + "\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(lines))
    rc = cmd_bridge(None)
    assert rc == 0
    out = capsys.readouterr().out.strip()
    return [json.loads(line) for line in out.splitlines()] if out else []


class TestBridge:
    def test_initialize(self, monkeypatch, capsys):
        (resp,) = _bridge([{"jsonrpc": "2.0", "id": 1,
                            "method": "initialize", "params": {}}],
                          monkeypatch, capsys)
        assert resp["id"] == 1
        assert resp["result"]["serverInfo"]["name"] == "godcode-bridge"
        assert "tools" in resp["result"]["capabilities"]

    def test_ping(self, monkeypatch, capsys):
        (resp,) = _bridge([{"jsonrpc": "2.0", "id": 2, "method": "ping"}],
                          monkeypatch, capsys)
        assert resp["result"] == {}

    def test_tools_list(self, monkeypatch, capsys):
        (resp,) = _bridge([{"jsonrpc": "2.0", "id": 3, "method": "tools/list"}],
                          monkeypatch, capsys)
        assert {t["name"] for t in resp["result"]["tools"]} == TestToolSchemas.NAMES

    def test_tools_call_check(self, tmp_path, monkeypatch, capsys):
        scroll = _write(tmp_path, "pure.god", PURE)
        (resp,) = _bridge(
            [{"jsonrpc": "2.0", "id": 4, "method": "tools/call",
              "params": {"name": "check", "arguments": {"file": scroll}}}],
            monkeypatch, capsys)
        body = json.loads(resp["result"]["content"][0]["text"])
        assert body["ok"] is True

    def test_tools_call_consult_and_intent(self, monkeypatch, capsys):
        resps = _bridge(
            [{"jsonrpc": "2.0", "id": 5, "method": "tools/call",
              "params": {"name": "consult",
                         "arguments": {"question": "How should I proceed?"}}},
             {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
              "params": {"name": "intent",
                         "arguments": {"text": "bring peace"}}}],
            monkeypatch, capsys)
        consult = json.loads(resps[0]["result"]["content"][0]["text"])
        assert "counsel of heaven" in consult["counsel"]
        intent = json.loads(resps[1]["result"]["content"][0]["text"])
        assert intent["result"]["intent"] == "Blessing of peace"

    def test_tools_call_unknown_tool_is_error(self, monkeypatch, capsys):
        (resp,) = _bridge(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/call",
              "params": {"name": "nope", "arguments": {}}}],
            monkeypatch, capsys)
        assert resp["result"]["isError"] is True

    def test_unknown_method(self, monkeypatch, capsys):
        (resp,) = _bridge([{"jsonrpc": "2.0", "id": 8, "method": "nope"}],
                          monkeypatch, capsys)
        assert resp["error"]["code"] == -32601

    def test_malformed_json(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("this is not json\n"))
        rc = cmd_bridge(None)
        assert rc == 0
        (resp,) = [json.loads(line)
                   for line in capsys.readouterr().out.splitlines()]
        assert resp["error"]["code"] == -32700

    def test_notification_gets_no_response(self, monkeypatch, capsys):
        resps = _bridge([{"jsonrpc": "2.0",
                          "method": "notifications/initialized"}],
                        monkeypatch, capsys)
        assert resps == []
