from __future__ import annotations

import re

from heirs_navigator.domain import Chunk, Source

CLAUSE = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?|[A-Z][.)]|\([a-z0-9ivx]+\))\s+")
HEADING = re.compile(r"^(?:chapter|section|part|annexure|schedule)\b", re.I)


def _units(text: str) -> list[str]:
    """Keep numbered clauses and table rows together until the size cap requires a split."""
    units: list[str] = []
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                units.append(current.strip())
                current = ""
            continue
        if CLAUSE.match(stripped) or HEADING.match(stripped) or "|" in stripped:
            if current:
                units.append(current.strip())
            current = stripped
        else:
            current = f"{current} {stripped}".strip()
    if current:
        units.append(current.strip())
    return units


def chunk_page(
    source: Source, page: int, text: str, target: int = 300, max_tokens: int = 350
) -> list[Chunk]:
    if target <= 0 or max_tokens < target:
        raise ValueError("Invalid chunk sizes")
    chunks: list[Chunk] = []
    words: list[str] = []
    section = ""

    def emit() -> None:
        nonlocal words
        if words:
            chunks.append(
                Chunk(
                    chunk_id=f"{source.doc_id}#p{page}-c{len(chunks) + 1}",
                    doc_id=source.doc_id,
                    section=section,
                    page=page,
                    text=" ".join(words),
                    token_count=len(words),
                    issuer=source.issuer,
                    doc_type=source.doc_type,
                    bank=source.bank,
                    effective_date=source.effective_date,
                    status=source.status,
                )
            )
            words = []

    for unit in _units(text):
        if HEADING.match(unit) or CLAUSE.match(unit):
            section = unit.split(" ", 1)[0]
        unit_words = unit.split()
        if len(words) + len(unit_words) > max_tokens and words:
            emit()
        if len(unit_words) > max_tokens:
            for start in range(0, len(unit_words), max_tokens):
                words = unit_words[start : start + max_tokens]
                emit()
        else:
            words.extend(unit_words)
            if len(words) >= target:
                emit()
    emit()
    return chunks


def fixed_chunks(source: Source, page: int, text: str, size: int = 400) -> list[Chunk]:
    """Permanent naive baseline: fixed windows with no structure awareness."""
    words = text.split()
    return [
        Chunk(
            chunk_id=f"{source.doc_id}#p{page}-n{start // size + 1}",
            doc_id=source.doc_id,
            section="",
            page=page,
            text=" ".join(words[start : start + size]),
            token_count=len(words[start : start + size]),
            issuer=source.issuer,
            doc_type=source.doc_type,
            bank=source.bank,
            effective_date=source.effective_date,
            status=source.status,
        )
        for start in range(0, len(words), size)
    ]
