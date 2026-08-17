import sqlite3
conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform = 'youtube'")
print(f"YouTube channels in DB: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform = 'instagram'")
print(f"Instagram profiles in DB: {c.fetchone()[0]}")

# Check scrape_logs table
try:
    c.execute("SELECT COUNT(*) FROM scrape_logs")
    print(f"Total scrape log entries: {c.fetchone()[0]}")
except:
    print("No scrape_logs table")

# Check if we have existing channel IDs
c.execute("SELECT platform_user_id FROM platform_profiles WHERE platform = 'youtube' LIMIT 5")
for r in c.fetchall():
    print(f"  Sample channel: {r[0]}")

conn.close()
