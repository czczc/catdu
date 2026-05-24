# ADR-0002: SQLite source of truth + derived JSON shards

## Status

Accepted — 2026-05-24.

## Context

The [[Catalog]] is read by three consumers with different access patterns:

- **Extraction pipeline** — mutates: upsert per [[Logo]]; create or extend a [[Set]]; deduplicate within-set by English slug.
- **Vue website** — static, GitHub-Pages hosted, no backend. Needs to render category browse, set toggling, logo grids.
- **External consumers** (e.g. `~/Code/dunecat/`) — fetch logos by stable URL or query the manifest for a category.

Growth: ~200 logos/day → ~73,000/year. At that scale a single global JSON manifest exceeds 15 MB and becomes impractical for a static site to load eagerly.

## Decision

- **SQLite at `data/meowphosis.db`** is the source of truth. Schema covers `top_category`, `sub_category`, `set` (with `(top_slug, sub_slug, set_number)` unique), and `logo` (with `(set_id, english_slug)` unique).
- A **build step** (`scripts/build_manifest.py`) regenerates per-sub-category JSON shards at `public/catalog/<top>/<sub>.json` plus a small top-level `public/catalog.json` index (top/sub categories + counts only).
- File-system URLs follow `public/logos/<top>/<sub>/<set_number>/<english_slug>.png` — e.g. `logos/mythology/greek/1/zeus.png`.
- [[Set]] IDs are **sequential integers per (top, sub) pair**, not slugs. `set.display` carries the human-readable name.
- Within-set [[Logo]] identity is the English-name slug. Re-extracting an existing name is an **upsert** — newer wins, image overwritten, source provenance refreshed.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Single global JSON manifest | At target volume (~15–20 MB inside a year) too large for static-site browser load. |
| Postgres / hosted database | Requires hosting + connection management. Static GH Pages site can't query a remote DB without a backend. Overkill at this scale. |
| SQLite shipped to browser via `sql.js` | Adds ~1 MB WASM to every page load. Per-sub-category JSON shards are smaller, faster, and need no client-side runtime. (Still available as a future enhancement for query-heavy consumers.) |
| Per-set JSON shards (finer than per-sub-category) | More index files, more discoverability cost. No real payoff at projected sizes — a sub-category with 5 sets × 70 cells is still a small shard. |
| Slug-based set IDs (`pixel-art`, `watercolor`) | Slug fragmentation risk across LLM runs (`pixel-art` vs `pixel_art` vs `pixel`). Numeric IDs eliminate the problem; `set.display` carries the human name and can be renamed without breaking URLs. |
| Append-only on duplicate logo names (`zeus-2.png`) | Junk-drawer growth across re-runs. Upsert matches the "discard raw sheets after processing" workflow — there is no expectation of keeping every generated variant of "Zeus". Variants belong in a different [[Set]]. |

## Consequences

**Enables**
- Fast static-site reads — one small shard per browse, never the whole catalog.
- External consumers fetch a single sub-category shard for their needs.
- Stable URLs via numeric set IDs. `set.display` and `style_description` can be edited freely without breaking links.
- Trivial dedup, history, and provenance queries via SQL.

**Costs**
- The `.db` file is committed binary — diffs are unreadable. Mitigation: the JSON shards are the human-readable public contract; the binary is the canonical store; day-to-day inspection uses the shards or `sqlite3` CLI.
- A build step must run between mutation and site update. Cheap (one Python script invocation), but it is an extra step in the loop.

**Reversibility**
- SQLite → JSON-only: dump and delete the `.db`. JSON shards become canonical.
- SQLite → hosted DB: import the SQLite file. Schema is portable.
- Neither migration is hard at projected scale.
