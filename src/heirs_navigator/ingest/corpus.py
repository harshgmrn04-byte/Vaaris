from __future__ import annotations

import csv
import hashlib
from datetime import date
from pathlib import Path

import httpx
import pymupdf as fitz
import yaml
from bs4 import BeautifulSoup

from heirs_navigator.domain import Source

MANIFEST_COLUMNS = [
    "doc_id",
    "title",
    "issuer",
    "doc_type",
    "url",
    "retrieved_date",
    "effective_date",
    "status",
    "bank",
    "file_path",
    "sha256",
    "ocr_applied",
    "redistribution",
    "notes",
]


def load_sources(path: Path) -> list[Source]:
    records = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    sources = [Source.model_validate(item) for item in records]
    ids = [item.doc_id for item in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source doc_id")
    return sources


def manifest_hash(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing manifest: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        if not all(
            row.get(key) for key in ("doc_id", "effective_date", "status", "redistribution")
        ):
            raise ValueError("Manifest lacks a required field")
        if row["status"] not in ("final", "draft", "superseded"):
            raise ValueError("Invalid source status")
        if row["redistribution"] not in ("public_ok", "fetch_only", "unclear"):
            raise ValueError("Invalid redistribution status")
        date.fromisoformat(row["effective_date"])
    return rows


def fetch_sources(sources: list[Source], raw_dir: Path, manifest: Path) -> list[str]:
    """Fetch only declared URLs. Never commit the downloaded text without review."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    rows = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for source in sources:
            try:
                response = client.get(source.url)
                response.raise_for_status()
                data = response.content
                suffix = ".pdf" if data.startswith(b"%PDF") else ".html"
                path = raw_dir / f"{source.doc_id}{suffix}"
                path.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                notes = ""
            except (httpx.HTTPError, OSError) as exc:
                path = Path("")
                digest = ""
                notes = type(exc).__name__
                missing.append(source.doc_id)
            rows.append(
                {
                    **source.model_dump(mode="json"),
                    "retrieved_date": date.today().isoformat(),
                    "file_path": str(path) if digest else "",
                    "sha256": digest,
                    "ocr_applied": "false",
                    "notes": notes,
                }
            )
    with manifest.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    if missing:
        (manifest.parent / "MISSING.md").write_text(
            "# Manual download needed\n\n" + "\n".join(f"- {x}" for x in missing) + "\n"
        )
    return missing


def parse_pages(path: Path) -> list[tuple[int, str]]:
    if path.suffix.lower() == ".pdf":
        with fitz.open(path) as document:
            pages = [(number + 1, page.get_text("text")) for number, page in enumerate(document)]
        if not any(text.strip() for _, text in pages):
            raise ValueError(f"Scanned PDF requires OCR before indexing: {path}")
        return pages
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return [(1, soup.get_text("\n", strip=True))]
