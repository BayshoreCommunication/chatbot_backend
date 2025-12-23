import os
import json
import time
import logging
from typing import Optional, Any, Dict

# Simple in-memory cache
_memory_cache: Dict[str, Dict[str, Any]] = {}

class RedisCache:
    """
    Simplified Cache Wrapper
    Defaults to in-memory caching to avoid Redis dependency issues.
    """
    def __init__(self):
        self.redis_client = None
        # print("[DEBUG] Cache initialized (In-Memory Mode)")

    def is_available(self):
        return False

# Global cache instance
cache = RedisCache()

def get_from_cache(key: str) -> Optional[Any]:
    """Get value from in-memory cache"""
    try:
        if key in _memory_cache:
            data = _memory_cache[key]
            # Check expiration
            if data["expires_at"] > time.time():
                # print(f"[DEBUG] Memory Cache HIT: {key}")
                return data["value"]
            else:
                # print(f"[DEBUG] Memory Cache EXPIRED: {key}")
                del _memory_cache[key]
        return None
    except Exception as e:
        print(f"[ERROR] Cache GET failed: {str(e)}")
        return None

def set_cache(key: str, value: Any, ttl_minutes: int = 30) -> bool:
    """Set value in in-memory cache"""
    try:
        expires_at = time.time() + (ttl_minutes * 60)
        _memory_cache[key] = {
            "value": value,
            "expires_at": expires_at
        }
        # print(f"[DEBUG] Memory Cache SET: {key} (TTL: {ttl_minutes}m)")
        return True
    except Exception as e:
        print(f"[ERROR] Cache SET failed: {str(e)}")
        return False

def delete_cache(key: str) -> bool:
    """Delete value from in-memory cache"""
    try:
        if key in _memory_cache:
            del _memory_cache[key]
            return True
        return False
    except Exception as e:
        print(f"[ERROR] Cache DELETE failed: {str(e)}")
        return False

def cache_key(*parts) -> str:
    """Generate a cache key from multiple parts"""
    return ":".join(str(part) for part in parts)

def invalidate_chatbot_cache(org_id: str = None):
    """Invalidate chatbot related cache keys"""
    try:
        keys_to_remove = []
        prefix = f"knowledge:{org_id}" if org_id else "knowledge:"
        
        for key in list(_memory_cache.keys()):
            if key.startswith(prefix) or "vectorstore" in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del _memory_cache[key]
            
        if keys_to_remove:
            print(f"[DEBUG] Invalidated {len(keys_to_remove)} cache keys for org {org_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Cache invalidation failed: {str(e)}")
        return False

def invalidate_admin_cache():
    """Invalidate admin related cache keys"""
    try:
        keys_to_remove = []
        
        for key in list(_memory_cache.keys()):
            if key.startswith("admin:"):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del _memory_cache[key]
            
        if keys_to_remove:
            print(f"[DEBUG] Invalidated {len(keys_to_remove)} admin cache keys")
        return True
    except Exception as e:
        print(f"[ERROR] Admin cache invalidation failed: {str(e)}")
        return False