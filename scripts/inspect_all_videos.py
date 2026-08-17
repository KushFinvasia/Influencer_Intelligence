import sqlite3
import json

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("SELECT id, name, is_relevant FROM creators")
creators = c.fetchall()

has_vids = 0
no_vids = 0

for cr in creators:
    cid = cr[0]
    c.execute("SELECT raw_data FROM platform_profiles WHERE creator_id = ?", (cid,))
    pp = c.fetchone()
    vids = []
    if pp and pp[0]:
        try:
            data = json.loads(pp[0]) if isinstance(pp[0], str) else pp[0]
            vids = data.get("videos", [])
        except Exception:
            pass
    if len(vids) > 0:
        has_vids += 1
    else:
        no_vids += 1

print(f"Total Creators: {len(creators)}")
print(f"Creators with stored video titles in raw_data: {has_vids}")
print(f"Creators with 0 video titles in raw_data: {no_vids}")

conn.close()
