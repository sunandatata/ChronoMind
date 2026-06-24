import re
from rank_bm25 import BM25Okapi
from typing import Optional


def normalize_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def tokenize(text: str) -> list[str]:
    return re.sub(r'[^\w\s]', '', text.lower()).split()


class BM25Index:
    def __init__(self):
        self.documents: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self.index: Optional[BM25Okapi] = None

    def add_document(self, doc_id: str, text: str, metadata: dict = None):
        document = {
            "id": doc_id,
            "text": text,
            "tokens": tokenize(text),
            "metadata": metadata or {}
        }
        self._by_id[doc_id] = document
        self.documents = list(self._by_id.values())
        self._rebuild()

    def add_documents(self, documents: list[dict]):
        for document in documents:
            doc_id = document.get("id") or document.get("event_id")
            text = document.get("text") or document.get("payload", {}).get("text", "")
            if not doc_id or not text:
                continue
            metadata = document.get("metadata") or document.get("payload") or document
            self._by_id[doc_id] = {
                "id": doc_id,
                "text": text,
                "tokens": tokenize(text),
                "metadata": metadata,
            }
        self.documents = list(self._by_id.values())
        self._rebuild()

    def _rebuild(self):
        if not self.documents:
            self.index = None
            return
        corpus = [doc["tokens"] for doc in self.documents]
        self.index = BM25Okapi(corpus)

    def __len__(self) -> int:
        return len(self.documents)

    def search(self, query: str, limit: int = 20) -> list[dict]:
        if not self.index or not self.documents:
            return []
        query_tokens = tokenize(query)
        scores = self.index.get_scores(query_tokens)
        ranked = sorted(zip(self.documents, scores), key=lambda x: -x[1])
        results = []
        for doc, score in ranked[:limit]:
            if score > 0:
                results.append({"id": doc["id"], "score": float(score), "payload": doc["metadata"]})
        return results


# Global singleton BM25 index
_bm25_index = BM25Index()


def get_bm25_index() -> BM25Index:
    return _bm25_index
