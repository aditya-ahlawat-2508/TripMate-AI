import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import certifi
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

load_dotenv()


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATION_STACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# LLM
# llama-3.3-70b-versatile was deprecated/removed from Groq at some point;
# openai/gpt-oss-20b confirmed live as of 2026-09-23 (see graph/llm.py).
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY
)


client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": "https://mcp.tavily.com/mcp/",
            # Header auth instead of a URL query param, so the key doesn't
            # land in proxy/server access logs.
            "headers": {
                "Authorization": f"Bearer {TAVILY_API_KEY}"
            }
        },

        "aviationstack": {
            "transport": "stdio",
            "command": "uvx",
            "args": [
                "aviationstack-mcp"
            ],
            "env": {
                "AVIATION_STACK_API_KEY": AVIATION_STACK_API_KEY
            }
        },

        "weather": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [
                str(Path(__file__).parent / "custom_weather_mcp_server.py")
            ],
            # Open-Meteo is free and keyless, so no env vars are needed here.
        },
    }
)




# Check if the client is connected to all servers
async def get_all_tools():

    tools = await client.get_tools()

    print("\nAvailable MCP Tools:\n")

    for tool in tools:
        print(tool.name)




###################################
# Tavlily and Aviation Tools
###################################


def find_tool(tools, name: str):
    """Look up an MCP tool by exact name, with a clear error if the upstream
    server renamed or dropped it (instead of a bare StopIteration)."""

    for tool in tools:
        if tool.name == name:
            return tool

    available = ", ".join(sorted(t.name for t in tools)) or "none"
    raise RuntimeError(
        f"MCP tool '{name}' was not found. Available tools: {available}. "
        "An upstream MCP server may have renamed or removed this tool."
    )


search_tool = None
aviation_tools = {}

async def initialize_search_tool():
    """Loads only the tavily server's tools. Split from
    initialize_aviation_tools() (and both from initialize_weather_tools())
    because MultiServerMCPClient.get_tools() with no server_name connects
    to every configured server at once — one broken server (e.g. Tavily
    with an invalid key) used to take down weather and aviation tool
    lookups too, even though they're otherwise independent.
    """

    global search_tool

    if search_tool is not None:
        return

    tools = await client.get_tools(server_name="tavily")
    search_tool = find_tool(tools, "tavily_search")


async def initialize_aviation_tools():
    global aviation_tools

    if aviation_tools:
        return

    tools = await client.get_tools(server_name="aviationstack")
    aviation_tools = {tool.name: tool for tool in tools}




async def tavily_mcp_search(query: str):
    await initialize_search_tool()
    result = await search_tool.ainvoke(
        {
            "query": query
        }
    )
    return result




async def aviation_mcp_call(
    tool_name: str,
    tool_args: dict = None
):

    await initialize_aviation_tools()

    if tool_name not in aviation_tools:
        available = ", ".join(sorted(aviation_tools)) or "none"
        raise RuntimeError(
            f"MCP tool '{tool_name}' was not found. Available aviation tools: {available}. "
            "The aviationstack-mcp server may have renamed or removed this tool."
        )

    tool = aviation_tools[tool_name]

    result = await tool.ainvoke(
        tool_args or {}
    )

    return result






###################################
# Weather Tools
###################################

weather_tool = None
forecast_tool = None


async def initialize_weather_tools():

    global weather_tool, forecast_tool

    if weather_tool is not None:
        return

    tools = await client.get_tools(server_name="weather")

    weather_tool = find_tool(tools, "get_current_weather")
    forecast_tool = find_tool(tools, "get_forecast")


async def weather_mcp_search(city: str):

    await initialize_weather_tools()

    return await weather_tool.ainvoke(
        {
            "city": city
        }
    )


async def forecast_mcp_search(
    city: str,
    start_date: str | None = None,
    end_date: str | None = None,
):

    await initialize_weather_tools()

    return await forecast_tool.ainvoke(
        {
            "city": city,
            "start_date": start_date,
            "end_date": end_date,
        }
    )




###################################
# Destination Extractor
###################################

async def extract_destination(query: str):

    prompt = f"""
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """

    response = await llm.ainvoke(prompt)

    return response.content.strip()




###################################
# Trip Date Extractor
###################################

async def extract_trip_dates(query: str, today: str | None = None):
    """Best-effort extraction of a trip's start/end dates from free text.

    Returns (start_date, end_date) as "YYYY-MM-DD" strings, or (None, None)
    if the query doesn't specify dates (callers should fall back to a
    default window, e.g. the next 5 days).
    """

    today = today or date.today().isoformat()

    prompt = f"""
    Today's date is {today}.

    Extract the trip's start and end date from this travel request. If a
    duration is given instead of an end date (e.g. "5 days"), compute the
    end date. If no date or duration is mentioned at all, return nulls.

    Query:
    {query}

    Respond with ONLY a JSON object, no other text, in exactly this shape:
    {{"start_date": "YYYY-MM-DD" or null, "end_date": "YYYY-MM-DD" or null}}
    """

    response = await llm.ainvoke(prompt)

    try:
        match = re.search(r"\{.*\}", response.content, re.DOTALL)
        data = json.loads(match.group(0)) if match else {}
        return data.get("start_date"), data.get("end_date")
    except (json.JSONDecodeError, AttributeError):
        return None, None


