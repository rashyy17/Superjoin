from store import get_connection

conn = get_connection()

def find_fact(doc_id_like, attribute_like, value_like=None):
    q = "SELECT id FROM facts WHERE doc_id LIKE ? AND attribute LIKE ?"
    params = [f"%{doc_id_like}%", f"%{attribute_like}%"]
    if value_like:
        q += " AND value LIKE ?"
        params.append(f"%{value_like}%")
    row = conn.execute(q, params).fetchone()
    return row["id"] if row else None

restored = 0

# --- Case 2/3: Colleran director status (re-insert via existing script logic) ---
prospectus_fact = conn.execute("""
    SELECT * FROM facts WHERE subject_canon LIKE '%colleran%' AND attribute = 'designation'
""").fetchone()
if prospectus_fact:
    cursor = conn.execute("""
        INSERT INTO facts (
            doc_id, page, block_id, subject, subject_canon, attribute,
            value, value_norm, unit, unit_norm, period, period_start, period_end,
            scope, basis, evidence_text, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "02-delhivery-annual-report-fy24-excerpt", 43, "manual_verification",
        "Donald Francis Colleran", "donald francis colleran", "director status",
        "ceased to be a Director", None, None, None,
        "September 27, 2023", "2023-09-27", "2023-09-27", None, None,
        "Mr. Donald Francis Colleran ceased to be a Director with effect from September 27, 2023.",
        "high"
    ))
    annual_fact_id = cursor.lastrowid
    conn.execute("""
        INSERT INTO relations (fact_id_a, fact_id_b, relation_type, reasoning)
        VALUES (?, ?, ?, ?)
    """, (
        prospectus_fact["id"], annual_fact_id, "RECONCILABLE",
        "The prospectus (May 2022) lists Donald Francis Colleran as an active "
        "Non-Executive Nominee Director (nominated by FedEx, DIN 00754512). The "
        "FY24 annual report footnote states he ceased to be a Director effective "
        "September 27, 2023. The apparent contradiction (active vs. not a "
        "director) is explained by time: he resigned in the period between the "
        "two documents' publication dates."
    ))
    restored += 1
    print(f"Restored: Colleran relation ({prospectus_fact['id']} <-> {annual_fact_id})")
else:
    print("WARNING: could not find prospectus Colleran fact — check subject_canon")

# --- Case 3: CIN reconciliation ---
cin_a = find_fact("01-delhivery-prospectus", "Corporate Identity Number")
cin_b = find_fact("02-delhivery-annual-report", "Corporate Identification Number")
if cin_a and cin_b:
    conn.execute("""
        INSERT INTO relations (fact_id_a, fact_id_b, relation_type, reasoning)
        VALUES (?, ?, ?, ?)
    """, (
        cin_a, cin_b, "RECONCILABLE",
        "The CIN prefix changes from U (unlisted) to L (listed) between the "
        "2022 prospectus and the FY24 annual report. Under India's MCA CIN "
        "scheme this letter encodes listing status. The prospectus itself "
        "states shares were 'proposed to be listed' at time of writing — the "
        "IPO it describes explains the change in status between documents."
    ))
    restored += 1
    print(f"Restored: CIN relation ({cin_a} <-> {cin_b})")
else:
    print(f"WARNING: could not find CIN facts (a={cin_a}, b={cin_b})")

# --- Case 1: FY24 Revenue corroboration ---
rev_a = find_fact("03-delhivery-q4-fy24", "revenue", "8,142")
rev_b = find_fact("02-delhivery-annual-report", "Revenue from services", "81,415")
if rev_a and rev_b:
    conn.execute("""
        INSERT INTO relations (fact_id_a, fact_id_b, relation_type, reasoning)
        VALUES (?, ?, ?, ?)
    """, (
        rev_a, rev_b, "CORROBORATES",
        "Both facts state FY24 revenue from services: INR 8,142 Cr (earnings "
        "deck) and INR 81,415 Mn (annual report). These normalize to the same "
        "figure (81,420 Mn vs 81,415 Mn, within rounding), confirming the same "
        "underlying fact stated in different units."
    ))
    restored += 1
    print(f"Restored: Revenue corroboration ({rev_a} <-> {rev_b})")
else:
    print(f"WARNING: could not find revenue facts (a={rev_a}, b={rev_b}) — may need manual lookup")

conn.commit()
conn.close()
print(f"\n{restored} relation(s) restored.")