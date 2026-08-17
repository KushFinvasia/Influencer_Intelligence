import sqlite3
c = sqlite3.connect("creator_intel.db").cursor()
c.execute("SELECT COUNT(*) FROM creators WHERE primary_language IS NULL OR primary_language = ''")
print("No language:", c.fetchone()[0])
c.execute("SELECT COUNT(*) FROM creators WHERE last_enriched_at IS NOT NULL")
print("Enriched:", c.fetchone()[0])
c.execute("SELECT COUNT(*) FROM creators WHERE last_enriched_at IS NULL")
print("Not enriched:", c.fetchone()[0])
# Check how many YouTube channels are in DB vs discovered
c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform = 'youtube'")
print("YouTube profiles in DB:", c.fetchone()[0])
# Check the discovery pipeline state
c.execute("SELECT id, job_type, status, total_discovered, total_new FROM scrape_jobs ORDER BY id DESC LIMIT 5")
for r in c.fetchall():
    print(f"Job #{r[0]}: {r[1]} - {r[2]} (discovered={r[3]}, new={r[4]})")
