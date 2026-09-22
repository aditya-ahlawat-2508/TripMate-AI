import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from pydantic import BaseModel

from backend import build_travel_graph, run_travel_agent
from graph.graph import build_plan_graph
from trips_store import ensure_trips_table, get_trip, list_demo_trips, save_trip

BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tripmate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.travel_graph, pool = await build_travel_graph()
    app.state.pool = pool

    plan_checkpointer = AsyncPostgresSaver(pool)
    app.state.plan_graph = build_plan_graph().compile(checkpointer=plan_checkpointer)
    await ensure_trips_table(pool)

    try:
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="TripMate AI",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0",
    lifespan=lifespan
)

# Dev-only: Next.js runs on a different origin (localhost:3000). There's no
# auth yet to scope this more tightly — revisit once Clerk is wired up.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)


templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)



class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.post("/api/travel")
async def travel_planner(request: Request, request_data: TravelRequest):
    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty."
                }
            )

        result = await run_travel_agent(
            request.app.state.travel_graph,
            user_input=user_message,
            thread_id=request_data.thread_id
        )

        return JSONResponse(
            content={
                "success": True,
                "thread_id": result["thread_id"],
                "answer": result["answer"],
                "flight_results": result["flight_results"],
                "hotel_results": result["hotel_results"],
                "weather_results": result["weather_results"],
                "itinerary": result["itinerary"],
                "llm_calls": result["llm_calls"],
            }
        )

    except Exception:
        error_id = uuid.uuid4().hex[:8]
        logger.exception("Unhandled error in /api/travel [error_id=%s]", error_id)

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Something went wrong on our end (reference: {error_id}).",
            }
        )



class PlanRequest(BaseModel):
    message: str | None = None
    thread_id: str | None = None
    resume_answer: str | None = None


@app.post("/api/plan")
async def plan_trip(request: Request, request_data: PlanRequest):
    """The typed-graph planner (docs/blueprint.md §04): TripSpec intake,
    interrupt()-based clarification, parallel provider fan-out, a
    structured-output composer, and a deterministic verifier with a repair
    loop. Returns either a clarifying question or a finished, typed Trip —
    never free-text prose. Additive alongside the legacy /api/travel, which
    stays for now (see docs/progress.md)."""

    try:
        graph = request.app.state.plan_graph
        thread_id = request_data.thread_id or f"plan_{uuid.uuid4().hex}"
        config = {"configurable": {"thread_id": thread_id}}

        if request_data.resume_answer is not None:
            result = await graph.ainvoke(Command(resume=request_data.resume_answer), config)
        else:
            message = (request_data.message or "").strip()
            if not message:
                return JSONResponse(status_code=400, content={"success": False, "error": "Message cannot be empty."})
            result = await graph.ainvoke(
                {"user_query": message, "warnings": [], "repair_count": 0},
                config,
            )

        if "__interrupt__" in result:
            question = result["__interrupt__"][0].value
            return JSONResponse(
                content={
                    "success": True,
                    "status": "needs_input",
                    "thread_id": thread_id,
                    "question": question,
                }
            )

        trip = result["trip"]
        await save_trip(request.app.state.pool, trip, thread_id)

        return JSONResponse(
            content={
                "success": True,
                "status": "done",
                "thread_id": thread_id,
                "trip": trip.model_dump(mode="json"),
            }
        )

    except Exception:
        error_id = uuid.uuid4().hex[:8]
        logger.exception("Unhandled error in /api/plan [error_id=%s]", error_id)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Something went wrong on our end (reference: {error_id})."},
        )


@app.get("/api/plan/{trip_id}")
async def get_plan(request: Request, trip_id: str):
    trip = await get_trip(request.app.state.pool, trip_id)
    if not trip:
        return JSONResponse(status_code=404, content={"success": False, "error": "Trip not found."})
    return JSONResponse(content={"success": True, "trip": trip.model_dump(mode="json")})


@app.get("/api/demo-trips")
async def demo_trips(request: Request):
    """Pre-generated showcase trips (docs/blueprint.md "demo mode") — zero
    API cost, for a landing-page "Try a sample trip" button. Seed with
    `python -m scripts.seed_demo_trips` from apps/api/."""
    trips = await list_demo_trips(request.app.state.pool)
    return JSONResponse(content={"success": True, "trips": [t.model_dump(mode="json") for t in trips]})


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "AI Travel Planner API is running"
    }


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})



if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )