import sqlite3
import json
import glob
import os

DB_PATH = "factlayer/data/facts.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    page INTEGER,
    block_id TEXT,
    subject TEXT,
    subject_canon TEXT,
    attribute TEXT,
    value TEXT,
    value_norm REAL,
    unit TEXT,
    unit_norm TEXT,
    period TEXT,
    period_start TEXT,
    period_end TEXT,
    scope TEXT,
    basis TEXT,
    evidence_text TEXT,
    confidence TEXT
);
CREATE INDEX IF NOT EXISTS idx_subject_canon ON facts(subject_canon);
CREATE INDEX IF NOT EXISTS idx_doc_id ON facts(doc_id);

CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id_a INTEGER NOT NULL,
    fact_id_b INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    reasoning TEXT,
    FOREIGN KEY (fact_id_a) REFERENCES facts(id),
    FOREIGN KEY (fact_id_b) REFERENCES facts(id)
);
"""

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    return conn

def load_facts_json(conn, facts_json_path):
    """Load one doc's _facts.json into the facts table, normalizing as we go."""
    from normalize import parse_value, parse_period, canon_subject

    with open(facts_json_path) as f:
        facts = json.load(f)

    rows = []
    for fact in facts:
        value_norm, unit_norm = parse_value(fact.get("value"), fact.get("unit"))
        period_start, period_end, _ = parse_period(fact.get("period"))
        subject_canon = canon_subject(fact.get("subject"))

        rows.append((
            fact.get("doc_id"),
            fact.get("page"),
            fact.get("block_id"),
            fact.get("subject"),
            subject_canon,
            fact.get("attribute"),
            fact.get("value"),
            value_norm,
            fact.get("unit"),
            unit_norm,
            fact.get("period"),
            period_start,
            period_end,
            fact.get("scope"),
            fact.get("basis"),
            fact.get("evidence_text"),
            fact.get("confidence"),
        ))

    conn.executemany("""
        INSERT INTO facts (
            doc_id, page, block_id, subject, subject_canon, attribute,
            value, value_norm, unit, unit_norm,
            period, period_start, period_end, scope, basis,
            evidence_text, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    return len(rows)

def load_all_facts(pattern="factlayer/data/*_facts.json"):
    """Rebuilds the facts table from every *_facts.json file found,
    but preserves the relations table (adjudication results are expensive
    to regenerate and should survive a facts reload)."""
    conn = init_db()
    conn.execute("DELETE FROM facts")
    conn.commit()

    total = 0
    for path in sorted(glob.glob(pattern)):
        n = load_facts_json(conn, path)
        print(f"Loaded {n} facts from {os.path.basename(path)}")
        total += n
    print(f"\nTotal facts in store: {total}")
    conn.close()

if __name__ == "__main__":
    load_all_facts()