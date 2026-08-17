import sqlite3
import re

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

# 1. Mainstream Media, TV Networks & News Outlets Blacklist
MEDIA_TV_NEWS_PATTERNS = [
    r"\bzee\b",
    r"\bcnbc\b",
    r"\bet\s*now\b",
    r"\bndtv\b",
    r"\baaj\s*tak\b",
    r"\babp\s*news\b",
    r"\bnews18\b",
    r"\btv18\b",
    r"\bnews24\b",
    r"\bnews\s*tamil\b",
    r"\bsakshi\s*tv\b",
    r"\bbusiness\s*today\b",
    r"\bmoneycontrol\b",
    r"\bbloomberg\b",
    r"\brepublic\b",
    r"\bthanthi\b",
    r"\bsun\s*news\b",
    r"\bpolimer\b",
    r"\bputhiyathaimurai\b",
    r"\bmalayala\s*manorama\b",
    r"\bmathrubhumi\b",
    r"\basianet\b",
    r"\btv9\b",
    r"\bv6\s*news\b",
    r"\bt\s*news\b",
    r"\bntv\b",
    r"\bhindustan\s*times\b",
    r"\btimes\s*now\b",
    r"\bfinancial\s*express\b",
    r"\bbusiness\s*standard\b",
    r"\bmint\b",
    r"\bthe\s*hindu\b",
    r"\bindian\s*express\b",
    r"\bdainik\s*bhaskar\b",
    r"\bpatrika\b",
    r"\bamar\s*ujala\b",
    r"\bjagran\b",
    r"\bmid-day\b",
    r"\bcnbc-tv18\b",
    r"\bcnbc\s*awaaz\b",
]

# 2. General Podcast, Interview Networks & Talk Shows (including Hindi script)
TALKSHOW_PATTERNS = [
    r"जोश",
    r"\bjosh\s*talks?\b",
    r"\braj\s*shamani\b",
    r"\bfiguring\s*out\b",
    r"\bbeerbiceps\b",
    r"\branveer\s*allahbadia\b",
    r"\bthe\s*ranveer\s*show\b",
    r"\brealhit\b",
    r"\buntold\s*stories\b",
    r"\btrippy\s*story\b",
    r"\bpodcast\b",
    r"\btalk\s*show\b",
    r"\binterview\s*show\b",
    r"\binterview\s*network\b",
    r"\btalks\b",
]

ALL_PATTERNS = MEDIA_TV_NEWS_PATTERNS + TALKSHOW_PATTERNS
regexes = [re.compile(p, re.IGNORECASE) for p in ALL_PATTERNS]

c.execute("""
    SELECT c.id, c.name, pp.username, pp.bio, pp.description
    FROM creators c
    LEFT JOIN platform_profiles pp ON pp.creator_id = c.id
""")

rows = c.fetchall()
to_purge = []

# Allowed Exceptions for individual creators whose channel name might have 'talks' or 'news' as part of creator name:
# e.g., 'Neeraj Joshi Talks' is an individual trader. But 'जोश Talks' or 'Josh Talks' or 'Zee Business' is a network.

for r in rows:
    cid, name, username, bio, desc = r
    name_str = name or ""
    user_str = username or ""
    combined = f"{name_str} {user_str} {bio or ''} {desc or ''}"
    
    # Specific checks
    for reg in regexes:
        if reg.search(combined):
            # Special exception check: If name is 'Neeraj Joshi Talks' (ID #1207), keep it unless it matches TV/News
            if "neeraj joshi talks" in name_str.lower() and not any(r_media.search(combined) for r_media in [re.compile(p, re.IGNORECASE) for p in MEDIA_TV_NEWS_PATTERNS]):
                continue
            to_purge.append((cid, name_str))
            break

print(f"Found {len(to_purge)} TV News, Media Networks, and Talk Shows to purge:")

if to_purge:
    purge_ids = [item[0] for item in to_purge]
    c.executemany("DELETE FROM creators WHERE id = ?", [(i,) for i in purge_ids])
    conn.commit()
    print(f"\n[OK] Successfully purged {len(to_purge)} TV/News & Talk Show channels from DB!")

c.execute("SELECT COUNT(*) FROM creators")
remaining = c.fetchone()[0]
print(f"REMAINING PURE CREATORS/INFLUENCERS IN DB: {remaining}")

conn.close()
