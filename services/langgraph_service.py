"""
Enhanced LangGraph Service Integration
Features:
1. MongoDB-backed memory with caching
2. Conversation summarization for long conversations
3. Query rewriting for context-dependent questions
4. Better session management
5. Off-topic detection and smart redirect
"""

from typing import Dict, Any, Optional, List
from .langgraph.graph import app
from .langgraph.memory import SessionMemory
from .langgraph.summarizer import get_summarized_context

class LangGraphService:
    """Enhanced service class for LangGraph-based chatbot interactions with off-topic handling"""

    def __init__(self, db):
        """
        Initialize service with database connection

        Args:
            db: MongoDB database instance
        """
        self.memory = SessionMemory(db)

    def process_query(
        self,
        question: str,
        session_id: str,
        organization_id: Optional[str] = None,
        visitor_id: Optional[str] = None,
        namespace: str = "kb_default",
        company_name: str = "our company"
    ) -> Dict[str, Any]:
        """
        Process a user query using enhanced LangGraph RAG pipeline with off-topic detection.

        Args:
            question: User's question
            session_id: Unique session identifier
            organization_id: Organization ID for MongoDB queries
            visitor_id: Visitor ID for tracking
            namespace: Organization's knowledge base namespace (vectorStoreId)
            company_name: Organization name for personalized responses

        Returns:
            Dictionary containing answer, sources, and metadata
        """
        print(f"\n[LANGGRAPH SERVICE] === Processing Query ===")
        print(f"[LANGGRAPH SERVICE] Session: {session_id}")
        print(f"[LANGGRAPH SERVICE] Organization: {organization_id}")
        print(f"[LANGGRAPH SERVICE] Company: {company_name}")
        print(f"[LANGGRAPH SERVICE] Namespace: {namespace}")
        print(f"[LANGGRAPH SERVICE] Question: {question}")

        try:
            # Get conversation history from MongoDB (with caching)
            chat_history = self.memory.get_history(session_id, organization_id)

            print(f"[LANGGRAPH SERVICE] Loaded {len(chat_history)} messages from history")

            # Get summarized context for long conversations
            context_data = get_summarized_context(chat_history, max_recent_turns=3)

            conversation_summary = context_data.get("summary", "")
            recent_messages = context_data.get("recent_messages", chat_history)
            has_summary = context_data.get("has_summary", False)

            if has_summary:
                print(f"[LANGGRAPH SERVICE] Using conversation summary for older messages")
                print(f"[LANGGRAPH SERVICE] Recent messages: {len(recent_messages)}")

            # Prepare state for LangGraph
            initial_state = {
                "session_id": session_id,
                "question": question,
                "original_question": question,
                "namespace": namespace,
                "chat_history": chat_history,  # Full history for rewriting
                "conversation_summary": conversation_summary,
                "recent_messages": recent_messages,
                "context": "",
                "answer": "",
                "sources": [],
                "company_name": company_name,
                "use_web_search": False,
                "skip_search": False,
                "rewritten_query": False,
                "is_off_topic": False,
                "off_topic_redirect": False,
                # 🆕 Lead Collection Fields
                "detected_intent": "",
                "conversation_stage": "greeting",
                "collected_contact": {"name": None, "phone": None, "email": None},
                "needs_callback": False,
                "contact_confirmed": False
            }

            # Run the enhanced LangGraph workflow
            print(f"[LANGGRAPH SERVICE] Invoking LangGraph app...")
            result = app.invoke(initial_state)

            # Extract results
            answer = result.get("answer", "I apologize, but I'm unable to process your request right now.")
            sources = result.get("sources", [])
            rewritten_query = result.get("rewritten_query", False)
            is_off_topic = result.get("is_off_topic", False)
            off_topic_redirect = result.get("off_topic_redirect", False)

            # 🆕 Extract lead collection fields
            detected_intent = result.get("detected_intent", "")
            conversation_stage = result.get("conversation_stage", "")
            collected_contact = result.get("collected_contact", {})
            needs_callback = result.get("needs_callback", False)
            contact_confirmed = result.get("contact_confirmed", False)

            print(f"[LANGGRAPH SERVICE] ✅ Answer generated: {len(answer)} characters")
            print(f"[LANGGRAPH SERVICE] ✅ Sources: {len(sources)} found")

            if rewritten_query:
                print(f"[LANGGRAPH SERVICE] ✅ Query was rewritten for better context")

            if is_off_topic:
                print(f"[LANGGRAPH SERVICE] ⚠️ Off-topic question detected and redirected")

            # 🆕 Log lead collection status
            if needs_callback:
                print(f"[LANGGRAPH SERVICE] 📞 Callback requested")
                if any(collected_contact.values()):
                    print(f"[LANGGRAPH SERVICE] 👤 Lead collected - Name: {collected_contact.get('name')}, Phone: {collected_contact.get('phone')}, Email: {collected_contact.get('email')}")

            # Save to conversation history (cache + will be persisted to MongoDB in route layer)
            self.memory.save_history(
                session_id=session_id,
                user_message=question,
                ai_message=answer,
                organization_id=organization_id,
                visitor_id=visitor_id
            )

            return {
                "answer": answer,
                "sources": sources,
                "session_id": session_id,
                "mode": "langgraph_rag",
                "query_rewritten": rewritten_query,
                "has_summary": has_summary,
                "is_off_topic": is_off_topic,
                "off_topic_redirect": off_topic_redirect,
                # 🆕 Lead Collection Data
                "detected_intent": detected_intent,
                "conversation_stage": conversation_stage,
                "collected_contact": collected_contact,
                "needs_callback": needs_callback,
                "contact_confirmed": contact_confirmed,
                # 🆕 Lead complete indicator
                "lead_collected": bool(collected_contact.get("name") and collected_contact.get("phone"))
            }

        except Exception as e:
            print(f"[LANGGRAPH SERVICE] ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()

            # Return fallback response
            return {
                "answer": "I apologize, but I encountered an error processing your request. Please try again.",
                "sources": [],
                "session_id": session_id,
                "mode": "error",
                "error": str(e),
                "is_off_topic": False,
                "off_topic_redirect": False
            }

    def clear_session(self, session_id: str):
        """Clear conversation history for a session"""
        self.memory.clear_history(session_id)
        print(f"[LANGGRAPH SERVICE] Session cleared: {session_id}")

    def get_session_history(self, session_id: str, organization_id: Optional[str] = None) -> List:
        """Retrieve conversation history for a session"""
        return self.memory.get_history(session_id, organization_id)

    def get_session_summary(self, session_id: str, organization_id: Optional[str] = None) -> str:
        """Get a text summary of the full conversation"""
        return self.memory.get_full_conversation_summary(session_id, organization_id)

    def cleanup_expired_sessions(self):
        """Remove expired entries from cache"""
        self.memory.clear_expired_cache()
        print(f"[LANGGRAPH SERVICE] Expired cache entries cleaned up")


# Singleton instance factory
_service_instance = None

def get_langgraph_service(db) -> LangGraphService:
    """
    Get singleton instance of LangGraphService

    Args:
        db: MongoDB database instance

    Returns:
        LangGraphService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = LangGraphService(db)
    return _service_instance
