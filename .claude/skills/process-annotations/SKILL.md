---
name: process-annotations
description: Process a sheet annotation JSON (produced by the manual annotation UI at tools/annotate/) into normalized 200×200 cat logos with full metadata. The user defines the grid by dragging row/column lines, then sets cat and text templates and fine-tunes per cell. For each cell, the LLM reads a two-tile composite (cat-on-top, text-below) to identify the character — Chinese name, English name, Wikipedia URL, iconography, confidence — and the pipeline crops the user-defined cat_bbox per cell. Falls back to auto-derive if cat_bbox is missing.
---

# /process-annotations

Process a sheet of annotated cells into the catalog. The user has dragged the grid lines and (optionally) marked skips or `cat_bbox` overrides for problem cells; this skill handles OCR, name resolution, iconography identification, image normalization, DB writes, and shard regen.

## Argument

Path to the annotations.json file (absolute or repo-relative). Annotations are bucketed by top category — sheets exported from the annotate tool land under `local/<top_category>/<stem>.annotations.json`. Example:
`local/mythology/myth-greek-1.annotations.json` or `/Users/.../Downloads/myth-greek.annotations.json`.

Sheets exported without `top_category` set fall into `local/_uncategorized/` — fix the top/sub category in the annotate tool and re-export to file them properly.

## Process

### 1. Prep — render each cell as a composite preview

```bash
uv run python scripts/prep_annotations.py <ANNOTATIONS_PATH>
```

This prints a JSON manifest to stdout: `{cache_dir, cells: [{cell_number, composite, english_override?}, ...]}`. Each `composite` is a single PNG with **cat-tile on top (320×320)** and **text-tile below (320×96)**, both letterboxed onto a cream canvas. Cells flagged `skip: true` are omitted.

Capture the manifest into a variable or temp file.

### 2. Identify each cell

For each cell in the manifest, **read the composite image** with the `Read` tool. The composite has two regions:

- **Top tile**: the cat illustration crop. Use this for `iconography`.
- **Bottom tile**: the text label crop. Use this for `chinese_name` and `english_name`.

Per cell, extract:

| Field | Type | Notes |
|---|---|---|
| `cell_number` | int | From the manifest entry. |
| `chinese_name` | string | The Chinese label as written. If the source label is English (and `english_override` is set or you see English text), produce the Chinese translation (e.g. "Zeus" → "宙斯"). |
| `english_name` | string | Canonical English name. If `english_override` is in the manifest, **use it verbatim**. Otherwise translate from the Chinese (e.g. "宙斯" → "Zeus"). Drop article-style decorations: "Zeus" not "Greek god Zeus". |
| `english_slug` | string | ASCII-slugged English name, lowercase, kebab-case: `zeus`, `loki`, `freyja`. |
| `wiki_url` | string \| null | `https://en.wikipedia.org/wiki/<EnglishName>` if confidently resolvable. Null otherwise — do not invent. |
| `iconography` | string[] | 1–4 short visual cues you can SEE on the cat that link to this character. e.g. Zeus → `["lightning bolt", "scepter"]`, Loki → `["black coat", "snake"]`. Avoid generic terms ("crown") if every cat has one. |
| `summary` | string | 1–2 short sentences (≈25–45 words) describing what/who this is, with enough context to relate back to the iconography on the cat. e.g. Ares → "Ares is the Greek god of war and courage, often depicted in armor with a spear and helmet — the cat wears a crested Greek helmet and carries a spear." Skip "the cat wears…" framing when the connection is obvious. |
| `confidence` | number, 0..1 | Drop below 0.7 if the label is illegible, iconography doesn't match the named character, or there's any other reason to flag for human review. |

**Batch the reads** — call `Read` on multiple composite paths in parallel within a single turn. Reading 6–12 cells per turn keeps the workflow responsive.

### 3. Compose records.json

Write a records file via the `Write` tool. Default path: **same directory as the annotations file**, named `<annotations-stem>.records.json` (so a bucketed annotations file at `local/<top>/<stem>.annotations.json` gets a sibling `local/<top>/<stem>.records.json`). Shape:

```json
{
  "cells": [
    {
      "cell_number": 1,
      "chinese_name": "宙斯",
      "english_name": "Zeus",
      "english_slug": "zeus",
      "wiki_url": "https://en.wikipedia.org/wiki/Zeus",
      "iconography": ["lightning bolt", "scepter"],
      "summary": "Zeus is the king of the Greek gods, ruler of the sky and thunder, wielding the lightning bolt and seated on Olympus.",
      "confidence": 0.98
    }
  ]
}
```

Order doesn't matter; one entry per processable cell.

### 4. Validate wiki URLs (Wikipedia + category-specific fallbacks)

```bash
uv run python scripts/validate_wiki_urls.py <ANNOTATIONS_PATH> <RECORDS_PATH>
```

For each cell, HEAD-tries the candidate URLs in this order — keeping the first that returns 200, otherwise nulling the field:

1. Category-specific wiki templates registered in `CATEGORY_WIKI_PATTERNS` in the script, keyed by `(top_category, sub_category)`. e.g. `game/league-of-legends` → `https://wiki.leagueoflegends.com/en-us/{name}`.
2. `https://en.wikipedia.org/wiki/<EnglishName>` (spaces → underscores) as a fallback.
3. The records' existing `wiki_url`, last — preserves manual overrides made via the review UI.

When a category-specific pattern is defined, it becomes the *preferred* source — even Wikipedia URLs that resolved on a prior run get re-targeted to the franchise wiki on the next run. To add a new game/franchise, add a row to `CATEGORY_WIKI_PATTERNS` and re-run. The validation uses a User-Agent (Wikipedia 403s anonymous requests).

### 5. Finalize — normalize, upsert DB, regen shards

```bash
uv run python scripts/finalize_annotations.py <ANNOTATIONS_PATH> <RECORDS_PATH>
```

For each cell, crops the user-supplied `cat_bbox` from the sheet, scales at 95% onto a 200×200 cream canvas, writes the logo PNG to `public/logos/<top>/<sub>/<set>/<english_slug>.png`, and upserts the `logo` row keyed on `(set_id, english_slug)`. Cells without `cat_bbox` fall back to the legacy auto-derive (text_region masking + diff vs bg). Finally regenerates `public/catalog.json` + per-sub-category shards.

The finalize report prints `[USER]` vs `[AUTO]` per cell so it's clear which came from manual bbox vs the fallback.

### 6. Upscale the new logos

```bash
uv run python scripts/upscale_logos.py --in-place --scale 2
```

Replaces each 200×200 logo PNG with a 400×400 version produced by `realesrgan-x4plus-anime` (run at native 4× then Lanczos-downsampled). The script is idempotent — it skips PNGs already ≥400px, so it only touches the new cells from this sheet. Atomic per-file rename, safe to interrupt.

### 7. Name the set (one-word content noun)

`scripts/finalize_annotations.py` creates new sets with `logo_set.display="Set"`. Every set needs a single-word content noun describing the theme (e.g. physics → "Particles", chemistry → "Elements", geography/usa → "States", mythology/* → "Deities", sports/soccer → "Nations"). This shows in the detail pane's **Set** column and the set-switcher chips.

First check the current value — if a meaningful name is already there from a prior run, skip this step:

```bash
sqlite3 data/catalog.db "SELECT ls.id, sc.slug, ls.set_number, ls.display FROM logo_set ls JOIN sub_category sc ON sc.id=ls.sub_category_id WHERE sc.slug='<sub_slug>' AND ls.set_number=<set_number>;"
```

If it's still `"Set"`, pick a one-word noun fitting the sheet's theme and update. Ask the user if you're not sure:

```bash
sqlite3 data/catalog.db "UPDATE logo_set SET display='<OneWord>' WHERE id=<id>;"
uv run python scripts/build_manifest.py
```

The manifest rebuild regenerates `public/catalog.json` and the affected shard.

### 8. Report

Summarize for the user:
- Total cells processed (user / auto split)
- Cells skipped (and why — marked skip, no record, no english_slug, auto-bbox empty)
- Cells with confidence < 0.7 (flag for review)
- Cells with `wiki_url = null` after validation

## Notes

- The skill is idempotent: re-running on the same annotations.json overwrites the logo PNGs and updates the DB rows in place.
- Cells marked `skip: true` are silently omitted from both prep and finalize.
- `english_override` from the UI is honored verbatim — useful when the LLM might mis-translate an obscure character.
- The composite tiles are letterboxed to fixed sizes for readability. Do not infer original bbox dimensions from them.
- The annotation UI exposes a "cat" mode and a "text" mode. In each, the user sets a template once (cell-relative `{x, y, w, h}` rectangle) which instantiates a bbox in every cell, then drags any cell's box to fine-tune.
- For backward compat: if a cell has no `cat_bbox`, the finalize step auto-derives one by masking `grid.text_region` and diffing against `#fefcf7` (controlled by optional `grid.diff_threshold`, default 6).
