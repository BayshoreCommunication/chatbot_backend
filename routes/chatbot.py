import logging

# Set up clean logging for chatbot
logger = logging.getLogger('chatbot')

# Reduce pymongo logging noise  
logging.getLogger('pymongo').setLevel(logging.WARNING)

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, Header, Body
import sys
import traceback

# Try to import required services with error handling
try:
    from services.langchain.engine import ask_bot, add_document, escalate_to_human
    from services.language_detect import detect_language
    from services.database import (
        get_organization_by_api_key, create_or_update_visitor, add_conversation_message, 
        get_visitor, get_conversation_history, save_user_profile, get_user_profile, db,
        set_agent_mode, set_bot_mode, is_chat_in_agent_mode, create_user, get_user_by_email,
        get_user_by_id, update_user, create_lead, get_leads_by_organization
    )
    # Import ObjectId with fallback
    try:
        from bson import ObjectId
        print("[INFO] ObjectId imported from bson")
    except ImportError:
        try:
            from pymongo import ObjectId
            print("[INFO] ObjectId imported from pymongo")
        except ImportError:
            print("[WARNING] ObjectId import failed, will use runtime imports")
            ObjectId = None
    
    from services.faq_matcher import find_matching_faq, get_suggested_faqs
    from services.langchain.user_management import handle_name_collection, handle_email_collection
    SERVICES_AVAILABLE = True
except Exception as e:
    print(f"Error importing services: {str(e)}")
    print(traceback.format_exc())
    SERVICES_AVAILABLE = False
    ObjectId = None  # Ensure ObjectId is defined even if import fails

from typing import Optional, Dict, Any, List
import json
import os
import uuid
import shutil
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime
import pymongo
import re
import openai
import socketio
from fastapi import FastAPI
from fastapi.responses import FileResponse
import boto3

router = APIRouter()
sio = None

def get_org_object_id(organization):
    """Helper function to safely get organization ID and handle both UUID and ObjectId formats"""
    org_id = organization.get("id") or organization.get("_id")
    if not org_id:
        raise ValueError("Organization ID is missing")
    
    # For UUIDs (36 characters with hyphens), use as string
    if isinstance(org_id, str) and len(org_id) == 36 and '-' in org_id:
        return org_id
    
    # For ObjectId strings (24 characters), try to convert to ObjectId
    if isinstance(org_id, str) and len(org_id) == 24:
        try:
            # Use global ObjectId if available
            if ObjectId is not None:
                return ObjectId(org_id)
            else:
                # Fallback to runtime import
                try:
                    from bson import ObjectId as RuntimeObjectId  # type: ignore
                    return RuntimeObjectId(org_id)
                except ImportError:
                    try:
                        from pymongo import ObjectId as RuntimeObjectId  # type: ignore
                        return RuntimeObjectId(org_id)
                    except ImportError:
                        # If ObjectId import fails, use as string
                        return org_id
        except Exception:
            # If ObjectId conversion fails, use as string
            return org_id
    
    # For any other format, use as string
    return org_id

# Initialize socket.io
def init_socketio(app: FastAPI):
    global sio
    sio = socketio.AsyncServer(
        cors_allowed_origins=[
            "http://localhost:3000",
            "http://localhost:5173", 
            "http://localhost:4173",
            "https://aibotwidget.bayshorecommunication.org",
            "https://dashboard.bayshorecommunication.org",
            "https://api.bayshorecommunication.org",
            "*"  # Allow all origins for development
        ],
        async_mode='asgi',
        logger=True,  # Enable logging for debugging
        engineio_logger=True,  # Enable engine.io logging for debugging
        ping_timeout=60,
        ping_interval=25
    )
    
    @sio.event
    async def connect(sid, environ, auth):
        logger.info(f"Client connected: {sid}")
        
        # Get API key from auth or query params
        api_key = None
        if auth and isinstance(auth, dict):
            api_key = auth.get('apiKey')
        
        if not api_key:
            # Try to get from query params
            query_string = environ.get('QUERY_STRING', '')
            if 'apiKey=' in query_string:
                for param in query_string.split('&'):
                    if param.startswith('apiKey='):
                        api_key = param.split('=')[1]
                        break
        
        if api_key:
            # Auto-join organization room using API key
            room_name = api_key
            await sio.enter_room(sid, room_name)
            logger.info(f"Client {sid} joined room: {room_name}")
            
            # Send a welcome message to confirm connection
            await sio.emit('connection_confirmed', {
                'status': 'connected',
                'room': room_name,
                'message': 'Socket.IO connection established successfully'
            }, room=sid)
        else:
            logger.warning(f"Client {sid} connected without API key")
            # Still allow connection but don't join any room
            await sio.emit('connection_confirmed', {
                'status': 'connected',
                'room': None,
                'message': 'Socket.IO connection established (no API key)'
            }, room=sid)

    @sio.event
    async def disconnect(sid):
        logger.info(f"Client disconnected: {sid}")

    @sio.event
    async def join_room(sid, data):
        room = data.get('room')
        if room:
            await sio.enter_room(sid, room)
            print(f"[SOCKET.IO] Client {sid} explicitly joined room: {room}")
            
            # Confirm room join
            await sio.emit('room_joined', {
                'room': room,
                'status': 'joined'
            }, room=sid)
    
    # Mount Socket.IO on the FastAPI app at /socket.io/
    socket_asgi_app = socketio.ASGIApp(sio, app, socketio_path='/socket.io')
    return socket_asgi_app

# Initialize collections and indexes
if SERVICES_AVAILABLE:
    instant_replies = db.instant_reply
    instant_replies.create_index("org_id")
    instant_replies.create_index([("org_id", pymongo.ASCENDING), ("is_active", pymongo.ASCENDING)])

    upload_history_collection = db.upload_history
    upload_history_collection.create_index("org_id")
    upload_history_collection.create_index([("org_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])

# User session storage (in a real application, use Redis for temporary storage)
user_sessions = {}

def is_first_message(org_id: str, session_id: str) -> bool:
    """Check if this is the first message in the conversation"""
    # Get count of all conversations for this session
    conversations_count = db.conversations.count_documents({
        "organization_id": org_id,
        "session_id": session_id
    })
    
    print(f"[DEBUG] Found {conversations_count} previous messages")
    return conversations_count == 0

# Add new ChatWidgetSettings model
class ChatWidgetSettings(BaseModel):
    name: str
    selectedColor: str
    leadCapture: bool
    botBehavior: str
    ai_behavior: Optional[str] = ""
    avatarUrl: Optional[str] = None
    is_bot_connected: Optional[bool] = False
    auto_open: Optional[bool] = False

class ChatRequest(BaseModel):
    question: str
    session_id: str
    mode: Optional[str] = "faq"
    user_data: Optional[dict] = None
    available_slots: Optional[str] = None

class ChatHistoryRequest(BaseModel):
    session_id: str

class UploadHistoryResponse(BaseModel):
    id: Optional[str] = None
    org_id: str
    url: Optional[str] = None
    file_name: Optional[str] = None
    status: str
    type: str  # "url" or "pdf"
    created_at: datetime

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    try:
        print(f"[DEBUG] ===== AUTHENTICATION DEBUG START =====")
        print(f"[DEBUG] Raw API key received: {api_key}")
        print(f"[DEBUG] API key length: {len(api_key) if api_key else 0}")
        print(f"[DEBUG] API key first 10 chars: {api_key[:10] if api_key else 'None'}...")
        print(f"[DEBUG] API key last 10 chars: ...{api_key[-10:] if api_key and len(api_key) > 10 else api_key}")
        
        if not api_key:
            print("[ERROR] No API key provided")
            raise HTTPException(status_code=401, detail="API key is required")
        
        print(f"[DEBUG] Looking up organization with API key: {api_key[:10]}...")
        
        # Test database connection first
        try:
            from services.database import db, client
            client.admin.command('ping')
            print("[DEBUG] Database ping successful in get_organization_from_api_key")
        except Exception as ping_error:
            print(f"[ERROR] Database ping failed in get_organization_from_api_key: {str(ping_error)}")
            raise HTTPException(status_code=500, detail=f"Database connection failed: {str(ping_error)}")
        
        # Check if organizations collection exists
        try:
            org_count = db.organizations.count_documents({})
            print(f"[DEBUG] Total organizations in database: {org_count}")
        except Exception as count_error:
            print(f"[ERROR] Failed to count organizations: {str(count_error)}")
        
        # Try to find organization
        try:
            from services.database import get_organization_by_api_key
            organization = get_organization_by_api_key(api_key)
            print(f"[DEBUG] Organization lookup result: {organization}")
        except Exception as lookup_error:
            print(f"[ERROR] Organization lookup failed: {str(lookup_error)}")
            raise HTTPException(status_code=500, detail=f"Organization lookup failed: {str(lookup_error)}")
        
        if not organization:
            print(f"[ERROR] Invalid API key: {api_key[:10]}...")
            print(f"[DEBUG] Searching for similar API keys...")
            
            # Try to find any organizations with similar API keys for debugging
            try:
                similar_orgs = list(db.organizations.find({}, {"api_key": 1, "name": 1}).limit(5))
                print(f"[DEBUG] Sample organizations in database: {similar_orgs}")
            except Exception as similar_error:
                print(f"[ERROR] Failed to get sample organizations: {str(similar_error)}")
            
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        print(f"[DEBUG] Organization found: {organization.get('_id')}")
        print(f"[DEBUG] Organization name: {organization.get('name', 'No name')}")
        print(f"[DEBUG] ===== AUTHENTICATION DEBUG END =====")
        return organization
        
    except HTTPException:
        print("[DEBUG] Re-raising HTTP exception from get_organization_from_api_key")
        raise
    except Exception as e:
        print(f"[ERROR] Exception in get_organization_from_api_key: {str(e)}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.post("/ask")
async def ask_question(
    request: ChatRequest, 
    organization=Depends(get_organization_from_api_key)
):
    """Process a chat message and return a response"""
    # Safely get organization ID
    org_id = organization.get("id") or organization.get("_id")
    if not org_id:
        raise HTTPException(status_code=500, detail="Organization ID not found")
    
    org_api_key = organization.get("api_key")
    namespace = organization.get("pinecone_namespace", "")

    try:
        print(f"[DEBUG] Processing message: {request.question}")
        print(f"[DEBUG] Session ID: {request.session_id}")

        # Ensure critical database helpers are available even if optional imports failed at module load
        try:
            create_or_update_visitor  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import create_or_update_visitor  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: create_or_update_visitor ({str(_e)})")

        try:
            add_conversation_message  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import add_conversation_message  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: add_conversation_message ({str(_e)})")

        try:
            get_conversation_history  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import get_conversation_history  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: get_conversation_history ({str(_e)})")

        try:
            get_user_profile  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import get_user_profile  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: get_user_profile ({str(_e)})")

        # Ensure is_chat_in_agent_mode is available even if optional imports failed at module load
        try:
            # Prefer already-imported symbol; if not, import locally
            is_chat_in_agent_mode  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import is_chat_in_agent_mode  # type: ignore
            except Exception:
                # Fallback: if the helper is unavailable on this environment, default to bot mode
                def is_chat_in_agent_mode(organization_id, session_id):  # type: ignore
                    return False

        # FIRST: Check if this chat is in agent mode
        if is_chat_in_agent_mode(org_id, request.session_id):
            print(f"[DEBUG] Chat {request.session_id} is in agent mode - skipping AI processing")
            
            # Get or create visitor for the user message
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

            # Store the user message only
            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="user",
                content=request.question,
                metadata={"mode": request.mode, "agent_mode": True}
            )

            # Emit user message to dashboard for agent to see
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

            # Return without AI response - agent will respond manually
            return {
                "answer": "",  # No AI response
                "mode": "agent",
                "language": "en",
                "user_data": request.user_data or {},
                "agent_mode": True,
                "message": "Message received - agent will respond shortly"
            }

        # Continue with normal AI processing if not in agent mode
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

        # Initialize or get existing session data
        if not request.user_data:
            request.user_data = {}
        
        # Get previous conversations from MongoDB and initialize history
        previous_conversations = get_conversation_history(org_id, request.session_id)
        print(f"[DEBUG] Previous conversations count: {len(previous_conversations)}")
        
        # Always initialize conversation history from MongoDB
        request.user_data["conversation_history"] = []
        for msg in previous_conversations:
            if "role" in msg and "content" in msg:
                request.user_data["conversation_history"].append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Get user profile
        user_profile = get_user_profile(org_id, request.session_id)
        if user_profile and "profile_data" in user_profile:
            request.user_data.update(user_profile["profile_data"])
            request.user_data["returning_user"] = True
            
            # Ensure appointment_context is loaded from profile
            if "appointment_context" in user_profile["profile_data"]:
                request.user_data["appointment_context"] = user_profile["profile_data"]["appointment_context"]

        # Store the current user message ONCE at the beginning
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
        await sio.emit('new_message', {
            'session_id': request.session_id,
            'message': {
                'role': 'user',
                'content': request.question,
                'timestamp': datetime.utcnow().isoformat()
            },
            'organization_id': org_id
        }, room=org_api_key)

        # Smart welcome logic - only for simple greetings, not actual questions
        is_first_message = len(previous_conversations) == 0
        
        # Check if this is just a simple greeting (not a real question)
        simple_greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
        user_message_lower = request.question.lower().strip()
        
        # Only show welcome if it's the first message AND it's a simple greeting
        is_simple_greeting = any(greeting in user_message_lower for greeting in simple_greetings)
        is_actual_question = any(word in user_message_lower for word in [
            "do you", "can you", "what", "how", "when", "where", "why", "who", 
            "injury", "law", "legal", "accident", "case", "help with", "about",
            "service", "take", "handle", "work", "cost", "fee", "consultation"
        ])
        
        # Show welcome only for simple greetings without questions
        should_show_welcome = is_first_message and is_simple_greeting and not is_actual_question
        
        if should_show_welcome:
            print(f"[DEBUG] First time simple greeting detected: '{request.question}'")
            
            # Get organization name from chat widget settings (preferred) or fallback to main name
            chat_settings = organization.get("chat_widget_settings", {})
            org_name = chat_settings.get("name", organization.get("name", "our team"))
            ai_behavior = chat_settings.get("ai_behavior", "")
            
            print(f"[DEBUG] Using organization name: '{org_name}' from chat_widget_settings")
            
            # Create personalized welcome message
            if ai_behavior:
                # Use the AI behavior setting if available
                welcome_msg = f"How may I assist you today?"
            else:
                # Default professional welcome
                welcome_msg = f"How may I assist you today?"
            
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
        
        # If it's the first message but contains a real question, just process it normally
        if is_first_message and is_actual_question:
            print(f"[DEBUG] First message contains actual question: '{request.question}' - processing directly")

        print("[DEBUG] Processing regular message with smart engine")
        
        # Ensure FAQ helpers are available at runtime
        try:
            find_matching_faq  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.faq_matcher import find_matching_faq  # type: ignore
            except Exception:
                def find_matching_faq(query, org_id, namespace):  # type: ignore
                    return None

        try:
            get_suggested_faqs  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.faq_matcher import get_suggested_faqs  # type: ignore
            except Exception:
                def get_suggested_faqs(org_id):  # type: ignore
                    return []

        # Skip the old lead collection logic - let smart engine handle it
        # Try to find matching FAQ first (with caching)
        matching_faq = find_matching_faq(
            query=request.question,
            org_id=org_id,
            namespace=namespace
        )
        print(f"[DEBUG] find_matching_faq returned: {matching_faq}")

        # If we found a good FAQ match, return it
        if matching_faq:
            print("[DEBUG] Found matching FAQ, preparing response...")
            
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

            # Update conversation history
            request.user_data["conversation_history"].append({
                "role": "assistant", 
                "content": matching_faq["response"]
            })

            # Emit assistant message to dashboard
            await sio.emit('new_message', {
                'session_id': request.session_id,
                'message': {
                    'role': 'assistant',
                    'content': matching_faq["response"],
                    'timestamp': datetime.utcnow().isoformat()
                },
                'organization_id': org_id
            }, room=org_api_key)

            # Get suggested FAQs for follow-up
            suggested_faqs = get_suggested_faqs(org_id)
            
            return {
                "answer": matching_faq["response"],
                "mode": "faq",
                "language": "en",
                "user_data": request.user_data,
                "suggested_faqs": suggested_faqs
            }

        # If no FAQ match, proceed with smart AI engine
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

        # Add organization_id to user_data for appointment persistence
        request.user_data["organization_id"] = org_id
        request.user_data["session_id"] = request.session_id
        
        # Don't add the enhanced query to conversation history - use original question
        response = ask_bot(
            query=enhanced_query,
            mode=request.mode,
            user_data=request.user_data,
            available_slots=request.available_slots,
            session_id=request.session_id,
            api_key=org_api_key
        )

        # Save assistant message to database FIRST
        add_conversation_message(
            organization_id=org_id,
            visitor_id=visitor["id"],
            session_id=request.session_id,
            role="assistant",
            content=response["answer"],
            metadata={"mode": request.mode}
        )

        # Then update conversation history in user_data to match database order
        response["user_data"]["conversation_history"].append({
            "role": "assistant", 
            "content": response["answer"]
        })

        # Get suggested FAQs
        suggested_faqs = get_suggested_faqs(org_id)
        response["suggested_faqs"] = suggested_faqs

        # After getting bot response, emit it to dashboard
        await sio.emit('new_message', {
            'session_id': request.session_id,
            'message': {
                'role': 'assistant',
                'content': response["answer"],
                'timestamp': datetime.utcnow().isoformat()
            },
            'organization_id': org_id
        }, room=org_api_key)
        
        # CRITICAL: Save appointment_context and email to user profile if they exist
        # This ensures state persists between requests
        if "appointment_context" in response.get("user_data", {}) or "email" in response.get("user_data", {}):
            try:
                from services.database import save_user_profile
                
                # Prepare profile data to save
                profile_data_to_save = {}
                
                # Save email if present
                if "email" in response["user_data"] and response["user_data"]["email"]:
                    profile_data_to_save["email"] = response["user_data"]["email"]
                
                # Save appointment_context if present
                if "appointment_context" in response["user_data"] and response["user_data"]["appointment_context"]:
                    profile_data_to_save["appointment_context"] = response["user_data"]["appointment_context"]
                
                # Save name if present
                if "name" in response["user_data"] and response["user_data"]["name"]:
                    profile_data_to_save["name"] = response["user_data"]["name"]
                
                # Save phone if present
                if "phone" in response["user_data"] and response["user_data"]["phone"]:
                    profile_data_to_save["phone"] = response["user_data"]["phone"]
                
                # Only save if we have data to persist
                if profile_data_to_save:
                    print(f"[DEBUG] Saving user profile data: {profile_data_to_save}")
                    save_user_profile(org_id, request.session_id, profile_data_to_save)
                    
            except Exception as e:
                print(f"[ERROR] Failed to save user profile: {str(e)}")
                # Don't fail the main flow if profile saving fails

        # Check if lead capture is enabled and we have collected both name and email
        chat_settings = organization.get("chat_widget_settings", {})
        lead_capture_enabled = chat_settings.get("leadCapture", False)
        
        if lead_capture_enabled:
            # Create or update lead when any of name/email/phone is present
            user_name = response.get("user_data", {}).get("name")
            user_email = response.get("user_data", {}).get("email")
            user_phone = response.get("user_data", {}).get("phone")
            
            if user_name or user_email or user_phone:
                try:
                    from services.database import create_lead
                    # Extract inquiry from conversation history
                    conversation_history = response.get("user_data", {}).get("conversation_history", [])
                    user_messages = [msg["content"] for msg in conversation_history if msg.get("role") == "user"]
                    inquiry = " | ".join(user_messages[:3]) if user_messages else "General inquiry"
                    created_lead = create_lead(
                        organization_id=org_id,
                        session_id=request.session_id,
                        name=user_name,
                        email=user_email,
                        phone=user_phone,
                        inquiry=inquiry if inquiry else "",
                        source="chatbot"
                    )
                    print(f"[DEBUG] Lead upserted successfully: {created_lead.get('lead_id')}")
                except Exception as e:
                    print(f"[ERROR] Failed to upsert lead: {str(e)}")
                    # Don't fail the main chat flow if lead creation fails

        return response

    except Exception as e:
        print(f"Error processing chat message: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Return a more detailed error response
        return {
            "answer": "I'm sorry, I'm experiencing technical difficulties. Please try again later.",
            "error": str(e),
            "error_type": type(e).__name__,
            "mode": "error"
        }

@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Retrieve chat history for a session"""
    try:
        print(f"[DEBUG] Getting chat history for session: {session_id}")
        print(f"[DEBUG] Session ID type: {type(session_id)}")
        print(f"[DEBUG] Session ID length: {len(session_id) if session_id else 0}")
        print(f"[DEBUG] Organization: {organization}")
        
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            print(f"[ERROR] No organization ID found in organization object: {organization}")
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        print(f"[DEBUG] Using organization ID: {org_id}")
        print(f"[DEBUG] Looking for visitor with org_id: {org_id}, session_id: {session_id}")
        
        # Ensure required database functions are available
        try:
            get_conversation_history  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import get_conversation_history  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: get_conversation_history ({str(_e)})")
        
        try:
            get_visitor  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import get_visitor  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: get_visitor ({str(_e)})")
        
        try:
            get_user_profile  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import get_user_profile  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: get_user_profile ({str(_e)})")
        
        try:
            get_suggested_faqs  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.faq_matcher import get_suggested_faqs  # type: ignore
            except Exception:
                def get_suggested_faqs(org_id):  # type: ignore
                    return []
        
        # Get fresh conversation data from MongoDB
        previous_conversations = get_conversation_history(organization_id=org_id, session_id=session_id)
        # Guard against None or unexpected types from storage layer
        if not isinstance(previous_conversations, list):
            previous_conversations = previous_conversations or []
            try:
                # Try to coerce iterable-like objects to list
                previous_conversations = list(previous_conversations)
            except Exception:
                previous_conversations = []
        print(f"[DEBUG] previous_conversations len: {len(previous_conversations)} organization: {org_id}")
        
        # Get visitor information
        visitor = get_visitor(org_id, session_id)
        if not visitor:
            print(f"[DEBUG] No visitor found for session: {session_id}, returning empty history")
            # Return empty history instead of error for missing visitors
            response = {
                "answer": "",
                "mode": "faq",
                "language": "en",
                "user_data": {
                    "conversation_history": [],
                    "returning_user": False
                },
                "suggested_faqs": [],
                "agent_mode": False,
                "agent_id": "",
                "agent_takeover_at": ""
            }
            print(f"[DEBUG] Returning empty history for new session: {session_id}")
            return response
        
        # Check if chat is in agent mode
        is_agent_mode = visitor.get("is_agent_mode", False)
        agent_id = visitor.get("agent_id")
        agent_takeover_at = visitor.get("agent_takeover_at")
        
        # Get user profile
        user_profile = get_user_profile(org_id, session_id)
        profile_data = {}
        if isinstance(user_profile, dict):
            pd = user_profile.get("profile_data", {})
            if isinstance(pd, dict):
                profile_data = pd
        
        # Format conversation history
        formatted_history = []
        for msg in previous_conversations:
            try:
                role = msg.get("role") if isinstance(msg, dict) else None
                content = msg.get("content") if isinstance(msg, dict) else None
                if role and content:
                    formatted_history.append({
                        "role": role,
                        "content": content
                    })
            except Exception:
                # Skip malformed entries
                continue
        
        # Get current mode
        current_mode = "agent" if is_agent_mode else "faq"
        if visitor and "metadata" in visitor and "mode" in visitor["metadata"]:
            current_mode = visitor["metadata"]["mode"]
            if is_agent_mode:
                current_mode = "agent"
        
        # Get last assistant message
        last_answer = ""
        for msg in reversed(formatted_history):
            if msg["role"] == "assistant":
                last_answer = msg["content"]
                break
        
        # Get suggested FAQs
        try:
            suggested_faqs = get_suggested_faqs(org_id) or []
        except Exception:
            suggested_faqs = []
        
        # Build response
        # Safely serialize agent_takeover_at which may be datetime or string
        agent_takeover_at_str = ""
        if agent_takeover_at:
            try:
                # datetime-like
                agent_takeover_at_str = agent_takeover_at.isoformat()
            except AttributeError:
                # already a string or other type; coerce to str
                agent_takeover_at_str = str(agent_takeover_at)

        # Ensure agent_id is a string, not None
        agent_id_str = str(agent_id) if agent_id else ""

        response = {
            "answer": last_answer,
            "mode": current_mode,
            "language": "en",
            "user_data": {
                **profile_data,
                "conversation_history": formatted_history,
                "returning_user": "name" in profile_data and bool(profile_data.get("name"))
            },
            "suggested_faqs": suggested_faqs,
            "agent_mode": is_agent_mode,
            "agent_id": agent_id_str,
            "agent_takeover_at": agent_takeover_at_str
        }
        
        print(f"[DEBUG] Successfully returning chat history for session: {session_id}")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error in get_chat_history: {str(e)}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/change_mode")
async def change_mode(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    data = await request.json()
    session_id = data.get("session_id")
    new_mode = data.get("mode")
    
    if not session_id or not new_mode:
        raise HTTPException(status_code=400, detail="Session ID and mode are required")
    
    # Safely get organization ID
    org_id = organization.get("id") or organization.get("_id")
    if not org_id:
        raise HTTPException(status_code=500, detail="Organization ID not found")
    
    # Get or create session
    session_key = f"{org_id}:{session_id}"
    session = user_sessions.get(session_key, {
        "conversation_history": [],
        "user_data": {},
        "current_mode": new_mode
    })
    
    # Update mode
    session["current_mode"] = new_mode
    user_sessions[session_key] = session
    
    # Update visitor data if exists
    visitor = get_visitor(org_id, session_id)
    if visitor:
        visitor_data = {
            "metadata": {
                "mode": new_mode,
                "user_data": visitor.get("metadata", {}).get("user_data", {})
            }
        }
        create_or_update_visitor(org_id, session_id, visitor_data)
    
    return {"status": "success", "mode": new_mode}

@router.get("/upload_history", response_model=List[UploadHistoryResponse])
async def get_upload_history(
    organization=Depends(get_organization_from_api_key)
):
    """Get upload history for an organization"""
    # Safely get organization ID
    org_id = organization.get("id") or organization.get("_id")
    if not org_id:
        raise HTTPException(status_code=500, detail="Organization ID not found")
    
    history = []
    for item in upload_history_collection.find(
        {"org_id": org_id},
        sort=[("created_at", pymongo.DESCENDING)]
    ):
        item["id"] = str(item.pop("_id"))
        history.append(item)
    
    return history

@router.delete("/upload_history/{document_id}")
async def delete_upload_history(
    document_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Delete a document from upload history and knowledge base"""
    try:
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        org_api_key = organization.get("api_key")
        
        print(f"[DELETE] Attempting to delete document: {document_id} for org: {org_id}")
        
        # Validate ObjectId format
        try:
            if ObjectId is not None:
                obj_id = ObjectId(document_id)
            else:
                # Fallback to runtime import
                try:
                    from bson import ObjectId as RuntimeObjectId  # type: ignore
                    obj_id = RuntimeObjectId(document_id)
                except ImportError:
                    try:
                        from pymongo import ObjectId as RuntimeObjectId  # type: ignore
                        obj_id = RuntimeObjectId(document_id)
                    except ImportError:
                        raise ValueError("ObjectId import unavailable")
        except Exception as e:
            print(f"[DELETE] Invalid ObjectId format: {document_id}")
            raise HTTPException(status_code=400, detail=f"Invalid document ID format: {document_id}")
        
        # Find the document in upload history
        document = upload_history_collection.find_one({
            "_id": obj_id,
            "org_id": org_id
        })
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from vector store (knowledge base)
        try:
            from services.langchain.engine import remove_document
            if document.get("file_name"):
                # For file uploads, use filename to identify in vector store
                remove_result = remove_document(
                    filename=document["file_name"], 
                    api_key=org_api_key
                )
            elif document.get("url"):
                # For URL uploads, use URL to identify in vector store
                remove_result = remove_document(
                    url=document["url"], 
                    api_key=org_api_key
                )
            else:
                print(f"No file_name or url found for document {document_id}")
                
        except Exception as e:
            print(f"Error removing from vector store: {str(e)}")
            # Continue with database deletion even if vector store removal fails
        
        # Delete from upload history
        delete_result = upload_history_collection.delete_one({
            "_id": obj_id,
            "org_id": org_id
        })
        
        if delete_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found or not authorized")
        
        return {
            "status": "success",
            "message": "Document removed from knowledge base successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting upload history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload_document")
async def upload_document(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    scrape_website: Optional[bool] = Form(False),
    max_pages: Optional[int] = Form(10),
    platform: Optional[str] = Form("website"),
    organization=Depends(get_organization_from_api_key)
):
    """
    Upload document to the vector database
    
    - file: Upload a PDF or text file directly
    - url: Provide a URL to a webpage or PDF  
    - text: Provide raw text content
    - scrape_website: Set to True to crawl and index an entire website (when URL is provided)
    - max_pages: Maximum number of pages to scrape when scrape_website is True (default: 10)
    
    When scrape_website=True, the system will:
    1. Start at the provided URL
    2. Extract all text content from the page
    3. Find links to other pages on the same domain
    4. Crawl those pages up to max_pages limit
    5. Index all content in the vector database
    
    All content is stored under the organization's namespace in the vector database.
    """
    # Safely get organization ID
    org_id = organization.get("id") or organization.get("_id")
    if not org_id:
        raise HTTPException(status_code=500, detail="Organization ID not found")
    org_api_key = organization.get("api_key")
    
    # Debug logging to see what we receive
    print(f"=== DEBUG upload_document ===")
    print(f"org_id: {org_id}")
    print(f"file: {file}")
    print(f"url: {url}")
    print(f"text: {text}")
    print(f"scrape_website: {scrape_website}")
    print(f"max_pages: {max_pages}")
    print(f"===============================")
    
    try:
        if file:
            # Save uploaded file temporarily
            file_path = f"temp_{file.filename}"
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Add to vectorstore with organization namespace
            result = add_document(file_path=file_path, api_key=org_api_key)
            
            # Store upload history
            upload_history_collection.insert_one({
                "org_id": org_id,
                "file_name": file.filename,
                "type": "pdf",
                "status": "Used",
                "created_at": datetime.utcnow()
            })
            
            # Clean up temporary file
            os.remove(file_path)
            
            return result
        
        elif url:
            # Validate URL format
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if not all([parsed.scheme, parsed.netloc]):
                    raise ValueError("Invalid URL format")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid URL format: {str(e)}")
            
            # Adjust max_pages based on platform to prevent timeouts
            if platform in ['facebook', 'instagram', 'twitter', 'linkedin', 'youtube']:
                max_pages = min(max_pages, 2)  # Limit social media to 2 pages max
            else:
                max_pages = min(max_pages, 5)  # Limit websites to 5 pages max for speed
            
            print(f"[UPLOAD_DOCUMENT] Training from {platform}: {url} (max_pages: {max_pages})")
            
            # Check if we should scrape the entire website
            if scrape_website:
                # Append parameters to URL to indicate scraping
                scrape_url = f"{url}?scrape_website=true&max_pages={max_pages}&platform={platform}"
                print(f"Scraping website: {url} with max_pages={max_pages}, platform={platform}")
                result = add_document(url=scrape_url, api_key=org_api_key)
            else:
                # Just process the single URL
                print(f"Processing single URL: {url}")
                result = add_document(url=url, api_key=org_api_key)
            
            # Store upload history
            upload_history_collection.insert_one({
                "org_id": org_id,
                "url": url,
                "type": "url",
                "status": "Used",
                "created_at": datetime.utcnow()
            })
            
            return result
        
        elif text:
            result = add_document(text=text, api_key=org_api_key)
            
            # Store upload history for text content
            upload_history_collection.insert_one({
                "org_id": org_id,
                "type": "text",
                "status": "Used",
                "created_at": datetime.utcnow()
            })
            
            return result
        
        else:
            raise HTTPException(status_code=400, detail="No document source provided")
            
    except Exception as e:
        # Store failed upload in history
        error_data = {
            "org_id": org_id,
            "status": "Failed",
            "created_at": datetime.utcnow()
        }
        
        if file:
            error_data["file_name"] = file.filename
            error_data["type"] = "pdf"
        elif url:
            error_data["url"] = url
            error_data["type"] = "url"
        else:
            error_data["type"] = "text"
            
        upload_history_collection.insert_one(error_data)
        
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/has_previous_uploads")
async def check_previous_uploads(
    organization=Depends(get_organization_from_api_key)
):
    """Check if organization has any previous successful uploads"""
    # Safely get organization ID
    org_id = organization.get("id") or organization.get("_id")
    if not org_id:
        raise HTTPException(status_code=500, detail="Organization ID not found")
    
    # Check for any successful uploads
    count = upload_history_collection.count_documents({
        "org_id": org_id,
        "status": "Used"
    })
    
    return {
        "has_previous_uploads": count > 0
    }

@router.post("/escalate")
async def escalate(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    data = await request.json()
    query = data.get("question")
    user_info = data.get("user_info", {})
    session_id = data.get("session_id")
    
    if not query:
        raise HTTPException(status_code=400, detail="Question is required")
    
    # Safely get organization ID
    org_id = organization.get("id") or organization.get("_id")
    if not org_id:
        raise HTTPException(status_code=500, detail="Organization ID not found")
    
    # Get visitor if session_id is provided
    visitor_id = None
    if session_id:
        visitor = get_visitor(org_id, session_id)
        if visitor:
            visitor_id = visitor["id"]
    
    # Add additional organization context
    escalation_context = {
        "organization_id": org_id,
        "organization_name": organization["name"],
        "visitor_id": visitor_id,
        "session_id": session_id,
        **user_info
    }
    
    return escalate_to_human(query, escalation_context)


        
@router.post("/agent-takeover")
async def agent_takeover(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Take over a chat conversation for manual agent handling"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        agent_id = data.get("agent_id")  # Optional: ID of the agent taking over
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        org_api_key = organization.get("api_key")
        
        print(f"Agent takeover request - Session ID: {session_id}, Agent ID: {agent_id}, Org ID: {org_id}")
        
        # Ensure required functions are available
        try:
            set_agent_mode  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import set_agent_mode  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: set_agent_mode ({str(_e)})")
        
        # Set the chat to agent mode
        updated_visitor = set_agent_mode(org_id, session_id, agent_id)
        
        if not updated_visitor:
            raise HTTPException(status_code=404, detail="Visitor not found or could not be updated")
        
        print(f"Successfully set agent mode for session {session_id}")
        
        # Only emit takeover notification to dashboard (no system message added to conversation)
        if sio:
            await sio.emit('agent_takeover', {
                'session_id': session_id,
                'agent_id': agent_id,
                'timestamp': datetime.now().isoformat()
            }, room=org_api_key)
            print(f"Emitted agent_takeover event to room {org_api_key}")
        
        return {
            "status": "success",
            "message": "Agent takeover successful",
            "session_id": session_id,
            "is_agent_mode": True,
            "agent_id": agent_id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error in agent takeover: {str(e)}")
        print(f"Exception type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/agent-release")
async def agent_release(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Release a chat conversation back to bot handling"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        org_api_key = organization.get("api_key")
        
        print(f"Agent release request - Session ID: {session_id}, Org ID: {org_id}")
        
        # Ensure required functions are available
        try:
            set_bot_mode  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import set_bot_mode  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: set_bot_mode ({str(_e)})")
        
        # Set the chat back to bot mode
        updated_visitor = set_bot_mode(org_id, session_id)
        
        if not updated_visitor:
            raise HTTPException(status_code=404, detail="Visitor not found or could not be updated")
        
        print(f"Successfully set bot mode for session {session_id}")
        
        # Only emit release notification to dashboard (no system message added to conversation)
        if sio:
            await sio.emit('agent_release', {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            }, room=org_api_key)
            print(f"Emitted agent_release event to room {org_api_key}")
        
        return {
            "status": "success",
            "message": "Chat released back to bot",
            "session_id": session_id,
            "is_agent_mode": False
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error in agent release: {str(e)}")
        print(f"Exception type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/send-agent-message")
async def send_agent_message(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Send a message as an agent in manual mode"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        message_content = data.get("message")
        agent_id = data.get("agent_id")
        
        if not session_id or not message_content:
            raise HTTPException(status_code=400, detail="Session ID and message are required")
        
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        org_api_key = organization.get("api_key")
        
        # Ensure required functions are available
        try:
            is_chat_in_agent_mode  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import is_chat_in_agent_mode  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: is_chat_in_agent_mode ({str(_e)})")
        
        try:
            get_visitor  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import get_visitor  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: get_visitor ({str(_e)})")
        
        try:
            add_conversation_message  # type: ignore  # noqa: F401
        except NameError:
            try:
                from services.database import add_conversation_message  # type: ignore
            except Exception as _e:
                raise RuntimeError(f"database helper unavailable: add_conversation_message ({str(_e)})")
        
        # Verify the chat is in agent mode
        if not is_chat_in_agent_mode(org_id, session_id):
            raise HTTPException(status_code=400, detail="Chat is not in agent mode")
        
        # Get visitor
        visitor = get_visitor(org_id, session_id)
        if not visitor:
            raise HTTPException(status_code=404, detail="Visitor not found")
        
        # Add the agent message
        add_conversation_message(
            organization_id=org_id,
            visitor_id=visitor["id"],
            session_id=session_id,
            role="assistant",
            content=message_content,
            metadata={"type": "agent_message", "agent_id": agent_id}
        )
        
        # Emit the agent message to dashboard and chat widget
        await sio.emit('new_message', {
            'session_id': session_id,
            'message': {
                'role': 'assistant',
                'content': message_content,
                'timestamp': datetime.now().isoformat(),
                'agent_id': agent_id
            },
            'organization_id': org_id
        }, room=org_api_key)
        
        return {
            "status": "success",
            "message": "Agent message sent successfully",
            "session_id": session_id,
            "content": message_content
        }
        
    except Exception as e:
        print(f"Error sending agent message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug-api-key")
async def debug_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Debug endpoint to test API key without authentication dependency"""
    try:
        print(f"[DEBUG] Debug API key endpoint called")
        print(f"[DEBUG] API key received: {api_key}")
        
        if not api_key:
            return {
                "status": "error",
                "message": "No API key provided",
                "received_key": None
            }
        
        # Test database connection
        try:
            from services.database import db, client
            client.admin.command('ping')
            print("[DEBUG] Database ping successful")
        except Exception as ping_error:
            return {
                "status": "error",
                "message": f"Database connection failed: {str(ping_error)}",
                "received_key": api_key[:10] + "..."
            }
        
        # Try to find organization
        try:
            from services.database import get_organization_by_api_key
            organization = get_organization_by_api_key(api_key)
            if organization:
                return {
                    "status": "success",
                    "message": "API key is valid",
                    "received_key": api_key[:10] + "...",
                    "organization_id": str(organization.get('_id')),
                    "organization_name": organization.get('name', 'No name')
                }
            else:
                return {
                    "status": "error",
                    "message": "API key not found in database",
                    "received_key": api_key[:10] + "..."
                }
        except Exception as lookup_error:
            return {
                "status": "error",
                "message": f"Organization lookup failed: {str(lookup_error)}",
                "received_key": api_key[:10] + "..."
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Debug endpoint error: {str(e)}",
            "received_key": api_key[:10] + "..." if api_key else None
        }

@router.get("/test")
async def test_endpoint():
    """Simple test endpoint to check if server is responding"""
    return {
        "status": "success",
        "message": "Chatbot router is working",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/health")
async def health_check():
    """Health check endpoint for database connectivity"""
    try:
        from services.database import db, client
        # Test database connection
        client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        print(f"[ERROR] Database health check failed: {str(e)}")
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@router.options("/settings")
async def options_settings():
    """Handle OPTIONS request for settings endpoint"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "X-API-Key, Content-Type, Authorization",
            "Access-Control-Max-Age": "3600"
        }
    )

@router.get("/settings")
async def get_chat_widget_settings(
    organization=Depends(get_organization_from_api_key)
):
    try:
        # Get organization from MongoDB
        org = db.organizations.find_one({"_id": organization["_id"]})
        print(f"[DEBUG] Retrieved org: {org}")  # Debug log
        print(f"[DEBUG] Retrieved chat_widget_settings: {org.get('chat_widget_settings') if org else None}")  # Debug log
        
        if not org or "chat_widget_settings" not in org:
            default_settings = {
                "name": "Bay AI",
                "selectedColor": "black",
                "leadCapture": True,
                "botBehavior": "2",
                "avatarUrl": None,
                "is_bot_connected": False,
                "ai_behavior": "You are a helpful and friendly AI assistant. You should be professional, concise, and focus on providing accurate information while maintaining a warm and engaging tone.",
                "intro_video": {
                    "enabled": False,
                    "video_url": None,
                    "video_filename": None,
                    "autoplay": True,
                    "duration": 10,
                    "show_on_first_visit": True
                }
            }
            
            # If no settings exist, save the default settings
            if org:
                db.organizations.update_one(
                    {"_id": organization["_id"]},
                    {"$set": {"chat_widget_settings": default_settings}}
                )
            
            return {
                "status": "success",
                "settings": default_settings
            }
            
        return {
            "status": "success",
            "settings": org["chat_widget_settings"]
        }
        
    except Exception as e:
        print(f"[ERROR] Exception in get_chat_widget_settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Add new router for chatbot widget settings
@router.post("/save-settings")
async def save_chat_widget_settings(
    settings: ChatWidgetSettings,
    organization=Depends(get_organization_from_api_key)
):
    try:
        print("\n=== Starting save_chat_widget_settings ===")
        print(f"Organization ID: {organization.get('_id')}")
        
        # Validate organization ID
        if not organization.get("_id"):
            print("[ERROR] Organization ID is missing")
            raise HTTPException(status_code=500, detail="Organization ID is missing")
            
        # Convert settings to dict and ensure is_bot_connected is included
        settings_dict = settings.dict()
        print(f"\n[DEBUG] Incoming settings: {settings_dict}")
        
        # First, get the existing settings to preserve video settings
        existing_org = db.organizations.find_one({"_id": organization["_id"]})
        existing_settings = existing_org.get("chat_widget_settings", {}) if existing_org else {}
        
        # Merge new settings with existing settings, preserving video settings
        merged_settings = {
            **existing_settings,
            **settings_dict
        }
        
        # Specifically preserve video settings if they exist
        if "intro_video" in existing_settings:
            merged_settings["intro_video"] = existing_settings["intro_video"]
        
        print(f"\n[DEBUG] Merged settings (preserving video): {merged_settings}")
        
        # Update organization in MongoDB with chat widget settings
        update_data = {
            "$set": {
                "chat_widget_settings": merged_settings
            },
            # Remove the old settings field if it exists
            "$unset": {
                "settings": ""
            }
        }
        
        print(f"\n[DEBUG] Update operation: {update_data}")
        
        result = db.organizations.update_one(
            {"_id": organization["_id"]},
            update_data
        )
        
        print(f"\n[DEBUG] MongoDB update result: {result.raw_result}")
        
        if result.matched_count == 0:
            print("[ERROR] No matching document found")
            raise HTTPException(status_code=404, detail="Organization not found")
            
        # Verify the update by retrieving the updated document
        updated_org = db.organizations.find_one({"_id": organization["_id"]})
        print(f"\n[DEBUG] Updated organization document: {updated_org}")
        print(f"\n[DEBUG] Updated chat_widget_settings: {updated_org.get('chat_widget_settings')}")
        print("\n=== Completed save_chat_widget_settings ===\n")
            
        return {
            "status": "success",
            "message": "Chat widget settings saved successfully"
        }
        
    except Exception as e:
        print(f"\n[ERROR] Exception in save_chat_widget_settings: {str(e)}")
        print(f"[ERROR] Exception type: {type(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# Video upload endpoints
@router.post("/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    organization=Depends(get_organization_from_api_key)
):
    """Upload a video for the chat widget"""
    try:
        # Validate file type
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="Only video files are allowed")
        
        # DigitalOcean Spaces configuration already imported at top
        
        # DigitalOcean Spaces Configuration
        SPACE_NAME = os.getenv('DO_SPACES_BUCKET', 'bayshore')
        SPACE_REGION = os.getenv('DO_SPACES_REGION', 'nyc3')
        SPACE_ENDPOINT = f"https://{SPACE_REGION}.digitaloceanspaces.com"
        ACCESS_KEY = os.getenv('DO_SPACES_KEY')
        SECRET_KEY = os.getenv('DO_SPACES_SECRET')
        FOLDER_NAME = os.getenv('DO_FOLDER_NAME', 'ai_bot')
        
        if not all([ACCESS_KEY, SECRET_KEY]):
            # Fallback to local storage if Spaces not configured
            print("DigitalOcean Spaces not configured, using local storage")
            upload_dir = Path("uploads/videos")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            file_extension = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = upload_dir / unique_filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            video_url = f"/api/chatbot/video/{unique_filename}"
        else:
            # Initialize S3 client for DigitalOcean Spaces
            s3_client = boto3.client('s3',
                endpoint_url=SPACE_ENDPOINT,
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY,
                region_name=SPACE_REGION
            )
            
            # Generate unique filename for Spaces
            file_extension = Path(file.filename).suffix
            unique_filename = f"{FOLDER_NAME}/videos/{uuid.uuid4()}{file_extension}"
            
            # Upload to DigitalOcean Spaces
            try:
                s3_client.upload_fileobj(
                    file.file,
                    SPACE_NAME,
                    unique_filename,
                    ExtraArgs={
                        'ACL': 'public-read',
                        'ContentType': file.content_type
                    }
                )
                
                # Generate the public URL
                video_url = f"https://{SPACE_NAME}.{SPACE_REGION}.digitaloceanspaces.com/{unique_filename}"
                unique_filename = unique_filename.split('/')[-1]  # Store just the filename for reference
                
            except Exception as e:
                print(f"Spaces upload error: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to upload video to storage")
        
        # Update organization settings with video info
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        print(f"[DEBUG] Updating video settings for org {org_id}")
        print(f"[DEBUG] Video URL: {video_url}")
        print(f"[DEBUG] Video filename: {unique_filename}")
        
        update_result = db.organizations.update_one(
            {"_id": organization["_id"]},
            {
                "$set": {
                    "chat_widget_settings.intro_video.enabled": True,
                    "chat_widget_settings.intro_video.video_url": video_url,
                    "chat_widget_settings.intro_video.video_filename": unique_filename,
                    "chat_widget_settings.intro_video.autoplay": True,
                    "chat_widget_settings.intro_video.duration": 10,
                    "chat_widget_settings.intro_video.show_on_first_visit": True
                }
            }
        )
        
        print(f"[DEBUG] Update result: {update_result.modified_count} documents modified")
        
        # Verify the update
        updated_org = db.organizations.find_one({"_id": organization["_id"]})
        print(f"[DEBUG] After update - intro_video: {updated_org.get('chat_widget_settings', {}).get('intro_video')}")
        
        return {
            "status": "success",
            "message": "Video uploaded successfully",
            "video_url": video_url,
            "filename": unique_filename
        }
        
    except Exception as e:
        print(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/video/{filename}")
async def get_video(filename: str):
    """Serve uploaded video files"""
    try:
        file_path = Path("uploads/videos") / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")
        
        return FileResponse(file_path, media_type="video/mp4")
        
    except Exception as e:
        print(f"Error serving video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/video")
async def delete_video(
    organization=Depends(get_organization_from_api_key)
):
    """Delete the current video"""
    try:
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        # Get current video info
        org = db.organizations.find_one({"_id": organization["_id"]})
        if org and "chat_widget_settings" in org and "intro_video" in org["chat_widget_settings"]:
            intro_video = org["chat_widget_settings"]["intro_video"]
            video_filename = intro_video.get("video_filename")
            video_url = intro_video.get("video_url")
            
            if video_filename:
                # Check if it's a cloud storage URL
                if video_url and "digitaloceanspaces.com" in video_url:
                    # Delete from DigitalOcean Spaces
                    try:
                        # boto3 already imported at top
                        
                        SPACE_NAME = os.getenv('DO_SPACES_BUCKET', 'bayshore')
                        SPACE_REGION = os.getenv('DO_SPACES_REGION', 'nyc3')
                        SPACE_ENDPOINT = f"https://{SPACE_REGION}.digitaloceanspaces.com"
                        ACCESS_KEY = os.getenv('DO_SPACES_KEY')
                        SECRET_KEY = os.getenv('DO_SPACES_SECRET')
                        FOLDER_NAME = os.getenv('DO_FOLDER_NAME', 'ai_bot')
                        
                        if all([ACCESS_KEY, SECRET_KEY]):
                            s3_client = boto3.client('s3',
                                endpoint_url=SPACE_ENDPOINT,
                                aws_access_key_id=ACCESS_KEY,
                                aws_secret_access_key=SECRET_KEY,
                                region_name=SPACE_REGION
                            )
                            
                            # Delete from Spaces
                            object_key = f"{FOLDER_NAME}/videos/{video_filename}"
                            s3_client.delete_object(Bucket=SPACE_NAME, Key=object_key)
                            print(f"Deleted video from Spaces: {object_key}")
                        
                    except Exception as e:
                        print(f"Error deleting from Spaces: {str(e)}")
                        # Continue with database cleanup even if cloud deletion fails
                        
                else:
                    # Delete local file
                    file_path = Path("uploads/videos") / video_filename
                    if file_path.exists():
                        file_path.unlink()
                        print(f"Deleted local video: {file_path}")
                
                # Update organization settings - reset intro_video to default state
                db.organizations.update_one(
                    {"_id": organization["_id"]},
                    {
                        "$set": {
                            "chat_widget_settings.intro_video": {
                                "enabled": False,
                                "video_url": None,
                                "video_filename": None,
                                "autoplay": True,
                                "duration": 10,
                                "show_on_first_visit": True
                            }
                        }
                    }
                )
        
        return {
            "status": "success",
            "message": "Video deleted successfully"
        }
        
    except Exception as e:
        print(f"Error deleting video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/video-settings")
async def update_video_settings(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Update video settings"""
    try:
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        data = await request.json()
        enabled = data.get("enabled", False)
        autoplay = data.get("autoplay", True)
        duration = data.get("duration", 10)
        show_on_first_visit = data.get("show_on_first_visit", True)
        
        db.organizations.update_one(
            {"_id": organization["_id"]},
            {
                "$set": {
                    "chat_widget_settings.intro_video.enabled": enabled,
                    "chat_widget_settings.intro_video.autoplay": autoplay,
                    "chat_widget_settings.intro_video.duration": duration,
                    "chat_widget_settings.intro_video.show_on_first_visit": show_on_first_visit
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Video settings updated successfully",
            "settings": {
                "enabled": enabled,
                "autoplay": autoplay,
                "duration": duration,
                "show_on_first_visit": show_on_first_visit
            }
        }
        
    except Exception as e:
        print(f"Error updating video settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/video-settings")
async def get_video_settings(
    organization=Depends(get_organization_from_api_key)
):
    """Get current video settings"""
    try:
        # Safely get organization ID
        org_id = organization.get("id") or organization.get("_id")
        if not org_id:
            raise HTTPException(status_code=500, detail="Organization ID not found")
        
        org = db.organizations.find_one({"_id": organization["_id"]})
        
        if org and "chat_widget_settings" in org and "intro_video" in org["chat_widget_settings"]:
            intro_video = org["chat_widget_settings"]["intro_video"]
            return {
                "status": "success",
                "settings": intro_video
            }
        else:
            # Return default settings if not found
            default_settings = {
                "enabled": False,
                "video_url": None,
                "video_filename": None,
                "autoplay": True,
                "duration": 10,
                "show_on_first_visit": True
            }
            return {
                "status": "success",
                "settings": default_settings
            }
        
    except Exception as e:
        print(f"Error getting video settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
