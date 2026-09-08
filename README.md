# Fact Knowledge Layer

A system that extracts grounded facts from PDFs, links related facts across
documents, and classifies their relationship as corroborating, contradicting,
or reconcilable — with every fact traceable to its exact source page and
evidence text.

## Setup and Run Instructions

**Requirements:** Python 3.10+, a Gemini API key (billing enabled recommended
for reasonable throughput — see Limitations).

```bash
git clone <this repo>
cd superjoin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `factlayer/.env`:GEMINI_API_KEY=your_key_here
Place PDFs in `factlayer/data/`. Run the pipeline per document:
```bash
python factlayer/ingest.py factlayer/data/<your-file>.pdf
python factlayer/extract.py factlayer/data/<your-file>_blocks.json
python factlayer/store.py          # loads all *_facts.json into SQLite
python factlayer/link.py           # finds candidate cross-document pairs
python factlayer/adjudicate.py 100 # classifies top N pairs (raise N for more coverage)
```

Launch the UI:
```bash
streamlit run factlayer/app.py
```
Upload a new PDF directly from the sidebar to run ingest + extract on it live;
then run `link.py` / `adjudicate.py` from the terminal to find its
relationships to existing facts.
Note: the repo already includes committed `*_facts.json` outputs from a full
run on the starter dataset, plus a findings summary
(`factlayer/data/findings.md`), so results can be inspected without needing
your own API key or billing set up. Run `python factlayer/store.py` once
after cloning to build the local `facts.db` from these committed outputs
before launching the UI — this needs no API key, since it only reads the
already-extracted JSON.

## Video Demo
[link to be added]

## Approach

**Pipeline:** `ingest.py` -> `extract.py` -> `normalize.py` -> `store.py` ->
`link.py` -> `adjudicate.py`.

- **Ingest** (PyMuPDF + pdfplumber): splits each PDF into page-anchored text
  and table blocks, preserving physical page numbers for citation, chosen
  over each document's own printed page numbers since printed numbering
  varies per document and physical page number is what any PDF viewer shows.
- **Extract** (Gemini 2.5 Flash): one LLM call per group of blocks, returns
  structured facts (subject, attribute, value, unit, period, scope, basis,
  evidence_text, confidence). Every evidence_text is verified as an exact
  substring of its source block before being accepted; facts with
  paraphrased or invented evidence are dropped rather than trusted. This
  trades recall for a hard grounding guarantee.
- **Normalize** (pure Python): converts raw values into comparable numbers
  (Cr/Mn/Lakh to INR millions, correctly distinguishing currency from bare
  counts), fiscal periods into ISO date ranges (India's Apr-Mar fiscal year),
  and subject names into a canonical form for matching across naming
  variants.
- **Store** (SQLite): a single facts table across all documents, plus a
  relations table for adjudicated pairs.
- **Link** (embedding similarity): each fact's subject + attribute + period
  + scope (deliberately excluding value) is embedded; cross-document facts
  above a similarity threshold become candidate pairs. Excluding the value
  from the embedded string was deliberate: two facts about the same thing
  with different values (a contradiction) should still be found as similar,
  since only their meaning, not their number, should drive matching.
- **Adjudicate** (Gemini 2.5 Flash): each candidate pair is classified as
  CORROBORATES / CONTRADICTS / RECONCILABLE / UNRELATED with a written
  reason citing the specific values/context.

**AI tools used:** Claude (Anthropic) for architecture, debugging, and code
generation throughout; Gemini 2.5 Flash for extraction and adjudication
(switched from Anthropic and briefly Groq mid-project due to rate limits,
see Limitations).

**The four required cases** (full detail in factlayer/data/findings.md):

1. **Corroborated:** FY24 revenue, INR 8,142 Cr (earnings deck) = INR 81,415
   Mn (annual report), same figure, different units, correctly normalized to
   match.
2. **Contradiction explained by context:** Donald Francis Colleran is listed
   as an active Non-Executive Nominee Director in the 2022 prospectus, but
   the FY24 annual report states he "ceased to be a Director with effect
   from September 27, 2023." Resolved by time: he resigned between the two
   documents.
3. **Apparent contradiction explained by context:** the company's CIN
   changes from U63090DL2011PLC221234 (prospectus) to L63090DL2011PLC221234
   (annual report). Under India's MCA scheme the first letter encodes
   listing status (U=unlisted, L=listed); the prospectus itself confirms
   shares were "proposed to be listed" at time of writing, the IPO it
   describes explains the change.
4. **Extraction failure:** FY23 EBITDA was extracted as "INR 4,516 million"
   (positive) when the source stated "a loss of INR 4,516 million", the
   model captured the magnitude but dropped the sign encoded only in prose,
   not notation. Caught via adjudication reasoning when compared against the
   deck's correctly-negative "(452) Cr" for the same fact.

## Limitations and Next Steps

- **Extraction recall vs. precision:** the strict verbatim-evidence check
  drops many true facts when the model paraphrases rather than quotes,
  especially in narrative/ESG sections. A future version could ask for a
  best-effort quote and fall back to a shorter verified fragment instead of
  discarding the whole fact.
- **Sign/direction loss:** see Case 4 above. Fix: add an explicit direction
  field to the extraction schema, populated whenever the source describes a
  loss, decline, or deficit in prose.
- **Large table truncation:** a handful of dense tables (share-allotment,
  cost-driver breakdowns) exceeded the model's output token budget mid-JSON
  and were dropped after retries rather than partially corrupted. Next step:
  auto-split oversized blocks by row before extraction.
- **Provider instability:** mid-project, Anthropic usage hit a limit,
  Gemini's free tier had aggressive per-minute/per-day caps, and Groq
  deprecated the model we'd switched to; we ultimately settled on Gemini
  with billing enabled (Tier 1), which later ran out of prepaid credit. A
  more resilient version would abstract the LLM call behind a
  provider-agnostic interface with automatic failover.
- **India macroeconomy dataset partially processed:** RBI Annual Report was
  fully processed (377 facts). Economic Survey and IMF Article IV were not
  attempted before API credits were exhausted. This does not affect any of
  the four required cases, which are drawn entirely from the Delhivery
  dataset. Pipeline logic is identical and would process these documents
  the same way given more API budget.
- **Linking by embedding similarity misses some matches:** named-person
  facts (e.g. director status) didn't score highly enough via embedding
  similarity to surface automatically; the Colleran case was found via a
  targeted SQL query, not the automated linking step. A production version
  would add rule-based candidate generation (e.g. same person name, both
  docs, any attribute) alongside embedding similarity.
- **Schema is currently fixed, not fully dynamic:** attribute is free text,
  which lets new fact types appear without a schema migration, but there is
  no explicit mechanism yet for evolving structured fields as new categories
  of fact emerge.

## Additional Notes

Built end-to-end with Claude assisting on every step: architecture
decisions, debugging live API errors across three LLM providers, and code
review throughout.
