"""
File-based cache for parsed job description results.

Avoids re-sending the same job URL to the LLM on repeated runs.
Cache is stored as a JSON file in the output/ directory.
Keyed by SHA-1 of the job URL so filenames stay short and safe.
"""
import hashlib
import json
import os
from typing import Optional

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "output", "job_parse_cache.json")
_cache: Optional[dict] = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
            return _cache
        except Exception:
            pass
    _cache = {}
    return _cache


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _key(url: str) -> str:
    return hashlib.sha1(url.strip().encode()).hexdigest()


def get(url: str) -> Optional[dict]:
    """Return cached parse result for url, or None if not cached."""
    return _load().get(_key(url))


def put(url: str, data: dict) -> None:
    """Store parse result for url."""
    cache = _load()
    cache[_key(url)] = data
    _save(cache)


def invalidate(url: str) -> None:
    """Remove a cached entry (e.g. if a job listing has changed)."""
    cache = _load()
    cache.pop(_key(url), None)
    _save(cache)
