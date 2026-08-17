import sqlite3

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("""
    SELECT c.id, c.name, pp.username, pp.bio, pp.description
    FROM creators c
    LEFT JOIN platform_profiles pp ON pp.creator_id = c.id
    WHERE LOWER(c.name) LIKE '%talks%'
       OR LOWER(c.name) LIKE '%जोश%'
       OR LOWER(pp.username) LIKE '%talks%'
       OR LOWER(pp.username) LIKE '%josh%'
       OR LOWER(c.name) LIKE '%podcast%'
       OR LOWER(c.name) LIKE '%show%'
""")

rows = c.fetchall()
print(f"Found {len(rows)} remaining talk show / podcast channels:")
for r in rows:
    print(f"  ID #{r[0]} | Name: '{r[1]}' | Username: '{r[2]}'")

# Delete all of them
if rows:
    purge_ids = [r[0] for r in rows]
    c.executemany("DELETE FROM creators WHERE id = ?", [(i,) for i in purge_ids])
    conn.commit()
    print(f"\n[OK] Deleted {len(rows)} remaining talk show channels!")

c.execute("SELECT COUNT(*) FROM creators")
print("Remaining creators in DB:", c.fetchone()[0])
conn.close()
