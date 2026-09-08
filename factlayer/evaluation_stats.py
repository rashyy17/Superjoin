from store import get_connection

conn = get_connection()

print("=== Fact extraction coverage ===")
rows = conn.execute("""
    SELECT doc_id, COUNT(*) as n,
           SUM(CASE WHEN confidence='high' THEN 1 ELSE 0 END) as high_conf
    FROM facts GROUP BY doc_id ORDER BY doc_id
""").fetchall()
total = 0
for r in rows:
    pct = 100 * r["high_conf"] / r["n"] if r["n"] else 0
    print(f"  {r['doc_id']}: {r['n']} facts ({pct:.0f}% high confidence)")
    total += r["n"]
print(f"  TOTAL: {total} facts across {len(rows)} documents\n")

print("=== Cross-document relations ===")
rows = conn.execute("SELECT relation_type, COUNT(*) as n FROM relations GROUP BY relation_type").fetchall()
for r in rows:
    print(f"  {r['relation_type']}: {r['n']}")

conn.close()
