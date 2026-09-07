from store import get_connection

conn = get_connection()
rows = conn.execute("""
    SELECT DISTINCT subject, subject_canon, doc_id
    FROM facts
    WHERE (
        LOWER(attribute) LIKE '%director%'
        OR LOWER(attribute) LIKE '%designation%'
        OR LOWER(attribute) LIKE '%appoint%'
        OR LOWER(attribute) LIKE '%resign%'
        OR LOWER(attribute) LIKE '%ceased%'
    )
    AND LOWER(subject) NOT LIKE '%delhivery%'
    AND LOWER(subject) NOT LIKE '%limited%'
    AND LOWER(subject) NOT LIKE '%company%'
    ORDER BY subject_canon
""").fetchall()

for r in rows:
    print(f"[{r['doc_id'][:3]}] {r['subject']!r:50s} -> canon: {r['subject_canon']!r}")

conn.close()