from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    groq_api_key: str = ""
    router_model: str = "openai/gpt-oss-20b"
    generator_model: str = "openai/gpt-oss-120b"
    judge_model: str = "qwen/qwen3.8-27b"
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "heirs-navigator"
    trace_sample_rate: float = Field(default=0.1, ge=0, le=1)
    llm_cache_dir: Path = Path(".cache/llm")
    ledger_path: Path = Path("logs/ledger.jsonl")
    node_log_path: Path = Path("logs/nodes.jsonl")
    daily_token_budget: int = Field(default=180000, ge=0)
    per_minute_token_budget: int = Field(default=7000, ge=0)
    per_minute_request_budget: int = Field(default=25, ge=0)
    index_dir: Path = Path("data/index")
    checkpoint_db_path: Path = Path(".cache/cases.sqlite")
    demo_mode: str = "replay"
    demo_max_turns_per_session: int = Field(default=12, gt=0)
    demo_max_input_chars: int = Field(default=2000, gt=0)
