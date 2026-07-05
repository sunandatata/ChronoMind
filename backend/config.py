from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "chronomind123"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = "chronomind_events"
    memory_retrieval_boost: float = 0.05
    memory_selection_boost: float = 0.08
    memory_answer_boost: float = 0.06
    memory_reference_boost: float = 0.04
    memory_ignored_decay: float = 0.01
    memory_age_decay: float = 0.02
    memory_connection_boost: float = 0.03
    memory_decay_floor: float = 0.15
    memory_decay_ceiling: float = 1.0
    memory_retrieval_growth: float = 0.04
    memory_selection_growth: float = 0.06
    memory_answer_growth: float = 0.08
    memory_reference_growth: float = 0.05
    ranker_model_path: str = "backend/data/ranker_model.json"
    session_expiry_hours: int = 36
    consolidation_similarity_threshold: float = 0.9
    consolidation_time_window_days: int = 14
    consolidation_limit: int = 7

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
