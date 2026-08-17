import sqlite3
import json

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("SELECT id, job_type, total_discovered, total_new, keyword_metrics FROM scrape_jobs ORDER BY id DESC LIMIT 10")
for row in c.fetchall():
    print(f"Job #{row[0]}: type={row[1]}, discovered={row[2]}, new={row[3]}")

c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform = 'youtube'")
print(f"\nYouTube platform profiles in DB: {c.fetchone()[0]}")

# Check featured / mentioned channel IDs stored in raw_data across YouTube profiles
c.execute("SELECT raw_data FROM platform_profiles WHERE platform = 'youtube'")
discovered_channel_ids = set()

for (rd,) in c.fetchall():
    if not rd:
        continue
    try:
        data = json.loads(rd) if isinstance(rd, str) else rd
        if isinstance(data, dict):
            # Featured channels
            branding = data.get("brandingSettings", {})
            channel_settings = branding.get("channel", {})
            featured = channel_settings.get("featuredChannelsUrls", [])
            for f in featured:
                if f:
                    discovered_channel_ids.add(f)
    except Exception as e:
        pass

print(f"Discovered featured channel IDs from existing YouTube profiles: {len(discovered_channel_ids)}")

conn.close()
