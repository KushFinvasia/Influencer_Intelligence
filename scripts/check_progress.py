import sqlite3
conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM creators")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform = 'youtube'")
yt = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM platform_profiles WHERE platform = 'instagram'")
ig = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM creators WHERE is_relevant = 1")
rel = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM creators WHERE is_relevant = 0")
not_rel = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM creators WHERE targets_india = 1")
india = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM creators WHERE targets_india = 0")
not_india = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM creators WHERE is_relevant IS NULL")
null_rel = c.fetchone()[0]

print(f"=== DATABASE STATE ===")
print(f"Total creators:     {total}")
print(f"  YouTube:          {yt}")
print(f"  Instagram:        {ig}")
print(f"  Relevant:         {rel}")
print(f"  Not relevant:     {not_rel}")
print(f"  Relevance NULL:   {null_rel}")
print(f"  Targets India:    {india}")
print(f"  Not India:        {not_india}")

# Job #18 status
c.execute("SELECT id, status, total_discovered, total_new, error_message FROM scrape_jobs ORDER BY id DESC LIMIT 3")
for row in c.fetchall():
    print(f"\nJob #{row[0]}: status={row[1]}, discovered={row[2]}, new={row[3]}")
    if row[4]:
        print(f"  error: {row[4][:200]}")

# New creators added since enrichment (id > 761)
c.execute("SELECT COUNT(*) FROM creators WHERE id > 761")
new_since = c.fetchone()[0]
print(f"\nNew creators added since enrichment: {new_since}")

# Language fill
c.execute("SELECT COUNT(*) FROM creators WHERE primary_language IS NOT NULL AND primary_language != ''")
lang = c.fetchone()[0]
print(f"Language detected: {lang}/{total}")

conn.close()
