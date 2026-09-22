import os

from langchain_groq import ChatGroq

_llm: ChatGroq | None = None
_composer_llm: ChatGroq | None = None


def get_llm() -> ChatGroq:
    """Fast model for intake and small tasks. Lazily constructed (and
    monkeypatchable in tests) rather than built at import time."""

    global _llm
    if _llm is None:
        _llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    return _llm


def get_composer_llm() -> ChatGroq:
    """Slightly stronger settings for the one big structured-output call.
    Same model family for now — swap this for a bigger model once cost
    tracking (blueprint §08 Observability) is wired up and the tradeoff can
    actually be measured instead of guessed."""

    global _composer_llm
    if _composer_llm is None:
        _composer_llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"), temperature=0.2)
    return _composer_llm
