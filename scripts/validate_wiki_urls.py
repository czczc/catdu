"""Validate (and backfill) wiki_url for each cell in a records.json.

Many catalog entries — especially game characters — have a richer wiki at
a franchise-specific URL than at Wikipedia (e.g. wiki.leagueoflegends.com
beats en.wikipedia.org for LoL champions). When a category-specific pattern
is registered, it becomes the preferred source; Wikipedia is the fallback.

Candidate order per cell:
  1. Category-specific URL patterns from CATEGORY_WIKI_PATTERNS, if any
     are registered for the annotations' (top_category, sub_category).
  2. https://en.wikipedia.org/wiki/<english_name>.
  3. The records' existing wiki_url, if any — last resort, so manual
     overrides via the review UI still survive if every pattern 404s.

HEAD each candidate; set wiki_url to the first that returns 200,
otherwise null. Idempotent — safe to re-run any time.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote

import httpx

USER_AGENT = "meowphosis/0.1 (chao.zh@gmail.com)"

# (top_category, sub_category) -> list of URL templates.
# Templates use {name} = english_name with spaces replaced by '_',
# url-encoded except for a small safe-set so existing punctuation
# like apostrophes survives.
CATEGORY_WIKI_PATTERNS: dict[tuple[str, str], list[str]] = {
    ("game", "league-of-legends"): [
        "https://wiki.leagueoflegends.com/en-us/{name}",
    ],
    # Add more game/franchise wikis as needed:
    # ("game", "arknight"): ["https://arknights.fandom.com/wiki/{name}"],
}


def _encode_name(english_name: str) -> str:
    """Replace spaces with underscores and URL-encode, preserving a small
    set of characters commonly used in character names ("()'&_)."""
    return quote(english_name.replace(" ", "_"), safe="_'()&")


def candidate_urls(
    english_name: str, top: str, sub: str, existing: str | None
) -> list[str]:
    out: list[str] = []
    encoded = _encode_name(english_name)
    for tmpl in CATEGORY_WIKI_PATTERNS.get((top, sub), []):
        url = tmpl.format(name=encoded)
        if url not in out:
            out.append(url)
    wiki = f"https://en.wikipedia.org/wiki/{encoded}"
    if wiki not in out:
        out.append(wiki)
    if existing and existing not in out:
        out.append(existing)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("annotations", type=Path)
    ap.add_argument("records", type=Path)
    args = ap.parse_args()

    annot = json.loads(args.annotations.read_text(encoding="utf-8"))
    top = annot["top_category"]
    sub = annot["sub_category"]
    data = json.loads(args.records.read_text(encoding="utf-8"))

    changed = 0
    flagged: list[tuple[int, str, str]] = []  # (n, name, outcome)

    with httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as h:
        for cell in data["cells"]:
            english_name = cell.get("english_name") or ""
            if not english_name or english_name.lower().startswith("unknown"):
                if cell.get("wiki_url") is not None:
                    cell["wiki_url"] = None
                    changed += 1
                continue
            urls = candidate_urls(english_name, top, sub, cell.get("wiki_url"))
            picked = None
            for url in urls:
                try:
                    r = h.head(url)
                    if r.status_code == 200:
                        picked = url
                        break
                except Exception:
                    continue
            if picked != cell.get("wiki_url"):
                changed += 1
            if picked is None:
                flagged.append((int(cell["cell_number"]), english_name, "no match"))
            elif picked != urls[0]:
                # Picked something other than the prior wiki_url (or backfilled
                # a previously-null entry).
                flagged.append(
                    (int(cell["cell_number"]), english_name, f"-> {picked}")
                )
            cell["wiki_url"] = picked

    args.records.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"records: {args.records}")
    print(f"taxonomy: {top}/{sub}")
    print(f"changed: {changed}")
    for n, name, outcome in flagged:
        print(f"  cell {n:03d} {name}: {outcome}")


if __name__ == "__main__":
    main()
