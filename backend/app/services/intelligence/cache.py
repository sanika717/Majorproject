import json
import math
import hashlib
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger("urbanpulse.intelligence.cache")

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
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
    Persistent Semantic Vector Cache backed by Redis.
    - Matches queries based on embedding cosine similarity (threshold >= 0.90)
    - Validates data-version fingerprint so stale answers are never served
    - Handles Redis connection failures gracefully with seamless bypass
    """

    def __init__(self, redis_url: str = "redis://127.0.0.1:6379/0", ttl: int = 86400, similarity_threshold: float = 0.90):
        self.redis_url = redis_url
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold
        self._client = None
        self._is_available = None
        self._last_check_time = 0

    def _get_client(self):
        """Lazy connects to Redis with timeout to prevent blocking."""
        now = time.time()
        # Retry connection every 10 seconds if previously unavailable
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

    def get_semantic_match(
        self,
        query: str,
        query_embedding: List[float],
        current_data_version: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[float], str]:
        """
        Searches cached questions for high semantic similarity (>= threshold)
        and matching data version.
        Returns: (cached_payload, similarity_score, cache_status)
        where cache_status is 'HIT', 'MISS', or 'UNAVAILABLE'.
        """
        client = self._get_client()
        if client is None:
            return None, None, "UNAVAILABLE"

        try:
            # 1. Exact match check via normalized query hash
            norm = normalize_query_text(query)
            exact_key = f"up:semcache:exact:{hashlib.sha256(norm.encode()).hexdigest()[:16]}"
            cached_ref = client.get(exact_key)
            if cached_ref:
                data = client.get(cached_ref)
                if data:
                    item = json.loads(data)
                    if item.get("data_version") == current_data_version:
                        return item["response"], 1.0, "HIT_EXACT"

            # 2. Semantic vector search across cached index
            index_keys = client.smembers("up:semcache:keys")
            if not index_keys:
                return None, None, "MISS"

            best_match = None
            highest_sim = 0.0

            # Scan up to 50 most recent cached queries
            keys_to_fetch = list(index_keys)[:50]
            pipe = client.pipeline()
            for k in keys_to_fetch:
                pipe.get(k)
            entries = pipe.execute()

            for k, raw in zip(keys_to_fetch, entries):
                if not raw:
                    client.srem("up:semcache:keys", k)
                    continue
                try:
                    cached_item = json.loads(raw)
                    cached_emb = cached_item.get("embedding")
                    if not cached_emb:
                        continue

                    # Check data version: invalidate if underlying datasets modified
                    if cached_item.get("data_version") != current_data_version:
                        continue

                    sim = cosine_similarity(query_embedding, cached_emb)
                    if sim > highest_sim:
                        highest_sim = sim
                        if sim >= self.similarity_threshold:
                            best_match = cached_item

                except Exception:
                    continue

            if best_match and highest_sim >= self.similarity_threshold:
                return best_match["response"], round(highest_sim, 4), "HIT_SEMANTIC"

            return None, (round(highest_sim, 4) if highest_sim > 0 else None), "MISS"

        except Exception as e:
            logger.warning(f"[Intelligence Cache] Error querying cache: {e}")
            return None, None, "UNAVAILABLE"

    def store(
        self,
        query: str,
        query_embedding: List[float],
        response: Dict[str, Any],
        supporting_datasets: List[str],
        data_version: str
    ) -> bool:
        """Stores a verified query and generated answer in Redis with TTL."""
        client = self._get_client()
        if client is None:
            return False

        try:
            norm = normalize_query_text(query)
            key_hash = hashlib.sha256((norm + str(query_embedding[:5])).encode()).hexdigest()[:16]
            cache_key = f"up:semcache:entry:{key_hash}"
            exact_key = f"up:semcache:exact:{hashlib.sha256(norm.encode()).hexdigest()[:16]}"

            payload = {
                "question": query,
                "normalized_query": norm,
                "embedding": query_embedding,
                "response": response,
                "supporting_datasets": supporting_datasets,
                "data_version": data_version,
                "created_at": datetime.utcnow().isoformat()
            }

            serialized = json.dumps(payload)
            pipe = client.pipeline()
            pipe.setex(cache_key, self.ttl, serialized)
            pipe.setex(exact_key, self.ttl, cache_key)
            pipe.sadd("up:semcache:keys", cache_key)
            pipe.execute()
            return True

        except Exception as e:
            logger.warning(f"[Intelligence Cache] Failed to store in cache: {e}")
            return False

    def invalidate_all(self) -> int:
        """Flushes all UrbanPulse semantic cache entries."""
        client = self._get_client()
        if client is None:
            return 0
        try:
            keys = client.keys("up:semcache:*")
            if keys:
                return client.delete(*keys)
            return 0
        except Exception:
            return 0

    def clear(self) -> int:
        return self.invalidate_all()

    def health_check(self) -> Dict[str, Any]:
        """Returns health and status of the Redis semantic cache."""
        online = self.is_online
        key_count = 0
        if online:
            try:
                key_count = self._client.scard("up:semcache:keys") or 0
            except Exception:
                pass
        return {
            "connected": online,
            "status": "online" if online else "bypassed_offline",
            "url": self.redis_url,
            "ttl_seconds": self.ttl,
            "similarity_threshold": self.similarity_threshold,
            "cached_queries_count": key_count
        }


from backend.app.core.config import settings

semantic_cache = RedisSemanticCache(
    redis_url=settings.REDIS_URL,
    ttl=settings.REDIS_CACHE_TTL,
    similarity_threshold=settings.REDIS_SIMILARITY_THRESHOLD
)

