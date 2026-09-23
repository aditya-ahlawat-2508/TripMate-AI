import os

from langchain_groq import ChatGroq

# llama-3.3-70b-versatile (the model this project originally shipped
# with) was deprecated/removed from Groq at some point — GROQ_API_KEY
# started returning 404 model_not_found. Checked what's actually live via
# the Groq models API rather than guessing; openai/gpt-oss-120b and
# openai/gpt-oss-20b are both confirmed working with structured output
# (with_structured_output) as of 2026-09-23.
INTAKE_MODEL = "openai/gpt-oss-20b"
COMPOSER_MODEL = "openai/gpt-oss-120b"

_llm: ChatGroq | None = None
_composer_llm: ChatGroq | None = None


def get_llm() -> ChatGroq:
    """Fast model for intake and small tasks. Lazily constructed (and
    monkeypatchable in tests) rather than built at import time."""

    global _llm
    if _llm is None:
        _llm = ChatGroq(model=INTAKE_MODEL, api_key=os.getenv("GROQ_API_KEY"))
    return _llm


def get_composer_llm() -> ChatGroq:
    """Stronger model for the one big structured-output call. Model
    routing per blueprint §04; swap this once cost tracking (blueprint
    §08 Observability, now wired via Langfuse) shows the actual
    quality/cost tradeoff instead of guessing at it."""

    global _composer_llm
    if _composer_llm is None:
        _composer_llm = ChatGroq(model=COMPOSER_MODEL, api_key=os.getenv("GROQ_API_KEY"), temperature=0.2)
    return _composer_llm
