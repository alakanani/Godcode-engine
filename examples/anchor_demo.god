# Anchor demo — ANCHOR writes a value's hash to the chain and returns a
# receipt map: {chain, anchor_hash, height, timestamp, payload_hash}.
# Run `godcode ledger verify` afterward to see both chains attested.
BEGIN CREATION
  DECLARE covenant AS contract("everlasting")
  BREATHE LIFE INTO covenant
  BLESS covenant
  DECLARE receipt AS ANCHOR(covenant)
  REVEAL(receipt)
  REVEAL("chain: " + receipt["chain"])
  REVEAL("height: " + STR(receipt["height"]))
  REVEAL("anchor hash: " + receipt["anchor_hash"])
END CREATION
