# Progress

## 2026-11-17

- Bootstrapped the Python package, indexer, hybrid retriever, guarded gateway, LangGraph workflow, synthetic replay UI, deterministic Stage A evaluation, and offline tests.
- Source manifest and gold-set files are intentionally empty pending official-source verification and owner review.
- Next: run dependency-backed verification, address test failures, then acquire and verify official source documents and gold labels.

## 2026-11-17 — verification pass

- Verified six official publisher-page candidates and recorded their dates/status in `data/sources.yaml` and `docs/SOURCE_REVIEW.md`; redistribution remains unclear.
- Fetched five sources locally. India Code PDF timed out and is listed in `data/MISSING.md`. Raw text and the derived index are Git-ignored.
- Built a local two-variant Chroma index from the fetched documents (41 structure-aware chunks). A real SBI-filtered hybrid query ranked the current SBI procedure and excluded the old FAQ. This is an ingestion smoke test, not a quality score.
- `make verify`: Ruff passed, mypy passed on 21 source files, and 16 offline tests passed. Streamlit AppTest rendered the page and a cited synthetic checklist without exceptions; the local health endpoint returned `ok`.
- Next: owner source redistribution review, remaining official bank/statute acquisition, owner verification of gold labels, then official Stage A ablations. Live provider and deployment require owner accounts.

