#!/usr/bin/env python3
"""Upscale public/logos/**/*.png with realesrgan-ncnn-vulkan (anime model).

Modes:
  --sample N      pick N random logos, write upscaled + orig side-by-side into
                  local/upscale-samples/ for quality evaluation. Originals untouched.
  --in-place      overwrite every PNG under public/logos/ with its upscaled version.
                  Run only after you're happy with --sample results.

Backups of the original 200x200 PNGs live at local/logos-200-backup/.
"""
import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

TARGET_PX = {2: 400, 3: 600, 4: 800}

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "tools/realesrgan/realesrgan-ncnn-vulkan"
MODEL_DIR = ROOT / "tools/realesrgan/models"
MODEL_NAME = "realesrgan-x4plus-anime"  # fixed 4x anime model
LOGOS_DIR = ROOT / "public/logos"
SAMPLE_DIR = ROOT / "local/upscale-samples"


def upscale(src: Path, dst: Path, scale: int) -> None:
    """Run anime model at native 4x, then Lanczos-resize to the requested scale."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [str(BIN), "-i", str(src), "-o", str(tmp_path),
             "-n", MODEL_NAME, "-s", "4", "-m", str(MODEL_DIR)],
            check=True, stderr=subprocess.DEVNULL,
        )
        if scale == 4:
            shutil.move(tmp_path, dst)
        else:
            with Image.open(tmp_path) as img:
                w, h = img.size
                target = (w * scale // 4, h * scale // 4)
                img.resize(target, Image.LANCZOS).save(dst, format="PNG")
    finally:
        tmp_path.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sample", type=int, metavar="N", help="upscale N random logos into local/upscale-samples/ for review")
    g.add_argument("--in-place", action="store_true", help="overwrite all logos under public/logos/")
    ap.add_argument("--scale", type=int, default=4, choices=[2, 3, 4])
    args = ap.parse_args()

    if not BIN.exists():
        sys.exit(f"binary not found at {BIN}")

    logos = sorted(LOGOS_DIR.rglob("*.png"))
    if not logos:
        sys.exit(f"no logos under {LOGOS_DIR}")

    if args.sample:
        random.seed(0)
        picked = random.sample(logos, min(args.sample, len(logos)))
        SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        for src in picked:
            rel = src.relative_to(LOGOS_DIR)
            stem = rel.with_suffix("").as_posix().replace("/", "_")
            orig_dst = SAMPLE_DIR / f"{stem}__orig.png"
            up_dst = SAMPLE_DIR / f"{stem}__x{args.scale}.png"
            shutil.copyfile(src, orig_dst)
            print(f"  {rel}  →  x{args.scale}")
            upscale(src, up_dst, args.scale)
        print(f"\nSamples in {SAMPLE_DIR.relative_to(ROOT)}/")
        return

    target = TARGET_PX[args.scale]
    total = len(logos)
    processed = skipped = 0
    for i, src in enumerate(logos, 1):
        rel = src.relative_to(LOGOS_DIR)
        with Image.open(src) as img:
            w, _ = img.size
        if w >= target:
            skipped += 1
            print(f"[{i}/{total}] skip {rel} (already {w}px)", flush=True)
            continue
        print(f"[{i}/{total}] {rel}", flush=True)
        tmp = src.with_suffix(".png.tmp")
        try:
            upscale(src, tmp, args.scale)
            os.replace(tmp, src)
            processed += 1
        finally:
            if tmp.exists():
                tmp.unlink()
    print(f"\nDone. processed={processed} skipped={skipped} total={total}")


if __name__ == "__main__":
    main()
