import sqlite3

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM creators")
total = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform='youtube'")
yt_count = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform='instagram'")
insta_count = c.fetchone()[0]

c.execute("SELECT COUNT(DISTINCT creator_id) FROM broker_associations")
broker_creators = c.fetchone()[0]

c.execute("SELECT broker_name, COUNT(*) FROM broker_associations GROUP BY broker_name ORDER BY COUNT(*) DESC LIMIT 10")
top_brokers = c.fetchall()

c.execute("SELECT primary_language, COUNT(*) FROM creators GROUP BY primary_language ORDER BY COUNT(*) DESC")
langs = c.fetchall()

print(f"Total Creators in Clean DB: {total}")
print(f" - YouTube Creators: {yt_count}")
print(f" - Instagram Creators: {insta_count}")
print(f" - Creators with Broker Associations: {broker_creators}")
print(f" - Top Associated Brokers: {top_brokers}")
print(f" - Language Breakdown: {langs}")
