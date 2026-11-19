from __future__ import annotations

import hashlib
import json
import platform
import random
import statistics
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from heirs_navigator.domain import Evidence
from heirs_navigator.ingest.corpus import manifest_hash


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrap_ci(
    values: list[float], iterations: int = 2000, seed: int = 42
) -> tuple[float, float]:
    if not values:
        raise ValueError("Cannot score an empty sample")
    rng = random.Random(seed)
    samples = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(iterations)]
    samples.sort()
    return samples[int(iterations * 0.025)], samples[int(iterations * 0.975)]


def retrieval_scores(
    evidence: list[Evidence], gold_docs: list[str], k: int = 5
) -> dict[str, float]:
    if not gold_docs:
        raise ValueError("A gold question needs verified gold_docs")
    ranked = [item.chunk.doc_id for item in evidence[:k]]
    hits = [index + 1 for index, doc in enumerate(ranked) if doc in gold_docs]
    return {
        "hit_at_1": float(bool(ranked and ranked[0] in gold_docs)),
        "hit_at_5": float(bool(hits)),
        "mrr": 1 / min(hits) if hits else 0.0,
        "context_precision": sum(doc in gold_docs for doc in ranked) / len(ranked) if ranked else 0,
        "context_recall": len(set(ranked) & set(gold_docs)) / len(set(gold_docs)),
    }


def fingerprint(split: str, config: dict[str, Any]) -> dict[str, Any]:
    import subprocess

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    gold_path = Path("eval/gold_set.jsonl")
    index_path = Path("data/index/meta.json")
    return {
        "git_commit": git.stdout.strip() if git.returncode == 0 else None,
        "git_dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
        "python": platform.python_version(),
        "os": platform.platform(),
        "corpus_manifest_sha256": manifest_hash(Path("data/manifest.csv")),
        "index_sha256": sha256(index_path),
        "gold_sha256": sha256(gold_path),
        "split": split,
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "model_roles": config.get("models", {}),
    }


def lock_test_split(path: Path, lock: Path) -> None:
    questions = [json.loads(line) for line in path.read_text().splitlines() if line]
    ids = sorted(item["id"] for item in questions if item["split"] == "test")
    if not ids:
        raise ValueError("Cannot lock an empty test split")
    if lock.exists():
        raise FileExistsError("Test split is already locked")
    lock.write_text(hashlib.sha256(json.dumps(ids).encode()).hexdigest() + "\n")


def verify_test_lock(path: Path, lock: Path) -> None:
    questions = [json.loads(line) for line in path.read_text().splitlines() if line]
    ids = sorted(item["id"] for item in questions if item["split"] == "test")
    actual = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
    if not lock.exists() or lock.read_text().strip() != actual:
        raise ValueError("Test split lock missing or mismatched")


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2)


def compare_results(left: dict[str, Any], right: dict[str, Any]) -> None:
    for key in ("corpus_manifest_sha256", "gold_sha256", "split"):
        if left["fingerprint"][key] != right["fingerprint"][key]:
            raise ValueError(f"Incomparable result fingerprints: {key}")
    if left.get("judge") != right.get("judge"):
        raise ValueError("Incomparable judge settings")


ABLATIONS = (
    ("naive", True, False, False, False),
    ("chunking", False, False, False, False),
    ("hybrid", False, True, False, False),
    ("rerank", False, True, True, False),
    ("filters", False, True, True, True),
    ("agentic", False, True, True, True),
)


def score_questions(
    questions: list[dict[str, Any]], search: Any, *, agentic: bool = False
) -> list[dict[str, Any]]:
    from heirs_navigator.retrieval.hybrid import route_and_decompose

    records = []
    for question in questions:
        queries = route_and_decompose(question["question"]) if agentic else [question["question"]]
        evidence: list[Evidence] = []
        seen: set[str] = set()
        for query in queries:
            for item in search(query, question.get("bank")):
                if item.chunk.chunk_id not in seen:
                    evidence.append(item)
                    seen.add(item.chunk.chunk_id)
        records.append(
            {
                "id": question["id"],
                "scores": retrieval_scores(evidence[:5], question["gold_docs"]),
                "retrieved_ids": [item.chunk.chunk_id for item in evidence[:5]],
            }
        )
    return records


def evaluate(split: str) -> dict[str, Any]:
    """Stage A is disabled until the owner verifies the gold set and builds a corpus."""
    gold = Path("eval/gold_set.jsonl")
    if not gold.exists() or not gold.read_text().strip():
        raise ValueError("No owner-verified gold set. See docs/QUESTIONS.md.")
    if split == "test":
        verify_test_lock(gold, Path("eval/TEST_SPLIT.lock"))
    from heirs_navigator.ingest.index import load_index
    from heirs_navigator.retrieval.hybrid import HybridRetriever

    index_dir = Path("data/index")
    manifest = Path("data/manifest.csv")
    chunks, collection = load_index(index_dir, manifest)
    naive_chunks, naive_collection = load_index(index_dir, manifest, naive=True)
    retriever = HybridRetriever(chunks, collection)
    naive_retriever = HybridRetriever(naive_chunks, naive_collection)
    questions = [json.loads(line) for line in gold.read_text().splitlines() if line]
    selected = [question for question in questions if question["split"] == split]
    if not selected:
        raise ValueError(f"No verified {split} questions")
    variants = ABLATIONS if split == "dev" else (ABLATIONS[0], ABLATIONS[4])
    results: dict[str, str] = {}
    for variant, naive, hybrid, rerank, filters in variants:
        if split == "test" and list(Path("eval/results/A1").glob(f"*_{variant}_test.json")):
            raise ValueError(f"Official test result for {variant} already exists")
        pipeline = naive_retriever if naive else retriever

        search = partial(
            pipeline.search,
            top_k=4 if naive else 5,
            use_dense=True,
            use_bm25=hybrid,
            use_rerank=rerank,
            use_filters=filters,
        )

        per_question = score_questions(selected, search, agentic=variant == "agentic")
        metrics = {}
        for metric in ("hit_at_1", "hit_at_5", "mrr", "context_precision", "context_recall"):
            values = [record["scores"][metric] for record in per_question]
            metrics[metric] = {"value": statistics.mean(values), "ci95": bootstrap_ci(values)}
        run_id = "A1_" + variant + "_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        result = {
            "run_id": run_id,
            "metric_id": "A1",
            "variant": variant,
            "split": split,
            "n": len(selected),
            "created_at": datetime.now(UTC).isoformat(),
            "fingerprint": fingerprint(
                split, {"variant": variant, "hybrid": hybrid, "rerank": rerank, "filters": filters}
            ),
            "metrics": metrics,
            "tokens": {"total": 0},
            "judge": None,
            "per_question": per_question,
        }
        path = Path("eval/results/A1") / f"{run_id}_{variant}_{split}.json"
        write_result(path, result)
        results[variant] = str(path)
    return {"result_files": results, "n": len(selected)}


def generate_ablation_report(results_dir: Path, destination: Path) -> Path:
    """Render only saved harness results; never fill missing rows with estimated numbers."""
    files = sorted(results_dir.glob("A1/*.json"))
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    dev = [run for run in runs if run.get("metric_id") == "A1" and run.get("split") == "dev"]
    if dev:
        baseline = dev[0]
        for run in dev[1:]:
            compare_results(baseline, run)
    latest = {run["variant"]: run for run in dev}
    lines = [
        "# Stage A retrieval ablations",
        "",
        "Generated from immutable result files.",
        "",
        "| Variant | N | Hit@5 (95% CI) | MRR (95% CI) | Result file |",
        "|---|---:|---:|---:|---|",
    ]
    for variant, *_ in ABLATIONS:
        run = latest.get(variant)
        if run is None:
            lines.append(f"| {variant} | — | pending | pending | — |")
            continue

        lines.append(
            f"| {variant} | {run['n']} | {_format_metric(run, 'hit_at_5')} | "
            f"{_format_metric(run, 'mrr')} | `{run['run_id']}` |"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def _format_metric(run: dict[str, Any], metric: str) -> str:
    item = run["metrics"][metric]
    return f"{item['value']:.3f} [{item['ci95'][0]:.3f}, {item['ci95'][1]:.3f}]"
