import json
import os
import sys
import time
from pathlib import Path
from google import genai
from dotenv import load_dotenv

load_dotenv("factlayer/.env")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM_PROMPT = """You extract discrete factual claims from chunks of a financial or economic document.

You will be given several labeled blocks, each marked like:
=== BLOCK: <block_id> ===
<text>

For EACH block, extract facts as objects with these fields:
- subject: the entity the fact is about (e.g. "Delhivery Limited", "India")
- attribute: what is being measured (e.g. "FY24 revenue from services")
- value: the raw value AS WRITTEN (e.g. "8,142", "12.7%")
- unit: unit if any (e.g. "INR Cr", "%") or null
- period: time period if stated (e.g. "FY2024", "Q4 FY24") or null
- scope: qualifier on what's included/excluded, or null
- basis: accounting/methodology basis if stated (e.g. "adjusted"), or null
- evidence_text: a VERBATIM substring copied exactly from THAT block's text. Must match character-for-character.
- confidence: "high" if stated plainly, "low" if from an ambiguous chart/table

Skip boilerplate, disclaimers, table of contents, page headers.

Return ONLY a single JSON object mapping each block_id to its array of facts, like:
{"block_id_1": [ {...fact...}, {...fact...} ], "block_id_2": [] }

Include EVERY block_id you were given, even if its array is empty. Nothing else in your response."""

def make_groups(blocks, char_budget=15000):
    groups, current, current_len = [], [], 0
    for b in blocks:
        blen = len(b["text"])
        if current and current_len + blen > char_budget:
            groups.append(current)
            current, current_len = [], 0
        current.append(b)
        current_len += blen
    if current:
        groups.append(current)
    return groups

def extract_facts_from_group(group, max_retries=3):
    """Returns a list of facts on success, or None if all retries failed
    (caller must NOT checkpoint a None result as done)."""
    block_map = {b["block_id"]: b for b in group}
    prompt_parts = [SYSTEM_PROMPT, ""]
    for b in group:
        prompt_parts.append(f"=== BLOCK: {b['block_id']} ===\n{b['text']}\n")
    full_prompt = "\n".join(prompt_parts)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)

            valid_facts = []
            for block_id, facts in parsed.items():
                block = block_map.get(block_id)
                if not block:
                    continue
                for f in facts:
                    if f.get("evidence_text") and f["evidence_text"] in block["text"]:
                        f["doc_id"] = block["doc_id"]
                        f["page"] = block["page"]
                        f["block_id"] = block["block_id"]
                        valid_facts.append(f)
                    else:
                        print(f"  [dropped: not verbatim] {f.get('attribute')}")
            return valid_facts
        except json.JSONDecodeError:
            print(f"  [retry {attempt+1}] bad JSON from group ({len(group)} blocks)")
            time.sleep(5)
        except Exception as e:
            print(f"  [error] {e}")
            time.sleep(10)
    return None  # total failure — caller must retry later, not mark as done

def load_checkpoint(checkpoint_path):
    done_ids, facts = set(), []
    if not os.path.exists(checkpoint_path):
        return done_ids, facts
    with open(checkpoint_path) as f:
        for line in f:
            entry = json.loads(line)
            done_ids.update(entry["block_ids"])
            facts.extend(entry["facts"])
    return done_ids, facts

def append_checkpoint(checkpoint_path, block_ids, facts):
    with open(checkpoint_path, "a") as f:
        f.write(json.dumps({"block_ids": block_ids, "facts": facts}) + "\n")

def extract_facts_from_doc(blocks_json_path, doc_id):
    with open(blocks_json_path) as f:
        blocks = json.load(f)
    blocks = [b for b in blocks if len(b["text"].strip()) >= 20]

    checkpoint_path = f"factlayer/data/{doc_id}_checkpoint.jsonl"
    done_ids, all_facts = load_checkpoint(checkpoint_path)
    if done_ids:
        print(f"Resuming: {len(done_ids)} blocks already done from checkpoint.")

    remaining = [b for b in blocks if b["block_id"] not in done_ids]
    groups = make_groups(remaining)
    print(f"{len(remaining)} blocks left, in {len(groups)} groups.")

    failed_groups = 0
    for i, g in enumerate(groups):
        block_ids = [b["block_id"] for b in g]
        facts = extract_facts_from_group(g)
        if facts is None:
            failed_groups += 1
            print(f"[{i+1}/{len(groups)}] group FAILED — not checkpointed, will retry next run")
            continue
        append_checkpoint(checkpoint_path, block_ids, facts)
        all_facts.extend(facts)
        print(f"[{i+1}/{len(groups)}] group done ({len(block_ids)} blocks, {len(facts)} facts)")
        if i < len(groups) - 1:
            time.sleep(2)

    if failed_groups:
        print(f"\n{failed_groups} group(s) failed completely — run this same command again to retry them.")

    return all_facts

if __name__ == "__main__":
    blocks_path = sys.argv[1]
    doc_id = Path(blocks_path).stem.replace("_blocks", "")
    facts = extract_facts_from_doc(blocks_path, doc_id)
    print(f"\nExtracted {len(facts)} total facts from {doc_id}")
    out_path = f"factlayer/data/{doc_id}_facts.json"
    with open(out_path, "w") as f:
        json.dump(facts, f, indent=2)
    print(f"Saved to {out_path}")