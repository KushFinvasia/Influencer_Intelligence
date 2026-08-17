import sqlite3

conn = sqlite3.connect("creator_intel.db")
c = conn.cursor()

c.execute("SELECT targets_india, COUNT(*) FROM creators GROUP BY targets_india")
print("UPDATED targets_india counts in DB:")
for r in c.fetchall():
    lbl = "India (1)" if r[0] == 1 else "Global (0)"
    print(f"  {lbl}: {r[1]} creators")

c.execute("SELECT is_relevant, COUNT(*) FROM creators GROUP BY is_relevant")
print("\nUPDATED is_relevant counts in DB:")
for r in c.fetchall():
    lbl = "Stock Market (1)" if r[0] == 1 else "Non-Stockmarket (0)"
    print(f"  {lbl}: {r[1]} creators")

c.execute("SELECT COUNT(*) FROM creators")
total = c.fetchone()[0]
print(f"\nTOTAL CLEAN CREATORS IN DATABASE: {total}")

conn.close()
