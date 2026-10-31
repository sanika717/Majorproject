import json
import math
import hashlib
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from backend.app.core.config import settings

logger = logging.getLogger("urbanpulse.intelligence.cache")


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors (kept for backward compatibility)."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


def normalize_query_text(text: str) -> str:
    """Normalizes query for whitespace, casing, and basic punctuation."""
    import re
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    return " ".join(cleaned.split())


class RedisSemanticCache:
    """
    High-performance Cache backed by Redis.
    - Exact match on sha256(normalized_question + data_version)
    - Zero LLM embedding overhead on cache lookup or storage
    - Validates data-version fingerprint so stale answers are never served
    - Handles Redis connection failures gracefully with seamless bypass
    """

    def __init__(
        self,
        redis_url: str = settings.REDIS_URL,
        ttl: int = settings.REDIS_CACHE_TTL,
        similarity_threshold: float = settings.REDIS_SIMILARITY_THRESHOLD
    ):
        self.redis_url = redis_url
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold
        self._client = None
        self._is_available = None
        self._last_check_time = 0

    def _get_client(self):
        """Lazy connects to Redis with timeout to prevent blocking."""
        now = time.time()
        if self._client is not None:
            return self._client

        if self._is_available is False and (now - self._last_check_time < 10):
            return None

        self._last_check_time = now
        try:
            import redis
            client = redis.Redis.from_url(
                self.redis_url,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                decode_responses=True
            )
            client.ping()
            self._client = client
            self._is_available = True
            logger.info(f"[Intelligence Cache] Connected to Redis at {self.redis_url}")
            return self._client
        except Exception as e:
            self._client = None
            self._is_available = False
            logger.debug(f"[Intelligence Cache] Redis unavailable ({e}). Continuing in bypassed mode.")
            return None

    @property
    def is_online(self) -> bool:
        return self._get_client() is not None

    def _compute_key(self, query: str, data_version: str) -> str:
        norm = normalize_query_text(query)
        token = f"{norm}::{data_version}"
        h = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"up:cache:{h}"

    def get_match(
        self,
        query: str,
        current_data_version: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[float], str]:
        """
        Looks up cached question by exact match on sha256(normalized question + data_version).
        Returns: (cached_payload, similarity_score, cache_status)
        where cache_status is 'HIT_EXACT', 'MISS', or 'UNAVAILABLE'.
        """
        client = self._get_client()
        if client is None:
            return None, None, "UNAVAILABLE"

        try:
            cache_key = self._compute_key(query, current_data_version)
            raw = client.get(cache_key)
            if not raw:
                return None, None, "MISS"

            item = json.loads(raw)
            if item.get("data_version") == current_data_version:
                return item.get("response"), 1.0, "HIT_EXACT"

            return None, None, "MISS"
        except Exception as e:
            logger.warning(f"[Intelligence Cache] Error querying cache: {e}")
            return None, None, "UNAVAILABLE"

    def get_semantic_match(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        current_data_version: str = ""
    ) -> Tuple[Optional[Dict[str, Any]], Optional[float], str]:
        """Compatibility alias delegating to get_match without requiring embeddings."""
        return self.get_match(query, current_data_version)

    def store(
        self,
        query: str,
        response_or_embedding: Any,
        response_or_datasets: Any = None,
        supporting_datasets_or_version: Any = None,
        data_version: str = "",
        **kwargs
    ) -> bool:
        """Stores a verified query and generated answer in Redis with TTL."""
        client = self._get_client()
        if client is None:
            return False

        # Support both (query, response, datasets, version) and old (query, embedding, response, datasets, version)
        if isinstance(response_or_embedding, list):
            response = response_or_datasets
            supporting_datasets = supporting_datasets_or_version or []
            version = data_version
        else:
            response = response_or_embedding
            supporting_datasets = response_or_datasets or []
            version = supporting_datasets_or_version or data_version

        try:
            cache_key = self._compute_key(query, version)
            payload = {
                "question": query,
                "normalized_query": normalize_query_text(query),
                "response": response,
                "supporting_datasets": supporting_datasets,
                "data_version": version,
                "created_at": datetime.utcnow().isoformat()
            }

            serialized = json.dumps(payload)
            pipe = client.pipeline()
            pipe.setex(cache_key, self.ttl, serialized)
            pipe.sadd("up:cache:keys", cache_key)
            pipe.execute()
            return True
        except Exception as e:
            logger.warning(f"[Intelligence Cache] Failed to store in cache: {e}")
            return False

    def invalidate_all(self) -> int:
        """Flushes all UrbanPulse cache entries."""
        client = self._get_client()
        if client is None:
            return 0
        try:
            keys = set(client.keys("up:cache:*") + client.keys("up:semcache:*"))
            if keys:
                return client.delete(*keys)
            return 0
        except Exception:
            return 0

    def clear(self) -> int:
        return self.invalidate_all()

    def health_check(self) -> Dict[str, Any]:
        """Returns health and status of the Redis cache."""
        online = self.is_online
        key_count = 0
        if online:
            try:
                key_count = self._client.scard("up:cache:keys") or 0
            except Exception:
                pass
        return {
            "connected": online,
            "status": "online" if online else "bypassed_offline",
            "url": self.redis_url,
            "ttl_seconds": self.ttl,
            "cached_queries_count": key_count
        }


semantic_cache = RedisSemanticCache(
    redis_url=settings.REDIS_URL,
    ttl=settings.REDIS_CACHE_TTL,
    similarity_threshold=settings.REDIS_SIMILARITY_THRESHOLD
)
