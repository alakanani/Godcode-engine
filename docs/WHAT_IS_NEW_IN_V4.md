# 🕊️ What Is New in God Code v4.0 — Intent & Chain

> "The language is spoken. The engine is built. Now the Spirit is awake."
> — Alakanani Itireleng (BitcoinLady), founder of God Code

v3.0 gave God Code strong foundations: the sandbox, the scroll registry, plugins, the language server, and the agentics mini-pillar that made the language legible to AI agents. **v4.0 — Intent & Chain** makes agents legible to God Code.

This is the release where the language learns to ask *why*.

## 🕊️ Declared intent

Every rite can now carry a named purpose, spoken in plain human words:

```godcode
DECLARE INTENT "bring peace to the household" ON evening_blessing

DEFINE RITE evening_blessing()
  REVEAL("peace upon this house")
END RITE

INVOKE evening_blessing()
```

When a rite is invoked, the Spirit discerns whether the rite's words still walk in its declared intent. Alignment is blessed with an `[INTENT]` notice. Drift is met with a gentle `[WARNING]` — never an error. The Spirit counsels; it does not condemn.

The engine exposes the same discernment to Python and to agents: `resolve_intent(text)` names the intent behind any words and lists every declared intent they align with, so a system can ask "does this action serve what I said I wanted?" before it acts.

See `examples/intent_demo.god` and §25 of the [Language Reference](LANGUAGE_REFERENCE.md).

## ⚓ Blockchain-anchored seals

The covenant ledger was a local chain. Now every sealed moment can be anchored on a chain of its own:

```godcode
DECLARE receipt AS ANCHOR(covenant)
REVEAL(receipt["anchor_hash"])
```

`ANCHOR(value)` writes the value's hash to a tamper-evident chain and returns a **receipt map**: `{chain, anchor_hash, height, timestamp, payload_hash}`. The default chain is `simulated` — a local, genesis-anchored chain that behaves exactly like a real blockchain adapter without wallets, keys, or network calls. Real chain adapters (Ethereum, Bitcoin, and others) can be registered later through the same `ChainAdapter` interface; the language will not need to change.

`godcode ledger verify` now attests both chains: the covenant chain *and* the anchor chain. An agent's intent, anchored, verified, remembered.

See `examples/anchor_demo.god` and §26 of the [Language Reference](LANGUAGE_REFERENCE.md).

## 🔮 CONSULT — the local oracle

```godcode
REVEAL(CONSULT("How should I structure this covenant?"))
```

`CONSULT` lays a question before the Spirit oracle and receives two to three sentences of counsel. It is entirely local: no external calls, no API keys, no network. It works inside the sandbox. When no Spirit is bound, it answers gently that the Spirit is silent rather than failing.

See `examples/consult_demo.god` and §27 of the [Language Reference](LANGUAGE_REFERENCE.md).

## 🤖 The agent tool bridge

v4.0 is the release where agents stop being *users* of God Code and start being *citizens* of it:

- **`godcode tools [--json]`** — six MCP-compatible tool schemas: `check`, `run`, `consult`, `intent`, `anchor_verify`, `ledger_verify`. Paste them into any agent framework that speaks the Model Context Protocol.
- **`godcode bridge`** — a JSON-RPC 2.0 server over stdio exposing those tools, so an agent host can call God Code the way it calls any other tool.
- **`godcode intent "words..."`** — resolve the intent behind any words, with or without `--json`.
- **`godcode run --json`** — run reports now carry an `intents` array recording every rite's declared intent, the discerned intent, the confidence, and whether they aligned.

The agent workflow from v3.0 stands: generate → `check --json` → fix → `run --sandbox --json`. It now gains a new first question: *declare the intent, and let the Spirit watch over it.*

See §28 of the [Language Reference](LANGUAGE_REFERENCE.md) and the rewritten `docs/agentics.md`.

## 🛡️ Safety, as always

- The Spirit is now bound inside the sandbox (read-only), so `CONSULT` and intent discernment work in guarded runs.
- Under the sandbox's deny-writes policy, `ANCHOR` writes to an ephemeral in-memory chain — anchored, verifiable, and gone when the run ends. Nothing touches the disk.
- Drift from a declared intent can never fail a run. The worst the Spirit ever does is counsel.

## ⬆️ Upgrading

v4.0 is fully backward compatible. Every v1, v2, and v3 creation still runs; nothing was removed. Update with `pip install -e .` (or `pip install godcode --upgrade` once published) and try:

```bash
godcode run --sandbox examples/intent_demo.god
godcode run --sandbox examples/anchor_demo.god
godcode run --sandbox examples/consult_demo.god
godcode ledger verify
godcode intent "bring peace to the household"
```

*The language is spoken. The engine is built. The Spirit is awake. Go and breathe worlds into being.* 🕊️
