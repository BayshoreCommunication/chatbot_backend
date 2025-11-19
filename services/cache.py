

import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

# Configure loggingformat
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [CACHE] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class CacheService:
    def __init__(self):
        """Initialize cache service with Redis fallback to in-memory"""
        self.redis_client = None
        self.memory_cache = {}  # Fallback in-memory cache
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        
        # Try to connect to Redis
        try:
            import redis
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Connected to Redis at {self.redis_host}:{self.redis_port}")
        except ImportError:
            logger.warning("❌ Redis package not installed. Using in-memory cache.")
            logger.info("💡 Install Redis: pip install redis")
        except Exception as e:
            logger.warning(f"❌ Failed to connect to Redis: {e}")
            logger.info("💡 Using in-memory cache. Install and start Redis for better performance.")
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self.redis_client is not None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a value in cache with TTL"""
        try:
            if self.redis_client:
                # Use Redis
                serialized_value = json.dumps(value, default=str)
                success = self.redis_client.setex(key, ttl, serialized_value)
                if success:
                    logger.info(f"📝 Redis SET: {key} (TTL: {ttl}s)")
                return success
            else:
                # Use in-memory cache with expiry
                expiry_time = datetime.now() + timedelta(seconds=ttl)
                self.memory_cache[key] = {
                    "value": value,
                    "expiry": expiry_time
                }
                logger.info(f"📝 Memory SET: {key} (TTL: {ttl}s)")
                return True
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        try:
            if self.redis_client:
                # Use Redis
                cached_value = self.redis_client.get(key)
                if cached_value is None:
                    logger.info(f"❌ Redis MISS: {key}")
                    return None
                logger.info(f"✅ Redis HIT: {key}")
                return json.loads(cached_value)
            else:
                # Use in-memory cache
                if key in self.memory_cache:
                    cache_entry = self.memory_cache[key]
                    if datetime.now() < cache_entry["expiry"]:
                        logger.info(f"✅ Memory HIT: {key}")
                        return cache_entry["value"]
                    else:
                        # Expired, remove it
                        del self.memory_cache[key]
                        logger.info(f"⏰ Memory EXPIRED: {key}")
                        return None
                else:
                    logger.info(f"❌ Memory MISS: {key}")
                    return None
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            if self.redis_client:
                success = bool(self.redis_client.delete(key))
                if success:
                    logger.info(f"🗑️ Redis DELETE: {key}")
                return success
            else:
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    logger.info(f"🗑️ Memory DELETE: {key}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    logger.info(f"🗑️ Redis DELETE PATTERN: {pattern} (deleted {deleted} keys)")
                    return deleted
                return 0
            else:
                # In-memory pattern matching
                import fnmatch
                matching_keys = [k for k in self.memory_cache.keys() if fnmatch.fnmatch(k, pattern)]
                for key in matching_keys:
                    del self.memory_cache[key]
                logger.info(f"🗑️ Memory DELETE PATTERN: {pattern} (deleted {len(matching_keys)} keys)")
                return len(matching_keys)
        except Exception as e:
            logger.error(f"Failed to delete keys with pattern {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.exists(key))
            else:
                return key in self.memory_cache and datetime.now() < self.memory_cache[key]["expiry"]
        except Exception as e:
            logger.error(f"Failed to check if key {key} exists: {e}")
            return False
    
    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key"""
        try:
            if self.redis_client:
                return self.redis_client.ttl(key)
            else:
                if key in self.memory_cache:
                    remaining = self.memory_cache[key]["expiry"] - datetime.now()
                    return int(remaining.total_seconds()) if remaining.total_seconds() > 0 else -2
                return -2
        except Exception as e:
            logger.error(f"Failed to get TTL for key {key}: {e}")
            return -1
    
    def get_cache_info(self) -> dict:
        """Get cache system information"""
        if self.redis_client:
            try:
                info = self.redis_client.info()
                return {
                    "type": "Redis",
                    "connected": True,
                    "host": self.redis_host,
                    "port": self.redis_port,
                    "db": self.redis_db,
                    "memory_usage": info.get("used_memory_human", "Unknown"),
                    "total_keys": info.get("db0", {}).get("keys", 0) if "db0" in info else 0
                }
            except Exception as e:
                return {
                    "type": "Redis",
                    "connected": False,
                    "error": str(e)
                }
        else:
            return {
                "type": "In-Memory",
                "connected": True,
                "total_keys": len(self.memory_cache),
                "memory_usage": f"{len(str(self.memory_cache))} bytes (approx)"
            }

# Create a global cache instance
cache = CacheService()

def cache_key(*args) -> str:
    """Generate a cache key from arguments"""
    return ":".join(str(arg) for arg in args)

def invalidate_admin_cache():
    """Invalidate all admin-related cache entries"""
    logger.info("Starting admin cache invalidation")
    patterns = [
        "admin:*",
        "dashboard:*",
        "organizations:*",
        "conversations:*",
        "subscriptions:*",
        "analytics:*"
    ]
    
    total_deleted = 0
    for pattern in patterns:
        deleted = cache.delete_pattern(pattern)
        total_deleted += deleted
        logger.info(f"Invalidated {deleted} cache entries matching pattern: {pattern}")
    
    logger.info(f"Total cache entries invalidated: {total_deleted}")
    return total_deleted

# Convenience functions for chatbot engine
def get_from_cache(key: str) -> Optional[Any]:
    """Get value from cache - convenience function for engine"""
    return cache.get(key)

def set_cache(key: str, value: Any, expiry_minutes: int = 5) -> bool:
    """Set value in cache - convenience function for engine"""
    ttl_seconds = expiry_minutes * 60
    return cache.set(key, value, ttl_seconds)

def invalidate_chatbot_cache(org_id: str = None):
    """Invalidate chatbot-related cache entries"""
    patterns = [
        "chatbot:*",
        "response:*",
        "knowledge:*"
    ]
    
    if org_id:
        patterns.append(f"org:{org_id}:*")
    
    total_deleted = 0
    for pattern in patterns:
        deleted = cache.delete_pattern(pattern)
        total_deleted += deleted
        logger.info(f"Invalidated {deleted} chatbot cache entries matching: {pattern}")
    
    return total_deleted

def get_cache_status():
    """Get comprehensive cache status"""
    return {
        "cache_info": cache.get_cache_info(),
        "is_available": cache.is_available(),
        "timestamp": datetime.now().isoformat()
    }