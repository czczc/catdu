# Sheet processing pipeline

How a new sheet of cat illustrations becomes browsable rows on the public site. Five steps; only step 1 is hands-on.

For domain vocabulary (logo, set, sheet, etc.), see [`../CONTEXT.md`](../CONTEXT.md).

## 1. Annotate the sheet

1. Drop the PNG into `raw/` (e.g. `raw/myth-norse.png`).
2. Open <http://localhost:5180/annotate/>.
3. Click **Sheet** → pick the PNG. Set the **top / sub / set** fields (the eventual taxonomy, e.g. `mythology / norse / 1`).
4. **Grid mode** (`g`): drag the orange grid lines so each cell holds exactly one cat + label. Rows and columns can be uneven — drag each line independently.
5. **Cat mode** (`c`): click **Set template…**, then drag a rectangle inside one cell — that rectangle's cell-relative ratio is replicated to every cell. Fine-tune outliers by dragging individual handles. The "Apply resize to: this cell / whole column / whole row" toggle replays the same drag delta to siblings.
6. **Text mode** (`t`): same flow for the label bbox.
7. Click **Export annotations** — saves to `local/<top_category>/<sheet-stem>.annotations.json`. If you exported before setting the top/sub fields it goes to `local/_uncategorized/`; fix the category and re-export to move it. The tool autosaves to localStorage as you work, and **Load annotations…** lists every annotations file (any depth) so you can resume later.

## 2. Identify, normalize, and write the catalog

Run the `/process-annotations` skill in Claude Code:

```
/process-annotations local/mythology/myth-norse.annotations.json
```

The skill, defined at [`../.claude/skills/process-annotations/SKILL.md`](../.claude/skills/process-annotations/SKILL.md), does seven things:

1. Calls `scripts/prep_annotations.py` to render per-cell composites (cat tile + label tile) into `local/.annotation-cache/<sheet-stem>/`.
2. Reads each composite, identifies the character (English + Chinese name, iconography, confidence).
3. Writes `local/<top_category>/<sheet-stem>.records.json` (sibling of the annotations file).
4. Validates `wiki_url`s via `scripts/validate_wiki_urls.py` — tries category-specific wikis first (e.g. `wiki.leagueoflegends.com` for LoL), then Wikipedia, then any existing URL.
5. Calls `scripts/finalize_annotations.py` to crop + normalize each cat to a 200×200 PNG under `public/logos/<top>/<sub>/<set>/<slug>.png`, upsert the DB row, and regenerate `public/catalog.json` + per-sub-category shards. A per-logo `image_fingerprint` (hash of `cat_bbox` + `text_bbox` + threshold) is stored on the DB row; a cell whose image inputs are unchanged keeps its existing PNG instead of being re-rendered, so metadata-only edits don't reset an already-upscaled logo back to 200px.
6. Calls `scripts/upscale_logos.py --in-place --scale 2` to upscale the new 200×200 PNGs to 400×400 with the `realesrgan-x4plus-anime` model. Idempotent — skips logos already ≥400px. Requires the [upscaler binary](#upscaler-setup-tools-realesrgan).
7. Reports cells with confidence < 0.7 or null `wiki_url`.

The annotations file is the source of truth for grid + bboxes; the records file is the source of truth for the LLM-derived semantics. Both live in `local/` and are gitignored.

## 3. Review and fix mistakes

Open <http://localhost:5180/review/>. The default view filters to cells flagged as low-confidence or missing a wiki URL. For each cell you can:

- Edit any field (Chinese / English name, slug, wiki URL, iconography, confidence).
- Delete the cell (drops from `records.json` + marks `skip: true` in `annotations.json`).

When done, click **Apply → DB**. This:

1. GCs any DB rows + PNGs whose slugs no longer appear in `records.json` (handles renames + deletions).
2. Re-runs `finalize_annotations.py` to upsert remaining cells and rebuild shards.
3. Re-runs `upscale_logos.py --in-place --scale 2` to restore any re-rendered 200×200 PNGs to 400×400 (idempotent — skips anything already ≥400px). Because finalize only re-renders cells whose image inputs changed, a review pass that edits metadata re-upscales nothing; changing one image re-upscales only that one.

## 4. Verify on the site

Refresh <http://localhost:5173/meowphosis/>. The home page lists top categories; clicking one opens a sub-category page with tabs for sibling sub-categories and sets. The header search filters by name + iconography across all loaded shards.

## 5. Adjust visibility (optional)

To hide a top or sub-category from the public catalog without deleting it:

```bash
uv run python scripts/visibility.py hide game            # hide a top category
uv run python scripts/visibility.py hide game/arknight   # hide a sub-category
uv run python scripts/visibility.py list                 # see current state
```

Or use the web UI at <http://localhost:5180/visibility/>. Visibility flags are stored on the DB rows; `scripts/build_manifest.py` (and the finalize step) filter accordingly.

## Adding a new game/franchise wiki

If a new game's characters mostly live in a franchise wiki rather than Wikipedia, register the URL template in [`../scripts/validate_wiki_urls.py`](../scripts/validate_wiki_urls.py):

```python
CATEGORY_WIKI_PATTERNS = {
    ("game", "league-of-legends"): [
        "https://wiki.leagueoflegends.com/en-us/{name}",
    ],
    # ("game", "arknight"): ["https://arknights.fandom.com/wiki/{name}"],
}
```

The template's `{name}` is the English name with spaces → underscores. Patterns registered here become the *preferred* wiki source for that taxonomy (Wikipedia falls back). Re-run the script (or the whole `/process-annotations` skill) to retroactively update existing records.

## Upscaler setup (`tools/realesrgan/`)

The upscale step in `/process-annotations` shells out to [Real-ESRGAN ncnn-vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan). The binary + anime model weights live under `tools/realesrgan/` (gitignored — ~50MB total). To install on macOS:

```bash
mkdir -p tools/realesrgan && cd tools/realesrgan
curl -L -o full.zip https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip
unzip -q full.zip && rm full.zip
chmod +x realesrgan-ncnn-vulkan
# Optional cleanup of demo files included in the zip:
rm -f input.jpg input2.jpg onepiece_demo.mp4 README_macos.md
```

`scripts/upscale_logos.py` always runs the `realesrgan-x4plus-anime` model at native 4×, then Lanczos-downsamples to the requested scale (`--scale 2` → 400×400). Modes:

- `--sample N` — upscale N random logos into `local/upscale-samples/` (with `__orig` and `__x{scale}` pairs) for side-by-side quality review. Originals untouched.
- `--in-place` — overwrite every PNG under `public/logos/`. Atomic per-file rename; idempotent skip when a PNG is already ≥ target resolution.

The original 200×200 PNGs from the first bulk run are preserved at `local/logos-200-backup/` (gitignored) as a restore point.
