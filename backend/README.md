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
