import os
import numpy as np
from google import genai
from dotenv import load_dotenv
from store import get_connection

load_dotenv("factlayer/.env")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def fact_to_text(fact_row):
    """Build the canonical string we embed for matching — subject + attribute + period.
    Deliberately excludes value, so facts about the SAME thing with DIFFERENT
    values (a contradiction!) still end up near each other in embedding space."""
    parts = [
        fact_row["subject_canon"] or "",
        fact_row["attribute"] or "",
        fact_row["period"] or "",
        fact_row["scope"] or "",
    ]
    return " | ".join(p for p in parts if p)

def embed_texts(texts, batch_size=100):
    """Returns a list of embedding vectors (as numpy arrays), same order as input."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=batch,
        )
        for e in result.embeddings:
            all_embeddings.append(np.array(e.values))
        print(f"  embedded {min(i+batch_size, len(texts))}/{len(texts)}")
    return all_embeddings

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def find_candidate_pairs(min_similarity=0.75, top_k=3):
    """For every fact, find its most similar facts IN OTHER DOCUMENTS.
    Returns a list of (fact_id_a, fact_id_b, similarity) tuples, deduplicated."""
    conn = get_connection()
    facts = conn.execute("SELECT * FROM facts").fetchall()
    conn.close()

    if not facts:
        print("No facts in store — run store.py first.")
        return []

    print(f"Embedding {len(facts)} facts...")
    texts = [fact_to_text(f) for f in facts]
    embeddings = embed_texts(texts)

    pairs = []
    seen = set()
    for i, fact_a in enumerate(facts):
        sims = []
        for j, fact_b in enumerate(facts):
            if i == j:
                continue
            if fact_a["doc_id"] == fact_b["doc_id"]:
                continue  # only cross-document pairs matter for corroborate/contradict
            sim = cosine_sim(embeddings[i], embeddings[j])
            if sim >= min_similarity:
                sims.append((j, sim))
        sims.sort(key=lambda x: -x[1])
        for j, sim in sims[:top_k]:
            key = tuple(sorted([facts[i]["id"], facts[j]["id"]]))
            if key not in seen:
                seen.add(key)
                pairs.append((facts[i]["id"], facts[j]["id"], sim))

    return pairs, facts

if __name__ == "__main__":
    import json
    pairs, facts = find_candidate_pairs()
    fact_by_id = {f["id"]: f for f in facts}

    output = []
    for a_id, b_id, sim in pairs:
        output.append({"fact_id_a": a_id, "fact_id_b": b_id, "similarity": float(sim)})

    with open("factlayer/data/candidate_pairs.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nFound {len(pairs)} candidate cross-document pairs.")
    print(f"Saved to factlayer/data/candidate_pairs.json")

    for a_id, b_id, sim in sorted(pairs, key=lambda x: -x[2])[:15]:
        a, b = fact_by_id[a_id], fact_by_id[b_id]
        print(f"[{sim:.3f}] {a['doc_id']} p{a['page']}: {a['subject']} | {a['attribute']} | {a['value']} {a['unit']} ({a['period']})")
        print(f"        {b['doc_id']} p{b['page']}: {b['subject']} | {b['attribute']} | {b['value']} {b['unit']} ({b['period']})")
        print()