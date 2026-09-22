from datetime import date

from langgraph.types import interrupt

QUESTIONS = {
    "origin": "Where are you traveling from?",
    "destination": "Where do you want to go? (or say 'surprise me')",
    "date_start": "When do you want to travel? (a date, or 'flexible')",
}


def clarify_node(state: dict) -> dict:
    """Asks a single question via LangGraph's interrupt() for the first
    missing required field, and applies the answer when resumed. Replaces
    the old free-text extract_destination() call with a structured,
    human-in-the-loop step — this is the only node in the graph that can
    pause a run.
    """

    spec = state["spec"]
    missing = spec.missing_required_fields()
    if not missing:
        return {}

    field = missing[0]
    answer = interrupt({"field": field, "question": QUESTIONS.get(field, f"Please provide: {field}")})

    updated = spec.model_copy(update=_apply_answer(field, answer, spec))
    return {"spec": updated}


def _apply_answer(field: str, answer: str, spec) -> dict:
    answer = (answer or "").strip()

    if field == "destination" and answer.lower() in {"surprise me", "suggest", "anywhere"}:
        return {"suggest_destination": True}

    if field == "date_start":
        if answer.lower() in {"flexible", "any", "any time"}:
            return {"flexible_dates": True}
        try:
            return {"date_start": date.fromisoformat(answer)}
        except ValueError:
            return {"flexible_dates": True}

    return {field: answer}
