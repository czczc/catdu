"""Initialize the SQLite catalog and seed the tracer Zeus row.

Idempotent: safe to re-run. The schema follows ADR-0002 (SQLite source of truth +
derived JSON shards). The `set` concept lives in the `logo_set` table — `set` is a
reserved word in standard SQL, so the table is named `logo_set` while the domain
term stays "set".
"""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "catalog.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS top_category (
    slug TEXT PRIMARY KEY,
    display TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sub_category (
    id INTEGER PRIMARY KEY,
    top_slug TEXT NOT NULL REFERENCES top_category(slug),
    slug TEXT NOT NULL,
    display TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    UNIQUE (top_slug, slug)
);

CREATE TABLE IF NOT EXISTS logo_set (
    id INTEGER PRIMARY KEY,
    sub_category_id INTEGER NOT NULL REFERENCES sub_category(id),
    set_number INTEGER NOT NULL,
    display TEXT NOT NULL,
    style_description TEXT,
    generator TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (sub_category_id, set_number)
);

CREATE TABLE IF NOT EXISTS logo (
    id INTEGER PRIMARY KEY,
    set_id INTEGER NOT NULL REFERENCES logo_set(id),
    english_name TEXT NOT NULL,
    english_slug TEXT NOT NULL,
    chinese_name TEXT,
    wiki_url TEXT,
    iconography TEXT,
    summary TEXT,
    palette TEXT,
    image_path TEXT NOT NULL,
    source_sheet TEXT,
    source_cell INTEGER,
    confidence REAL,
    image_fingerprint TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (set_id, english_slug)
);

CREATE INDEX IF NOT EXISTS idx_logo_english_name ON logo(english_name);
CREATE INDEX IF NOT EXISTS idx_logo_set_id ON logo(set_id);
"""


def init() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    cur = conn.cursor()

    for table in ("top_category", "sub_category"):
        cols = {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        if "hidden" not in cols:
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0"
            )

    cur.execute(
        "INSERT OR IGNORE INTO top_category (slug, display) VALUES (?, ?)",
        ("mythology", "Mythology"),
    )
    cur.execute(
        "INSERT OR IGNORE INTO sub_category (top_slug, slug, display) VALUES (?, ?, ?)",
        ("mythology", "greek", "Greek"),
    )
    cur.execute(
        "SELECT id FROM sub_category WHERE top_slug = ? AND slug = ?",
        ("mythology", "greek"),
    )
    sub_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT OR IGNORE INTO logo_set
            (sub_category_id, set_number, display, style_description)
        VALUES (?, ?, ?, ?)
        """,
        (
            sub_id,
            1,
            "Chibi Watercolor",
            "Soft watercolor chibi cats with thematic accessories on a cream background",
        ),
    )
    cur.execute(
        "SELECT id FROM logo_set WHERE sub_category_id = ? AND set_number = ?",
        (sub_id, 1),
    )
    set_id = cur.fetchone()[0]

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
            "Zeus",
            "zeus",
            "宙斯",
            "https://en.wikipedia.org/wiki/Zeus",
            json.dumps(["lightning bolt", "scepter"]),
            "logos/mythology/greek/1/zeus.png",
            "myth-greek.png",
            1,
            1.0,
        ),
    )

    conn.commit()
    conn.close()
    print(f"Initialized {DB_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    init()
