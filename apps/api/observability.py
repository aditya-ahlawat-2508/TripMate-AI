"""Langfuse tracing (docs/blueprint.md §08 Observability). Every LLM call
in the typed graph (graph/intake.py, graph/compose.py) passes
get_langfuse_callbacks() into its .ainvoke() config — this stays a no-op
list when Langfuse isn't configured, so nothing breaks if the keys are
ever removed.
"""

import os

_handler = None
_checked = False


def get_langfuse_callbacks() -> list:
    global _handler, _checked

    if not _checked:
        _checked = True
        if os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY"):
            from langfuse.langchain import CallbackHandler

            _handler = CallbackHandler()

    return [_handler] if _handler else []
