"""Crop Zeus from raw/myth-greek.png and write a 200x200 normalized PNG.

Manual one-shot used by the tracer slice (issue #1). The real cropping pipeline
ships in issue #2 (/process-cell) with proper text masking and tight-bbox via
connected components. This script just gets one usable image in place.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "raw" / "myth-greek.png"
OUT = ROOT / "public" / "logos" / "mythology" / "greek" / "1" / "zeus.png"

TARGET = 200


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(SHEET).convert("RGB")
    width, height = img.size

    cols, rows = 6, 12
    cell_w, cell_h = width // cols, height // rows

    # Cell 01 is top-left. Keep the whole cell — text masking + tight-bbox
    # ships in issue #2; the tracer accepts label bleed.
    cell = img.crop((0, 0, cell_w, cell_h))

    # Sample the cream background from a corner pixel (sheet edge is always bg).
    bg = img.getpixel((2, 2))

    # Fit cell into TARGET x TARGET, leaving ~5% margin on the longer side.
    cw, ch = cell.size
    scale = min(TARGET / cw, TARGET / ch) * 0.95
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    resized = cell.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGB", (TARGET, TARGET), bg)
    canvas.paste(resized, ((TARGET - nw) // 2, (TARGET - nh) // 2))
    canvas.save(OUT)
    print(f"Wrote {OUT.relative_to(ROOT)} ({TARGET}x{TARGET}, bg={bg})")


if __name__ == "__main__":
    main()
