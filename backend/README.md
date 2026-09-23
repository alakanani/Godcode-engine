# God Code Scroll Registry — Backend

Live at **https://api.getgodcode.com**. A Cloudflare Worker backed by a D1
database (`godcode_registry`). This is where God Code scrolls (packages) are
published, listed, searched and downloaded.

Public read API. Publishing requires the `PUBLISH_TOKEN` secret.

## Endpoints

- `GET /health` — service status.
- `GET /v1/scrolls?q=&limit=&offset=` — list/search published scrolls.
- `POST /v1/scrolls` — publish a scroll. Header: `Authorization: Bearer <PUBLISH_TOKEN>`.
  Body: `{ "name": "my-scroll", "version": "1.0.0", "code": "...", "description": "...", "author": "..." }`.
- `GET /v1/scrolls/:name` — scroll details and published versions.
- `GET /v1/scrolls/:name/download` — download the latest version as a `.god` file.
- `GET /v1/scrolls/:name/versions/:version` — one specific version with its code.

## Security

- Publishing is locked behind the `PUBLISH_TOKEN` secret (timing-safe
  comparison). Reading is public, like npm or PyPI.
- Per-IP rate limiting in the Worker, backed by D1 (`rate_limits` table):
  120 reads/minute, 10 publishes/minute. Abusers get HTTP 429.
- Request bodies are capped (600KB total, 500KB scroll code). Field lengths
  are enforced and control characters are stripped from text fields.
- Every response carries hardened headers (`nosniff`, `DENY` framing,
  `no-referrer`).
- Cloudflare edge protection: a WAF custom rule ("Allow API clients") skips
  bot challenges on `api.getgodcode.com` so real API clients and CLIs are
  never blocked; the main site keeps full bot protection.

## Files

- `worker.js` — the Worker source (deployed as `godcode-registry`).
- `schema.sql` — D1 tables (`scrolls`, `versions`).
- `wrangler.toml` — Wrangler config for future CLI deploys.

## Deployment notes

Deploys are currently done through the Cloudflare dashboard (the account
cannot issue API tokens until its email is verified, so Wrangler CLI deploys
are on hold). To update: Workers & Pages → godcode-registry → Edit code,
paste `worker.js`, Save and Deploy. The D1 binding (`DB` →
`godcode_registry`) and the `PUBLISH_TOKEN` secret persist across deploys.

Once API tokens work, fill in `database_id` in `wrangler.toml` and deploy
with `wrangler deploy`.
