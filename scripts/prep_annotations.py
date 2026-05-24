"""Prep step for the /process-annotations skill.

Reads an annotations.json (produced by tools/annotate/) and renders each cell
as a two-tile composite — cat crop on top, text crop below — letterboxed onto
a consistent cream canvas. The composite gives the LLM a tightly framed view
of the cat AND the label, regardless of original bbox dimensions.

When a cell lacks `cat_bbox` or `text_bbox`, falls back to the whole-cell
crop for the missing tile so the LLM still sees something useful.

Cells flagged `skip: true` are omitted; otherwise every cell in the rows×cols
grid is rendered.

Outputs a JSON manifest to stdout — the skill iterates this and Reads each
composite.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
CACHE_BASE = ROOT / "local" / ".annotation-cache"
BG_COLOR = (0xFE, 0xFC, 0xF7)

CAT_TILE = 320
TEXT_TILE_W = 320
TEXT_TILE_H = 96
GAP = 12


def letterbox(crop: Image.Image, target_w: int, target_h: int) -> Image.Image:
    cw, ch = crop.size
    if cw == 0 or ch == 0:
        return Image.new("RGB", (target_w, target_h), BG_COLOR)
    scale = min(target_w / cw, target_h / ch)
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    resized = crop.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), BG_COLOR)
    canvas.paste(resized, ((target_w - nw) // 2, (target_h - nh) // 2))
    return canvas


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


def composite_for_cell(
    sheet: Image.Image,
    cell_bounds: tuple[int, int, int, int],
    cat_bbox: list[int] | None,
    text_bbox: list[int] | None,
) -> Image.Image:
    width = max(CAT_TILE, TEXT_TILE_W)
    height = CAT_TILE + GAP + TEXT_TILE_H
    canvas = Image.new("RGB", (width, height), BG_COLOR)

    cat_crop = sheet.crop(tuple(int(v) for v in cat_bbox)) if cat_bbox else sheet.crop(cell_bounds)
    cat_tile = letterbox(cat_crop, CAT_TILE, CAT_TILE)
    canvas.paste(cat_tile, ((width - CAT_TILE) // 2, 0))

    if text_bbox:
        text_crop = sheet.crop(tuple(int(v) for v in text_bbox))
    else:
        text_crop = sheet.crop(cell_bounds)
    text_tile = letterbox(text_crop, TEXT_TILE_W, TEXT_TILE_H)
    canvas.paste(text_tile, ((width - TEXT_TILE_W) // 2, CAT_TILE + GAP))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("annotations", type=Path, help="Path to annotations.json")
    args = ap.parse_args()

    data = json.loads(args.annotations.read_text(encoding="utf-8"))
    sheet_filename = data["sheet_filename"]
    sheet_path = RAW / sheet_filename
    if not sheet_path.exists():
        raise SystemExit(f"Sheet not found at raw/{sheet_filename}")

    sheet = Image.open(sheet_path).convert("RGB")
    cache_dir = CACHE_BASE / Path(sheet_filename).stem
    cache_dir.mkdir(parents=True, exist_ok=True)

    for old in cache_dir.glob("cell-*.png"):
        old.unlink()

    grid = data["grid"]
    rows = int(grid["rows"])
    cols = int(grid["cols"])
    overrides = {int(c["cell_number"]): c for c in data.get("cells", [])}

    manifest_cells = []
    for n in range(1, rows * cols + 1):
        ov = overrides.get(n, {})
        if ov.get("skip"):
            continue
        bounds = cell_bounds_from_grid(grid, n)
        composite = composite_for_cell(
            sheet,
            bounds,
            ov.get("cat_bbox"),
            ov.get("text_bbox"),
        )
        out_path = cache_dir / f"cell-{n:03d}.png"
        composite.save(out_path)
        entry = {
            "cell_number": n,
            "composite": str(out_path.relative_to(ROOT)),
        }
        if ov.get("english_override"):
            entry["english_override"] = ov["english_override"]
        manifest_cells.append(entry)

    manifest = {
        "annotations_path": str(
            args.annotations.resolve().relative_to(ROOT)
            if args.annotations.is_absolute() and ROOT in args.annotations.resolve().parents
            else args.annotations
        ),
        "sheet_filename": sheet_filename,
        "top_category": data["top_category"],
        "sub_category": data["sub_category"],
        "set_number": data["set_number"],
        "cache_dir": str(cache_dir.relative_to(ROOT)),
        "cells": manifest_cells,
    }
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
