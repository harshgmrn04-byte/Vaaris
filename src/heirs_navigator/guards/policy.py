from __future__ import annotations

import re
from difflib import SequenceMatcher

from heirs_navigator.domain import Checklist, Evidence

INJECTION = re.compile(
    r"ignore (?:all |the |previous )?(?:instructions|rules)|"
    r"system prompt|developer message|you are now|reveal (?:secrets|api key)|"
    r"<\|im_start\|>|\[INST\]|act as (?:a )?system",
    re.I,
)
OUT_OF_SCOPE = re.compile(
    r"who (?:legally )?inherits|who (?:should|will) inherit|contest (?:the )?will|"
    r"win (?:the )?dispute|draft (?:a )?(?:legal notice|will|affidavit)|"
    r"tax (?:liability|advice)|avoid (?:inheritance )?tax",
    re.I,
)


def screen_input(text: str) -> str | None:
    if INJECTION.search(text):
        return "prompt_injection"
    if OUT_OF_SCOPE.search(text):
        return "legal_advice"
    return None


def validate_citations(checklist: Checklist, evidence: list[Evidence]) -> list[str]:
    allowed = {item.chunk.chunk_id for item in evidence}
    cited = checklist.citation_ids + [cid for item in checklist.items for cid in item.citation_ids]
    return [cid for cid in cited if cid not in allowed]


def validate_quote(quote: str, evidence: Evidence, threshold: float = 0.85) -> bool:
    if quote.casefold() in evidence.chunk.text.casefold():
        return True
    return (
        SequenceMatcher(None, quote.casefold(), evidence.chunk.text.casefold()).ratio() >= threshold
    )


def should_escalate(evidence: list[Evidence], *, dispute: bool = False) -> str | None:
    if dispute:
        return "A dispute requires review by the bank or a qualified adviser."
    if not evidence:
        return "The verified corpus does not contain enough evidence for this case."
    return None
