from dataclasses import dataclass

import pytest

from mcp_client import find_tool


@dataclass
class FakeTool:
    name: str


def test_find_tool_returns_matching_tool():
    tools = [FakeTool("tavily_search"), FakeTool("list_airports")]
    assert find_tool(tools, "list_airports") is tools[1]


def test_find_tool_missing_raises_clear_error():
    tools = [FakeTool("tavily_search"), FakeTool("list_airports")]

    with pytest.raises(RuntimeError) as exc_info:
        find_tool(tools, "get_forecast")

    message = str(exc_info.value)
    assert "get_forecast" in message
    assert "tavily_search" in message
    assert "list_airports" in message


def test_find_tool_empty_list_raises_clear_error():
    with pytest.raises(RuntimeError) as exc_info:
        find_tool([], "get_forecast")

    assert "none" in str(exc_info.value)
