"""Local tooling server.

Hosts both the annotation tool (tools/annotate/) and the review tool
(tools/review/), plus the review API endpoints + cache/logo image
serving. Pick a tool from the nav bar.

Run:
    uv run python tools/server.py
    # then open http://localhost:5180/
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
LOCAL = ROOT / "local"
RAW = ROOT / "raw"
PUBLIC = ROOT / "public"
DB_PATH = ROOT / "data" / "meowphosis.db"

app = FastAPI(title="meowphosis tools")


_SKIP_DIRS = {".annotation-cache", "_scratch"}


def _iter_local(pattern: str):
    """Yield files matching `pattern` anywhere under local/, skipping cache
    and scratch dirs. Tolerates both flat (local/<stem>.x.json) and bucketed
    (local/<top>/<stem>.x.json) layouts during the transition."""
    for p in LOCAL.rglob(pattern):
        if _SKIP_DIRS.intersection(p.relative_to(LOCAL).parts):
            continue
        yield p


def _find_local(stem: str, suffix: str) -> Path:
    matches = list(_iter_local(f"{stem}{suffix}"))
    if not matches:
        raise HTTPException(404, f"{suffix} not found: {stem}")
    if len(matches) > 1:
        raise HTTPException(
            409, f"ambiguous stem {stem!r}: {[str(m.relative_to(LOCAL)) for m in matches]}"
        )
    return matches[0]


def _records_path(stem: str) -> Path:
    return _find_local(stem, ".records.json")


def _annotations_path(stem: str) -> Path:
    return _find_local(stem, ".annotations.json")


def _atomic_write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _composite_url(sheet_filename: str, cell_number: int) -> str:
    stem = Path(sheet_filename).stem
    return f"/cache/{stem}/cell-{cell_number:03d}.png"


def _logo_url(top: str, sub: str, set_number: int, slug: str) -> str:
    return f"/logos/{top}/{sub}/{set_number}/{slug}.png"


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/review/")


@app.get("/api/sheets")
def list_sheets() -> list[dict]:
    out = []
    for records_p in sorted(_iter_local("*.records.json")):
        stem = records_p.name.removesuffix(".records.json")
        annot_p = records_p.with_name(f"{stem}.annotations.json")
        if not annot_p.exists():
            continue
        try:
            annot = json.loads(annot_p.read_text(encoding="utf-8"))
            rec = json.loads(records_p.read_text(encoding="utf-8"))
        except Exception as e:
            out.append({"stem": stem, "error": str(e)})
            continue
        flagged = sum(
            1
            for c in rec.get("cells", [])
            if (c.get("confidence") or 0) < 0.7
            or not c.get("wiki_url")
            or (c.get("english_slug") or "").startswith("unknown-")
        )
        out.append(
            {
                "stem": stem,
                "top_category": annot.get("top_category"),
                "sub_category": annot.get("sub_category"),
                "set_number": annot.get("set_number"),
                "sheet_filename": annot.get("sheet_filename"),
                "cells_total": len(rec.get("cells", [])),
                "cells_flagged": flagged,
            }
        )
    return out


@app.get("/api/sheets/{stem}")
def get_sheet(stem: str) -> dict:
    records = json.loads(_records_path(stem).read_text(encoding="utf-8"))
    annot = json.loads(_annotations_path(stem).read_text(encoding="utf-8"))
    sheet_filename = annot["sheet_filename"]
    top = annot["top_category"]
    sub = annot["sub_category"]
    set_number = int(annot["set_number"])

    cells = []
    for r in records.get("cells", []):
        n = int(r["cell_number"])
        slug = r.get("english_slug") or ""
        cells.append(
            {
                **r,
                "composite_url": _composite_url(sheet_filename, n),
                "logo_url": _logo_url(top, sub, set_number, slug) if slug else None,
            }
        )
    cells.sort(key=lambda c: c["cell_number"])

    return {
        "stem": stem,
        "top_category": top,
        "sub_category": sub,
        "set_number": set_number,
        "sheet_filename": sheet_filename,
        "cells": cells,
    }


class CellUpdate(BaseModel):
    chinese_name: str | None = None
    english_name: str | None = None
    english_slug: str | None = None
    wiki_url: str | None = None
    iconography: list[str] = Field(default_factory=list)
    summary: str | None = None
    confidence: float = 1.0


@app.put("/api/sheets/{stem}/cells/{cell_number}")
def update_cell(stem: str, cell_number: int, payload: CellUpdate) -> dict:
    p = _records_path(stem)
    records = json.loads(p.read_text(encoding="utf-8"))
    cells = records.get("cells", [])
    for i, c in enumerate(cells):
        if int(c["cell_number"]) == cell_number:
            cells[i] = {
                "cell_number": cell_number,
                "chinese_name": payload.chinese_name,
                "english_name": payload.english_name,
                "english_slug": payload.english_slug,
                "wiki_url": payload.wiki_url,
                "iconography": payload.iconography,
                "summary": payload.summary,
                "confidence": payload.confidence,
            }
            break
    else:
        raise HTTPException(404, f"cell {cell_number} not in {stem}")
    _atomic_write_json(p, records)
    return {"ok": True}


@app.delete("/api/sheets/{stem}/cells/{cell_number}")
def delete_cell(stem: str, cell_number: int) -> dict:
    p = _records_path(stem)
    records = json.loads(p.read_text(encoding="utf-8"))
    before = len(records.get("cells", []))
    records["cells"] = [
        c for c in records.get("cells", []) if int(c["cell_number"]) != cell_number
    ]
    if len(records["cells"]) == before:
        raise HTTPException(404, f"cell {cell_number} not in {stem}")
    _atomic_write_json(p, records)

    ann_p = _annotations_path(stem)
    annot = json.loads(ann_p.read_text(encoding="utf-8"))
    cells = annot.setdefault("cells", [])
    for c in cells:
        if int(c["cell_number"]) == cell_number:
            c["skip"] = True
            break
    else:
        cells.append({"cell_number": cell_number, "skip": True})
    _atomic_write_json(ann_p, annot)

    return {"ok": True}


def _gc_orphan_logos(stem: str) -> list[str]:
    annot = json.loads(_annotations_path(stem).read_text(encoding="utf-8"))
    records = json.loads(_records_path(stem).read_text(encoding="utf-8"))
    top = annot["top_category"]
    sub = annot["sub_category"]
    set_number = int(annot["set_number"])
    wanted = {
        r.get("english_slug") for r in records.get("cells", []) if r.get("english_slug")
    }

    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT logo.id, logo.english_slug
          FROM logo
          JOIN logo_set ON logo.set_id = logo_set.id
          JOIN sub_category ON logo_set.sub_category_id = sub_category.id
         WHERE sub_category.top_slug = ?
           AND sub_category.slug = ?
           AND logo_set.set_number = ?
        """,
        (top, sub, set_number),
    )
    removed: list[str] = []
    for logo_id, slug in cur.fetchall():
        if slug in wanted:
            continue
        cur.execute("DELETE FROM logo WHERE id = ?", (logo_id,))
        png = PUBLIC / "logos" / top / sub / str(set_number) / f"{slug}.png"
        if png.exists():
            png.unlink()
        removed.append(slug)
    conn.commit()
    conn.close()
    return removed


@app.post("/api/sheets/{stem}/apply")
def apply_sheet(stem: str) -> JSONResponse:
    annot_p = _annotations_path(stem)
    rec_p = _records_path(stem)

    removed = _gc_orphan_logos(stem)

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/finalize_annotations.py",
            str(annot_p.relative_to(ROOT)),
            str(rec_p.relative_to(ROOT)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    upscale = None
    if result.returncode == 0:
        upscale = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/upscale_logos.py",
                "--in-place",
                "--scale",
                "2",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    return JSONResponse(
        {
            "ok": result.returncode == 0
            and (upscale is None or upscale.returncode == 0),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "upscale_stdout": upscale.stdout if upscale else None,
            "upscale_stderr": upscale.stderr if upscale else None,
            "gc_removed": removed,
        }
    )


@app.get("/api/annotations")
def list_annotations() -> list[dict]:
    out = []
    for p in sorted(_iter_local("*.annotations.json")):
        stem = p.name.removesuffix(".annotations.json")
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            out.append({"stem": stem, "error": str(e)})
            continue
        sheet = d.get("sheet_filename") or ""
        sheet_exists = (RAW / sheet).exists() if sheet else False
        out.append(
            {
                "stem": stem,
                "top_category": d.get("top_category"),
                "sub_category": d.get("sub_category"),
                "set_number": d.get("set_number"),
                "sheet_filename": sheet,
                "sheet_exists": sheet_exists,
                "cells_total": len(d.get("cells", [])),
                "rows": (d.get("grid") or {}).get("rows"),
                "cols": (d.get("grid") or {}).get("cols"),
            }
        )
    return out


@app.get("/api/annotations/{stem}")
def get_annotations(stem: str) -> JSONResponse:
    p = _annotations_path(stem)
    return JSONResponse(json.loads(p.read_text(encoding="utf-8")))


_BUCKET_SAFE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_UNCATEGORIZED = "_uncategorized"


def _bucket_for(top_category: str | None) -> str:
    """Return the top-level subdirectory under local/ for a sheet whose
    annotations declare `top_category`. Blank/invalid → `_uncategorized/`
    so it's obviously unfinished. Categories are kept lowercase + kebab."""
    if not top_category:
        return _UNCATEGORIZED
    norm = top_category.strip().lower()
    if not _BUCKET_SAFE.fullmatch(norm):
        return _UNCATEGORIZED
    return norm


@app.post("/api/annotations/save")
def save_annotations(payload: dict) -> dict:
    """Persist an annotations JSON, bucketing by `top_category`. Stem is
    derived from `sheet_filename`. If a same-stem file already exists in
    another bucket (e.g. the user renamed the category), move it so we
    never end up with two copies."""
    stem_source = payload.get("sheet_filename") or ""
    stem = Path(stem_source).stem
    if not stem:
        raise HTTPException(400, "missing sheet_filename in payload")
    bucket = _bucket_for(payload.get("top_category"))
    target_dir = LOCAL / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{stem}.annotations.json"

    # If a same-stem annotations file lives elsewhere (different bucket or
    # legacy flat path), relocate so we keep one file per sheet.
    for existing in _iter_local(f"{stem}.annotations.json"):
        if existing.resolve() != target.resolve():
            existing.unlink()
    # Same for the records sidecar.
    for existing in _iter_local(f"{stem}.records.json"):
        new_records = target_dir / existing.name
        if existing.resolve() != new_records.resolve():
            existing.replace(new_records)

    _atomic_write_json(target, payload)
    return {
        "ok": True,
        "path": str(target.relative_to(ROOT)),
        "bucket": bucket,
    }


@app.get("/api/visibility")
def list_visibility() -> dict:
    if not DB_PATH.exists():
        raise HTTPException(404, "db not initialized")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tc.slug AS top_slug, tc.display AS top_display, tc.hidden AS top_hidden,
               sc.slug AS sub_slug, sc.display AS sub_display, sc.hidden AS sub_hidden,
               COUNT(l.id) AS logo_count
          FROM top_category tc
          LEFT JOIN sub_category sc ON sc.top_slug = tc.slug
          LEFT JOIN logo_set ls ON ls.sub_category_id = sc.id
          LEFT JOIN logo l ON l.set_id = ls.id
         GROUP BY tc.slug, sc.slug
         ORDER BY tc.slug, sc.slug
        """
    )
    tops: dict[str, dict] = {}
    for row in cur.fetchall():
        slug = row["top_slug"]
        if slug not in tops:
            tops[slug] = {
                "slug": slug,
                "display": row["top_display"],
                "hidden": bool(row["top_hidden"]),
                "sub_categories": [],
            }
        if row["sub_slug"] is not None:
            tops[slug]["sub_categories"].append(
                {
                    "slug": row["sub_slug"],
                    "display": row["sub_display"],
                    "hidden": bool(row["sub_hidden"]),
                    "logo_count": row["logo_count"],
                }
            )
    conn.close()
    return {"categories": list(tops.values())}


class VisibilityToggle(BaseModel):
    scope: str  # "top" or "sub"
    top: str
    sub: str | None = None
    hidden: bool


@app.post("/api/visibility/toggle")
def toggle_visibility(payload: VisibilityToggle) -> JSONResponse:
    if not DB_PATH.exists():
        raise HTTPException(404, "db not initialized")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    hidden = 1 if payload.hidden else 0
    if payload.scope == "top":
        cur.execute("SELECT slug FROM top_category WHERE slug = ?", (payload.top,))
        if not cur.fetchone():
            conn.close()
            raise HTTPException(404, f"no top category: {payload.top}")
        cur.execute(
            "UPDATE top_category SET hidden = ? WHERE slug = ?", (hidden, payload.top)
        )
    elif payload.scope == "sub":
        if not payload.sub:
            conn.close()
            raise HTTPException(400, "sub required when scope=sub")
        cur.execute(
            "SELECT id FROM sub_category WHERE top_slug = ? AND slug = ?",
            (payload.top, payload.sub),
        )
        if not cur.fetchone():
            conn.close()
            raise HTTPException(404, f"no sub: {payload.top}/{payload.sub}")
        cur.execute(
            "UPDATE sub_category SET hidden = ? WHERE top_slug = ? AND slug = ?",
            (hidden, payload.top, payload.sub),
        )
    else:
        conn.close()
        raise HTTPException(400, f"bad scope: {payload.scope}")
    conn.commit()
    conn.close()

    result = subprocess.run(
        ["uv", "run", "python", "scripts/build_manifest.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return JSONResponse(
        {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )


@app.get("/raw/{name}")
def serve_raw(name: str) -> FileResponse:
    if "/" in name or ".." in name:
        raise HTTPException(400, "bad name")
    p = RAW / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/cache/{sheet_stem}/{name}")
def serve_cache(sheet_stem: str, name: str) -> FileResponse:
    if not re.fullmatch(r"cell-\d{3}\.png", name):
        raise HTTPException(400, "bad name")
    if "/" in sheet_stem or ".." in sheet_stem:
        raise HTTPException(400, "bad stem")
    p = LOCAL / ".annotation-cache" / sheet_stem / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/logos/{top}/{sub}/{set_n}/{name}")
def serve_logo(top: str, sub: str, set_n: str, name: str) -> FileResponse:
    for part in (top, sub, set_n, name):
        if "/" in part or ".." in part:
            raise HTTPException(400, "bad path")
    p = PUBLIC / "logos" / top / sub / set_n / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


app.mount(
    "/annotate", StaticFiles(directory=str(TOOLS / "annotate"), html=True), name="annotate"
)
app.mount(
    "/review", StaticFiles(directory=str(TOOLS / "review"), html=True), name="review"
)
app.mount(
    "/visibility",
    StaticFiles(directory=str(TOOLS / "visibility"), html=True),
    name="visibility",
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5180"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
