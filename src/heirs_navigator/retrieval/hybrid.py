from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from rank_bm25 import BM25Okapi

from heirs_navigator.domain import Chunk, Evidence
from heirs_navigator.ingest.index import EMBEDDING_MODEL

RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


def eligible(chunks: Sequence[Chunk], bank: str | None = None) -> list[Chunk]:
    bank_lower = bank.casefold() if bank else None
    return [
        c
        for c in chunks
        if c.status == "final" and (not bank_lower or not c.bank or c.bank.casefold() == bank_lower)
    ]


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)
    return scores


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


_GENERIC = {
    "what",
    "which",
    "where",
    "when",
    "how",
    "the",
    "for",
    "from",
    "with",
    "have",
    "need",
    "claim",
    "claims",
    "bank",
    "deceased",
    "customer",
    "documents",
    "document",
    "account",
    "accounts",
    "process",
    "steps",
}


def evidence_sufficient(query: str, evidence: list[Evidence]) -> bool:
    if not evidence:
        return False
    terms = {term for term in tokenize(query) if len(term) > 3 and term not in _GENERIC}
    if not terms:
        return True
    return any(terms & set(tokenize(item.chunk.text)) for item in evidence)


class HybridRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        collection: object,
        *,
        embedder: object | None = None,
        reranker: object | None = None,
    ) -> None:
        self.chunks = chunks
        self.collection = collection
        self._embedder = embedder
        self._reranker = reranker

    @property
    def embedder(self) -> object:
        if self._embedder is None:
            self._embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
        return self._embedder

    @property
    def reranker(self) -> object:
        if self._reranker is None:
            self._reranker = TextCrossEncoder(model_name=RERANK_MODEL)
        return self._reranker

    def search(
        self,
        query: str,
        bank: str | None = None,
        *,
        top_k: int = 4,
        use_dense: bool = True,
        use_bm25: bool = True,
        use_rerank: bool = True,
        use_filters: bool = True,
    ) -> list[Evidence]:
        candidates = eligible(self.chunks, bank) if use_filters else self.chunks
        if not candidates:
            return []
        by_id = {c.chunk_id: c for c in candidates}
        rankings: list[list[str]] = []
        if use_dense:
            vector = next(iter(self.embedder.query_embed(query))).tolist()  # type: ignore[attr-defined]
            where: dict[str, Any] | None = None
            if use_filters:
                where = {"status": "final"}
                if bank:
                    canonical_bank = next(
                        (
                            c.bank
                            for c in candidates
                            if c.bank and c.bank.casefold() == bank.casefold()
                        ),
                        bank,
                    )
                    where = {
                        "$and": [
                            {"status": "final"},
                            {"$or": [{"bank": ""}, {"bank": canonical_bank}]},
                        ]
                    }
            result = self.collection.query(  # type: ignore[attr-defined]
                query_embeddings=[vector],
                n_results=min(len(candidates), max(20, top_k * 5)),
                include=["metadatas"],
                where=where,
            )
            rankings.append([cid for cid in result["ids"][0] if cid in by_id])
        if use_bm25:
            corpus = [tokenize(c.text) or [""] for c in candidates]
            bm25 = BM25Okapi(corpus)
            scores = bm25.get_scores(tokenize(query))
            order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
            rankings.append([candidates[i].chunk_id for i in order[: max(20, top_k * 5)]])
        if not rankings:
            raise ValueError("Enable at least one retrieval mode")
        fused = reciprocal_rank_fusion(rankings)
        ordered = sorted(
            fused, key=lambda cid: (fused[cid], by_id[cid].effective_date), reverse=True
        )
        shortlist = ordered[: max(20, top_k * 5)]
        rerank_scores: dict[str, float] = {}
        if use_rerank and shortlist:
            values = list(
                self.reranker.rerank(  # type: ignore[attr-defined]
                    query, [by_id[cid].text for cid in shortlist]
                )
            )
            rerank_scores = dict(zip(shortlist, map(float, values), strict=True))
            shortlist.sort(
                key=lambda cid: (rerank_scores[cid], by_id[cid].effective_date), reverse=True
            )
        return [
            Evidence(chunk=by_id[cid], rrf_score=fused[cid], rerank_score=rerank_scores.get(cid))
            for cid in shortlist[:top_k]
        ]


def route_and_decompose(question: str) -> list[str]:
    """Deterministic fallback router: split independent questions without model calls."""
    parts = [x.strip(" .?") for x in re.split(r"\?\s+|;\s+", question) if x.strip(" .?")]
    return parts[:3] or [question]


def retrieve_with_retry(
    search: Callable[[str], list[Evidence]], question: str, *, max_retries: int = 2
) -> list[Evidence]:
    evidence: list[Evidence] = []
    for attempt in range(max_retries + 1):
        if attempt == 0:
            query = question
        elif attempt == 1:
            query = f"deceased bank customer claim {question} documents"
        else:
            query = f"RBI settlement directions {question} claim form death certificate"
        evidence = search(query)
        if evidence_sufficient(question, evidence):
            return evidence
    return []
