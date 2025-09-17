"""
IMPROVED CHATBOT ROUTE - Clean, Fast, Smart
==========================================
This version removes duplicate logic and lets the smart engine handle everything.
"""

import logging
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, Header, Body
from typing import Optional, Dict, Any, List
import json
import os
from pydantic import BaseModel
from datetime import datetime

# Import services
from services.langchain.engine import ask_bot, add_document, escalate_to_human
from services.language_detect import detect_language
from services.database import (
    get_organization_by_api_key, create_or_update_visitor, add_conversation_message, 
    get_visitor, get_conversation_history, save_user_profile, get_user_profile, db,
    set_agent_mode, set_bot_mode, is_chat_in_agent_mode
)
from services.faq_matcher import find_matching_faq, get_suggested_faqs
from services.cache import get_from_cache, set_cache

router = APIRouter()
sio = None

# Request models
class ChatRequest(BaseModel):
    question: str
    mode: str = "faq"
    user_data: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    available_slots: Optional[List[str]] = None

class ChatWidgetSettings(BaseModel):
    name: str
    selectedColor: str
    leadCapture: bool
    botBehavior: str
    ai_behavior: str
    avatarUrl: Optional[str] = None
    is_bot_connected: Optional[bool] = False

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

def get_welcome_message(organization: dict, is_first_visit: bool) -> str:
    """Generate appropriate welcome message"""
    org_name = organization.get("name", "our team")
    chat_settings = organization.get("chat_widget_settings", {})
    ai_behavior = chat_settings.get("ai_behavior", "")
    
    if is_first_visit:
        if ai_behavior:
            return f"Hello! Welcome to {org_name}. {ai_behavior.split('.')[0]}. How can I help you today?"
        else:
            return f"Hello! Welcome to {org_name}. I'm here to help answer your questions and assist you. What would you like to know?"
    else:
        return f"Welcome back! How can I assist you today?"

@router.post("/ask")
async def ask_question(
    request: ChatRequest, 
    organization=Depends(get_organization_from_api_key)
):
    """Process a chat message and return a response - IMPROVED VERSION"""
    org_id = organization["id"]
    org_api_key = organization.get("api_key")
    namespace = organization.get("pinecone_namespace", "")

    try:
        print(f"[DEBUG] Processing message: {request.question}")
        print(f"[DEBUG] Session ID: {request.session_id}")

        # Check if this chat is in agent mode
        if is_chat_in_agent_mode(org_id, request.session_id):
            print(f"[DEBUG] Chat {request.session_id} is in agent mode - skipping AI processing")
            
            # Handle agent mode (existing logic)
            visitor = create_or_update_visitor(
                organization_id=org_id,
                session_id=request.session_id,
                visitor_data={
                    "last_active": None,
                    "metadata": {
                        "mode": request.mode,
                        "user_data": request.user_data
                    }
                }
            )

            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="user",
                content=request.question,
                metadata={"mode": request.mode, "agent_mode": True}
            )

            if sio:
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'user',
                        'content': request.question,
                        'timestamp': datetime.utcnow().isoformat()
                    },
                    'organization_id': org_id,
                    'agent_mode': True
                }, room=org_api_key)

            return {
                "answer": "",
                "mode": "agent",
                "language": "en",
                "user_data": request.user_data or {},
                "agent_mode": True,
                "message": "Message received - agent will respond shortly"
            }

        # Continue with normal AI processing
        print(f"[DEBUG] Chat {request.session_id} is in bot mode - continuing with AI processing")

        # Get or create visitor
        visitor = create_or_update_visitor(
            organization_id=org_id,
            session_id=request.session_id,
            visitor_data={
                "last_active": None,
                "metadata": {
                    "mode": request.mode,
                    "user_data": request.user_data
                }
            }
        )

        # Initialize session data
        if not request.user_data:
            request.user_data = {}
        
        # Get previous conversations with caching
        cache_key = f"conversations:{org_id}:{request.session_id}"
        previous_conversations = get_from_cache(cache_key)
        
        if not previous_conversations:
            previous_conversations = get_conversation_history(org_id, request.session_id)
            set_cache(cache_key, previous_conversations, 2)  # Cache for 2 minutes
        
        print(f"[DEBUG] Previous conversations count: {len(previous_conversations)}")
        
        # Initialize conversation history from MongoDB
        request.user_data["conversation_history"] = []
        for msg in previous_conversations:
            if "role" in msg and "content" in msg:
                request.user_data["conversation_history"].append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Get user profile with caching
        profile_cache_key = f"profile:{org_id}:{request.session_id}"
        user_profile = get_from_cache(profile_cache_key)
        
        if not user_profile:
            user_profile = get_user_profile(org_id, request.session_id)
            if user_profile:
                set_cache(profile_cache_key, user_profile, 10)  # Cache for 10 minutes
        
        if user_profile and "profile_data" in user_profile:
            request.user_data.update(user_profile["profile_data"])
            request.user_data["returning_user"] = True

        # Check if this is the first message
        is_first_message = len(previous_conversations) == 0
        
        # Store the current user message
        add_conversation_message(
            organization_id=org_id,
            visitor_id=visitor["id"],
            session_id=request.session_id,
            role="user",
            content=request.question,
            metadata={"mode": request.mode}
        )
        
        request.user_data["conversation_history"].append({
            "role": "user",
            "content": request.question
        })

        # Emit user message to dashboard
        if sio:
            await sio.emit('new_message', {
                'session_id': request.session_id,
                'message': {
                    'role': 'user',
                    'content': request.question,
                    'timestamp': datetime.utcnow().isoformat()
                },
                'organization_id': org_id
            }, room=org_api_key)

        # Handle first message with welcome
        if is_first_message:
            welcome_msg = get_welcome_message(organization, True)
            
            # Store welcome message
            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="assistant",
                content=welcome_msg,
                metadata={"mode": "welcome", "type": "first_message"}
            )
            
            request.user_data["conversation_history"].append({
                "role": "assistant",
                "content": welcome_msg
            })

            # Emit welcome message
            if sio:
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': welcome_msg,
                        'timestamp': datetime.utcnow().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)

            return {
                "answer": welcome_msg,
                "mode": "faq",
                "language": "en",
                "user_data": request.user_data,
                "first_message": True
            }

        # Try FAQ matching first (cached)
        faq_cache_key = f"faq:{org_id}:{hash(request.question)}"
        matching_faq = get_from_cache(faq_cache_key)
        
        if not matching_faq:
            matching_faq = find_matching_faq(
                query=request.question,
                org_id=org_id,
                namespace=namespace
            )
            if matching_faq:
                set_cache(faq_cache_key, matching_faq, 30)  # Cache FAQ matches for 30 minutes

        if matching_faq:
            print("[DEBUG] Found matching FAQ, returning cached response")
            
            # Store the FAQ response
            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="assistant",
                content=matching_faq["response"],
                metadata={
                    "mode": "faq",
                    "type": "faq_match",
                    "faq_id": matching_faq["id"],
                    "similarity_score": matching_faq["similarity_score"]
                }
            )

            request.user_data["conversation_history"].append({
                "role": "assistant", 
                "content": matching_faq["response"]
            })

            if sio:
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': matching_faq["response"],
                        'timestamp': datetime.utcnow().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)

            # Get suggested FAQs
            suggested_faqs = get_suggested_faqs(org_id)
            
            return {
                "answer": matching_faq["response"],
                "mode": "faq",
                "language": "en",
                "user_data": request.user_data,
                "suggested_faqs": suggested_faqs
            }

        # No FAQ match - use smart engine for AI response
        print("[DEBUG] No FAQ match, using smart AI engine")
        
        # Prepare context for the bot
        user_context = ""
        if "name" in request.user_data and request.user_data["name"]:
            user_context = f"The user's name is {request.user_data['name']}. "
        if "email" in request.user_data and request.user_data["email"]:
            user_context += f"The user's email is {request.user_data['email']}. "

        # Get AI behavior from organization settings
        ai_behavior = organization.get("chat_widget_settings", {}).get("ai_behavior", "")
        if ai_behavior:
            user_context += f"\nAI Behavior Instructions: {ai_behavior}\n"

        # Enhance query with user context if needed
        enhanced_query = request.question
        if user_context and request.user_data.get("returning_user"):
            enhanced_query = f"{user_context}The user, who you already know, asks: {request.question}"

        # Call the smart engine (handles lead capture intelligently)
        response = ask_bot(
            query=enhanced_query,
            mode=request.mode,
            user_data=request.user_data,
            available_slots=request.available_slots,
            session_id=request.session_id,
            api_key=org_api_key
        )

        # Save assistant message to database
        add_conversation_message(
            organization_id=org_id,
            visitor_id=visitor["id"],
            session_id=request.session_id,
            role="assistant",
            content=response["answer"],
            metadata={"mode": request.mode}
        )

        # Update conversation history in user_data
        response["user_data"]["conversation_history"].append({
            "role": "assistant", 
            "content": response["answer"]
        })

        # Get suggested FAQs
        suggested_faqs = get_suggested_faqs(org_id)
        response["suggested_faqs"] = suggested_faqs

        # Emit response to dashboard
        if sio:
            await sio.emit('new_message', {
                'session_id': request.session_id,
                'message': {
                    'role': 'assistant',
                    'content': response["answer"],
                    'timestamp': datetime.utcnow().isoformat()
                },
                'organization_id': org_id
            }, room=org_api_key)

        return response

    except Exception as e:
        print(f"Error processing chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep all your other existing routes unchanged...
# (settings, upload, etc.)
