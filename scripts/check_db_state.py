"""Quick check of database state."""
import sqlite3
import json
import os

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

# Total creators
c.execute("SELECT COUNT(*) FROM creators")
total = c.fetchone()[0]
print(f"Total creators: {total}")

# By platform
c.execute("SELECT pp.platform, COUNT(DISTINCT pp.creator_id) FROM platform_profiles pp GROUP BY pp.platform")
print(f"By platform: {c.fetchall()}")

# Categorized
c.execute("SELECT COUNT(*) FROM creators WHERE primary_category IS NOT NULL AND primary_category != ''")
print(f"Categorized: {c.fetchone()[0]}")

# Language
c.execute("SELECT COUNT(*) FROM creators WHERE primary_language IS NOT NULL AND primary_language != ''")
print(f"Language detected: {c.fetchone()[0]}")

# Categories distribution
c.execute("SELECT primary_category, COUNT(*) as cnt FROM creators WHERE primary_category IS NOT NULL AND primary_category != '' GROUP BY primary_category ORDER BY cnt DESC")
print(f"Category distribution: {c.fetchall()}")

# Check youtube_resume_state
if os.path.exists("youtube_resume_state.json"):
    with open("youtube_resume_state.json") as f:
        state = json.load(f)
    print(f"\nResume state keys: {list(state.keys())}")
    if "discovered_channels" in state:
        print(f"Discovered channels in resume state: {len(state['discovered_channels'])}")
    if "processed_keywords" in state:
        print(f"Processed keywords: {len(state['processed_keywords'])}")

# How many have social links
c.execute("SELECT COUNT(DISTINCT creator_id) FROM social_links")
print(f"\nCreators with social links: {c.fetchone()[0]}")

# How many have broker associations
c.execute("SELECT COUNT(DISTINCT creator_id) FROM broker_associations")
print(f"Creators with broker associations: {c.fetchone()[0]}")

# Check broker_associations table
c.execute("PRAGMA table_info(broker_associations)")
print(f"broker_associations columns: {[r[1] for r in c.fetchall()]}")

# Sample creators without language
c.execute("SELECT id, name, primary_category, primary_language FROM creators WHERE primary_language IS NULL OR primary_language = '' LIMIT 10")
print(f"\nSample no-language: {c.fetchall()}")

# Creator type distribution
c.execute("SELECT creator_type, COUNT(*) FROM creators GROUP BY creator_type")
print(f"Creator type distribution: {c.fetchall()}")

# Audience bucket distribution
c.execute("SELECT audience_bucket, COUNT(*) FROM creators WHERE audience_bucket IS NOT NULL GROUP BY audience_bucket")
print(f"Audience bucket: {c.fetchall()}")

conn.close()
