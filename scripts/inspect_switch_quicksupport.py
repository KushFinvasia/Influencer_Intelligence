import sqlite3
import json

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("""
    SELECT c.id, c.name, pp.bio, pp.description, pp.raw_data
    FROM creators c
    LEFT JOIN platform_profiles pp ON pp.creator_id = c.id
    WHERE LOWER(c.name) LIKE '%switch%' OR LOWER(c.name) LIKE '%quick support%'
""")

rows = c.fetchall()
for r in rows:
    cid, name, bio, desc, rd = r
    print(f"\n==========================================")
    print(f"ID #{cid} | Name: '{name}'")
    if rd:
        try:
            data = json.loads(rd) if isinstance(rd, str) else rd
            videos = data.get("videos", [])
            print(f"Total Videos Analyzed: {len(videos)}")
            for v in videos[:10]:
                if isinstance(v, dict):
                    title = v.get("title", "")
                    print(f"  - Video Title: {title.encode('ascii', 'ignore').decode('ascii')}")
        except Exception as e:
            print("  Err reading raw_data:", e)

conn.close()
