"""Finalize step for the /process-annotations skill.

Reads annotations.json (grid + optional cell overrides) + records.json
(LLM-produced semantics) and:

  1. Ensures top_category / sub_category / logo_set rows exist.
  2. For each cell in the rows×cols grid (minus skipped cells), uses the
     `cat_bbox` override if present, otherwise derives one from the cell
     bounds by diff-from-bg with the text band masked out. Crops, normalizes
     to 200×200, writes the logo PNG, upserts the logo row.
  3. Regenerates the JSON shards via scripts/build_manifest.py.

Idempotent on (set_id, english_slug) per ADR-0002.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
PUBLIC = ROOT / "public"
DB_PATH = ROOT / "data" / "meowphosis.db"

TARGET = 200
BG_COLOR = (0xFE, 0xFC, 0xF7)
CONTENT_SCALE = 0.95
DEFAULT_DIFF_THRESHOLD = 6
# Palette sampling: quantize to N buckets, drop near-bg, take top 5 by area.
PALETTE_SLOTS = 5
PALETTE_QUANTIZE = 16
PALETTE_BG_TOLERANCE = 20
# Cell-relative {x, y, w, h} (each 0..1) for the text region. Default None →
# no masking (works when the cat is the only non-bg content in the cell).
# Sheets where the label sits alongside the cat must supply text_region in the
# annotations.json grid block.
DEFAULT_TEXT_REGION = None


def ensure_taxonomy(
    conn: sqlite3.Connection,
    top_slug: str,
    sub_slug: str,
    set_number: int,
    set_display: str = "Set",
) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO top_category (slug, display) VALUES (?, ?)",
        (top_slug, top_slug.replace("-", " ").title()),
    )
    cur.execute(
        "INSERT OR IGNORE INTO sub_category (top_slug, slug, display) VALUES (?, ?, ?)",
        (top_slug, sub_slug, sub_slug.replace("-", " ").title()),
    )
    cur.execute(
        "SELECT id FROM sub_category WHERE top_slug = ? AND slug = ?",
        (top_slug, sub_slug),
    )
    sub_id = cur.fetchone()[0]
    cur.execute(
        "INSERT OR IGNORE INTO logo_set (sub_category_id, set_number, display) VALUES (?, ?, ?)",
        (sub_id, set_number, set_display),
    )
    cur.execute(
        "SELECT id FROM logo_set WHERE sub_category_id = ? AND set_number = ?",
        (sub_id, set_number),
    )
    return cur.fetchone()[0]


def cell_bounds_from_grid(grid: dict, cell_number: int) -> tuple[int, int, int, int]:
    rows = int(grid["rows"])
    cols = int(grid["cols"])
    idx = cell_number - 1
    row = idx // cols
    col = idx % cols
    if "x_lines" in grid and "y_lines" in grid:
        x_lines = grid["x_lines"]
        y_lines = grid["y_lines"]
    else:
        ext = grid.get("extent")
        if not ext:
            raise ValueError("grid missing both x_lines/y_lines and extent")
        x1, y1, x2, y2 = ext["x1"], ext["y1"], ext["x2"], ext["y2"]
        x_lines = [x1 + (x2 - x1) * i / cols for i in range(cols + 1)]
        y_lines = [y1 + (y2 - y1) * i / rows for i in range(rows + 1)]
    return (
        int(x_lines[col]),
        int(y_lines[row]),
        int(x_lines[col + 1]),
        int(y_lines[row + 1]),
    )


def derive_cat_bbox(
    sheet: Image.Image,
    cell_bounds: tuple[int, int, int, int],
    text_region: dict | None = DEFAULT_TEXT_REGION,
    diff_threshold: int = DEFAULT_DIFF_THRESHOLD,
) -> list[int] | None:
    """Find the tight bbox of non-bg pixels inside the cell, after masking the
    text region. Returns sheet-relative coords, or None if the cell looks
    empty.

    `text_region`, if provided, is `{x, y, w, h}` in cell-relative ratios
    (each 0..1). The named rectangle inside each cell is filled with bg before
    the diff, so the label doesn't get caught in the cat bbox.
    """
    cx1, cy1, cx2, cy2 = cell_bounds
    crop = sheet.crop((cx1, cy1, cx2, cy2)).convert("RGB")

    if text_region:
        tx = int(crop.width * float(text_region["x"]))
        ty = int(crop.height * float(text_region["y"]))
        tw = int(crop.width * float(text_region["w"]))
        th = int(crop.height * float(text_region["h"]))
        if tw > 0 and th > 0:
            d = ImageDraw.Draw(crop)
            d.rectangle([tx, ty, tx + tw, ty + th], fill=BG_COLOR)

    bg_img = Image.new("RGB", crop.size, BG_COLOR)
    diff = ImageChops.difference(crop, bg_img).convert("L")
    mask = diff.point(lambda v: 255 if v > diff_threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return None
    rx1, ry1, rx2, ry2 = bbox
    return [cx1 + rx1, cy1 + ry1, cx1 + rx2, cy1 + ry2]


def sample_palette(img: Image.Image) -> list[str]:
    """Return up to PALETTE_SLOTS hex codes for the most-occupied colors in
    the normalized logo, excluding pixels near the cream background.
    """
    q = img.convert("RGB").quantize(
        colors=PALETTE_QUANTIZE, method=Image.Quantize.MEDIANCUT
    )
    raw = q.getpalette() or []
    counts = q.getcolors() or []
    counts.sort(key=lambda c: -c[0])
    bg_r, bg_g, bg_b = BG_COLOR
    out: list[str] = []
    for _, idx in counts:
        r = raw[idx * 3]
        g = raw[idx * 3 + 1]
        b = raw[idx * 3 + 2]
        if (
            abs(r - bg_r) < PALETTE_BG_TOLERANCE
            and abs(g - bg_g) < PALETTE_BG_TOLERANCE
            and abs(b - bg_b) < PALETTE_BG_TOLERANCE
        ):
            continue
        out.append(f"#{r:02x}{g:02x}{b:02x}")
        if len(out) >= PALETTE_SLOTS:
            break
    return out


def normalize_cat(
    sheet: Image.Image,
    cat_bbox: list[int],
    out_path: Path,
    text_bbox: list[int] | None = None,
    diff_threshold: int = DEFAULT_DIFF_THRESHOLD,
) -> None:
    """Crop cat_bbox from the sheet, mask any overlap with text_bbox, tighten
    to the actual cat content via diff-from-bg, then scale + letterbox to
    200×200 on a cream canvas.
    """
    x1, y1, x2, y2 = (int(v) for v in cat_bbox)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"cat_bbox is empty or inverted: {cat_bbox!r}")

    pad_left = max(0, -x1)
    pad_top = max(0, -y1)
    pad_right = max(0, x2 - sheet.size[0])
    pad_bottom = max(0, y2 - sheet.size[1])
    work = sheet
    if pad_left or pad_top or pad_right or pad_bottom:
        new_w = work.size[0] + pad_left + pad_right
        new_h = work.size[1] + pad_top + pad_bottom
        padded = Image.new("RGB", (new_w, new_h), BG_COLOR)
        padded.paste(work, (pad_left, pad_top))
        work = padded
        x1 += pad_left
        y1 += pad_top
        x2 += pad_left
        y2 += pad_top

    cat = work.crop((x1, y1, x2, y2)).convert("RGB")

    # If the user defined a text_bbox, mask any overlap so the label doesn't
    # bleed into the final logo. text_bbox is in sheet coords (pre-pad); shift
    # to cat-crop-local coords.
    if text_bbox:
        tx1, ty1, tx2, ty2 = (int(v) for v in text_bbox)
        tx1 += pad_left
        tx2 += pad_left
        ty1 += pad_top
        ty2 += pad_top
        ix1 = max(tx1, x1) - x1
        iy1 = max(ty1, y1) - y1
        ix2 = min(tx2, x2) - x1
        iy2 = min(ty2, y2) - y1
        if ix2 > ix1 and iy2 > iy1:
            ImageDraw.Draw(cat).rectangle([ix1, iy1, ix2, iy2], fill=BG_COLOR)

    # Tighten to actual non-bg content so the cat sits centered after letterbox.
    bg_img = Image.new("RGB", cat.size, BG_COLOR)
    diff = ImageChops.difference(cat, bg_img).convert("L")
    mask = diff.point(lambda v: 255 if v > diff_threshold else 0)
    tight = mask.getbbox()
    if tight:
        cat = cat.crop(tight)

    cw, ch = cat.size
    scale = min(TARGET / cw, TARGET / ch) * CONTENT_SCALE
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    resized = cat.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (TARGET, TARGET), BG_COLOR)
    canvas.paste(resized, ((TARGET - nw) // 2, (TARGET - nh) // 2))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("annotations", type=Path)
    ap.add_argument("records", type=Path)
    args = ap.parse_args()

    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    records_data = json.loads(args.records.read_text(encoding="utf-8"))
    records_by_cell: dict[int, dict] = {
        int(r["cell_number"]): r for r in records_data["cells"]
    }

    sheet_path = RAW / annotations["sheet_filename"]
    if not sheet_path.exists():
        raise SystemExit(f"Sheet not found at raw/{annotations['sheet_filename']}")
    sheet = Image.open(sheet_path).convert("RGB")

    top = annotations["top_category"]
    sub = annotations["sub_category"]
    set_num = int(annotations["set_number"])
    grid = annotations["grid"]
    rows = int(grid["rows"])
    cols = int(grid["cols"])
    text_region = grid.get("text_region", DEFAULT_TEXT_REGION)
    diff_threshold = int(grid.get("diff_threshold", DEFAULT_DIFF_THRESHOLD))

    overrides = {int(c["cell_number"]): c for c in annotations.get("cells", [])}

    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}. Run scripts/init_db.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    set_id = ensure_taxonomy(conn, top, sub, set_num)
    cur = conn.cursor()

    written: list[tuple[int, str, str]] = []  # (n, slug, source: "override"|"auto")
    skipped: list[tuple[int, str]] = []

    for n in range(1, rows * cols + 1):
        ov = overrides.get(n, {})
        if ov.get("skip"):
            skipped.append((n, "marked skip"))
            continue
        rec = records_by_cell.get(n)
        if not rec:
            skipped.append((n, "no record"))
            continue
        if not rec.get("english_slug"):
            skipped.append((n, "no english_slug"))
            continue

        bounds = cell_bounds_from_grid(grid, n)
        if ov.get("cat_bbox"):
            cat_bbox = ov["cat_bbox"]
            source = "user"
        else:
            # Fallback: derive from cell + text_region (legacy path).
            cat_bbox = derive_cat_bbox(sheet, bounds, text_region, diff_threshold)
            source = "auto"
            if cat_bbox is None:
                skipped.append((n, "auto cat_bbox empty (cell looks blank)"))
                continue

        image_rel = f"logos/{top}/{sub}/{set_num}/{rec['english_slug']}.png"
        normalize_cat(
            sheet,
            cat_bbox,
            PUBLIC / image_rel,
            text_bbox=ov.get("text_bbox"),
            diff_threshold=diff_threshold,
        )
        palette = sample_palette(Image.open(PUBLIC / image_rel))

        cur.execute(
            """
            INSERT INTO logo
                (set_id, english_name, english_slug, chinese_name, wiki_url,
                 iconography, summary, palette, image_path, source_sheet,
                 source_cell, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (set_id, english_slug) DO UPDATE SET
                english_name = excluded.english_name,
                chinese_name = excluded.chinese_name,
                wiki_url = excluded.wiki_url,
                iconography = excluded.iconography,
                summary = excluded.summary,
                palette = excluded.palette,
                image_path = excluded.image_path,
                source_sheet = excluded.source_sheet,
                source_cell = excluded.source_cell,
                confidence = excluded.confidence,
                added_at = datetime('now')
            """,
            (
                set_id,
                rec["english_name"],
                rec["english_slug"],
                rec.get("chinese_name"),
                rec.get("wiki_url"),
                json.dumps(rec.get("iconography", []), ensure_ascii=False),
                rec.get("summary"),
                json.dumps(palette, ensure_ascii=False),
                image_rel,
                annotations["sheet_filename"],
                n,
                rec.get("confidence", 1.0),
            ),
        )
        written.append((n, rec["english_slug"], source))

    conn.commit()
    conn.close()

    subprocess.run(
        ["uv", "run", "python", str(ROOT / "scripts" / "build_manifest.py")],
        check=True,
        cwd=ROOT,
    )

    user_count = sum(1 for _, _, s in written if s == "user")
    auto_count = sum(1 for _, _, s in written if s == "auto")
    print(
        f"Wrote {len(written)} logo(s) ({user_count} user, {auto_count} auto), "
        f"skipped {len(skipped)}.",
        file=sys.stderr,
    )
    for n, slug, source in written:
        tag = "USER" if source == "user" else "AUTO"
        print(f"  ✓ [{tag}] cell {n:03d} → {top}/{sub}/{set_num}/{slug}", file=sys.stderr)
    for n, reason in skipped:
        print(f"  · skip cell {n:03d}: {reason}", file=sys.stderr)


if __name__ == "__main__":
    main()
