import json
import os
import time
import sys
from google import genai
from dotenv import load_dotenv
from store import get_connection

load_dotenv("factlayer/.env")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM_PROMPT = """You are comparing two facts extracted from different documents about the same company or economy.

Classify their relationship as exactly one of:
- CORROBORATES: both facts state the same underlying truth, even if worded or scaled differently.
- CONTRADICTS: the facts genuinely conflict and cannot both be true as stated.
- RECONCILABLE: the facts appear to differ, but the difference is explained by context — different time periods, different scope (e.g. standalone vs consolidated), different units, or a real-world status change between the two document dates.
- UNRELATED: despite superficial similarity, these facts are not actually about the same thing.

Respond with ONLY a JSON object:
{"relation": "CORROBORATES" | "CONTRADICTS" | "RECONCILABLE" | "UNRELATED", "reasoning": "one or two sentences explaining your classification, referencing the specific values/dates/context that justify it"}"""

def adjudicate_pair(fact_a, fact_b, max_retries=3):
    prompt = f"""FACT A (from {fact_a['doc_id']}, page {fact_a['page']}):
Subject: {fact_a['subject']}
Attribute: {fact_a['attribute']}
Value: {fact_a['value']} {fact_a['unit'] or ''}
Period: {fact_a['period']}
Scope: {fact_a['scope']}
Basis: {fact_a['basis']}
Evidence: "{fact_a['evidence_text']}"

FACT B (from {fact_b['doc_id']}, page {fact_b['page']}):
Subject: {fact_b['subject']}
Attribute: {fact_b['attribute']}
Value: {fact_b['value']} {fact_b['unit'] or ''}
Period: {fact_b['period']}
Scope: {fact_b['scope']}
Basis: {fact_b['basis']}
Evidence: "{fact_b['evidence_text']}"
"""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{SYSTEM_PROMPT}\n\n{prompt}",
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            if parsed.get("relation") in ("CORROBORATES", "CONTRADICTS", "RECONCILABLE", "UNRELATED"):
                return parsed
        except json.JSONDecodeError:
            print(f"  [retry {attempt+1}] bad JSON")
            time.sleep(3)
        except Exception as e:
            print(f"  [error] {e}")
            time.sleep(5)
    return None

def run_adjudication(pairs_path="factlayer/data/candidate_pairs.json", limit=None, min_similarity=0.85):
    with open(pairs_path) as f:
        pairs = json.load(f)

    # Prioritize the strongest matches first — most likely to be genuinely related
    pairs = [p for p in pairs if p["similarity"] >= min_similarity]
    pairs.sort(key=lambda p: -p["similarity"])
    if limit:
        pairs = pairs[:limit]

    conn = get_connection()

    # skip pairs already adjudicated (resumable, same spirit as extraction checkpointing)
    done = set()
    for row in conn.execute("SELECT fact_id_a, fact_id_b FROM relations"):
        done.add((row["fact_id_a"], row["fact_id_b"]))

    print(f"{len(pairs)} pairs to adjudicate (similarity >= {min_similarity}).")
    results_summary = {"CORROBORATES": 0, "CONTRADICTS": 0, "RECONCILABLE": 0, "UNRELATED": 0}

    for i, pair in enumerate(pairs):
        a_id, b_id = pair["fact_id_a"], pair["fact_id_b"]
        key = (a_id, b_id) if a_id < b_id else (b_id, a_id)
        if key in done:
            continue

        fact_a = conn.execute("SELECT * FROM facts WHERE id = ?", (a_id,)).fetchone()
        fact_b = conn.execute("SELECT * FROM facts WHERE id = ?", (b_id,)).fetchone()
        if not fact_a or not fact_b:
            continue

        result = adjudicate_pair(fact_a, fact_b)
        if result is None:
            print(f"[{i+1}/{len(pairs)}] FAILED — skipping")
            continue

        conn.execute(
            "INSERT INTO relations (fact_id_a, fact_id_b, relation_type, reasoning) VALUES (?, ?, ?, ?)",
            (a_id, b_id, result["relation"], result["reasoning"])
        )
        conn.commit()
        results_summary[result["relation"]] += 1
        print(f"[{i+1}/{len(pairs)}] {result['relation']}: {fact_a['attribute']} <-> {fact_b['attribute']}")
        time.sleep(1)

    conn.close()
    print(f"\nDone. Summary: {results_summary}")

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_adjudication(limit=limit)