from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

import streamlit as st
from langgraph.checkpoint.sqlite import SqliteSaver

from heirs_navigator.app.demo import DEMO_CASES, demo_search
from heirs_navigator.config import Settings
from heirs_navigator.domain import Evidence
from heirs_navigator.graph.workflow import Workflow
from heirs_navigator.guards.pii import PIIMasker
from heirs_navigator.ingest.index import load_index
from heirs_navigator.platform.llm import Gateway, GroqProvider, RateLimiter, TokenLedger
from heirs_navigator.retrieval.hybrid import HybridRetriever

st.set_page_config(page_title="Vaaris: Claims Navigator", layout="wide")
st.title("Vaaris: Claims Navigator")
st.info(
    "Synthetic cases only. Process guidance, not legal advice. Do not enter real personal data."
)
settings = Settings()


@st.cache_resource
def make_workflow() -> tuple[Workflow, bool]:
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    masker = PIIMasker()
    settings.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_db_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    index_exists = (settings.index_dir / "meta.json").exists()
    live = bool(settings.groq_api_key and index_exists and settings.demo_mode == "live")
    search: Callable[[str, str | None], list[Evidence]]
    if live:
        chunks, collection = load_index(settings.index_dir, Path("data/manifest.csv"))
        retriever = HybridRetriever(chunks, collection)
        search = retriever.search
    else:
        search = demo_search
    gateway = None
    if live:
        gateway = Gateway(
            GroqProvider(settings.groq_api_key),
            TokenLedger(
                settings.ledger_path, settings.daily_token_budget, settings.per_minute_token_budget
            ),
            settings.llm_cache_dir,
            masker,
            rate_limiter=RateLimiter(
                settings.per_minute_request_budget, settings.per_minute_token_budget
            ),
        )
    workflow = Workflow(
        search,
        masker,
        gateway,
        settings.generator_model,
        checkpointer=checkpointer,
        replay=not live,
        log_path=settings.node_log_path,
        tracing_enabled=settings.langsmith_tracing and bool(settings.langsmith_api_key),
        tracing_project=settings.langsmith_project,
        trace_sample_rate=settings.trace_sample_rate,
        replay_search=demo_search,
    )
    return workflow, live


workflow, live = make_workflow()
st.caption("Live mode" if live else "Replay mode: synthetic example sources and no model calls")
with st.sidebar:
    st.header("Case")
    choice = st.selectbox("Synthetic case", list(DEMO_CASES))
    case_id = st.text_input("Case ID", value=choice, max_chars=80)
    facts = DEMO_CASES[choice]
    st.json(facts)
    st.caption("Only masked text is checkpointed. Case state is local to this app instance.")

left, right = st.columns([2, 1])
with left:
    question = st.chat_input("Ask about claim documents or next steps")
    if question:
        if len(question) > settings.demo_max_input_chars:
            st.error("Input is too long.")
        else:
            key = f"turns:{case_id}"
            turns = st.session_state.get(key, 0)
            if turns >= settings.demo_max_turns_per_session:
                st.error("This demo session has reached its turn limit.")
            else:
                st.session_state[key] = turns + 1
                try:
                    result = workflow.run(case_id, question, facts)
                except ValueError as exc:
                    st.error(str(exc))
                    st.stop()
                st.chat_message("user").write(workflow.masker.mask(question))
                if "__interrupt__" in result:
                    st.warning(result["__interrupt__"][0].value["message"])
                else:
                    st.chat_message("assistant").write(result.get("response", ""))
                    if result.get("replay_used"):
                        st.warning(
                            "Live quota or provider unavailable. "
                            "Showing a synthetic replay example."
                        )
                    st.session_state[f"last:{case_id}"] = result
    last = st.session_state.get(f"last:{case_id}", {})
with right:
    st.header("Case state")
    st.json(last.get("facts", facts))
    st.header("Citations")
    for item in last.get("evidence", []):
        chunk = item["chunk"]
        st.write(f"**{chunk['chunk_id']}** — {chunk['issuer']}, section {chunk['section']}")
        st.caption(f"Effective {chunk['effective_date']} · {chunk['status']}")
    if last.get("escalation"):
        st.error(last["escalation"])
