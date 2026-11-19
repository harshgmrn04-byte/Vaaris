# Vaaris: Claims Navigator

Vaaris is a Python prototype for **synthetic** deceased-customer bank claim cases in India. It is intended to produce cited document checklists and hand off uncertain or disputed cases. It is **not legal advice** and should not receive real personal data.

The two design documents in this repository are the project specification. This implementation covers the principal architecture paths but is not a completed public release: the full official corpus, owner-verified gold set, measured ablations, live provider credentials, and deployment are pending. [RESULTS.md](RESULTS.md) contains no invented numbers.

## What runs today

- Offline source manifest validation, PDF/HTML parsing, clause-aware chunking, ChromaDB indexing with FastEmbed ONNX vectors, and manifest-hash mismatch detection.
- Status and bank filtering, BM25 plus dense search with reciprocal rank fusion, FastEmbed cross-encoder reranking, and a bounded evidence retry.
- LangGraph case flow: input guard, intake interrupt, retrieval, checklist, output guard, response or escalation. SQLite checkpoints use the case ID as the thread ID.
- Presidio pattern recognition with Verhoeff validation for Aadhaar; masking before model, cache, ledger, trace, and checkpoint paths; injection and scope screening; citation ID checks; escalation for disputes, weak evidence, or a configured confidence threshold.
- A Groq gateway with a token ledger, per-model budget checks, a per-model request/token limiter, response cache, retries and circuit breaker. Provider failure or quota exhaustion falls back to synthetic replay.
- Streamlit demo with three synthetic cases, citations, state panel, and a permanent notice.
- Stage A retrieval ablation runner with bootstrap confidence intervals, corpus and gold fingerprints, test split lock, append-only result writer, and comparison guard. Optional LangSmith graph tracing is sampled by case ID; local node JSONL logs contain only hashed case IDs and timings.

## Run

Use Python 3.12 and [`uv`](https://docs.astral.sh/uv/):

```sh
make setup
make verify
make demo
```

The demo defaults to **replay mode**, so no API key is needed. It uses clearly labeled synthetic example sources until a reviewed corpus is built. The starter `data/sources.yaml` lists six publisher-page candidates, including an RBI draft announcement and an older SBI FAQ that are excluded by default, plus SBI's revised procedure. Review their dates and redistribution permissions, expand the corpus, then run:

```sh
uv run heirs fetch
make index
```

To use live generation, set `GROQ_API_KEY` and `DEMO_MODE=live` in your environment. Keep the key outside the repository. The app chooses live mode only when a verified index exists. A missing or stale index prevents live retrieval.

## Evaluation

`make eval SPLIT=dev` requires an owner-verified `eval/gold_set.jsonl` and a built index. The locked test split is refused unless `eval/TEST_SPLIT.lock` matches its IDs. Stage A uses no LLM calls. Results are new files under `eval/results/`; they are never overwritten. The benchmark work described in the build plan remains open until real sources and labels are verified.

`make bench-report` regenerates [eval/ablation.md](eval/ablation.md) from saved result files; missing rows stay marked pending.

## Privacy and limitations

The masking layer detects checksum-valid Aadhaar, PAN, email, phone, and long account-number patterns. Name detection is not complete. No system can guarantee that free text is free of all personal data; only synthetic cases are supported. Checkpoint storage on Streamlit Community Cloud is ephemeral. The regex injection screen and output citation check are safety layers, not proof against every attack. Cross-encoder scores need calibration on a verified dev set before enabling a confidence threshold in live use.

See [docs/QUESTIONS.md](docs/QUESTIONS.md) for the specific owner decisions needed to complete the corpus, evaluation, and release.

