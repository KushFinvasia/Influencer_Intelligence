import sqlite3
import json

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("""
    SELECT 
        c.id, 
        c.name, 
        c.primary_category, 
        c.primary_language, 
        pp.platform, 
        pp.followers, 
        c.influencer_score,
        c.targets_india,
        pp.profile_url
    FROM creators c
    JOIN platform_profiles pp ON pp.creator_id = c.id
    WHERE c.is_relevant = 1
    ORDER BY pp.followers DESC NULLS LAST
    LIMIT 25
""")

rows = c.fetchall()
results = []

for r in rows:
    cid, name, cat, lang, platform, followers, score, india, url = r
    results.append({
        "id": cid,
        "name": name,
        "category": cat or "Equity",
        "language": lang or "Hindi",
        "platform": platform,
        "followers": followers or 0,
        "score": score or 0.0,
        "targets_india": bool(india),
        "url": url or ""
    })

print(json.dumps(results, indent=2, ensure_ascii=True))
conn.close()
