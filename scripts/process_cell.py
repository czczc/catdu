"""Normalize a single cell image and upsert its logo record.

Pipeline: crop the cell to the LLM-provided `cat_bbox` → letterbox onto a
canonical `#fefcf7` canvas at 90% scale → write the PNG → upsert the `logo`
row → invoke `scripts/build_manifest.py` to regenerate the JSON shards.

Invoked by `.claude/skills/process-cell/SKILL.md` after the in-session LLM
extracts the cell's metadata. The metadata JSON arrives on stdin; the cell
image path and `(top, sub, set_number)` triple come from CLI args.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "catalog.db"
PUBLIC = ROOT / "public"
TARGET = 200

# Canonical logo background. All logos share this cream regardless
# of subtle variations in the source sheet's printed background.
BG_COLOR = (0xFE, 0xFC, 0xF7)

# Cat content's LONG axis occupies CONTENT_SCALE of the 200x200 frame; short
# axis is letterboxed with bg, so its margin depends on the cat_bbox aspect
# ratio (taller-than-wide bboxes get wider side bars).
CONTENT_SCALE = 0.95


def _clamp_bbox(bbox: list[int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = (max(0, int(v)) for v in bbox)
    x2 = min(size[0], x2)
    y2 = min(size[1], y2)
    return x1, y1, x2, y2


def normalize_cell(
    cell_image_path: Path,
    cat_bbox: list[int],
    mask_regions: list[list[int]] | None,
    out_path: Path,
) -> None:
    """Mask listed regions with canonical bg, crop to cat_bbox, letterbox.

    `cat_bbox` is the LLM-provided positive bbox of the cat illustration
    (with its iconography). `mask_regions` is a list of rectangles to fill
    with `BG_COLOR` before cropping — used for text labels, neighbor-cell
    bleed, or any non-cat content that falls inside `cat_bbox`.

    Why both: a tight `cat_bbox` produces portrait crops for cells with
    portrait-aspect cats, which letterbox into the square frame with wide
    side bars. A wider `cat_bbox` (extending into cream space around the
    cat) reduces the letterbox effect — but that wider area often contains
    text or bleed. Masking first lets the LLM widen the bbox safely.
    """
    img = Image.open(cell_image_path).convert("RGB")

    if not cat_bbox or len(cat_bbox) != 4:
        raise ValueError(f"cat_bbox required, got: {cat_bbox!r}")

    work = img.copy()
    for region in mask_regions or []:
        if not region or len(region) != 4:
            continue
        x1, y1, x2, y2 = _clamp_bbox(region, work.size)
        if x2 > x1 and y2 > y1:
            patch = Image.new("RGB", (x2 - x1, y2 - y1), BG_COLOR)
            work.paste(patch, (x1, y1))

    # cat_bbox can extend beyond the cell boundary (negative or > cell size);
    # we pad with canonical bg so the LLM can pick a square bbox centered on
    # an asymmetrically-placed cat without being constrained by cell edges.
    x1, y1, x2, y2 = (int(v) for v in cat_bbox)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"cat_bbox is empty or inverted: {cat_bbox!r}")
    pad_left = max(0, -x1)
    pad_top = max(0, -y1)
    pad_right = max(0, x2 - work.size[0])
    pad_bottom = max(0, y2 - work.size[1])
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
    cat = work.crop((x1, y1, x2, y2))

    cw, ch = cat.size
    scale = min(TARGET / cw, TARGET / ch) * CONTENT_SCALE
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    resized = cat.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGB", (TARGET, TARGET), BG_COLOR)
    canvas.paste(resized, ((TARGET - nw) // 2, (TARGET - nh) // 2))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def upsert_logo(
    record: dict,
    top: str,
    sub: str,
    set_num: int,
    image_path: str,
) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.execute(
        """
        SELECT ls.id
        FROM logo_set ls
        JOIN sub_category sc ON ls.sub_category_id = sc.id
        WHERE sc.top_slug = ? AND sc.slug = ? AND ls.set_number = ?
        """,
        (top, sub, set_num),
    )
    row = cur.fetchone()
    if row is None:
        raise SystemExit(
            f"Set not found: {top}/{sub}/{set_num}. "
            "Initialize it via /process-sheet (#3) or seed the row manually."
        )
    set_id = row[0]

    cur.execute(
        """
        INSERT INTO logo
            (set_id, english_name, english_slug, chinese_name, wiki_url,
             iconography, image_path, source_sheet, source_cell, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (set_id, english_slug) DO UPDATE SET
            english_name = excluded.english_name,
            chinese_name = excluded.chinese_name,
            wiki_url = excluded.wiki_url,
            iconography = excluded.iconography,
            image_path = excluded.image_path,
            source_sheet = excluded.source_sheet,
            source_cell = excluded.source_cell,
            confidence = excluded.confidence,
            added_at = datetime('now')
        """,
        (
            set_id,
            record["english_name"],
            record["english_slug"],
            record.get("chinese_name"),
            record.get("wiki_url"),
            json.dumps(record.get("iconography", []), ensure_ascii=False),
            image_path,
            record.get("source_sheet"),
            record.get("cell_number"),
            record.get("confidence", 1.0),
        ),
    )
    conn.commit()
    conn.close()


def rebuild_shards() -> None:
    subprocess.run(
        ["uv", "run", "python", str(ROOT / "scripts" / "build_manifest.py")],
        check=True,
        cwd=ROOT,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cell-image", required=True, type=Path)
    ap.add_argument("--top", required=True)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--set", required=True, type=int, dest="set_num")
    args = ap.parse_args()

    record = json.loads(sys.stdin.read())

    image_rel = (
        f"logos/{args.top}/{args.sub}/{args.set_num}/{record['english_slug']}.png"
    )
    image_abs = PUBLIC / image_rel

    normalize_cell(
        args.cell_image,
        record["cat_bbox"],
        record.get("mask_regions"),
        image_abs,
    )
    print(f"Wrote {image_rel}", file=sys.stderr)

    upsert_logo(record, args.top, args.sub, args.set_num, image_rel)
    print(
        f"Upserted: {args.top}/{args.sub}/{args.set_num}/{record['english_slug']}",
        file=sys.stderr,
    )

    rebuild_shards()


if __name__ == "__main__":
    main()
