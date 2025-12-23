"""
LangGraph Service Integration
Provides a clean interface to use LangGraph with the existing chatbot system.
"""

from typing import Dict, Any, Optional, List
from .langgraph.graph import app
from .langgraph.memory import get_history, save_history, clear_history

class LangGraphService:
    """Service class for LangGraph-based chatbot interactions"""
    
    @staticmethod
    def process_query(
        question: str,
        session_id: str,
        namespace: str = "kb_default",
        company_name: str = "our company"
    ) -> Dict[str, Any]:
        """
        Process a user query using LangGraph RAG pipeline.
        
        Args:
            question: User's question
            session_id: Unique session identifier
            namespace: Organization's knowledge base namespace (vectorStoreId)
            company_name: Organization name for personalized responses
            
        Returns:
            Dictionary containing answer, sources, and metadata
        """
        print(f"\n[LANGGRAPH SERVICE] === Processing Query ===")
        print(f"[LANGGRAPH SERVICE] Session: {session_id}")
        print(f"[LANGGRAPH SERVICE] Company: {company_name}")
        print(f"[LANGGRAPH SERVICE] Namespace: {namespace}")
        print(f"[LANGGRAPH SERVICE] Question: {question}")
        
        try:
            # Get conversation history
            chat_history = get_history(session_id)
            
            # Prepare state for LangGraph
            initial_state = {
                "session_id": session_id,
                "question": question,
                "namespace": namespace,
                "chat_history": chat_history,
                "context": "",
                "answer": "",
                "sources": [],
                "company_name": company_name
            }
            
            # Run the LangGraph workflow
            print(f"[LANGGRAPH SERVICE] Invoking LangGraph app...")
            result = app.invoke(initial_state)
            
            # Extract results
            answer = result.get("answer", "I apologize, but I'm unable to process your request right now.")
            sources = result.get("sources", [])
            
            print(f"[LANGGRAPH SERVICE] ✅ Answer generated: {len(answer)} characters")
            print(f"[LANGGRAPH SERVICE] ✅ Sources: {len(sources)} found")
            
            # Save to conversation history
            save_history(session_id, question, answer)
            
            return {
                "answer": answer,
                "sources": sources,
                "session_id": session_id,
                "mode": "langgraph_rag"
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
                "error": str(e)
            }
    
    @staticmethod
    def clear_session(session_id: str):
        """Clear conversation history for a session"""
        clear_history(session_id)
        print(f"[LANGGRAPH SERVICE] Session cleared: {session_id}")
    
    @staticmethod
    def get_session_history(session_id: str) -> List:
        """Retrieve conversation history for a session"""
        return get_history(session_id)
