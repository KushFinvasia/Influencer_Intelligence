import sqlite3
import json
import os

pool_file = "candidates_pool.json"
pool_count = 0
if os.path.exists(pool_file):
    with open(pool_file) as f:
        data = json.load(f)
        pool_count = len(data)

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform = 'youtube'")
yt_db = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM creators")
total_db = c.fetchone()[0]

print(f"Candidate Pool File Exists: {os.path.exists(pool_file)}")
print(f"Total Candidate Channel IDs in Pool: {pool_count}")
print(f"Current YouTube Creators in DB: {yt_db}")
print(f"Total Creators in DB: {total_db}")
if pool_count > 0:
    pending = pool_count - yt_db
    print(f"Pending Creators to run Phase 2, 3 & 4: {max(0, pending)}")
conn.close()
