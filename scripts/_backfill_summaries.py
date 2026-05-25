"""One-off: inject `summary` into each cell of a records.json by slug.

Usage:
    uv run python scripts/_backfill_summaries.py <records.json> <map.json>

The map JSON is `{slug: summary_text}`. Missing slugs are reported.
Safe to re-run; existing summaries are overwritten only when the map has a value.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("records", type=Path)
    ap.add_argument("summaries", type=Path)
    args = ap.parse_args()

    data = json.loads(args.records.read_text(encoding="utf-8"))
    summaries: dict[str, str] = json.loads(args.summaries.read_text(encoding="utf-8"))

    have = {c["english_slug"] for c in data["cells"]}
    missing_in_map = sorted(have - set(summaries))
    extra_in_map = sorted(set(summaries) - have)

    n_updated = 0
    for c in data["cells"]:
        s = summaries.get(c["english_slug"])
        if s:
            c["summary"] = s
            n_updated += 1

    args.records.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"updated {n_updated}/{len(data['cells'])} cells in {args.records.name}")
    if missing_in_map:
        print(f"  no summary for {len(missing_in_map)} slugs: {missing_in_map}")
    if extra_in_map:
        print(f"  unused entries in map: {extra_in_map}")


if __name__ == "__main__":
    main()
