from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from heirs_navigator.guards.pii import PIIMasker


class BudgetExceeded(RuntimeError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int


class Provider(Protocol):
    def complete(self, model: str, prompt: str, *, temperature: float = 0) -> Completion: ...


class GroqProvider:
    def __init__(self, api_key: str, timeout: float = 30) -> None:
        if not api_key:
            raise ValueError("GROQ_API_KEY is required for live mode")
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, model: str, prompt: str, *, temperature: float = 0) -> Completion:
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
                timeout=self.timeout,
            )
            if response.status_code == 429:
                value = response.headers.get("retry-after", "1")
                raise ProviderError("Groq rate limited", float(value))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(type(exc).__name__) from exc
        body = response.json()
        usage = body.get("usage", {})
        return Completion(
            text=body["choices"][0]["message"]["content"],
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


class FakeProvider:
    def __init__(self, responses: list[Completion]) -> None:
        self.responses = responses
        self.calls = 0

    def complete(self, model: str, prompt: str, *, temperature: float = 0) -> Completion:
        self.calls += 1
        if not self.responses:
            raise ProviderError("No fake response available")
        return self.responses.pop(0)


class ReplayProvider:
    def __init__(self, fixtures: Mapping[str, Completion]) -> None:
        self.fixtures = fixtures

    def complete(self, model: str, prompt: str, *, temperature: float = 0) -> Completion:
        key = cache_key(model, prompt, temperature, "")
        if key not in self.fixtures:
            raise ProviderError("No recorded response for this prompt")
        return self.fixtures[key]


def cache_key(model: str, prompt: str, temperature: float, corpus_version: str) -> str:
    body = json.dumps([model, prompt, temperature, corpus_version], ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


class TokenLedger:
    def __init__(self, path: Path, daily_limit: int, minute_limit: int) -> None:
        self.path = path
        self.daily_limit = daily_limit
        self.minute_limit = minute_limit

    def _entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]

    def check(self, estimated_tokens: int, model: str | None = None) -> None:
        now = datetime.now(UTC)
        entries = [x for x in self._entries() if model is None or x["model"] == model]
        day_used = sum(
            x["tokens"] for x in entries if x["timestamp"][:10] == now.date().isoformat()
        )
        minute_used = sum(
            x["tokens"]
            for x in entries
            if (now - datetime.fromisoformat(x["timestamp"])).total_seconds() < 60
        )
        if day_used + estimated_tokens > self.daily_limit:
            raise BudgetExceeded("Daily model token budget exhausted")
        if minute_used + estimated_tokens > self.minute_limit:
            raise BudgetExceeded("Per-minute model token budget exhausted")

    def record(
        self, model: str, role: str, completion: Completion, latency: float, cached: bool
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "model": model,
            "role": role,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "tokens": 0 if cached else completion.input_tokens + completion.output_tokens,
            "latency_ms": round(latency * 1000),
            "cached": cached,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")


class RateLimiter:
    """Nonblocking per-model request and estimated-token window for demo safety."""

    def __init__(self, requests_per_minute: int, tokens_per_minute: int) -> None:
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self._events: dict[str, list[tuple[float, int]]] = {}
        self._lock = threading.Lock()

    def acquire(self, model: str, estimated_tokens: int) -> None:
        with self._lock:
            now = time.monotonic()
            recent = [(t, n) for t, n in self._events.get(model, []) if now - t < 60]
            if len(recent) >= self.requests_per_minute:
                raise BudgetExceeded("Per-minute request budget exhausted")
            if sum(tokens for _, tokens in recent) + estimated_tokens > self.tokens_per_minute:
                raise BudgetExceeded("Per-minute token budget exhausted")
            recent.append((now, estimated_tokens))
            self._events[model] = recent


T = TypeVar("T", bound=BaseModel)


class Gateway:
    def __init__(
        self,
        provider: Provider,
        ledger: TokenLedger,
        cache_dir: Path,
        masker: PIIMasker,
        *,
        corpus_version: str = "",
        max_retries: int = 2,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.provider = provider
        self.ledger = ledger
        self.cache_dir = cache_dir
        self.masker = masker
        self.corpus_version = corpus_version
        self.max_retries = max_retries
        self.rate_limiter = rate_limiter or RateLimiter(30, ledger.minute_limit)
        self.failures = 0

    def complete(self, model: str, role: str, prompt: str) -> Completion:
        safe_prompt = self.masker.mask(prompt)
        key = cache_key(model, safe_prompt, 0, self.corpus_version)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            cached = Completion(**json.loads(path.read_text(encoding="utf-8")))
            self.ledger.record(model, role, cached, 0, cached=True)
            return cached
        if self.failures >= 3:
            raise ProviderError("Circuit breaker open")
        estimated_tokens = max(1, len(safe_prompt) // 4) + 600
        self.ledger.check(estimated_tokens, model)
        for attempt in range(self.max_retries + 1):
            start = time.monotonic()
            try:
                self.rate_limiter.acquire(model, estimated_tokens)
                result = self.provider.complete(model, safe_prompt)
                safe_result = Completion(
                    self.masker.mask(result.text), result.input_tokens, result.output_tokens
                )
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(safe_result.__dict__), encoding="utf-8")
                self.ledger.record(model, role, safe_result, time.monotonic() - start, cached=False)
                self.failures = 0
                return safe_result
            except ProviderError as exc:
                self.failures += 1
                if attempt == self.max_retries:
                    raise
                time.sleep(exc.retry_after or min(2**attempt + random.random(), 10))
        raise ProviderError("Unreachable retry state")

    def structured(self, model: str, role: str, prompt: str, schema: type[T]) -> T:
        for attempt in range(2):
            result = self.complete(model, role, prompt)
            try:
                return schema.model_validate_json(result.text)
            except ValidationError as exc:
                if attempt:
                    raise ProviderError("Model output failed schema validation") from exc
                prompt += f"\nReturn valid JSON matching this schema: {schema.model_json_schema()}"
        raise ProviderError("Unreachable validation state")
