import sqlite3
import json

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("SELECT id, name, is_relevant, relevance_confidence, primary_category, primary_language FROM creators WHERE LOWER(name) LIKE '%raj shamani%' OR LOWER(name) LIKE '%josh talk%' OR LOWER(name) LIKE '%beerbiceps%' OR LOWER(name) LIKE '%ranveer%'")
rows = c.fetchall()

print(f"Found {len(rows)} matching creators in DB:")
for r in rows:
    cid, name, rel, rel_conf, cat, lang = r
    print(f"\nID: {cid} | Name: '{name}'")
    print(f"  is_relevant: {rel} | relevance_confidence: {rel_conf}")
    print(f"  primary_category: {cat} | primary_language: {lang}")

    # Check platform profile text & recent videos
    c.execute("SELECT bio, description, raw_data FROM platform_profiles WHERE creator_id = ?", (cid,))
    pp = c.fetchone()
    if pp:
        bio, desc, rd = pp
        print(f"  Bio: {bio[:150] if bio else 'None'}")
        print(f"  Desc: {desc[:200] if desc else 'None'}")
        if rd:
            try:
                data = json.loads(rd) if isinstance(rd, str) else rd
                vids = data.get("videos", [])
                print(f"  Video Count in raw_data: {len(vids)}")
                for v in vids[:5]:
                    if isinstance(v, dict):
                        print(f"    - Video Title: {v.get('title')}")
            except Exception as e:
                print("  Err reading raw_data:", e)

conn.close()
