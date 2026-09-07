# Required Cases — Findings Summary

## Case 1: Corroborated Fact
**FY24 Revenue from Services**
- Earnings deck (p5): ₹8,142 Cr
- Annual report (p4): ₹81,415 Mn
- Normalized: both = ₹81,420 million (within rounding)
- Verdict: CORROBORATES

## Case 2/3: Contradiction Explained by Context — Director Status
**Donald Francis Colleran**
- Prospectus (May 2022, p87): "Donald Francis Colleran is a Non-Executive Nominee
  Director of our Company as a nominee of FedEx." DIN 00754512, director since
  March 1, 2016, five-year term from October 1, 2021.
- Annual Report FY24 (p43, footnote 2): "Mr. Donald Francis Colleran ceased to be
  a Director with effect from September 27, 2023."
- Apparent contradiction (active vs. not a director) explained by time — he
  resigned in the ~16 months between the two documents' publication dates.
- Verdict: RECONCILABLE
- Stored as fact IDs 458 (prospectus) and 1229 (annual report), relation saved
  in `relations` table.

## Case 3 (additional): Corporate Identity Number Change
- Prospectus (2022, p1, p30): CIN = U63090DL2011PLC221234
- Annual Report FY24 (p76, p78): CIN = L63090DL2011PLC221234
- Same registration number; only the first letter changed (U → L).
- Under India's MCA CIN scheme, U = unlisted, L = listed.
- Prospectus itself states (p1): shares "are proposed to be listed" — i.e. NOT
  YET listed at time of writing.
- Explained by context: the IPO (documented in this very prospectus) completed,
  changing Delhivery's listing status between the two documents.
- Verdict: RECONCILABLE

## Case 3 (additional): EBITDA Metric/Period Variants
- Q4 FY24 EBITDA (₹46 Cr) vs full FY24 EBITDA (₹1,266 Mn / ₹126.6 Cr):
  reconciled as quarter vs. full-year figures (quarters sum to the year).
- Adjusted EBITDA (₹76 Cr) vs standard/reported EBITDA (₹1,266 Mn):
  reconciled as different metric definitions (adjustments explain the gap).

## Case 4: Extraction/Reasoning Failure
**Sign-loss on FY23 EBITDA**
- Annual report source text: "Our EBITDA improved from a loss of ₹4,516 million
  in FY23 to a profit of ₹1,266 million in FY24."
- Extracted value: "₹4,516 million" (positive) — lost the "loss of" semantic,
  should have been -4,516.
- Root cause: extraction prompt captures magnitude from evidence_text but does
  not explicitly encode direction/sign when the source states it via prose
  ("a loss of X") rather than notation ("(X)" or "-X").
- How we caught it: link.py's embedding similarity correctly matched this fact
  against the deck's "(452) Cr" (properly negative), and adjudicate.py's
  RECONCILABLE reasoning explained the sign convention — surfacing the
  extraction gap during manual review of that adjudication.
- Improvement: add explicit sign/direction handling to the extraction prompt,
  or a separate `direction` field independent of raw magnitude.

**Secondary Case 4 example: table truncation**
- Two dense financial tables (prospectus p12 share-allotment table, p99 KMP
  attrition table; annual report cost-drivers table) failed extraction after
  3 retries — JSON output exceeded the model's max_tokens mid-generation.
- Handled by: checkpointing marks these as failed (not silently empty) so they
  can be retried; documented as a known limitation rather than silently dropped.
- Improvement: auto-split oversized table blocks row-wise before extraction.