import json
from typing import Any, Optional
import redis
from redis import Redis
from app.core.config import settings

_client: Optional[Any] = None
_use_mock = False

class MockRedis:
    def __init__(self):
        self.store = {}
    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)
    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

def get_cache_client() -> Any:
    global _client, _use_mock
    if _client is not None:
        return _client
        
    if _use_mock:
        return MockRedis()
        
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1.0)
        client.ping()
        _client = client
        return _client
    except Exception:
        # Fall back to in-memory mock cache
        _use_mock = True
        _client = MockRedis()
        return _client


def cache_get_json(key: str) -> Any:
    value = get_cache_client().get(key)
    if not value:
        return None
    return json.loads(value)


def cache_set_json(key: str, payload: Any, ttl_seconds: int) -> None:
    get_cache_client().setex(key, ttl_seconds, json.dumps(payload))

