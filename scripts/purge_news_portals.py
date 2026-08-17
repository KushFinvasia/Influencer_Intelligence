import sqlite3
import re

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

NEWS_PORTAL_PATTERNS = [
    r"\bnews\b",
    r"\bnewsletter\b",
    r"\bmedia\b",
    r"\btelevision\b",
    r"\bnewspaper\b",
    r"\bpress\b",
    r"\bjournal\b",
    r"\bbulletin\b",
]

regexes = [re.compile(p, re.IGNORECASE) for p in NEWS_PORTAL_PATTERNS]

c.execute("SELECT id, name FROM creators")
rows = c.fetchall()

to_purge = []
for r in rows:
    cid, name = r
    name_str = (name or "").strip()
    
    # Exceptions: Creator names that happen to contain news or talks (e.g. 'Neeraj joshi', 'Neeraj Joshi Talks')
    if "neeraj joshi" in name_str.lower():
        continue

    for reg in regexes:
        if reg.search(name_str):
            to_purge.append((cid, name_str))
            break

print(f"Found {len(to_purge)} news portals / media channels to purge:")

if to_purge:
    c.executemany("DELETE FROM creators WHERE id = ?", [(item[0],) for item in to_purge])
    conn.commit()
    print(f"\n[OK] Purged {len(to_purge)} news portals from DB!")

c.execute("SELECT COUNT(*) FROM creators")
print("REMAINING PURE INDIVIDUAL CREATORS IN DB:", c.fetchone()[0])

conn.close()
