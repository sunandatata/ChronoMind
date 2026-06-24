from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from api import ingest, query, timeline, graph as graph_api, stats
from services.graph import get_graph_service
from services.vector import get_vector_service


async def _retry_startup(name: str, action, attempts: int = 30, delay: float = 2.0):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return await action()
        except Exception as exc:
            last_error = exc
            print(f"Waiting for {name} ({attempt}/{attempts}): {exc}")
            await asyncio.sleep(delay)
    raise RuntimeError(f"{name} did not become ready") from last_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _retry_startup("Neo4j", get_graph_service().init_schema)
    await _retry_startup("Qdrant", get_vector_service().init_collection)
    yield


app = FastAPI(
    title="ChronoMind API",
    description="Temporal RAG Memory Engine",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(ingest.router, prefix="/api", tags=["ingestion"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(timeline.router, prefix="/api", tags=["timeline"])
app.include_router(graph_api.router, prefix="/api", tags=["graph"])
app.include_router(stats.router, prefix="/api", tags=["stats"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ChronoMind"}
