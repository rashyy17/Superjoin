import streamlit as st
import json
import os
import tempfile
from store import get_connection, init_db, load_facts_json
from ingest import extract_pdf
from extract import extract_facts_from_doc
from pathlib import Path

st.set_page_config(page_title="Fact Knowledge Layer", layout="wide")
st.title("📄 Fact Knowledge Layer")
st.caption("Upload PDFs, extract grounded facts, and see corroborations/contradictions across documents.")

# --- Sidebar: upload + process new PDF ---
st.sidebar.header("Add a document")
uploaded = st.sidebar.file_uploader("Upload a PDF", type="pdf")

if uploaded and st.sidebar.button("Process this PDF"):
    doc_id = Path(uploaded.name).stem
    with st.spinner(f"Ingesting {doc_id}..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        blocks = extract_pdf(tmp_path, doc_id)
        blocks_path = f"factlayer/data/{doc_id}_blocks.json"
        with open(blocks_path, "w") as f:
            json.dump(blocks, f)
        st.sidebar.success(f"Ingested {len(blocks)} blocks.")

    with st.spinner("Extracting facts (this calls the LLM, may take a while)..."):
        facts = extract_facts_from_doc(blocks_path, doc_id)
        facts_path = f"factlayer/data/{doc_id}_facts.json"
        with open(facts_path, "w") as f:
            json.dump(facts, f)
        st.sidebar.success(f"Extracted {len(facts)} facts.")

    with st.spinner("Loading into fact store..."):
        conn = init_db()
        n = load_facts_json(conn, facts_path)
        conn.close()
        st.sidebar.success(f"Loaded {n} facts into store.")
    st.sidebar.info("Run link.py + adjudicate.py separately to find cross-document relations for this doc.")

st.sidebar.markdown("---")
st.sidebar.caption("To find NEW cross-document relations after adding a doc, run from terminal:\n\n`python factlayer/link.py`\n`python factlayer/adjudicate.py <N>`")

# --- Main tabs ---
tab1, tab2, tab3 = st.tabs(["🔍 Browse Facts", "🔗 Relations", "⭐ Four Required Cases"])

conn = get_connection()

with tab1:
    st.subheader("All extracted facts")
    docs = [r["doc_id"] for r in conn.execute("SELECT DISTINCT doc_id FROM facts").fetchall()]
    col1, col2 = st.columns(2)
    doc_filter = col1.selectbox("Filter by document", ["All"] + sorted(docs))
    search = col2.text_input("Search subject/attribute/evidence")

    query = "SELECT doc_id, page, subject, attribute, value, unit, period, evidence_text, confidence FROM facts WHERE 1=1"
    params = []
    if doc_filter != "All":
        query += " AND doc_id = ?"
        params.append(doc_filter)
    if search:
        query += " AND (subject LIKE ? OR attribute LIKE ? OR evidence_text LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    query += " LIMIT 500"

    rows = conn.execute(query, params).fetchall()
    st.write(f"{len(rows)} facts shown (max 500)")
    st.dataframe([dict(r) for r in rows], use_container_width=True)

with tab2:
    st.subheader("Cross-document relations")
    rel_filter = st.selectbox("Filter by relation type", ["All", "CORROBORATES", "CONTRADICTS", "RECONCILABLE", "UNRELATED"])

    query = """
        SELECT r.relation_type, r.reasoning,
               fa.doc_id as doc_a, fa.page as page_a, fa.subject as subject_a, fa.attribute as attribute_a, fa.value as value_a, fa.evidence_text as evidence_a,
               fb.doc_id as doc_b, fb.page as page_b, fb.subject as subject_b, fb.attribute as attribute_b, fb.value as value_b, fb.evidence_text as evidence_b
        FROM relations r
        JOIN facts fa ON r.fact_id_a = fa.id
        JOIN facts fb ON r.fact_id_b = fb.id
    """
    params = []
    if rel_filter != "All":
        query += " WHERE r.relation_type = ?"
        params.append(rel_filter)

    rows = conn.execute(query, params).fetchall()
    st.write(f"{len(rows)} relations")
    for r in rows:
        with st.expander(f"[{r['relation_type']}] {r['attribute_a']} ({r['doc_a']}) ↔ {r['attribute_b']} ({r['doc_b']})"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**{r['doc_a']}**, page {r['page_a']}")
                st.write(f"{r['subject_a']} — {r['attribute_a']}: **{r['value_a']}**")
                st.caption(f"Evidence: \"{r['evidence_a']}\"")
            with c2:
                st.markdown(f"**{r['doc_b']}**, page {r['page_b']}")
                st.write(f"{r['subject_b']} — {r['attribute_b']}: **{r['value_b']}**")
                st.caption(f"Evidence: \"{r['evidence_b']}\"")
            st.info(r["reasoning"])

with tab3:
    st.subheader("The four required cases for this assignment")

    st.markdown("### 1️⃣ Corroborated Fact — FY24 Revenue")
    st.write("Same figure (₹8,142 Cr ≈ ₹81,415 Mn), stated in two documents, different units.")
    rows = conn.execute("""
        SELECT doc_id, page, attribute, value, unit, evidence_text FROM facts
        WHERE (attribute LIKE '%revenue%' AND period LIKE '%FY24%')
          AND (value LIKE '%8,142%' OR value LIKE '%81,415%')
        ORDER BY doc_id
        LIMIT 8
    """).fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)

    st.markdown("### 2️⃣ Contradiction Explained by Context — Director Status")
    st.write("Donald Francis Colleran: active director (2022 prospectus) vs. resigned (FY24 annual report).")
    rows = conn.execute("SELECT doc_id, page, attribute, value, evidence_text FROM facts WHERE subject_canon LIKE '%colleran%'").fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)
    rel = conn.execute("""
        SELECT reasoning FROM relations r
        JOIN facts fa ON r.fact_id_a = fa.id
        WHERE fa.subject_canon LIKE '%colleran%'
    """).fetchone()
    if rel:
        st.info(rel["reasoning"])

    st.markdown("### 3️⃣ Apparent Contradiction Explained by Context — CIN Change")
    st.write("CIN prefix U→L reflects unlisted→listed status change after the IPO.")
    rows = conn.execute("SELECT doc_id, page, attribute, value, evidence_text FROM facts WHERE attribute LIKE '%Identity%' OR attribute LIKE '%Identification%'").fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)

    st.markdown("### 4️⃣ Extraction/Reasoning Failure — EBITDA Sign Loss")
    st.write("Source says 'a loss of ₹4,516 million' but extracted value dropped the negative sign.")
    rows = conn.execute("SELECT doc_id, page, attribute, value, period, evidence_text FROM facts WHERE value LIKE '%4,516%' OR value LIKE '%452%'").fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)
    st.warning("See factlayer/data/findings.md for full writeup of root cause and proposed fix.")

conn.close()