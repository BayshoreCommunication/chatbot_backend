import redis
import json
import os
from datetime import timedelta
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [CACHE] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class CacheService:
    def __init__(self):
        # Connect to Redis on WSL Ubuntu (default localhost:6379)
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        
        try:
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
            logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self.redis_client is not None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Set a value in cache with TTL (Time To Live)
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 5 minutes)
        """
        if not self.is_available():
            logger.warning(f"Cache SKIP (Redis unavailable): {key}")
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            success = self.redis_client.setex(key, ttl, serialized_value)
            if success:
                logger.info(f"Cache SET: {key} (TTL: {ttl}s)")
            else:
                logger.warning(f"Cache SET failed: {key}")
            return success
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        if not self.is_available():
            logger.warning(f"Cache SKIP (Redis unavailable): {key}")
            return None
        
        try:
            cached_value = self.redis_client.get(key)
            if cached_value is None:
                logger.info(f"Cache MISS: {key}")
                return None
            logger.info(f"Cache HIT: {key}")
            return json.loads(cached_value)
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        if not self.is_available():
            logger.warning(f"Cache SKIP (Redis unavailable): {key}")
            return False
        
        try:
            success = bool(self.redis_client.delete(key))
            if success:
                logger.info(f"Cache DELETE: {key}")
            else:
                logger.warning(f"Cache DELETE failed (key not found): {key}")
            return success
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern"""
        if not self.is_available():
            logger.warning(f"Cache SKIP (Redis unavailable): {pattern}")
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cache DELETE PATTERN: {pattern} (deleted {deleted} keys)")
                return deleted
            logger.info(f"Cache DELETE PATTERN: {pattern} (no keys found)")
            return 0
        except Exception as e:
            logger.error(f"Failed to delete keys with pattern {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        if not self.is_available():
            logger.warning(f"Cache SKIP (Redis unavailable): {key}")
            return False
        
        try:
            exists = bool(self.redis_client.exists(key))
            if exists:
                logger.debug(f"Cache EXISTS: {key}")
            else:
                logger.debug(f"Cache NOT EXISTS: {key}")
            return exists
        except Exception as e:
            logger.error(f"Failed to check if key {key} exists: {e}")
            return False
    
    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key"""
        if not self.is_available():
            logger.warning(f"Cache SKIP (Redis unavailable): {key}")
            return -1
        
        try:
            ttl = self.redis_client.ttl(key)
            if ttl > 0:
                logger.debug(f"Cache TTL: {key} ({ttl}s remaining)")
            elif ttl == -1:
                logger.debug(f"Cache TTL: {key} (no expiry)")
            else:
                logger.debug(f"Cache TTL: {key} (expired/not found)")
            return ttl
        except Exception as e:
            logger.error(f"Failed to get TTL for key {key}: {e}")
            return -1

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