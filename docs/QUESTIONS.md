# Owner decisions and missing evidence

## 2026-11-17 — Corpus

The build plan requires at least 30 official documents and an owner decision on redistribution for each. The initial repository contained only two design documents. Six publisher-page candidates are now recorded in `data/sources.yaml`, with redistribution marked `unclear`; no third-party text is committed. Please review the source list, add more current bank documents, and decide which sources may be redistributed. Bank documents with unclear terms should be fetched locally only.

The India Code PDF timed out during local fetch. Its publisher page and metadata are documented in `docs/SOURCE_REVIEW.md`; the raw file remains missing until a manual download or a successful retry.

The RBI draft consultation page is fetched, but its linked draft PDF served a human-verification challenge during inspection. The draft itself needs manual acquisition before a genuine draft-versus-final trap evaluation.

## 2026-11-17 — Gold set and resume metrics

The plan requires 60 dev and 20 locked test questions with exact supporting passages. The owner must verify every answer against the downloaded primary source before promotion. No A1–A9 result or numerical resume claim can be issued before then.

## 2026-11-17 — Live services and deployment

Live Groq calls, LangSmith traces, and a Streamlit Community Cloud release require the owner's accounts and keys. This workspace has no credentials or linked GitHub repository. The replay demo runs without them.

