from __future__ import annotations

from datetime import date

from heirs_navigator.domain import Chunk, Evidence
from heirs_navigator.retrieval.hybrid import eligible, tokenize

DEMO_CASES = {
    "savings_nominee": {"bank": "Example Bank", "product": "savings", "nominee_exists": True},
    "fd_no_nominee": {"bank": "Example Bank", "product": "fd", "nominee_exists": False},
    "locker_dispute": {"bank": "Example Bank", "product": "locker", "dispute": True},
}

DEMO_CHUNKS = [
    Chunk(
        chunk_id="synthetic-savings#p1-c1",
        doc_id="synthetic-savings",
        section="1",
        page=1,
        text="Synthetic example for savings deposit claim; document: death certificate; "
        "document: bank claim form; document: claimant identity proof",
        token_count=17,
        issuer="Synthetic fixture",
        doc_type="demo",
        bank="Example Bank",
        effective_date=date(2026, 1, 1),
        status="final",
    ),
    Chunk(
        chunk_id="synthetic-fd#p1-c1",
        doc_id="synthetic-fd",
        section="1",
        page=1,
        text="Synthetic example for fixed deposit claim; document: death certificate; "
        "document: bank claim form; document: claimant identity proof",
        token_count=18,
        issuer="Synthetic fixture",
        doc_type="demo",
        bank="Example Bank",
        effective_date=date(2026, 1, 1),
        status="final",
    ),
    Chunk(
        chunk_id="synthetic-locker#p1-c1",
        doc_id="synthetic-locker",
        section="1",
        page=1,
        text="Synthetic example for locker claim; document: death certificate; "
        "document: bank claim form; document: claimant identity proof",
        token_count=17,
        issuer="Synthetic fixture",
        doc_type="demo",
        bank="Example Bank",
        effective_date=date(2026, 1, 1),
        status="final",
    ),
]


def demo_search(question: str, bank: str | None = None) -> list[Evidence]:
    words = set(tokenize(question))
    chunks = eligible(DEMO_CHUNKS, bank)
    if "fd" in words or "fixed" in words:
        doc = "synthetic-fd"
    elif "locker" in words:
        doc = "synthetic-locker"
    else:
        doc = "synthetic-savings"
    return [Evidence(chunk=c, rrf_score=1) for c in chunks if c.doc_id == doc]
