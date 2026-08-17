import sqlite3
import re

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

TALKSHOW_PATTERNS = [
    r"\braj\s+shamani\b",
    r"\bfiguring\s+out\b",
    r"\bjosh\s+talks?\b",
    r"\bbeerbiceps\b",
    r"\branveer\s+allahbadia\b",
    r"\bthe\s+ranveer\s+show\b",
    r"\brealhit\b",
    r"\buntold\s+stories\b",
    r"\btrippy\s+story\b",
    r"\bpodcast\b",
    r"\btalk\s+show\b",
    r"\binterview\s+show\b",
    r"\binterview\s+network\b",
]

regexes = [re.compile(p, re.IGNORECASE) for p in TALKSHOW_PATTERNS]

c.execute("""
    SELECT c.id, c.name, pp.bio, pp.description
    FROM creators c
    LEFT JOIN platform_profiles pp ON pp.creator_id = c.id
""")

rows = c.fetchall()
to_purge = []

for r in rows:
    cid, name, bio, desc = r
    combined = f"{name or ''} {bio or ''} {desc or ''}"
    for reg in regexes:
        if reg.search(combined):
            to_purge.append((cid, name))
            break

print(f"Found {len(to_purge)} talk show / podcast channels to purge:")

if to_purge:
    purge_ids = [item[0] for item in to_purge]
    c.executemany("DELETE FROM creators WHERE id = ?", [(i,) for i in purge_ids])
    conn.commit()
    print(f"\n[OK] Successfully purged {len(to_purge)} podcast and talk show channels from DB!")

c.execute("SELECT COUNT(*) FROM creators")
remaining = c.fetchone()[0]
print(f"Remaining clean creators in DB: {remaining}")

conn.close()
