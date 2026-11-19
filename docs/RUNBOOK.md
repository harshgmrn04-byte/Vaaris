# Runbook

1. Use Python 3.12 and run `make setup` then `make verify`.
2. Review and expand `data/sources.yaml` with verified official source metadata. Record redistribution decisions and keep raw files out of Git.
3. Run `uv run heirs fetch`, inspect `data/MISSING.md` if present, OCR scanned PDFs locally, and validate each manifest row.
4. Run `make index`. The app fails if the manifest hash no longer matches the index.
5. Have the owner verify gold candidates against exact source passages and lock the test split before official evaluation.
6. Set keys only through environment or Streamlit secrets. Run replay mode by default, then smoke-test one live turn when the owner has an account.
7. On provider outage or exhausted quota, the workflow falls back to a clearly labeled synthetic replay response. Do not use unverified sources as if they were official.

