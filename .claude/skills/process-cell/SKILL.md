---
name: process-cell
description: Extract a single pre-cropped meowphosis cell image into the catalog. Identifies the character (Chinese label + English name + iconography + wiki URL), normalizes the cat to a 200×200 PNG via text masking and tight-bbox cropping, and upserts the logo row to `data/meowphosis.db`. Auto-regenerates JSON shards.
---

# /process-cell

Process one pre-cropped cell — the unit produced by `/process-sheet` (#3) when batch-processing sheets. This skill handles a cell end-to-end so the cell logic can be developed and tested independently.

## Arguments

Four positional arguments:

1. `cell_image_path` — absolute or repo-relative path to a PNG containing one cell (cat + label, no neighbors).
2. `top_category` — slug of the top category (`mythology`, `games`, …).
3. `sub_category` — slug of the sub-category (`greek`, `league-of-legends`, …).
4. `set_number` — integer set number within the sub-category (`1`, `2`, …).

The `(top, sub, set_number)` triple must already exist in `logo_set` — this skill does NOT classify. Use `/process-sheet` for that.

## Process

### 1. Read the cell

Use the `Read` tool on `cell_image_path`. Inspect the cat and its label together.

### 2. Extract the fields

Produce a JSON record with exactly these keys:

| Field | Type | Notes |
|---|---|---|
| `cell_number` | int | The small sequential number printed in the cell. |
| `chinese_name` | string | The Chinese label as written, exactly. |
| `english_name` | string | Canonical English name. `Zeus`, not `Greek God Zeus` or `宙斯`. |
| `english_slug` | string | ASCII-slugged English name, lowercase, kebab-case. `zeus`, `loki`, `freyja`. |
| `wiki_url` | string \| null | `https://en.wikipedia.org/wiki/<EnglishName>` if confidently resolvable, otherwise `null`. |
| `iconography` | string[] | 1–4 short visual cues you can SEE in the cat illustration that link it to the character. Examples — Zeus: `["lightning bolt", "scepter"]`, Loki: `["black coat", "snake"]`, Demeter: `["wheat sheaf"]`. Avoid generic words like "crown" if every cat has one; prefer character-specific cues. |
| `confidence` | number, 0..1 | Your overall confidence in this cell's data. Drop below 0.7 if the label is ambiguous, the iconography doesn't match the named character, or the wiki URL is uncertain. |
| `cat_bbox` | [x1, y1, x2, y2] | Pixel bounding box of the **logo content** in the cell, in cell-image pixel coordinates (origin top-left). The pipeline crops to this and letterboxes. **Make it square** (`x2 - x1 == y2 - y1`) centered on the cat — cells are not square (typically ~165×131), so a square bbox centered on the cat will usually extend beyond the cell boundary on one side. That's OK — the pipeline auto-pads with canonical bg (`#fefcf7`) on whichever side overflows. Square bbox → no letterbox margins → cat fills the 200×200 frame with uniform ~5px breathing room. Include the cat's full body and all attached iconography in the bbox; mask anything that's not the cat via `mask_regions`. |
| `mask_regions` | list[[x1, y1, x2, y2]] | Optional. Rectangles to fill with canonical bg (`#fefcf7`) BEFORE the crop. Use this to wipe text labels, cell numbers, or neighbor-cell bleed that fall INSIDE the cat_bbox. Without masking, those would appear in the final logo. Typical use: cat_bbox wraps the cat plus surrounding cream space; mask_regions wipe the text that lives in that cream space. Order doesn't matter; regions can overlap. Empty list / omitted if there's nothing to mask. |

### 3. Validate the wiki URL

Wikipedia 403s requests without a User-Agent. HEAD-check the URL:

```bash
uv run python -c "
import httpx
r = httpx.head(
    '<URL>',
    follow_redirects=True,
    headers={'User-Agent': 'meowphosis/0.1 (chao.zh@gmail.com)'},
)
print(r.status_code, r.url)
"
```

If non-200, set `wiki_url` to `null` in the record. Do not invent or guess a URL.

### 4. Hand off to the Python pipeline

Pass the record on stdin to `scripts/process_cell.py` along with the positional args:

```bash
echo '<JSON_RECORD>' | uv run python scripts/process_cell.py \
    --cell-image '<cell_image_path>' \
    --top '<top_category>' \
    --sub '<sub_category>' \
    --set <set_number>
```

The script:

1. Crops the cell to `cat_bbox`.
2. Scales the crop so its longer side is 90% of 200px; letterboxes onto a canonical `#fefcf7` canvas, centered.
3. Writes `public/logos/<top>/<sub>/<set>/<english_slug>.png`.
4. Upserts the `logo` row (newer overwrites by `(set_id, english_slug)`).
5. Calls `scripts/build_manifest.py` to regenerate the JSON shards.

### 5. Report

Tell the user:

- The resolved English name and image path.
- The confidence value.
- Flag anything suspicious: confidence < 0.7, `wiki_url` set to null, iconography that didn't match expectations.

## Idempotency

Re-running on the same cell is safe — the DB row upserts on `(set_id, english_slug)` and the image file is overwritten in place. The shard regeneration is deterministic.

## What this skill does NOT do

- It does not classify the cell's `(top, sub, set)`. The caller must pass those. `/process-sheet` (#3) handles full-sheet classification.
- It does not detect or split a multi-cell sheet. Pre-cropped single-cell input only.
- It does not handle layout detection. The `label_bbox` you provide encodes the layout for this cell.
