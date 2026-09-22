from dataclasses import dataclass, field

from langgraph.graph import END, START, StateGraph

from providers.flights import DuffelFlightProvider
from providers.places import OverpassPlacesProvider
from providers.routing import OSRMGroundProvider
from providers.stays import LiteAPIStayProvider, TavilyStaySearchProvider
from providers.weather import OpenMeteoWeatherProvider

from .clarify import clarify_node
from .compose import compose_node
from .fanout import make_flights_node, make_ground_node, make_places_node, make_stays_node, make_weather_node
from .intake import intake_node
from .state import PlanState
from .verify import route_after_verify, verify_node

FANOUT_NODES = ["flights", "stays", "weather", "places", "ground"]


@dataclass
class ProviderBundle:
    flights: object = field(default_factory=DuffelFlightProvider)
    stays: list = field(default_factory=lambda: [LiteAPIStayProvider(), TavilyStaySearchProvider()])
    weather: object = field(default_factory=OpenMeteoWeatherProvider)
    places: object = field(default_factory=OverpassPlacesProvider)
    ground: object = field(default_factory=OSRMGroundProvider)


def route_after_clarify(state: dict):
    spec = state["spec"]
    if spec.missing_required_fields():
        return "clarify"
    return FANOUT_NODES


def build_plan_graph(providers: ProviderBundle | None = None) -> StateGraph:
    """Builds the typed planning graph (uncompiled) — see docs/blueprint.md
    §04. Parallel fan-out uses plain multi-target conditional edges rather
    than LangGraph's Send API: Send is for a dynamic/unknown-size list of
    branches (map-reduce), but our five branches (flights/stays/weather/
    places/ground) are a fixed, known set, so a conditional edge returning
    a list of node names is the simpler mechanism for the same effect.
    """

    providers = providers or ProviderBundle()

    graph = StateGraph(PlanState)
    graph.add_node("intake", intake_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("flights", make_flights_node(providers.flights))
    graph.add_node("stays", make_stays_node(providers.stays))
    graph.add_node("weather", make_weather_node(providers.weather))
    graph.add_node("places", make_places_node(providers.places))
    graph.add_node("ground", make_ground_node(providers.ground))
    graph.add_node("compose", compose_node)
    graph.add_node("verify", verify_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "clarify")
    graph.add_conditional_edges("clarify", route_after_clarify, ["clarify", *FANOUT_NODES])

    for node_name in FANOUT_NODES:
        graph.add_edge(node_name, "compose")

    graph.add_edge("compose", "verify")
    graph.add_conditional_edges("verify", route_after_verify, {"repair": "compose", "done": END})

    return graph
