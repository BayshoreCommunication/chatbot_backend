from datetime import datetime
from typing import Dict, Any, Optional

# Import the AI Engine
from services.langchain.engine import ask_bot

# Import Database Helpers (Assuming these exist in your project)
from services.database import (
    create_or_update_visitor,
    add_conversation_message,
    is_chat_in_agent_mode,
    save_user_profile
)

class ChatbotService:
    """
    Orchestrates the chatbot flow: Validation -> Persistence -> AI Engine
    """
    
    @staticmethod
    async def process_chat_request(
        question: str,
        session_id: str,
        api_key: str,
        organization: Dict,
        mode: str = "chat",
        user_data: Dict = None,
        **kwargs
    ) -> Dict:
        
        org_id = str(organization["_id"])
        org_name = organization.get("name", "Unknown")

        # ---------------------------------------------------------
        # 1. AGENT MODE CHECK (Stop AI if human is here)
        # ---------------------------------------------------------
        if is_chat_in_agent_mode(org_id, session_id):
            # We still save the message so the agent sees it
            ChatbotService._save_message(org_id, session_id, "user", question, mode)
            return {
                "answer": "", 
                "mode": "agent_active", 
                "message": "Message sent to human agent."
            }

        # ---------------------------------------------------------
        # 2. SESSION & VISITOR SETUP
        # ---------------------------------------------------------
        # Ensure visitor exists in DB
        visitor = create_or_update_visitor(org_id, session_id, {"user_data": user_data})
        
        # Save the User's Question to DB
        ChatbotService._save_message(org_id, session_id, "user", question, mode)

        # ---------------------------------------------------------
        # 3. CALL THE AI ENGINE (The Brain)
        # ---------------------------------------------------------
        # This is where the RAG magic happens
        # Extract vectorStoreId from kwargs to avoid duplicate
        vector_store_id = kwargs.get("vectorStoreId")
        kb_id = kwargs.get("kb_id")
        
        ai_result = ask_bot(
            query=question,
            session_id=session_id,
            api_key=api_key,
            user_data=user_data,
            org_name=org_name,
            vectorStoreId=vector_store_id,
            kb_id=kb_id
        )

        answer_text = ai_result.get("answer", "I'm sorry, I couldn't process that.")
        sources = ai_result.get("sources", [])

        # ---------------------------------------------------------
        # 4. SAVE RESPONSE & UPDATE PROFILE
        # ---------------------------------------------------------
        # Save AI Answer to DB
        ChatbotService._save_message(
            org_id, 
            session_id, 
            "assistant", 
            answer_text, 
            mode, 
            metadata={"sources": sources}
        )

        # If user provided name/email in the chat, update their profile
        if user_data:
            save_user_profile(org_id, session_id, user_data)
        
        return {
            "answer": answer_text,
            "session_id": session_id,
            "mode": "rag",
            "sources": sources
        }

    @staticmethod
    def _save_message(org_id, session_id, role, content, mode, metadata=None):
        """Helper to save messages to DB"""
        if metadata is None: metadata = {}
        metadata["mode"] = mode
        
        add_conversation_message(
            organization_id=org_id,
            visitor_id=None, # database function handles looking this up usually
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata
        )