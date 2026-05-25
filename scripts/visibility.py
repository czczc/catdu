"""Toggle visibility of top/sub categories without deleting them.

Hidden categories stay in the DB but are excluded from the public catalog
(catalog.json + per-sub shards). Use this to stage categories that aren't
ready to ship publicly yet.

Usage:
    uv run python scripts/visibility.py list
    uv run python scripts/visibility.py hide <top>
    uv run python scripts/visibility.py hide <top>/<sub>
    uv run python scripts/visibility.py show <top>
    uv run python scripts/visibility.py show <top>/<sub>

After a toggle, the catalog is rebuilt automatically.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "meowphosis.db"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit(f"DB not found: {DB_PATH}. Run scripts/init_db.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def cmd_list() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tc.slug, tc.display, tc.hidden,
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
    current_top = None
    for row in cur.fetchall():
        if row["slug"] != current_top:
            current_top = row["slug"]
            mark = "HIDDEN " if row["hidden"] else "       "
            print(f"{mark}{row['slug']:<14} {row['display']}")
        if row["sub_slug"] is None:
            continue
        sub_mark = "HIDDEN " if row["sub_hidden"] else "       "
        print(
            f"  {sub_mark}{row['sub_slug']:<24} {row['sub_display']:<24}"
            f" ({row['logo_count']} cats)"
        )
    conn.close()


def _set_hidden(target: str, hidden: int) -> None:
    parts = target.split("/", 1)
    top = parts[0]
    sub = parts[1] if len(parts) == 2 else None

    conn = _connect()
    cur = conn.cursor()

    if sub is None:
        cur.execute("SELECT slug FROM top_category WHERE slug = ?", (top,))
        if not cur.fetchone():
            sys.exit(f"no top category: {top}")
        cur.execute("UPDATE top_category SET hidden = ? WHERE slug = ?", (hidden, top))
        print(f"{'Hid' if hidden else 'Showed'} top category: {top}")
    else:
        cur.execute(
            "SELECT id FROM sub_category WHERE top_slug = ? AND slug = ?", (top, sub)
        )
        if not cur.fetchone():
            sys.exit(f"no sub category: {top}/{sub}")
        cur.execute(
            "UPDATE sub_category SET hidden = ? WHERE top_slug = ? AND slug = ?",
            (hidden, top, sub),
        )
        print(f"{'Hid' if hidden else 'Showed'} sub category: {top}/{sub}")

    conn.commit()
    conn.close()

    print("Rebuilding catalog…")
    subprocess.run(
        ["uv", "run", "python", "scripts/build_manifest.py"], cwd=ROOT, check=True
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show all categories with their hidden flag")
    p_hide = sub.add_parser("hide", help="hide a top or sub category")
    p_hide.add_argument("target", help="<top> or <top>/<sub>")
    p_show = sub.add_parser("show", help="unhide a top or sub category")
    p_show.add_argument("target", help="<top> or <top>/<sub>")

    args = parser.parse_args()
    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "hide":
        _set_hidden(args.target, 1)
    elif args.cmd == "show":
        _set_hidden(args.target, 0)


if __name__ == "__main__":
    main()
