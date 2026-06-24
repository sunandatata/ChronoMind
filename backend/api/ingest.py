from fastapi import APIRouter
from models.event import IngestRequest, IngestResponse
from services.ingestion import ingest

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_text(request: IngestRequest) -> IngestResponse:
    """Ingest raw text and extract memory events into the temporal graph."""
    return await ingest(request)
