"""
Enhanced Memory Management for LangGraph
Uses MongoDB as primary storage with in-memory caching for performance.
"""

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import List, Optional
from datetime import datetime, timedelta
from .config import RAG_MAX_HISTORY_TURNS
import time

# In-memory cache for active sessions (TTL-based)
MEMORY_CACHE = {}
CACHE_TTL = 3600  # 1 hour cache TTL

class SessionMemory:
    """Session memory with MongoDB persistence and in-memory caching"""

    def __init__(self, db):
        """
        Initialize session memory with database connection

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.conversations_collection = db.conversations

    def _get_from_cache(self, session_id: str) -> Optional[dict]:
        """Get session from cache if not expired"""
        if session_id in MEMORY_CACHE:
            cache_entry = MEMORY_CACHE[session_id]
            if time.time() - cache_entry['timestamp'] < CACHE_TTL:
                return cache_entry['messages']
            else:
                # Cache expired
                del MEMORY_CACHE[session_id]
        return None

    def _set_cache(self, session_id: str, messages: List[BaseMessage]):
        """Store messages in cache"""
        MEMORY_CACHE[session_id] = {
            'messages': messages,
            'timestamp': time.time()
        }

    def get_history(self, session_id: str, organization_id: Optional[str] = None) -> List[BaseMessage]:
        """
        Retrieve conversation history for a session from MongoDB.
        Uses in-memory cache for performance.

        Args:
            session_id: Unique session identifier
            organization_id: Organization ID for filtering (optional)

        Returns:
            List of conversation messages (limited by RAG_MAX_HISTORY_TURNS)
        """
        # Try cache first
        cached_messages = self._get_from_cache(session_id)
        if cached_messages is not None:
            print(f"[MEMORY V2] 🚀 Cache hit for session {session_id}: {len(cached_messages)} messages")
            return cached_messages

        # Cache miss - fetch from MongoDB
        print(f"[MEMORY V2] 💾 Loading from MongoDB for session {session_id}")

        query = {"session_id": session_id}
        if organization_id:
            query["organization_id"] = organization_id

        # Fetch conversations sorted by creation time
        conversations = list(
            self.conversations_collection.find(query)
            .sort("created_at", 1)  # Oldest first
            .limit(RAG_MAX_HISTORY_TURNS * 2)  # Limit to max turns * 2 messages
        )

        # Convert to LangChain messages
        messages = []
        for conv in conversations:
            role = conv.get("role")
            content = conv.get("content", "")

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        # Keep only recent turns (sliding window)
        max_messages = RAG_MAX_HISTORY_TURNS * 2
        if len(messages) > max_messages:
            messages = messages[-max_messages:]

        # Update cache
        self._set_cache(session_id, messages)

        print(f"[MEMORY V2] Retrieved {len(messages)} messages for session {session_id}")
        return messages

    def save_history(self, session_id: str, user_message: str, ai_message: str,
                     organization_id: Optional[str] = None, visitor_id: Optional[str] = None):
        """
        Save a conversation turn to session history in MongoDB.
        Updates cache automatically.

        Args:
            session_id: Unique session identifier
            user_message: User's question
            ai_message: AI's response
            organization_id: Organization ID (for MongoDB storage)
            visitor_id: Visitor ID (for MongoDB storage)
        """
        # Note: MongoDB persistence happens in the route layer (chatbot.py)
        # This method updates the cache

        # Get current history
        history = self.get_history(session_id, organization_id)

        # Add new messages
        history.append(HumanMessage(content=user_message))
        history.append(AIMessage(content=ai_message))

        # Keep only recent turns
        max_messages = RAG_MAX_HISTORY_TURNS * 2
        if len(history) > max_messages:
            history = history[-max_messages:]

        # Update cache
        self._set_cache(session_id, history)

        print(f"[MEMORY V2] Saved turn for session {session_id}. Total messages: {len(history)}")

    def clear_history(self, session_id: str):
        """Clear conversation history for a session from cache"""
        if session_id in MEMORY_CACHE:
            del MEMORY_CACHE[session_id]
            print(f"[MEMORY V2] Cleared cache for session {session_id}")

    def clear_expired_cache(self):
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_sessions = [
            sid for sid, data in MEMORY_CACHE.items()
            if current_time - data['timestamp'] > CACHE_TTL
        ]

        for sid in expired_sessions:
            del MEMORY_CACHE[sid]

        if expired_sessions:
            print(f"[MEMORY V2] Cleared {len(expired_sessions)} expired cache entries")

    def get_session_count(self) -> int:
        """Get number of active cached sessions"""
        self.clear_expired_cache()
        return len(MEMORY_CACHE)

    def get_full_conversation_summary(self, session_id: str, organization_id: Optional[str] = None) -> str:
        """
        Get a text summary of the full conversation for context.
        Useful for long conversations that exceed token limits.

        Args:
            session_id: Unique session identifier
            organization_id: Organization ID for filtering

        Returns:
            Formatted conversation summary
        """
        messages = self.get_history(session_id, organization_id)

        if not messages:
            return "No previous conversation"

        summary_parts = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                summary_parts.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                summary_parts.append(f"Assistant: {msg.content}")

        return "\n".join(summary_parts)
