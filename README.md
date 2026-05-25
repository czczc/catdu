# meowphosis

A catalog of AI-generated cat logos, organized by theme (mythology, games, …) and browsable as a static website. For background on what a *logo*, *set*, *sheet*, etc. mean here, see [`CONTEXT.md`](CONTEXT.md).

## Setup

```bash
uv sync                   # Python deps
( cd web && npm install ) # frontend deps
```

## Running locally

Two dev servers, one for each side of the project:

| Server | What it serves | Run |
|---|---|---|
| Tools server (port 5180) | `tools/annotate/` editor, `tools/review/` editor, and the editing API | `uv run python tools/server.py` |
| Website (port 5179) | The browse-able catalog at `web/` (Vue + Vite) | `( cd web && npm run dev )` |

After both are up: open <http://localhost:5180/> for the editing tools and <http://localhost:5179/meowphosis/> for the public site.

## Processing a new sheet end-to-end

A *sheet* is a single PNG in `raw/` holding ~72 cat logos in a grid. Going from a fresh sheet to the public site is five steps; only step 1 is hands-on.

### 1. Annotate the sheet

1. Drop the PNG into `raw/` (e.g. `raw/myth-norse.png`).
2. Open <http://localhost:5180/annotate/>.
3. Click **Sheet** → pick the PNG. Set the **top / sub / set** fields (the eventual taxonomy, e.g. `mythology / norse / 1`).
4. **Grid mode** (`g`): drag the orange grid lines so each cell holds exactly one cat + label. Rows and columns can be uneven — drag each line independently.
5. **Cat mode** (`c`): click **Set template…**, then drag a rectangle inside one cell — that rectangle's cell-relative ratio is replicated to every cell. Fine-tune outliers by dragging individual handles. The "Apply resize to: this cell / whole column / whole row" toggle replays the same drag delta to siblings.
6. **Text mode** (`t`): same flow for the label bbox.
7. Click **Export annotations** — saves to `local/<sheet-stem>.annotations.json`. The tool autosaves to localStorage as you work, and **Load annotations…** lists every `local/*.annotations.json` so you can resume later.

### 2. Identify, normalize, and write the catalog

Run the `/process-annotations` skill in Claude Code:

```
/process-annotations local/myth-norse.annotations.json
```

The skill, defined at [`.claude/skills/process-annotations/SKILL.md`](.claude/skills/process-annotations/SKILL.md), does six things:

1. Calls `scripts/prep_annotations.py` to render per-cell composites (cat tile + label tile) into `local/.annotation-cache/<sheet-stem>/`.
2. Reads each composite, identifies the character (English + Chinese name, iconography, confidence).
3. Writes `local/<sheet-stem>.records.json`.
4. Validates `wiki_url`s via `scripts/validate_wiki_urls.py` — tries category-specific wikis first (e.g. `wiki.leagueoflegends.com` for LoL), then Wikipedia, then any existing URL.
5. Calls `scripts/finalize_annotations.py` to crop + normalize each cat to a 200×200 PNG under `public/logos/<top>/<sub>/<set>/<slug>.png`, upsert the DB row, and regenerate `public/catalog.json` + per-sub-category shards.
6. Reports cells with confidence < 0.7 or null `wiki_url`.

The annotations file is the source of truth for grid + bboxes; the records file is the source of truth for the LLM-derived semantics. Both live in `local/` and are gitignored.

### 3. Review and fix mistakes

Open <http://localhost:5180/review/>. The default view filters to cells flagged as low-confidence or missing a wiki URL. For each cell you can:

- Edit any field (Chinese / English name, slug, wiki URL, iconography, confidence).
- Delete the cell (drops from `records.json` + marks `skip: true` in `annotations.json`).

When done, click **Apply → DB**. This:

1. GCs any DB rows + PNGs whose slugs no longer appear in `records.json` (handles renames + deletions).
2. Re-runs `finalize_annotations.py` to upsert remaining cells and rebuild shards.

### 4. Verify on the site

Refresh <http://localhost:5179/meowphosis/>. The home page lists top categories; clicking one opens a sub-category page with tabs for sibling sub-categories and sets. The header search filters by name + iconography across all loaded shards.

### 5. Adding a new game/franchise wiki

If a new game's characters mostly live in a franchise wiki rather than Wikipedia, register the URL template in [`scripts/validate_wiki_urls.py`](scripts/validate_wiki_urls.py):

```python
CATEGORY_WIKI_PATTERNS = {
    ("game", "league-of-legends"): [
        "https://wiki.leagueoflegends.com/en-us/{name}",
    ],
    # ("game", "arknight"): ["https://arknights.fandom.com/wiki/{name}"],
}
```

The template's `{name}` is the English name with spaces → underscores. Patterns registered here become the *preferred* wiki source for that taxonomy (Wikipedia falls back). Re-run the script (or the whole `/process-annotations` skill) to retroactively update existing records.

## Layout

```
raw/                       sheet PNGs (input)
local/                     per-sheet annotations + records JSON; gitignored
public/                    site-served assets; logos + catalog shards; gitignored
data/meowphosis.db         SQLite catalog DB; gitignored
scripts/                   pipeline (prep / validate / finalize / build_manifest)
tools/
  annotate/                annotation editor (static + served by tools/server.py)
  review/                  review/fix editor (static + same server)
  server.py                FastAPI dev server for both tools
web/                       Vue/Vite public site
docs/                      ADRs + agent docs
.claude/skills/            invocable skills (process-cell, process-annotations)
CONTEXT.md                 domain glossary (logo / sheet / set / category / …)
```

## Issue tracker

Backlog lives as GitHub Issues under [`czczc/meowphosis`](https://github.com/czczc/meowphosis/issues). Triage labels defined in [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md).
