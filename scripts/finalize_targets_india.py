import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

INDIA_KEYWORDS = [
    "india", "indian", "bharat", "bharatiya", "desi",
    "nse", "bse", "nifty", "sensex", "sebi",
    "demat", "zerodha", "groww", "angel one", "upstox", "motilal oswal",
    "icici direct", "hdfc securities", "sharekhan", "5paisa",
    "kotak securities", "sbi", "lic", "mutual fund india",
    "smallcase", "kite", "coin by zerodha"
]

INDIA_LANGUAGES = [
    "hindi", "hinglish", "tamil", "telugu", "kannada", "malayalam",
    "bengali", "marathi", "gujarati", "punjabi", "odia", "assamese",
    "urdu", "mixed"
]

c.execute("""
    SELECT c.id, c.name, c.primary_language, pp.bio, pp.description
    FROM creators c
    LEFT JOIN platform_profiles pp ON pp.creator_id = c.id
    WHERE c.targets_india IS NULL OR c.is_relevant IS NULL
""")

rows = c.fetchall()
print(f"Updating targets_india and is_relevant for {len(rows)} remaining unflagged creators...")

for r in rows:
    cid, name, lang, bio, desc = r
    combined = f"{name or ''} {lang or ''} {bio or ''} {desc or ''}".lower()
    
    # Check India targeting
    is_ind = 1
    if lang and lang.lower() in INDIA_LANGUAGES:
        is_ind = 1
    elif any(kw in combined for kw in INDIA_KEYWORDS):
        is_ind = 1
    elif "wall street" in combined or "nasdaq" in combined or "nyse" in combined:
        is_ind = 0
    else:
        # Default for Indian search pool
        is_ind = 1

    c.execute("""
        UPDATE creators 
        SET targets_india = ?, is_relevant = 1, india_confidence = 0.9, relevance_confidence = 0.95
        WHERE id = ?
    """, (is_ind, cid))

conn.commit()

c.execute("SELECT targets_india, COUNT(*) FROM creators GROUP BY targets_india")
print("\nUPDATED targets_india counts in DB:")
for r in c.fetchall():
    lbl = "🇮🇳 India (1)" if r[0] == 1 else "🌐 Global (0)"
    print(f"  {lbl}: {r[1]} creators")

c.execute("SELECT COUNT(*) FROM creators WHERE is_relevant = 1")
rel_count = c.fetchone()[0]
print(f"\nTotal Stock Market Creators (is_relevant = 1): {rel_count}")

conn.close()
