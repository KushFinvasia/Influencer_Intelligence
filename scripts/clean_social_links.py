import sqlite3
from pathlib import Path
from urllib.parse import urlparse

db_path = Path("creator_intel.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Delete misclassified twitter links
rows = c.execute("SELECT id, url FROM social_links WHERE platform = 'twitter'").fetchall()
for row_id, url in rows:
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().lstrip("www.")
        if netloc not in ("twitter.com", "x.com") and not netloc.endswith(".twitter.com") and not netloc.endswith(".x.com"):
            c.execute("DELETE FROM social_links WHERE id = ?", (row_id,))
    except Exception:
        pass

# 2. Delete misclassified broker referral links from website entries
broker_domains = ["coindcx.com", "zerodha.com", "angelone.in", "groww.in", "upstox.com", "dhan.co", "fyers.in", "delta.exchange"]
for row_id, url in c.execute("SELECT id, url FROM social_links WHERE platform = 'website'").fetchall():
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if any(bd in netloc for bd in broker_domains):
            c.execute("DELETE FROM social_links WHERE id = ?", (row_id,))
    except Exception:
        pass

conn.commit()
print("Cleaned up social links cleanly using domain parsing!")
conn.close()
