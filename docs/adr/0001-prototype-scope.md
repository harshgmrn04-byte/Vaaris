# ADR 0001: Evidence-gated prototype

**Status:** accepted for the initial implementation.

**Context:** Only the build and architecture plans were supplied. No official corpus, verified labels, credentials, or repository existed.

**Decision:** Build the named components and a synthetic replay demo. Keep official source and gold-set files empty, refuse benchmark execution until they are populated, and report no numerical results.

**Consequences:** The architecture can be exercised and reviewed locally, but the resume metrics, public deployment, source redistribution, and production safety claims remain unverified.

