"""Normalize a single cell image and upsert its logo record.

Pipeline: mask the label region with the sheet's cream background → find
tight bbox of remaining non-background pixels (the cat) → letterbox to
200×200 → write the PNG → upsert the `logo` row → invoke
`scripts/build_manifest.py` to regenerate the JSON shards.

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
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "meowphosis.db"
PUBLIC = ROOT / "public"
TARGET = 200
MARGIN_PCT = 0.05
DIFF_THRESHOLD = 12  # how much a pixel must differ from bg to count as content


def detect_bg(img: Image.Image) -> tuple[int, int, int]:
    """Sample the four corners and return the mode color.

    Corners are reliably background on every cell layout we've seen — the
    cream extends to the edges of each cell. Using the mode of four samples
    handles the rare case where one corner clips a glyph or stroke.
    """
    w, h = img.size
    samples = [
        img.getpixel((1, 1)),
        img.getpixel((w - 2, 1)),
        img.getpixel((1, h - 2)),
        img.getpixel((w - 2, h - 2)),
    ]
    return Counter(samples).most_common(1)[0][0]


def normalize_cell(
    cell_image_path: Path,
    label_bbox: list[int] | None,
    out_path: Path,
) -> None:
    img = Image.open(cell_image_path).convert("RGB")
    bg = detect_bg(img)

    masked = img.copy()
    if label_bbox and len(label_bbox) == 4:
        x1, y1, x2, y2 = (max(0, int(v)) for v in label_bbox)
        x2 = min(masked.size[0], x2)
        y2 = min(masked.size[1], y2)
        if x2 > x1 and y2 > y1:
            patch = Image.new("RGB", (x2 - x1, y2 - y1), bg)
            masked.paste(patch, (x1, y1))

    # Difference against a solid-bg image, threshold the result, take getbbox.
    # Thresholding rejects sub-pixel anti-aliasing fringe that would otherwise
    # extend the bbox beyond the actual content.
    bg_img = Image.new("RGB", masked.size, bg)
    diff = ImageChops.difference(masked, bg_img).convert("L")
    mask = diff.point(lambda p: 255 if p > DIFF_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None:
        bbox = (0, 0, masked.size[0], masked.size[1])

    x1, y1, x2, y2 = bbox
    margin = int(max(x2 - x1, y2 - y1) * MARGIN_PCT)
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(masked.size[0], x2 + margin)
    y2 = min(masked.size[1], y2 + margin)
    cat = masked.crop((x1, y1, x2, y2))

    cw, ch = cat.size
    scale = min(TARGET / cw, TARGET / ch)
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    resized = cat.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGB", (TARGET, TARGET), bg)
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

    normalize_cell(args.cell_image, record.get("label_bbox"), image_abs)
    print(f"Wrote {image_rel}", file=sys.stderr)

    upsert_logo(record, args.top, args.sub, args.set_num, image_rel)
    print(
        f"Upserted: {args.top}/{args.sub}/{args.set_num}/{record['english_slug']}",
        file=sys.stderr,
    )

    rebuild_shards()


if __name__ == "__main__":
    main()
