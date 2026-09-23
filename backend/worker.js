/* God Code Scroll Registry - Cloudflare Worker + D1
 * Public read API, token-protected publishing.
 * v1 endpoints:
 *   GET  /health
 *   GET  /v1/scrolls?q=&limit=&offset=
 *   POST /v1/scrolls                      (Authorization: Bearer <PUBLISH_TOKEN>)
 *   GET  /v1/scrolls/:name
 *   GET  /v1/scrolls/:name/download
 *   GET  /v1/scrolls/:name/versions/:version
 */

const NAME_RE = /^[a-z0-9][a-z0-9-]{1,62}$/;
const VER_RE = /^[0-9]+\.[0-9]+\.[0-9]+$/;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,POST,OPTIONS",
      "access-control-allow-headers": "content-type,authorization",
    },
  });
}

function err(message, status = 400) {
  return json({ ok: false, error: message }, status);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") return json({ ok: true });

    if (url.pathname === "/" || url.pathname === "/health") {
      return json({ ok: true, service: "godcode-scroll-registry", version: "1.0.0" });
    }

    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] !== "v1" || parts[1] !== "scrolls") return err("Not found", 404);

    try {
      // GET /v1/scrolls?q=&limit=&offset=
      if (parts.length === 2 && request.method === "GET") {
        const q = (url.searchParams.get("q") || "").trim();
        const limit = Math.min(Math.max(parseInt(url.searchParams.get("limit") || "50", 10) || 50, 1), 100);
        const offset = Math.max(parseInt(url.searchParams.get("offset") || "0", 10) || 0, 0);
        let rows;
        if (q) {
          rows = await env.DB.prepare(
            `SELECT s.name, s.description, s.author, s.downloads, s.updated_at,
                    (SELECT version FROM versions v WHERE v.scroll_id = s.id ORDER BY v.id DESC LIMIT 1) AS latest
             FROM scrolls s WHERE s.name LIKE ? OR s.description LIKE ?
             ORDER BY s.downloads DESC LIMIT ? OFFSET ?`
          ).bind(`%${q}%`, `%${q}%`, limit, offset).all();
        } else {
          rows = await env.DB.prepare(
            `SELECT s.name, s.description, s.author, s.downloads, s.updated_at,
                    (SELECT version FROM versions v WHERE v.scroll_id = s.id ORDER BY v.id DESC LIMIT 1) AS latest
             FROM scrolls s ORDER BY s.downloads DESC LIMIT ? OFFSET ?`
          ).bind(limit, offset).all();
        }
        return json({ ok: true, scrolls: rows.results });
      }

      // POST /v1/scrolls  (publish, needs bearer token)
      if (parts.length === 2 && request.method === "POST") {
        const auth = request.headers.get("authorization") || "";
        if (!env.PUBLISH_TOKEN || auth !== `Bearer ${env.PUBLISH_TOKEN}`) {
          return err("Unauthorized", 401);
        }
        const body = await request.json().catch(() => null);
        if (!body) return err("Invalid JSON body");
        const name = String(body.name || "").toLowerCase().trim();
        const version = String(body.version || "").trim();
        const code = String(body.code || "");
        const description = String(body.description || "").slice(0, 500);
        const author = String(body.author || "").slice(0, 120);
        if (!NAME_RE.test(name)) return err("Invalid scroll name (lowercase letters, numbers, hyphens)");
        if (!VER_RE.test(version)) return err("Invalid version (use x.y.z)");
        if (!code || code.length > 500000) return err("Code is required (max 500KB)");

        let scroll = await env.DB.prepare("SELECT id FROM scrolls WHERE name = ?").bind(name).first();
        if (!scroll) {
          const ins = await env.DB.prepare(
            "INSERT INTO scrolls (name, description, author) VALUES (?, ?, ?)"
          ).bind(name, description, author).run();
          scroll = { id: ins.meta.last_row_id };
        } else {
          await env.DB.prepare(
            "UPDATE scrolls SET description = ?, author = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?"
          ).bind(description, author, scroll.id).run();
        }
        const exists = await env.DB.prepare(
          "SELECT id FROM versions WHERE scroll_id = ? AND version = ?"
        ).bind(scroll.id, version).first();
        if (exists) return err("That version is already published", 409);

        await env.DB.prepare(
          "INSERT INTO versions (scroll_id, version, code) VALUES (?, ?, ?)"
        ).bind(scroll.id, version, code).run();
        return json({ ok: true, name, version }, 201);
      }

      const name = (parts[2] || "").toLowerCase();
      if (!NAME_RE.test(name)) return err("Invalid scroll name", 404);
      const scroll = await env.DB.prepare("SELECT * FROM scrolls WHERE name = ?").bind(name).first();
      if (!scroll) return err("Scroll not found", 404);

      const versionRows = await env.DB.prepare(
        "SELECT version, created_at, length(code) AS bytes FROM versions WHERE scroll_id = ? ORDER BY id DESC"
      ).bind(scroll.id).all();
      const latest = versionRows.results[0];

      // GET /v1/scrolls/:name
      if (parts.length === 3 && request.method === "GET") {
        return json({
          ok: true,
          name: scroll.name,
          description: scroll.description,
          author: scroll.author,
          downloads: scroll.downloads,
          latest: latest ? latest.version : null,
          versions: versionRows.results.map((v) => v.version),
          updated_at: scroll.updated_at,
        });
      }

      // GET /v1/scrolls/:name/download  (latest code)
      if (parts.length === 4 && parts[3] === "download" && request.method === "GET") {
        if (!latest) return err("No versions published", 404);
        const row = await env.DB.prepare(
          "SELECT code FROM versions WHERE scroll_id = ? ORDER BY id DESC LIMIT 1"
        ).bind(scroll.id).first();
        await env.DB.prepare("UPDATE scrolls SET downloads = downloads + 1 WHERE id = ?").bind(scroll.id).run();
        return new Response(row.code, {
          headers: {
            "content-type": "text/plain; charset=utf-8",
            "access-control-allow-origin": "*",
            "content-disposition": `attachment; filename="${scroll.name}.god"`,
          },
        });
      }

      // GET /v1/scrolls/:name/versions/:version
      if (parts.length === 5 && parts[3] === "versions" && request.method === "GET") {
        const ver = parts[4];
        const row = await env.DB.prepare(
          "SELECT version, code, created_at FROM versions WHERE scroll_id = ? AND version = ?"
        ).bind(scroll.id, ver).first();
        if (!row) return err("Version not found", 404);
        return json({ ok: true, name: scroll.name, version: row.version, code: row.code, created_at: row.created_at });
      }

      return err("Not found", 404);
    } catch (e) {
      return err("Server error", 500);
    }
  },
};
