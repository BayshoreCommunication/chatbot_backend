from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import List
from .config import RAG_MAX_HISTORY_TURNS

# In-memory session storage (replace with Redis/MongoDB in production)
SESSION_DB = {}

def get_history(session_id: str) -> List[BaseMessage]:
    """
    Retrieve conversation history for a session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        List of conversation messages
    """
    history = SESSION_DB.get(session_id, [])
    print(f"[MEMORY] Retrieved {len(history)} messages for session {session_id}")
    return history

def save_history(session_id: str, user_message: str, ai_message: str):
    """
    Save a conversation turn to session history.
    Maintains a sliding window of recent turns.
    
    Args:
        session_id: Unique session identifier
        user_message: User's question
        ai_message: AI's response
    """
    history = SESSION_DB.get(session_id, [])
    
    # Add new messages
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=ai_message))
    
    # Keep only recent turns (each turn = 2 messages)
    max_messages = RAG_MAX_HISTORY_TURNS * 2
    if len(history) > max_messages:
        history = history[-max_messages:]
    
    SESSION_DB[session_id] = history
    print(f"[MEMORY] Saved turn for session {session_id}. Total messages: {len(history)}")

def clear_history(session_id: str):
    """Clear conversation history for a session"""
    if session_id in SESSION_DB:
        del SESSION_DB[session_id]
        print(f"[MEMORY] Cleared history for session {session_id}")

def get_session_count() -> int:
    """Get number of active sessions"""
    return len(SESSION_DB)
