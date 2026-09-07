import fitz  # pymupdf
import pdfplumber
import json
import sys
from pathlib import Path

def extract_pdf(pdf_path: str, doc_id: str):
    blocks = []

    # text via pymupdf, chunked per page
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        if not text:
            continue
        # simple chunking: split page text into ~1500 char pieces on paragraph breaks
        chunks = chunk_text(text, max_len=1500)
        for i, chunk in enumerate(chunks):
            blocks.append({
                "doc_id": doc_id,
                "page": page_num + 1,
                "block_id": f"{doc_id}_p{page_num+1}_t{i}",
                "kind": "text",
                "text": chunk
            })
    doc.close()

    # tables via pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                table_text = table_to_text(table)
                if table_text.strip():
                    blocks.append({
                        "doc_id": doc_id,
                        "page": page_num + 1,
                        "block_id": f"{doc_id}_p{page_num+1}_tbl{t_idx}",
                        "kind": "table",
                        "text": table_text
                    })
    return blocks

def chunk_text(text, max_len=1500):
    paras = text.split("\n\n")
    chunks, current = [], ""
    for p in paras:
        if len(current) + len(p) > max_len and current:
            chunks.append(current.strip())
            current = p
        else:
            current += "\n\n" + p if current else p
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]

def table_to_text(table):
    rows = []
    for row in table:
        cells = [c if c else "" for c in row]
        rows.append(" | ".join(cells))
    return "\n".join(rows)

if __name__ == "__main__":
    pdf_path = sys.argv[1]
    doc_id = Path(pdf_path).stem
    blocks = extract_pdf(pdf_path, doc_id)
    print(f"Extracted {len(blocks)} blocks from {doc_id}")
    for b in blocks[:5]:
        print(f"--- page {b['page']} ({b['kind']}) ---")
        print(b['text'][:200])
        print()
    out_path = f"factlayer/data/{doc_id}_blocks.json"
    with open(out_path, "w") as f:
        json.dump(blocks, f, indent=2)
    print(f"Saved to {out_path}")