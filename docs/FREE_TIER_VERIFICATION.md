# Free-tier verification

Checked 2026-11-17. These are published figures, not account-specific guarantees.

- Groq's [rate limit table](https://console.groq.com/docs/rate-limits) lists `openai/gpt-oss-120b` and `openai/gpt-oss-20b` at 30 requests/minute, 1,000 requests/day, 8,000 tokens/minute, and 200,000 tokens/day in its displayed table. It says exact account limits appear on the account limits page and `Retry-After` appears on 429 responses.
- Groq's [prompt caching documentation](https://console.groq.com/docs/prompt-caching) says GPT-OSS caching is automatic and cache hits are not guaranteed.
- [FastEmbed's documentation](https://github.com/qdrant/fastembed/blob/main/README.md) shows `TextEmbedding` and `TextCrossEncoder` with ONNX models used by this project.
- LangSmith and Streamlit account-specific caps and deployed memory have not been verified in this workspace. They must be checked in the owner's accounts before release.

