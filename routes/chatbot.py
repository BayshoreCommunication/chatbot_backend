import logging

# Set up clean logging for chatbot
logger = logging.getLogger('chatbot')

# Reduce pymongo logging noise  
logging.getLogger('pymongo').setLevel(logging.WARNING)

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, Header, Body
from fastapi.responses import FileResponse
import sys
import traceback
import boto3
from botocore.config import Config

# Try to import required services with error handling
try:
    from services.langchain.engine import ask_bot, add_document, escalate_to_human
    from services.language_detect import detect_language
    from services.database import (
        get_organization_by_api_key, create_or_update_visitor, add_conversation_message, 
        get_visitor, get_conversation_history, save_user_profile, get_user_profile, db,
        set_agent_mode, set_bot_mode, is_chat_in_agent_mode
    )
    from services.faq_matcher import find_matching_faq, get_suggested_faqs
    from services.langchain.user_management import handle_name_collection, handle_email_collection
    SERVICES_AVAILABLE = True
except Exception as e:
    print(f"Error importing services: {str(e)}")
    print(traceback.format_exc())
    SERVICES_AVAILABLE = False

from typing import Optional, Dict, Any, List
import json
import os
from pydantic import BaseModel
from datetime import datetime
import pymongo
import re
import openai
import socketio
from fastapi import FastAPI
import shutil
import uuid
from pathlib import Path

router = APIRouter()
sio = None

# Initialize socket.io
def init_socketio(app: FastAPI):
    global sio
    sio = socketio.AsyncServer(
        cors_allowed_origins="*",
        async_mode='asgi',
        logger=True,  # Enable logging for debugging
        engineio_logger=True,  # Enable engine.io logging for debugging
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1e8,
        allow_upgrades=True,
        transports=['websocket', 'polling'],
        cors_credentials=True,
        always_connect=True
    )
    
    @sio.event
    async def connect(sid, environ, auth):
        logger.info(f"Client connected: {sid}")
        logger.info(f"Environment: {environ}")
        logger.info(f"Auth: {auth}")
        
        try:
            # Get API key from auth or query params
            api_key = None
            if auth and isinstance(auth, dict):
                api_key = auth.get('apiKey')
                logger.info(f"API key from auth: {api_key}")
            
            if not api_key:
                # Try to get from query params
                query_string = environ.get('QUERY_STRING', '')
                logger.info(f"Query string: {query_string}")
                if 'apiKey=' in query_string:
                    for param in query_string.split('&'):
                        if param.startswith('apiKey='):
                            api_key = param.split('=')[1]
                            break
            
            logger.info(f"Final API key: {api_key}")
            
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
                    'status': 'connected_no_api_key',
                    'message': 'Socket.IO connection established but no API key provided'
                }, room=sid)
        except Exception as e:
            logger.error(f"Error in socket connect: {str(e)}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            # Still allow connection even if there's an error
            await sio.emit('connection_confirmed', {
                'status': 'connected_with_error',
                'message': f'Socket.IO connection established with error: {str(e)}'
            }, room=sid)

    @sio.event
    async def disconnect(sid):
        logger.info(f"Client disconnected: {sid}")
        # Clean up any rooms the client was in
        try:
            rooms = await sio.get_rooms(sid)
            for room in rooms:
                await sio.leave_room(sid, room)
                logger.info(f"Client {sid} left room: {room}")
        except Exception as e:
            logger.error(f"Error cleaning up rooms for client {sid}: {str(e)}")

    @sio.event
    async def join_room(sid, data):
        logger.info(f"Join room request from {sid}: {data}")
        room = data.get('room')
        if room:
            try:
                await sio.enter_room(sid, room)
                logger.info(f"Client {sid} explicitly joined room: {room}")
                
                # Confirm room join
                await sio.emit('room_joined', {
                    'room': room,
                    'status': 'joined'
                }, room=sid)
            except Exception as e:
                logger.error(f"Error joining room {room} for client {sid}: {str(e)}")
                await sio.emit('room_join_error', {
                    'room': room,
                    'error': str(e)
                }, room=sid)
        else:
            logger.warning(f"Client {sid} tried to join room without room name")
            await sio.emit('room_join_error', {
                'error': 'No room name provided'
            }, room=sid)
    
    # Mount Socket.IO on the FastAPI app at /socket.io/
    socket_asgi_app = socketio.ASGIApp(
        sio, 
        app, 
        socketio_path='/socket.io'
    )
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
    video_autoplay: Optional[bool] = False
    video_duration: Optional[int] = 10

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
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

@router.post("/ask")
async def ask_question(
    request: ChatRequest, 
    organization=Depends(get_organization_from_api_key)
):
    """Process a chat message and return a response"""
    # Use the correct organization ID field - try 'id' first, then '_id'
    org_id = organization.get("id") or str(organization.get("_id"))
    org_api_key = organization.get("api_key")
    namespace = organization.get("pinecone_namespace", "")

    print(f"[DEBUG] Organization object: {organization}")
    print(f"[DEBUG] Using org_id: {org_id}")

    try:
        print(f"[DEBUG] Processing message: {request.question}")
        print(f"[DEBUG] Session ID: {request.session_id}")

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
                                    'timestamp': datetime.now().isoformat()
            },
            'organization_id': org_id,
            'agent_mode': True
            }, room=org_api_key)

            # Return without AI response - agent will respond manually (no automatic message)
            return {
                "answer": "",  # No AI response
                "mode": "agent", 
                "language": "en",
                "user_data": request.user_data or {},
                "agent_mode": True
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
            print(f"[DEBUG] Loaded user profile: {user_profile['profile_data']}")
        else:
            print("[DEBUG] No user profile found")

        # Store the current user message ONCE at the beginning
        try:
            print(f"[DEBUG] Storing user message: {request.question}")
            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="user",
                content=request.question,
                metadata={"mode": request.mode}
            )
            print(f"[DEBUG] User message stored successfully")
        except Exception as e:
            print(f"[ERROR] Failed to store user message: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            # Continue processing even if message storage fails
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
                'timestamp': datetime.now().isoformat()
            },
            'organization_id': org_id
        }, room=org_api_key)

        print("[DEBUG] Checking user information collection")
        print(f"[DEBUG] Current user_data: {request.user_data}")
        
        # Import the improved conversation flow functions
        from services.conversation_flow import (
            process_user_message_for_info, extract_name_from_text, extract_email_from_text,
            get_natural_greeting, should_collect_contact_info, should_offer_calendar,
            get_natural_contact_prompt, get_calendar_offer
        )
        
        # Process the current message for name/email extraction
        request.user_data = process_user_message_for_info(request.question, request.user_data)
        
        # Calculate conversation depth for natural flow
        conversation_history = request.user_data.get("conversation_history", [])
        conversation_count = len(conversation_history)
        
        # Check if we need to collect user information naturally
        has_name = "name" in request.user_data and request.user_data["name"] and request.user_data["name"] not in ["Anonymous User", "Guest User"]
        has_email = "email" in request.user_data and request.user_data["email"] and request.user_data["email"] != "anonymous@user.com"
        
        print(f"[DEBUG] Has name: {has_name}, Has email: {has_email}, Conversation count: {conversation_count}")
        
        # Check if we should collect contact info naturally
        should_collect = should_collect_contact_info(conversation_history, request.question, request.user_data)
        
        # Check if we should offer calendar
        should_offer_cal = should_offer_calendar(conversation_history, request.question, request.user_data)
        
        # Handle contact information collection naturally
        if should_collect and not has_name:
            print("[DEBUG] Name not found, processing name collection")
            
            # Use the improved name extraction function
            extracted_name, is_refusal = extract_name_from_text(request.question)
            print(f"[DEBUG] Extracted name: {extracted_name}, Is refusal: {is_refusal}")
            
            if is_refusal:
                print("[DEBUG] User refused to share name")
                request.user_data["name"] = "Anonymous User"
                save_user_profile(org_id, request.session_id, request.user_data)
                
                # Continue with natural conversation
                continue_response = "No problem at all! How can I help you with your legal questions today?"
                
                # Store and add to history
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="assistant",
                    content=continue_response,
                    metadata={"mode": "faq"}
                )
                request.user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": continue_response
                })
                
                # Emit assistant message to dashboard
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': continue_response,
                        'timestamp': datetime.now().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)
                
                return {
                    "answer": continue_response,
                    "mode": "faq",
                    "language": "en",
                    "user_data": request.user_data
                }
            elif extracted_name:
                print("[DEBUG] Valid name found")
                request.user_data["name"] = extracted_name
                save_user_profile(org_id, request.session_id, request.user_data)
                
                # Natural acknowledgment and continue conversation
                acknowledgment = f"Nice to meet you, {extracted_name}! How can I help you with your legal questions today?"
                
                # Store and add to history
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="assistant",
                    content=acknowledgment,
                    metadata={"mode": "faq"}
                )
                request.user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": acknowledgment
                })
                
                # Emit assistant message to dashboard
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': acknowledgment,
                        'timestamp': datetime.now().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)
                
                return {
                    "answer": acknowledgment,
                    "mode": "faq",
                    "language": "en",
                    "user_data": request.user_data
                }
            else:
                print("[DEBUG] No valid name found")
                
                # Use natural contact prompt
                name_prompt = get_natural_contact_prompt(request.user_data, conversation_count)
                
                # Store and add to history
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="assistant",
                    content=name_prompt,
                    metadata={"mode": "faq"}
                )
                request.user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": name_prompt
                })
                
                # Emit assistant message to dashboard
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': name_prompt,
                        'timestamp': datetime.now().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)
                
                return {
                    "answer": name_prompt,
                    "mode": "faq",
                    "language": "en",
                    "user_data": request.user_data
                }
                print(f"[DEBUG] Error in AI name extraction: {str(e)}")
                fallback_response = handle_name_collection(request.question, request.user_data, "faq", "en")
                
                # Save the user profile if name was collected in fallback
                if fallback_response and "user_data" in fallback_response and "name" in fallback_response["user_data"]:
                    save_user_profile(org_id, request.session_id, fallback_response["user_data"])
                    print(f"[DEBUG] Saved user profile with name: {fallback_response['user_data']['name']}")
                
                # Save the assistant message to database (which handle_name_collection doesn't do)
                if fallback_response and "answer" in fallback_response:
                    add_conversation_message(
                        organization_id=org_id,
                        visitor_id=visitor["id"],
                        session_id=request.session_id,
                        role="assistant",
                        content=fallback_response["answer"],
                        metadata={"mode": "faq", "fallback": True}
                    )
                    
                    # Emit assistant message to dashboard
                    await sio.emit('new_message', {
                        'session_id': request.session_id,
                        'message': {
                            'role': 'assistant',
                            'content': fallback_response["answer"],
                            'timestamp': datetime.now().isoformat()
                        },
                        'organization_id': org_id
                    }, room=org_api_key)
                
                return fallback_response
                
        elif should_collect and has_name and not has_email:
            print("[DEBUG] Email not found, processing email collection")
            
            # Use the improved email extraction function
            extracted_email, is_refusal = extract_email_from_text(request.question)
            print(f"[DEBUG] Extracted email: {extracted_email}, Is refusal: {is_refusal}")
            
            if extracted_email:
                request.user_data["email"] = extracted_email
                save_user_profile(org_id, request.session_id, request.user_data)
                
                # Natural acknowledgment and continue
                acknowledgment = f"Perfect! I'll make sure to send you helpful information. How can I assist you with your legal questions today?"
                
                # Store and add to history
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="assistant",
                    content=acknowledgment,
                    metadata={"mode": "faq"}
                )
                request.user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": acknowledgment
                })
                
                # Emit assistant message to dashboard
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': acknowledgment,
                        'timestamp': datetime.utcnow().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)
                
                return {
                    "answer": acknowledgment,
                    "mode": "faq",
                    "language": "en",
                    "user_data": request.user_data
                }
            elif is_refusal:
                request.user_data["email"] = "anonymous@user.com"
                save_user_profile(org_id, request.session_id, request.user_data)
                
                # Natural acknowledgment and continue
                acknowledgment = "No problem at all! How can I help you with your legal questions today?"
                
                # Store and add to history
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="assistant",
                    content=acknowledgment,
                    metadata={"mode": "faq"}
                )
                request.user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": acknowledgment
                })
                
                # Emit assistant message to dashboard
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': acknowledgment,
                        'timestamp': datetime.now().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)
                
                return {
                    "answer": acknowledgment,
                    "mode": "faq",
                    "language": "en",
                    "user_data": request.user_data
                }
            else:
                # Use natural email prompt
                email_prompt = get_natural_contact_prompt(request.user_data, conversation_count)
                
                # Store and add to history
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="assistant",
                    content=email_prompt,
                    metadata={"mode": "faq"}
                )
                request.user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": email_prompt
                })
                
                # Emit assistant message to dashboard
                await sio.emit('new_message', {
                    'session_id': request.session_id,
                    'message': {
                        'role': 'assistant',
                        'content': email_prompt,
                        'timestamp': datetime.now().isoformat()
                    },
                    'organization_id': org_id
                }, room=org_api_key)
                
                return {
                    "answer": email_prompt,
                    "mode": "faq",
                    "language": "en",
                    "user_data": request.user_data
                }
                print(f"[DEBUG] Error in AI email validation: {str(e)}")
                # Fall back to regex validation
                email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", request.question)
                if email_match or request.question.lower() in ["skip", "no", "pass"]:
                    if email_match:
                        request.user_data["email"] = email_match.group(0)
                    else:
                        request.user_data["email"] = "anonymous@user.com"
                    
                    save_user_profile(org_id, request.session_id, request.user_data)
                    
                    welcome = f"Thank you{' ' + request.user_data['name'] if request.user_data.get('name') and request.user_data['name'] != 'Anonymous User' else ''}! How can I assist you today?"
                    
                    # Store and add to history
                    add_conversation_message(
                        organization_id=org_id,
                        visitor_id=visitor["id"],
                        session_id=request.session_id,
                        role="assistant",
                        content=welcome,
                        metadata={"mode": "faq"}
                    )
                    request.user_data["conversation_history"].append({
                        "role": "assistant",
                        "content": welcome
                    })
                    
                    # Emit assistant message to dashboard
                    await sio.emit('new_message', {
                        'session_id': request.session_id,
                        'message': {
                            'role': 'assistant',
                            'content': welcome,
                            'timestamp': datetime.now().isoformat()
                        },
                        'organization_id': org_id
                    }, room=org_api_key)
                    
                    return {
                        "answer": welcome,
                        "mode": "faq",
                        "language": "en",
                        "user_data": request.user_data
                    }

        # Try to find matching FAQ only after user info is collected
        print("[DEBUG] Starting FAQ matching process...")
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
                    'timestamp': datetime.now().isoformat()
                },
                'organization_id': org_id
            }, room=org_api_key)

            # Get suggested FAQs for follow-up
            print("[DEBUG] Getting suggested FAQs...")
            suggested_faqs = get_suggested_faqs(org_id)
            print(f"[DEBUG] Found {len(suggested_faqs)} suggested FAQs")

            print("[DEBUG] Returning FAQ response...")
            return {
                "answer": matching_faq["response"],
                "mode": "faq",
                "language": "en",
                "user_data": request.user_data,
                "suggested_faqs": suggested_faqs
            }

        # Check if we should offer calendar scheduling
        if should_offer_cal:
            print("[DEBUG] Offering calendar scheduling")
            calendar_offer = get_calendar_offer(request.user_data)
            
            # Store and add to history
            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="assistant",
                content=calendar_offer,
                metadata={"mode": "faq", "calendar_offer": True}
            )
            request.user_data["conversation_history"].append({
                "role": "assistant",
                "content": calendar_offer
            })
            
            # Emit assistant message to dashboard
            await sio.emit('new_message', {
                'session_id': request.session_id,
                'message': {
                    'role': 'assistant',
                    'content': calendar_offer,
                    'timestamp': datetime.now().isoformat()
                },
                'organization_id': org_id
            }, room=org_api_key)
            
            return {
                "answer": calendar_offer,
                "mode": "faq",
                "language": "en",
                "user_data": request.user_data
            }

        # If no FAQ match, proceed with normal chatbot flow
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
        else:
            # Use default Carter Injury Law behavior if none is set
            from services.ai_improvement import AIImprovementService
            default_behavior = AIImprovementService.CARTER_INJURY_LAW_PROMPTS["default_behavior"]
            user_context += f"\nAI Behavior Instructions: {default_behavior}\n"

        # Enhance query with user context if needed
        enhanced_query = request.question
        if user_context and request.user_data.get("returning_user"):
            enhanced_query = f"{user_context}The user, who you already know, asks: {request.question}"

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
        try:
            print(f"[DEBUG] Storing assistant message: {response['answer'][:50]}...")
            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="assistant",
                content=response["answer"],
                metadata={"mode": request.mode}
            )
            print(f"[DEBUG] Assistant message stored successfully")
        except Exception as e:
            print(f"[ERROR] Failed to store assistant message: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            # Continue processing even if message storage fails

        # Then update conversation history in user_data to match database order
        response["user_data"]["conversation_history"].append({
            "role": "assistant", 
            "content": response["answer"]
        })

        # Get suggested FAQs
        suggested_faqs = get_suggested_faqs(org_id)
        response["suggested_faqs"] = suggested_faqs

        # Store interaction for learning
        try:
            from services.user_learning import user_learning_service
            
            interaction_data = {
                "user_question": request.question,
                "ai_response": response["answer"],
                "mode": response.get("mode", "faq"),
                "intent_detected": "",  # Could be enhanced with intent detection
                "knowledge_base_used": "sources" in response,
                "faq_matched": "suggested_faqs" in response,
                "conversation_stage": "early" if len(request.user_data.get("conversation_history", [])) < 6 else "engaged",
                "user_data": {
                    "has_name": bool(request.user_data.get("name")),
                    "has_email": bool(request.user_data.get("email")),
                    "conversation_count": len(request.user_data.get("conversation_history", []))
                }
            }
            
            user_learning_service.store_interaction(org_id, request.session_id, interaction_data)
        except Exception as e:
            print(f"Error storing learning data: {str(e)}")

        # After getting bot response, emit it to dashboard
        await sio.emit('new_message', {
            'session_id': request.session_id,
            'message': {
                'role': 'assistant',
                'content': response["answer"],
                'timestamp': datetime.now().isoformat()
            },
            'organization_id': org_id
        }, room=org_api_key)

        return response

    except Exception as e:
        print(f"Error processing chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Retrieve chat history for a session"""
    org_id = organization["id"]
    
    # Get fresh conversation data from MongoDB
    previous_conversations = get_conversation_history(organization_id=org_id, session_id=session_id)
    print(f"[DEBUG] previous_conversations: {previous_conversations} organization: {org_id}")
    
    # Get visitor information - create if doesn't exist for new users
    visitor = get_visitor(org_id, session_id)
    if not visitor:
        # Create a new visitor for new users instead of returning 404
        print(f"[DEBUG] Creating new visitor for session: {session_id}")
        visitor = create_or_update_visitor(
            organization_id=org_id,
            session_id=session_id,
            visitor_data={
                "last_active": None,
                "metadata": {
                    "mode": "faq",
                    "user_data": {}
                }
            }
        )
    
    # Check if chat is in agent mode
    is_agent_mode = visitor.get("is_agent_mode", False)
    agent_id = visitor.get("agent_id")
    agent_takeover_at = visitor.get("agent_takeover_at")
    
    # Get user profile
    user_profile = get_user_profile(org_id, session_id)
    profile_data = {}
    
    if user_profile and "profile_data" in user_profile:
        profile_data = user_profile["profile_data"]
    
    # Format conversation history
    formatted_history = []
    for msg in previous_conversations:
        if "role" in msg and "content" in msg:
            formatted_history.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })
    
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
    suggested_faqs = get_suggested_faqs(org_id)
    
    # Build response
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
        "agent_id": agent_id,
        "agent_takeover_at": agent_takeover_at.isoformat() if agent_takeover_at else None
    }
    
    return response

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
    
    # Get organization ID
    org_id = organization["id"]
    
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
    org_id = organization["id"]
    
    history = []
    for item in upload_history_collection.find(
        {"org_id": org_id},
        sort=[("created_at", pymongo.DESCENDING)]
    ):
        item["id"] = str(item.pop("_id"))
        history.append(item)
    
    return history

@router.post("/upload_document")
async def upload_document(
    request: Request,
    file: Optional[UploadFile] = File(None),
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
    org_id = organization["id"]
    org_api_key = organization["api_key"]
    
    try:
        # Handle both JSON and form data
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
            url = data.get("url")
            text = data.get("text")
            scrape_website = data.get("scrape_website", False)
            max_pages = data.get("max_pages", 10)
        else:
            # Handle form data
            form_data = await request.form()
            url = form_data.get("url")
            text = form_data.get("text")
            scrape_website = form_data.get("scrape_website", "false").lower() == "true"
            max_pages = int(form_data.get("max_pages", "10"))
        
        print(f"[UPLOAD_DOCUMENT] Processing: file={file is not None}, url={url}, scrape_website={scrape_website}")
        
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
                "created_at": datetime.now()
            })
            
            # Clean up temporary file
            os.remove(file_path)
            
            return result
        
        elif url:
            # Get platform info if provided
            platform = data.get("platform", "website") if 'data' in locals() else "website"
            
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
                result = add_document(url=url, api_key=org_api_key)
            
            # Store upload history
            upload_history_collection.insert_one({
                "org_id": org_id,
                "url": url,
                "type": "url",
                "status": "Used",
                "created_at": datetime.now()
            })
            
            return result
        
        elif text:
            result = add_document(text=text, api_key=org_api_key)
            
            # Store upload history for text content
            upload_history_collection.insert_one({
                "org_id": org_id,
                "type": "text",
                "status": "Used",
                "created_at": datetime.now()
            })
            
            return result
        
        else:
            raise HTTPException(status_code=400, detail="No document source provided")
            
    except Exception as e:
        # Store failed upload in history
        error_data = {
            "org_id": org_id,
            "status": "Failed",
            "created_at": datetime.now()
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
    org_id = organization["id"]
    
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
    
    # Get organization ID
    org_id = organization["id"]
    
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
        
        # Update organization in MongoDB with chat widget settings
        update_data = {
            "$set": {
                "chat_widget_settings": settings_dict
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
        
        org_id = organization["id"]
        org_api_key = organization.get("api_key")
        
        print(f"Agent takeover request - Session ID: {session_id}, Agent ID: {agent_id}, Org ID: {org_id}")
        
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
        
        org_id = organization["id"]
        org_api_key = organization.get("api_key")
        
        print(f"Agent release request - Session ID: {session_id}, Org ID: {org_id}")
        
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
        
        org_id = organization["id"]
        org_api_key = organization.get("api_key")
        
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
                "auto_open": False
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

@router.get("/welcome-message")
async def get_welcome_message(
    organization=Depends(get_organization_from_api_key)
):
    """Get the welcome message for the chat widget from instant reply model"""
    try:
        # Step 1: Get organization details from API key
        org_id = organization["id"]  # Use "id" field, not "_id"
        print(f"[DEBUG] Step 1: Found organization ID from API key: {org_id}")
        
        # Step 2: Use organization ID to find instant reply
        print(f"[DEBUG] Step 2: Searching for instant reply with organization_id: {org_id}")
        instant_reply = db.instant_reply.find_one({
            "organization_id": org_id,
            "type": "instant_reply"
        })
        
        print(f"[DEBUG] Step 2 Result: Found instant reply: {instant_reply is not None}")
        
        # Step 3: Check if we found any instant reply
        if not instant_reply or not instant_reply.get("messages"):
            # Return default welcome message if no instant replies found
            default_message = "👋 Welcome! I'm your AI assistant. I can help you with:\n• Scheduling appointments\n• Answering questions about our services\n• Providing information and support"
            print(f"[DEBUG] Step 3: No instant replies found, using default message")
            return {
                "status": "success",
                "data": {
                    "message": default_message
                }
            }
        
        # Step 4: Get the first message from instant replies as welcome message
        messages = instant_reply.get("messages", [])
        print(f"[DEBUG] Step 4: Found {len(messages)} instant reply messages")
        
        if messages and len(messages) > 0:
            # Sort by order and get the first message
            sorted_messages = sorted(messages, key=lambda x: x.get("order", 0))
            welcome_message = sorted_messages[0].get("message", "")
            
            print(f"[DEBUG] Step 4 Result: Using first message as welcome: {welcome_message[:50]}...")
            
            if welcome_message:
                return {
                    "status": "success",
                    "data": {
                        "message": welcome_message
                    }
                }
        
        # Fallback to default message
        default_message = "👋 Welcome! I'm your AI assistant. I can help you with:\n• Scheduling appointments\n• Answering questions about our services\n• Providing information and support"
        print(f"[DEBUG] Fallback: Using default message")
        return {
            "status": "success",
            "data": {
                "message": default_message
            }
        }
        
    except Exception as e:
        print(f"[ERROR] Exception in get_welcome_message: {str(e)}")
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Test route to debug loading issue
@router.get("/test-route")
async def test_route():
    """Simple test route to check if routes after settings work"""
    return {"status": "success", "message": "Test route working"}

@router.get("/socket-health")
async def socket_health_check():
    """Health check for Socket.IO functionality"""
    try:
        if sio:
            return {
                "status": "healthy",
                "socket_io": "available",
                "message": "Socket.IO server is running"
            }
        else:
            return {
                "status": "unhealthy",
                "socket_io": "unavailable",
                "message": "Socket.IO server is not initialized"
            }
    except Exception as e:
        return {
            "status": "error",
            "socket_io": "error",
            "message": f"Socket.IO health check failed: {str(e)}"
        }

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
        org_id = organization["id"]
        
        db.organizations.update_one(
            {"_id": organization["_id"]},
            {
                "$set": {
                    "chat_widget_settings.video_url": video_url,
                    "chat_widget_settings.video_filename": unique_filename,
                    "chat_widget_settings.video_autoplay": True,
                    "chat_widget_settings.video_duration": 10
                }
            }
        )
        
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
        org_id = organization["id"]
        
        # Get current video info
        org = db.organizations.find_one({"_id": organization["_id"]})
        if org and "chat_widget_settings" in org:
            video_filename = org["chat_widget_settings"].get("video_filename")
            video_url = org["chat_widget_settings"].get("video_url")
            
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
                
                # Update organization settings
                db.organizations.update_one(
                    {"_id": organization["_id"]},
                    {
                        "$unset": {
                            "chat_widget_settings.video_url": "",
                            "chat_widget_settings.video_filename": "",
                            "chat_widget_settings.video_autoplay": "",
                            "chat_widget_settings.video_duration": ""
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
        data = await request.json()
        autoplay = data.get("autoplay", True)
        duration = data.get("duration", 10)
        
        db.organizations.update_one(
            {"_id": organization["_id"]},
            {
                "$set": {
                    "chat_widget_settings.video_autoplay": autoplay,
                    "chat_widget_settings.video_duration": duration
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Video settings updated successfully",
            "autoplay": autoplay,
            "duration": duration
        }
        
    except Exception as e:
        print(f"Error updating video settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear-cache")
async def clear_conversation_cache_endpoint(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Clear conversation cache for better flow"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        org_id = organization["id"]
        
        # Import and use the conversation flow module
        from services.conversation_flow import clear_conversation_cache, reset_user_session
        
        # Clear cache
        cache_cleared = clear_conversation_cache(session_id, org_id)
        session_reset = reset_user_session(org_id, session_id)
        
        return {
            "status": "success",
            "message": "Cache cleared successfully",
            "cache_cleared": cache_cleared,
            "session_reset": session_reset
        }
        
    except Exception as e:
        print(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-conversation")
async def reset_conversation_flow(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Reset conversation flow to start fresh"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        org_id = organization["id"]
        
        # Clear all conversation data
        db.conversations.delete_many({
            "organization_id": org_id,
            "session_id": session_id
        })
        
        # Clear visitor data
        db.visitors.update_one(
            {"organization_id": org_id, "session_id": session_id},
            {"$unset": {"metadata": "", "profile_data": ""}}
        )
        
        # Clear user profiles
        db.user_profiles.delete_many({
            "organization_id": org_id,
            "session_id": session_id
        })
        
        return {
            "status": "success",
            "message": "Conversation reset successfully",
            "session_id": session_id
        }
        
    except Exception as e:
        print(f"Error resetting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/learning-analytics")
async def get_learning_analytics(
    organization=Depends(get_organization_from_api_key)
):
    """Get AI learning analytics and improvement suggestions"""
    try:
        from services.user_learning import user_learning_service
        
        org_id = organization["id"]
        
        # Get analytics
        analytics = user_learning_service.get_learning_analytics(org_id)
        
        # Get improvement suggestions
        suggestions = user_learning_service.get_response_improvement_suggestions(org_id)
        
        return {
            "status": "success",
            "analytics": analytics,
            "improvement_suggestions": suggestions
        }
        
    except Exception as e:
        print(f"Error getting learning analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/common-questions")
async def get_common_questions(
    days: int = 30,
    organization=Depends(get_organization_from_api_key)
):
    """Get most common questions from users"""
    try:
        from services.user_learning import user_learning_service
        
        org_id = organization["id"]
        common_questions = user_learning_service.analyze_common_questions(org_id, days)
        
        return {
            "status": "success",
            "common_questions": common_questions,
            "period_days": days
        }
        
    except Exception as e:
        print(f"Error getting common questions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auto-train-from-website")
async def auto_train_from_website(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Automatically train AI from Carter Injury Law website"""
    try:
        data = await request.json()
        website_url = data.get("url", "https://www.carterinjurylaw.com")
        
        org_id = organization["id"]
        org_api_key = organization["api_key"]
        
        print(f"[AUTO-TRAIN] Starting auto-training from website: {website_url}")
        
        # Add comprehensive Carter Injury Law knowledge
        training_content = f"""
Carter Injury Law - Personal Injury Law Firm Information

FIRM OVERVIEW:
Carter Injury Law is a premier personal injury law firm based in Tampa, Florida, serving clients throughout the state. Our experienced team is led by attorneys David J. Carter and Robert Johnson, who have decades of combined experience helping accident victims recover fair compensation.

SERVICE AREAS:
- Auto Accidents & Motor Vehicle Collisions
- Motorcycle Accidents  
- Truck Accidents & Commercial Vehicle Crashes
- Slip & Fall / Premises Liability
- Medical Malpractice
- Workers' Compensation
- Wrongful Death Cases
- Product Liability
- Dog Bites & Animal Attacks
- Nursing Home Abuse
- General Negligence Claims

GEOGRAPHIC COVERAGE:
We serve clients throughout Florida, not just Tampa. Our attorneys are licensed to practice statewide and can travel to meet clients wherever they are located. We handle cases in all Florida counties and cities including:
- Tampa
- St. Petersburg
- Clearwater
- Orlando
- Miami
- Jacksonville
- Fort Lauderdale
- And all other Florida cities

FIRM VALUES & GUARANTEES:
- No fee unless we win your case (contingency fee basis)
- 30-day no-fee satisfaction guarantee
- Free initial consultations
- 24/7 availability for clients
- Personalized attention to every case
- Decades of combined experience
- Millions of dollars recovered for clients

CONTACT INFORMATION:
Phone: (813) 922-0228
Address: 3114 N. BOULEVARD TAMPA, FL 33603
Satellite Office: 801 W. Bay Dr., Suite 229, Largo, FL 33770 (By Appointment)

FREQUENTLY ASKED QUESTIONS:

Q: How much will it cost me to hire you?
A: We work on a contingency fee basis, which means no fee unless we win your case. We also offer a 30-day no-fee satisfaction guarantee to ensure you're completely satisfied with our services.

Q: How long will my personal injury case take?
A: Case duration varies depending on complexity, severity of injuries, and other factors. However, we work efficiently to resolve cases as quickly as possible while ensuring you receive maximum compensation. Simple cases may settle in a few months, while complex cases involving severe injuries may take longer.

Q: How much is my case worth?
A: Case value depends on several factors including injury severity, medical expenses (current and future), lost wages, pain and suffering, and impact on your quality of life. We provide free case evaluations to assess your claim's potential value and explain what damages you may be entitled to recover.

Q: Who pays my medical bills after an accident?
A: Medical bills may be covered through various sources including your health insurance, the at-fault party's insurance, your auto insurance (PIP coverage in Florida), or through medical providers who agree to wait for payment until your case settles. We help coordinate payment and ensure you receive proper medical care.

Q: How long do I have to file my claim?
A: In Florida, the statute of limitations for personal injury cases is typically 2-4 years depending on the type of case. However, it's crucial to act quickly to preserve evidence, gather witness statements, and protect your rights. The sooner you contact us, the better we can help you.

Q: Will my insurance go up if I make a claim?
A: Generally, filing a claim against another party's insurance shouldn't affect your rates since you're not at fault. However, filing claims with your own insurance (like PIP or collision coverage) may impact premiums depending on your policy terms and circumstances.

Q: Do you handle cases outside of Tampa?
A: Yes! We handle personal injury cases throughout Florida. Our attorneys are licensed to practice statewide and regularly travel to meet clients and handle cases in all Florida cities and counties.

Q: What should I do immediately after an accident?
A: 1) Ensure everyone's safety and call 911 if needed, 2) Document the scene with photos, 3) Exchange insurance information, 4) Get witness contact information, 5) Seek medical attention even if you feel fine, 6) Contact our office for a free consultation. Do not admit fault or sign anything from insurance companies before speaking with an attorney.

Q: What types of damages can I recover?
A: You may be entitled to compensation for medical expenses, lost wages, future medical care, pain and suffering, emotional distress, property damage, and in some cases punitive damages. The specific damages available depend on your unique circumstances.

Q: Do I have to go to court?
A: Most personal injury cases settle out of court through negotiations with insurance companies. However, we're fully prepared to take your case to trial if necessary to secure fair compensation. Our experienced trial attorneys will fight for your rights in court if needed.

ATTORNEY PROFILES:

David J. Carter:
Lead attorney with extensive experience in personal injury law. Known for his compassionate approach to client service and aggressive representation against insurance companies.

Robert Johnson:  
Experienced personal injury attorney specializing in complex cases involving severe injuries and wrongful death. Committed to achieving maximum compensation for clients.

WHAT MAKES US DIFFERENT:
- Personalized attention - you're not just a case number
- Aggressive representation against insurance companies
- Thorough investigation of every case
- Network of medical experts and accident reconstruction specialists
- No upfront costs or hidden fees
- 30-day satisfaction guarantee
- Proven track record of successful settlements and verdicts
"""

        # Add the training content to the vector database
        result = add_document(text=training_content, api_key=org_api_key)
        
        # Also try to scrape the actual website for additional content
        try:
            website_result = add_document(url=f"{website_url}?scrape_website=true&max_pages=20&platform=website", api_key=org_api_key)
            print(f"[AUTO-TRAIN] Website scraping result: {website_result}")
        except Exception as scrape_error:
            print(f"[AUTO-TRAIN] Website scraping failed: {str(scrape_error)}")
        
        # Store the auto-training in upload history
        upload_history_collection.insert_one({
            "org_id": org_id,
            "url": website_url,
            "type": "auto_training",
            "status": "Used",
            "created_at": datetime.now(),
            "description": "Auto-training from Carter Injury Law website"
        })
        
        return {
            "status": "success",
            "message": "AI auto-training completed successfully from Carter Injury Law website",
            "training_result": result,
            "content_added": "Comprehensive Carter Injury Law knowledge base including FAQs, practice areas, and firm information"
        }
        
    except Exception as e:
        print(f"Error in auto-training: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-training")
async def verify_ai_training(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Verify that AI can access trained content"""
    try:
        data = await request.json()
        test_question = data.get("question", "Do you handle cases outside of Tampa?")
        
        org_api_key = organization["api_key"]
        
        # Test the AI with the question
        response = ask_bot(
            query=test_question,
            mode="faq",
            user_data={"conversation_history": []},
            session_id="test_session",
            api_key=org_api_key
        )
        
        return {
            "status": "success",
            "test_question": test_question,
            "ai_response": response["answer"],
            "training_verified": len(response["answer"]) > 50 and "How can I assist you today?" not in response["answer"]
        }
        
    except Exception as e:
        print(f"Error verifying training: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quick-test-ai")
async def quick_test_ai(
    request: Request,
    organization=Depends(get_organization_from_api_key)
):
    """Quick test of AI responses for debugging"""
    try:
        data = await request.json()
        question = data.get("question", "Do you handle cases outside of Tampa?")
        
        org_api_key = organization["api_key"]
        
        print(f"[QUICK-TEST] Testing question: {question}")
        
        # Test the AI response
        response = ask_bot(
            query=question,
            mode="faq",
            user_data={"conversation_history": []},
            session_id="quick_test",
            api_key=org_api_key
        )
        
        # Also test FAQ matching separately
        from services.faq_matcher import find_matching_faq
        org_id = organization["id"]
        namespace = organization.get("pinecone_namespace", "")
        
        faq_match = find_matching_faq(question, org_id, namespace)
        
        # Test knowledge base search
        from services.langchain.engine import get_org_vectorstore
        from services.langchain.knowledge import search_knowledge_base
        
        org_vectorstore = get_org_vectorstore(org_api_key)
        knowledge_results = None
        if org_vectorstore:
            try:
                knowledge_results, _ = search_knowledge_base(question, org_vectorstore, {"name": "Test", "email": "test@test.com"})
            except Exception as kb_error:
                print(f"Knowledge base search error: {str(kb_error)}")
        
        return {
            "status": "success",
            "question": question,
            "ai_response": response["answer"],
            "faq_match": faq_match,
            "knowledge_base_results": knowledge_results[:500] if knowledge_results else None,
            "vectorstore_available": org_vectorstore is not None,
            "response_quality": "good" if len(response["answer"]) > 50 and "How can I assist you today?" not in response["answer"] else "poor"
        }
        
    except Exception as e:
        print(f"Error in quick test: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "suggestion": "Try running auto-training first or check your API key configuration"
        }
