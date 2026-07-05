from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue,
)
from typing import Optional
from config import get_settings
import uuid

try:
    from qdrant_client.models import DatetimeRange
except ImportError:  # pragma: no cover - compatibility with older qdrant-client
    from qdrant_client.models import Range as DatetimeRange

settings = get_settings()
VECTOR_SIZE = 1536


class VectorService:
    def __init__(self):
        self.client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )
        self.collection = settings.collection_name

    async def init_collection(self):
        try:
            await self.client.get_collection(self.collection)
        except Exception:
            await self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )

    async def upsert_event(self, event_id: str, embedding: list[float], payload: dict) -> str:
        point = PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, event_id)),
            vector=embedding,
            payload={**payload, "event_id": event_id}
        )
        await self.client.upsert(collection_name=self.collection, points=[point])
        return str(point.id)

    async def update_event_payload(self, event_id: str, payload: dict) -> None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, event_id))
        await self.client.set_payload(
            collection_name=self.collection,
            payload=payload,
            points=[point_id],
        )

    def _query_filter(self, must: list[FieldCondition] | None = None) -> Filter:
        return Filter(
            must=must or [],
            must_not=[
                FieldCondition(key="is_demo", match=MatchValue(value=True))
            ],
        )

    async def search(self, query_embedding: list[float], limit: int = 20, filter_payload: dict = None) -> list[dict]:
        must: list[FieldCondition] = []
        for key, value in (filter_payload or {}).items():
            must.append(FieldCondition(key=key, match=MatchValue(value=value)))

        results = await self.client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            query_filter=self._query_filter(must),
            limit=limit,
            with_payload=True,
            with_vectors=True
        )
        return [
            {
                "id": r.payload.get("event_id", str(r.id)),
                "score": r.score,
                "payload": r.payload,
                "embedding": r.vector
            }
            for r in results
        ]

    async def search_with_time_filter(
        self,
        query_embedding: list[float],
        start_iso: str,
        end_iso: str,
        limit: int = 20
    ) -> list[dict]:
        results = await self.client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="timestamp",
                        range=DatetimeRange(gte=start_iso, lte=end_iso),
                    )
                ],
                must_not=[
                    FieldCondition(key="is_demo", match=MatchValue(value=True))
                ],
            ),
            limit=limit,
            with_payload=True,
            with_vectors=True
        )
        return [
            {
                "id": r.payload.get("event_id", str(r.id)),
                "score": r.score,
                "payload": r.payload,
                "embedding": r.vector
            }
            for r in results
        ]

    async def get_all_events(self, limit: int = 500) -> list[dict]:
        results, _ = await self.client.scroll(
            collection_name=self.collection,
            limit=limit,
            scroll_filter=self._query_filter(),
            with_payload=True,
            with_vectors=True
        )
        return [
            {
                "id": r.payload.get("event_id", str(r.id)),
                "payload": r.payload,
                "embedding": r.vector
            }
            for r in results
        ]


_vector_service: Optional[VectorService] = None


def get_vector_service() -> VectorService:
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service
