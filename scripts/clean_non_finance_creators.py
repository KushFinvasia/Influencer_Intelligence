"""Clean non-finance and mainstream media channels from SQLite database."""

import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "creator_intel.db"
EXCLUSIONS_PATH = PROJECT_ROOT / "app" / "config" / "exclusions.json"


def clean_db():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    with open(EXCLUSIONS_PATH, "r", encoding="utf-8") as f:
        exclusions_config = json.load(f)

    excluded_patterns = [
        p.lower().strip() for p in exclusions_config.get("excluded_channel_patterns", [])
    ]
    fin_keywords = [
        k.lower().strip() for k in exclusions_config.get("financial_keywords", [])
    ]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    creators = c.execute("SELECT id, name, primary_category FROM creators").fetchall()
    deleted_count = 0

    print(f"Inspecting {len(creators)} creators in database...")

    for creator in creators:
        cid = creator["id"]
        name = (creator["name"] or "").lower().strip()
        category = (creator["primary_category"] or "").lower().strip()

        should_delete = False
        delete_reason = ""

        # 1. Pattern blacklist check
        for pat in excluded_patterns:
            if pat in name:
                should_delete = True
                delete_reason = f"Matched blacklisted pattern '{pat}'"
                break

        # 2. Content relevance check
        if not should_delete:
            profiles = c.execute(
                "SELECT id, bio, description FROM platform_profiles WHERE creator_id = ?",
                (cid,),
            ).fetchall()

            all_text = name
            for p in profiles:
                pid = p["id"]
                bio = (p["bio"] or "")
                desc = (p["description"] or "")
                all_text += f" {bio} {desc}"
                
                video_rows = c.execute(
                    "SELECT title, description FROM videos WHERE platform_profile_id = ?",
                    (pid,),
                ).fetchall()
                for v in video_rows:
                    all_text += f" {v['title'] or ''} {v['description'] or ''}"

            all_text = all_text.lower()
            has_fin = any(kw in all_text for kw in fin_keywords)
            brokers_count = c.execute(
                "SELECT COUNT(*) FROM broker_associations WHERE creator_id = ?", (cid,)
            ).fetchone()[0]

            # If no brokers, no financial keywords anywhere, and no valid finance category
            if not has_fin and brokers_count == 0 and category not in ("f&o", "equity", "ipo", "mutual funds", "personal finance", "crypto", "intraday"):
                should_delete = True
                delete_reason = "No financial keywords, broker associations, or finance category"

        if should_delete:
            print(f"[-] Deleting Creator ID {cid} ('{creator['name']}'): {delete_reason}")
            # Get profile ids to delete videos/posts
            profile_ids = [p[0] for p in c.execute("SELECT id FROM platform_profiles WHERE creator_id = ?", (cid,)).fetchall()]
            for pid in profile_ids:
                c.execute("DELETE FROM videos WHERE platform_profile_id = ?", (pid,))
                c.execute("DELETE FROM posts WHERE platform_profile_id = ?", (pid,))
                c.execute("DELETE FROM engagement_metrics WHERE platform_profile_id = ?", (pid,))
            
            c.execute("DELETE FROM platform_profiles WHERE creator_id = ?", (cid,))
            c.execute("DELETE FROM social_links WHERE creator_id = ?", (cid,))
            c.execute("DELETE FROM broker_associations WHERE creator_id = ?", (cid,))
            c.execute("DELETE FROM creator_categories WHERE creator_id = ?", (cid,))
            c.execute("DELETE FROM creator_relationships WHERE source_creator_id = ? OR target_creator_id = ?", (cid, cid))
            c.execute("DELETE FROM creators WHERE id = ?", (cid,))
            deleted_count += 1

    conn.commit()
    conn.close()

    print(f"\n[OK] Successfully purged {deleted_count} non-financial channels from database!")


if __name__ == "__main__":
    clean_db()
