from store import get_connection

conn = get_connection()

# Facts likely about a specific person's board/KMP role — attribute mentions
# director/designation/appointed/resigned, and subject looks like a person
# (not "Delhivery Limited" or similar corporate names).
rows = conn.execute("""
    SELECT id, doc_id, page, subject, subject_canon, attribute, value, period, evidence_text
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
    ORDER BY subject_canon, doc_id
""").fetchall()

print(f"Found {len(rows)} director/board-related facts about named individuals.\n")

# Group by person (subject_canon) to see who appears in which doc(s)
from collections import defaultdict
by_person = defaultdict(list)
for r in rows:
    by_person[r["subject_canon"]].append(r)

# Only show people who appear in MORE THAN ONE document — that's where a
# status contradiction (active vs resigned) would actually be checkable.
for person, facts in sorted(by_person.items()):
    docs = set(f["doc_id"] for f in facts)
    if len(docs) < 2:
        continue
    print(f"=== {person} (appears in {len(docs)} docs) ===")
    for f in facts:
        print(f"  [{f['doc_id']} p{f['page']}] {f['attribute']}: {f['value']} ({f['period']})")
        print(f"    evidence: {f['evidence_text'][:150]}")
    print()

conn.close()