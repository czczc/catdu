"""Build the public catalog from the SQLite source of truth.

Emits:
  public/catalog.json               — top-level index (categories + counts)
  public/catalog/<top>/<sub>.json   — per-sub-category shard with full logo records

Run after every DB mutation. The Vue site reads these files; consumers may read
either the top-level index or a specific sub-category shard.
"""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "meowphosis.db"
PUBLIC = ROOT / "public"


def build() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}. Run scripts/init_db.py first.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            tc.slug          AS top_slug,
            tc.display       AS top_display,
            sc.slug          AS sub_slug,
            sc.display       AS sub_display,
            COUNT(l.id)      AS logo_count
        FROM top_category tc
        JOIN sub_category sc ON sc.top_slug = tc.slug
        LEFT JOIN logo_set ls ON ls.sub_category_id = sc.id
        LEFT JOIN logo l ON l.set_id = ls.id
        GROUP BY tc.slug, sc.slug
        ORDER BY tc.slug, sc.slug
        """
    )
    by_top: dict[str, dict] = {}
    for row in cur.fetchall():
        top_slug = row["top_slug"]
        if top_slug not in by_top:
            by_top[top_slug] = {
                "slug": top_slug,
                "display": row["top_display"],
                "sub_categories": [],
            }
        by_top[top_slug]["sub_categories"].append(
            {
                "slug": row["sub_slug"],
                "display": row["sub_display"],
                "logo_count": row["logo_count"],
            }
        )

    catalog = {"categories": list(by_top.values())}
    (PUBLIC / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"Wrote public/catalog.json ({len(catalog['categories'])} top categories)")

    shard_count = 0
    for top in catalog["categories"]:
        for sub in top["sub_categories"]:
            cur.execute(
                """
                SELECT
                    ls.set_number         AS set_number,
                    ls.display            AS set_display,
                    ls.style_description  AS style_description,
                    l.english_name, l.english_slug, l.chinese_name, l.wiki_url,
                    l.iconography, l.summary, l.palette, l.image_path,
                    l.confidence, l.source_cell
                FROM logo l
                JOIN logo_set ls    ON l.set_id = ls.id
                JOIN sub_category sc ON ls.sub_category_id = sc.id
                WHERE sc.top_slug = ? AND sc.slug = ?
                ORDER BY ls.set_number, l.english_slug
                """,
                (top["slug"], sub["slug"]),
            )

            sets_by_number: dict[int, dict] = {}
            for r in cur.fetchall():
                sn = r["set_number"]
                if sn not in sets_by_number:
                    sets_by_number[sn] = {
                        "set_number": sn,
                        "display": r["set_display"],
                        "style_description": r["style_description"],
                        "logos": [],
                    }
                sets_by_number[sn]["logos"].append(
                    {
                        "id": f"{top['slug']}/{sub['slug']}/{sn}/{r['english_slug']}",
                        "english_name": r["english_name"],
                        "english_slug": r["english_slug"],
                        "chinese_name": r["chinese_name"],
                        "wiki_url": r["wiki_url"],
                        "iconography": json.loads(r["iconography"]) if r["iconography"] else [],
                        "summary": r["summary"],
                        "palette": json.loads(r["palette"]) if r["palette"] else [],
                        "image_path": r["image_path"],
                        "confidence": r["confidence"],
                        "source_cell": r["source_cell"],
                    }
                )

            shard = {
                "top": {"slug": top["slug"], "display": top["display"]},
                "sub": {"slug": sub["slug"], "display": sub["display"]},
                "sets": list(sets_by_number.values()),
            }

            shard_path = PUBLIC / "catalog" / top["slug"] / f"{sub['slug']}.json"
            shard_path.parent.mkdir(parents=True, exist_ok=True)
            shard_path.write_text(
                json.dumps(shard, indent=2, ensure_ascii=False) + "\n"
            )
            shard_count += 1
            print(f"Wrote public/catalog/{top['slug']}/{sub['slug']}.json")

    print(f"Built {shard_count} shard(s).")
    conn.close()


if __name__ == "__main__":
    build()
