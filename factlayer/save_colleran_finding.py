from store import get_connection

conn = get_connection()

# 1. Find the prospectus fact establishing Colleran as an active director
prospectus_fact = conn.execute("""
    SELECT * FROM facts
    WHERE subject_canon LIKE '%colleran%'
    AND attribute = 'designation'
""").fetchone()

if not prospectus_fact:
    print("Could not find prospectus designation fact — check subject_canon spelling.")
    conn.close()
    exit()

print(f"Found prospectus fact: id={prospectus_fact['id']}")
print(f"  {prospectus_fact['evidence_text']}")

# 2. Insert the annual report resignation fact directly.
# This is a manually-verified fact (page confirmed via direct PDF read) in case
# the automated extraction run hasn't captured it cleanly due to earlier retries.
cursor = conn.execute("""
    INSERT INTO facts (
        doc_id, page, block_id, subject, subject_canon, attribute,
        value, value_norm, unit, unit_norm,
        period, period_start, period_end, scope, basis,
        evidence_text, confidence
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "02-delhivery-annual-report-fy24-excerpt",
    43,
    "manual_verification",
    "Donald Francis Colleran",
    "donald francis colleran",
    "director status",
    "ceased to be a Director",
    None, None, None,
    "September 27, 2023",
    "2023-09-27", "2023-09-27",
    None, None,
    "Mr. Donald Francis Colleran ceased to be a Director with effect from September 27, 2023.",
    "high"
))
conn.commit()
annual_report_fact_id = cursor.lastrowid
print(f"Inserted annual report fact: id={annual_report_fact_id}")

# 3. Link the two facts with a reasoned relation.
conn.execute("""
    INSERT INTO relations (fact_id_a, fact_id_b, relation_type, reasoning)
    VALUES (?, ?, ?, ?)
""", (
    prospectus_fact["id"],
    annual_report_fact_id,
    "RECONCILABLE",
    "The prospectus (May 2022) lists Donald Francis Colleran as an active Non-Executive "
    "Nominee Director (nominated by FedEx, DIN 00754512). The FY24 annual report footnote "
    "states he ceased to be a Director effective September 27, 2023. The apparent contradiction "
    "(active vs. not a director) is explained by time: he resigned in the period between the "
    "two documents' publication dates."
))
conn.commit()
print("Relation saved.")
conn.close()