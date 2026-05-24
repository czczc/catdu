---
name: process-annotations
description: Process a sheet annotation JSON (produced by the manual annotation UI at tools/annotate/) into normalized 200×200 cat logos with full metadata. The user defines the grid by dragging row/column lines, then sets cat and text templates and fine-tunes per cell. For each cell, the LLM reads a two-tile composite (cat-on-top, text-below) to identify the character — Chinese name, English name, Wikipedia URL, iconography, confidence — and the pipeline crops the user-defined cat_bbox per cell. Falls back to auto-derive if cat_bbox is missing.
---

# /process-annotations

Process a sheet of annotated cells into the meowphosis catalog. The user has dragged the grid lines and (optionally) marked skips or `cat_bbox` overrides for problem cells; this skill handles OCR, name resolution, iconography identification, image normalization, DB writes, and shard regen.

## Argument

Path to the annotations.json file (absolute or repo-relative). Example:
`local/myth-greek.annotations.json` or `/Users/.../Downloads/myth-greek.annotations.json`.

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
| `confidence` | number, 0..1 | Drop below 0.7 if the label is illegible, iconography doesn't match the named character, or there's any other reason to flag for human review. |

**Batch the reads** — call `Read` on multiple composite paths in parallel within a single turn. Reading 6–12 cells per turn keeps the workflow responsive.

### 3. Compose records.json

Write a records file via the `Write` tool. Default path: same directory as the annotations file, named `<annotations-stem>.records.json`. Shape:

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
      "confidence": 0.98
    }
  ]
}
```

Order doesn't matter; one entry per processable cell.

### 4. Validate wiki URLs (HEAD with User-Agent)

Wikipedia 403s requests without a User-Agent. Run:

```bash
uv run python -c "
import json, sys, httpx
path = '<RECORDS_PATH>'
data = json.load(open(path))
ua = {'User-Agent': 'meowphosis/0.1 (chao.zh@gmail.com)'}
flagged = []
with httpx.Client(timeout=10.0, follow_redirects=True, headers=ua) as h:
    for cell in data['cells']:
        url = cell.get('wiki_url')
        if not url:
            continue
        try:
            r = h.head(url)
            if r.status_code != 200:
                flagged.append((cell['cell_number'], cell['english_name'], r.status_code))
                cell['wiki_url'] = None
        except Exception as e:
            flagged.append((cell['cell_number'], cell['english_name'], str(e)))
            cell['wiki_url'] = None
json.dump(data, open(path, 'w'), ensure_ascii=False, indent=2)
for n, name, code in flagged:
    print(f'cell {n:03d} {name}: {code} → wiki_url cleared')
"
```

### 5. Finalize — normalize, upsert DB, regen shards

```bash
uv run python scripts/finalize_annotations.py <ANNOTATIONS_PATH> <RECORDS_PATH>
```

For each cell, crops the user-supplied `cat_bbox` from the sheet, scales at 95% onto a 200×200 cream canvas, writes the logo PNG to `public/logos/<top>/<sub>/<set>/<english_slug>.png`, and upserts the `logo` row keyed on `(set_id, english_slug)`. Cells without `cat_bbox` fall back to the legacy auto-derive (text_region masking + diff vs bg). Finally regenerates `public/catalog.json` + per-sub-category shards.

The finalize report prints `[USER]` vs `[AUTO]` per cell so it's clear which came from manual bbox vs the fallback.

### 6. Report

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
