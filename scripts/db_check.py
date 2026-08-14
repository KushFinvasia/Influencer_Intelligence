import sqlite3

conn = sqlite3.connect('C:/Finvasia/Influencer_Scraper/creator_intel.db')
print('Journal mode:', conn.execute('PRAGMA journal_mode').fetchone()[0])
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables in DB:', tables)
for t in tables:
    cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    print(f" - {t}: {cnt} rows")
