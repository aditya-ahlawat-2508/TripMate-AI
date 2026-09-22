import os

import certifi
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import operator
import uuid
from typing import Annotated, TypedDict
from urllib.parse import urlparse

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from mcp_client import (
    aviation_mcp_call,
    extract_destination,
    extract_trip_dates,
    forecast_mcp_search,
    tavily_mcp_search,
    weather_mcp_search,
)
from tools.flight_tool import AIRPORTS, parse_route

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Please add your PostgreSQL connection string to .env"
        )

    host = urlparse(database_url).hostname or ""
    is_local = host in LOCAL_HOSTS

    if not is_local and "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")


# =========================
# LLM
# =========================

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY
)


# =========================
# State
# =========================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int
    weather_results: str


# =========================
# Flight Agent
# =========================

# Flight Tool Router Prompt
FLIGHT_AGENT_PROMPT = """
You are a travel flight expert.

User Query:
{query}

Resolved route (from IATA airport data, not a guess):
- Departure: {dep_info}
- Arrival: {arr_info}

A sample of airlines AviationStack knows about:
{airline_data}

AviationStack provides flight schedules/status only — it has no ticket
pricing data. Do NOT invent or estimate a specific fare number or price
range; if pricing comes up, say live pricing isn't available here and
suggest checking an airline site or OTA.

Generate:
1. Confirmation of the departure and arrival airports above (note if either
   could not be resolved from the query).
2. Airlines plausibly serving this route, if evident from the sample above.
3. Typical flight duration for a route like this, described qualitatively.
4. General booking advice (no prices).

Return concise travel guidance.
"""


def describe_airport(iata: str | None) -> str:
    if not iata:
        return "could not be determined from the request"

    airport = AIRPORTS.get(iata)
    if not airport:
        return iata

    return f"{iata} — {airport.get('name')}, {airport.get('city')}, {airport.get('country')}"


# Flight Agent
async def flight_agent(state: TravelState):
    query = state["user_query"]

    try:
        dep_iata, arr_iata = parse_route(query)

        airlines = await aviation_mcp_call("list_airlines")

        prompt = FLIGHT_AGENT_PROMPT.format(
            query=query,
            dep_info=describe_airport(dep_iata),
            arr_info=describe_airport(arr_iata),
            airline_data=str(airlines)[:2000]
        )

        response = await llm.ainvoke([
            SystemMessage(
                content="You are an expert travel flight planner."
            ),
            HumanMessage(content=prompt)
        ])

        flight_data = response.content

    except Exception as e:

        flight_data = f"Flight information unavailable: {str(e)}"

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(
                content="Flight recommendations generated"
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }





# =========================
# Hotel Agent
# =========================

async def hotel_agent(state: TravelState):
    query = f"Best hotels for {state['user_query']}"
    hotel_results = await tavily_mcp_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }




# =========================
# Weather Agent
# =========================

async def weather_agent(state: TravelState):

    city = await extract_destination(state["user_query"])
    start_date, end_date = await extract_trip_dates(state["user_query"])

    weather_data = await weather_mcp_search(city)

    forecast_data = await forecast_mcp_search(city, start_date, end_date)

    return {
        "weather_results": f"""
        Current Weather:
        {weather_data}

        Forecast:
        {forecast_data}
        """,
        "messages": [
            AIMessage(
                content="Weather information fetched"
            )
        ]
    }




# =========================
# Itinerary Agent
# =========================

async def itinerary_agent(state: TravelState):
    prompt = f"""
Create a complete travel itinerary.

User Query:
{state['user_query']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Weather Results:
{state['weather_results']}

Make the itinerary practical, budget-aware, and easy to follow.
"""

    response = await llm.ainvoke([
        SystemMessage(content="You are an expert travel planner."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# =========================
# Final Response Agent
# =========================

async def final_agent(state: TravelState):
    final_prompt = f"""
Generate the final travel response for the user.

User Request:
{state['user_query']}

Flights:
{state['flight_results']}

Hotels:
{state['hotel_results']}

Weather:
{state['weather_results']}

Itinerary:
{state['itinerary']}

Format the final answer beautifully using these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Weather Information
5. Day-by-Day Itinerary
6. Estimated Budget
7. Final Recommendations


Important:
- Be clear and practical.
- Mention that live flight API may not provide ticket prices if pricing is unavailable.
- Include weather-based travel advice.
- Keep the response useful for real travel planning.
"""

    response = await llm.ainvoke([
        SystemMessage(content="You are a professional AI travel booking assistant."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Build Graph
# =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("weather_agent", weather_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "weather_agent")
graph.add_edge("weather_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# =========================
# PostgreSQL Checkpointer
# =========================
# The connection and the compiled graph are built inside FastAPI's lifespan
# (see app.py), not at import time: AsyncPostgresSaver.__init__ calls
# asyncio.get_running_loop(), so it cannot exist outside a running loop.

async def build_travel_graph():
    """Open a pooled async Postgres connection and compile the graph.

    A single shared AsyncConnection can't serve concurrent requests safely;
    a pool lets each request borrow its own connection.

    Returns (compiled_graph, pool) — the caller owns the pool and must close
    it on shutdown.
    """
    pool = AsyncConnectionPool(
        get_database_url(),
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    await pool.open()

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()

    return graph.compile(checkpointer=checkpointer), pool



# =========================
# Function for FastAPI
# =========================

async def run_travel_agent(
    travel_graph,
    user_input: str,
    thread_id: str | None = None
):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = await travel_graph.ainvoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "weather_results": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "weather_results": result.get("weather_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }
