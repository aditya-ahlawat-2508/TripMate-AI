import logging
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage

from models import TripSpec
from observability import get_langfuse_callbacks

from .llm import get_llm

logger = logging.getLogger("tripmate.graph.intake")

INTAKE_SYSTEM = """Extract trip-planning details from the user's message into the given schema.
Today's date is {today}. Rules:
- If the user asks you to suggest/surprise them with a destination, set suggest_destination=true
  and leave destination null.
- If no dates are mentioned, leave date_start/date_end null (don't guess a date).
- If a budget is mentioned, convert it into whole-currency-unit minor units (e.g. Rs 20,000 ->
  amount_minor=2000000, currency="INR"). If no budget is mentioned, leave budget null.
- Never invent an origin, destination, or date that isn't stated or clearly implied.
"""


async def intake_node(state: dict) -> dict:
    llm = get_llm()
    structured_llm = llm.with_structured_output(TripSpec)

    try:
        spec = await structured_llm.ainvoke(
            [
                SystemMessage(content=INTAKE_SYSTEM.format(today=date.today().isoformat())),
                HumanMessage(content=state["user_query"]),
            ],
            config={"callbacks": get_langfuse_callbacks(), "run_name": "intake"},
        )
    except Exception as exc:
        logger.warning("Structured intake failed, falling back to an empty spec: %s", exc)
        spec = TripSpec()

    return {"spec": spec}
