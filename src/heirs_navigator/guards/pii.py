from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer

PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+91[-\s]?)?[6-9]\d{9}(?!\d)")
ACCOUNT = re.compile(r"\b\d{9,18}\b")
AADHAAR = re.compile(r"(?<!\d)(?:\d{4}[ -]?){2}\d{4}(?!\d)")
_TABLE = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_PERM = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def valid_aadhaar(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 12 or digits[0] in "01":
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        checksum = _TABLE[checksum][_PERM[index % 8][int(digit)]]
    return checksum == 0


class PIIMasker:
    """Token map stays in process memory. Persisted strings contain only typed tokens."""

    def __init__(self) -> None:
        self.tokens: dict[str, str] = {}

        class AadhaarRecognizer(PatternRecognizer):
            def validate_result(self, pattern_text: str) -> bool:
                return valid_aadhaar(pattern_text)

        self.recognizers = [
            (
                AadhaarRecognizer(
                    supported_entity="AADHAAR", patterns=[Pattern("aadhaar", AADHAAR.pattern, 0.5)]
                ),
                "AADHAAR",
            ),
            (
                PatternRecognizer(
                    supported_entity="PAN", patterns=[Pattern("pan", PAN.pattern, 0.8)]
                ),
                "PAN",
            ),
            (
                PatternRecognizer(
                    supported_entity="EMAIL", patterns=[Pattern("email", EMAIL.pattern, 0.8)]
                ),
                "EMAIL",
            ),
            (
                PatternRecognizer(
                    supported_entity="PHONE", patterns=[Pattern("phone", PHONE.pattern, 0.8)]
                ),
                "PHONE",
            ),
            (
                PatternRecognizer(
                    supported_entity="ACCOUNT", patterns=[Pattern("account", ACCOUNT.pattern, 0.6)]
                ),
                "ACCOUNT",
            ),
        ]

    def mask(self, text: str) -> str:
        for recognizer, kind in self.recognizers:
            matches = recognizer.analyze(text, entities=[kind])
            for match in sorted(matches, key=lambda x: x.start, reverse=True):
                value = text[match.start : match.end]
                token = self.tokens.setdefault(value, f"[PII_{kind}_{len(self.tokens) + 1}]")
                text = text[: match.start] + token + text[match.end :]
        return text

    def has_unmasked_pii(self, text: str) -> bool:
        return self.mask(text) != text
