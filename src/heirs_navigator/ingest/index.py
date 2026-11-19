from __future__ import annotations

import json
from pathlib import Path

import chromadb
from fastembed import TextEmbedding

from heirs_navigator.domain import Chunk, Source
from heirs_navigator.ingest.chunk import chunk_page, fixed_chunks
from heirs_navigator.ingest.corpus import manifest_hash, parse_pages, read_manifest

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def build_index(manifest: Path, index_dir: Path) -> int:
    rows = read_manifest(manifest)
    chunks: list[Chunk] = []
    naive_chunks: list[Chunk] = []
    for row in rows:
        path = Path(row["file_path"])
        if not path.is_file():
            continue
        source = Source.model_validate({key: row[key] for key in Source.model_fields})
        for page, text in parse_pages(path):
            chunks.extend(chunk_page(source, page, text))
            naive_chunks.extend(fixed_chunks(source, page, text))
    if not chunks:
        raise ValueError("No parsed corpus documents; fetch and verify sources first")
    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
    encoder = TextEmbedding(model_name=EMBEDDING_MODEL)
    existing = {collection.name for collection in client.list_collections()}
    for name, records in (("claims", chunks), ("claims_naive", naive_chunks)):
        if name in existing:
            client.delete_collection(name)
        collection = client.create_collection(name, metadata={"hnsw:space": "cosine"})
        for start in range(0, len(records), 100):
            batch = records[start : start + 100]
            vectors = [x.tolist() for x in encoder.passage_embed([c.text for c in batch])]
            collection.add(
                ids=[c.chunk_id for c in batch],
                embeddings=vectors,
                documents=[c.text for c in batch],
                metadatas=[
                    {
                        **c.model_dump(mode="json", exclude={"text"}),
                        "effective_date": c.effective_date.isoformat(),
                    }
                    for c in batch
                ],
            )
        filename = "chunks.jsonl" if name == "claims" else "chunks_naive.jsonl"
        (index_dir / filename).write_text(
            "".join(json.dumps(c.model_dump(mode="json")) + "\n" for c in records),
            encoding="utf-8",
        )
    (index_dir / "meta.json").write_text(
        json.dumps(
            {
                "manifest_sha256": manifest_hash(manifest),
                "embedding_model": EMBEDDING_MODEL,
                "chunk_count": len(chunks),
                "naive_chunk_count": len(naive_chunks),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(chunks)


def load_index(
    index_dir: Path, manifest: Path, *, naive: bool = False
) -> tuple[list[Chunk], object]:
    meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))
    if meta["manifest_sha256"] != manifest_hash(manifest):
        raise ValueError("Corpus manifest changed. Run `make index` before starting the app.")
    filename = "chunks_naive.jsonl" if naive else "chunks.jsonl"
    chunks = [
        Chunk.model_validate_json(line)
        for line in (index_dir / filename).read_text(encoding="utf-8").splitlines()
    ]
    name = "claims_naive" if naive else "claims"
    collection = chromadb.PersistentClient(path=str(index_dir / "chroma")).get_collection(name)
    return chunks, collection
