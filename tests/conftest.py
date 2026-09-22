import os

# backend.py and mcp_client.py read these at import time (API clients are
# constructed at module scope), so they must be set before anything in the
# test suite imports those modules. No real network calls are made in CI.
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("AVIATIONSTACK_API_KEY", "test-aviationstack-key")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/travel_db")
