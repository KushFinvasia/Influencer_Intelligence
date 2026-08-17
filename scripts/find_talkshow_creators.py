import sqlite3

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

print("Searching DB for talk show / podcast channels...")
c.execute("""
    SELECT c.id, c.name, c.primary_category, c.is_relevant, c.targets_india, pp.followers
    FROM creators c
    LEFT JOIN platform_profiles pp ON pp.creator_id = c.id
    WHERE LOWER(c.name) LIKE '%raj shamani%'
       OR LOWER(c.name) LIKE '%josh talk%'
       OR LOWER(c.name) LIKE '%podcast%'
       OR LOWER(c.name) LIKE '%beerbiceps%'
       OR LOWER(c.name) LIKE '%ranveer%'
       OR LOWER(c.name) LIKE '%talks%'
""")

rows = c.fetchall()
print(f"Found {len(rows)} matching channels in DB:")
for r in rows:
    print(f"  ID #{r[0]} | Name: '{r[1]}' | Cat: {r[2]} | Relevant: {r[3]} | India: {r[4]} | Followers: {r[5]}")

conn.close()
