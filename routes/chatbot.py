from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, Header
from services.langchain.engine import ask_bot, add_document, escalate_to_human
from services.language_detect import detect_language
from services.database import get_organization_by_api_key, create_or_update_visitor, add_conversation_message, get_visitor, get_conversation_history, save_user_profile, get_user_profile
from typing import Optional, Dict, Any
import json
import os
from pydantic import BaseModel

router = APIRouter()

# User session storage (in a real application, use Redis for temporary storage)
user_sessions = {}

# Add new ChatWidgetSettings model
class ChatWidgetSettings(BaseModel):
    name: str
    selectedColor: str
    leadCapture: bool
    botBehavior: str
    avatarUrl: Optional[str] = None

class ChatRequest(BaseModel):
    question: str
    session_id: str
    mode: Optional[str] = "faq"
    user_data: Optional[dict] = None
    available_slots: Optional[str] = None

class ChatHistoryRequest(BaseModel):
    session_id: str

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
    # Get organization ID
    org_id = organization["id"]
    org_api_key = organization["api_key"]
    org_namespace = organization.get("pinecone_namespace", "")
    
    print(f"Processing request for organization: {org_id}")
    print(f"Organization API key: {org_api_key[:8]}...")
    print(f"Organization namespace: {org_namespace}")
    
    # Get previous conversations from MongoDB
    previous_conversations = get_conversation_history(org_id, request.session_id)
    
    # Get or create visitor
    visitor = create_or_update_visitor(
        organization_id=org_id,
        session_id=request.session_id,
        visitor_data={
            "last_active": None,  # MongoDB will set this
            "metadata": {
                "mode": request.mode,
                "user_data": request.user_data
            }
        }
    )
    
    # Convert MongoDB conversations to desired format for client
    formatted_history = []
    for msg in previous_conversations:
        if "role" in msg and "content" in msg:
            formatted_history.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })
    
    # Get user profile from dedicated collection
    user_profile = get_user_profile(org_id, request.session_id)
    profile_data = {}
    
    if user_profile and "profile_data" in user_profile:
        profile_data = user_profile["profile_data"]
        print(f"Found existing user profile: {profile_data}")
    
    # Initialize user_data if not provided
    if not request.user_data:
        request.user_data = {}
    
    # Merge profile data with request user_data (request takes precedence)
    merged_user_data = {**profile_data, **request.user_data}
    
    # Add conversation history to user_data - Use only MongoDB history, don't add to user_data yet
    merged_user_data["conversation_history"] = formatted_history
    
    # Add indicator for returning users
    if "name" in merged_user_data and merged_user_data["name"]:
        merged_user_data["returning_user"] = True
        print(f"Recognized returning user: {merged_user_data['name']}")
    
    # Get or create session (in-memory for now)
    session_key = f"{org_id}:{request.session_id}"
    session = user_sessions.get(session_key, {
        "user_data": merged_user_data,
        "current_mode": request.mode
    })
    
    # Update user session with merged data but keep original conversation history
    session["user_data"] = merged_user_data
    
    # Update user session
    user_sessions[session_key] = session
    
    # Print debugging info about the question
    print(f"Question: '{request.question}'")
    if "unique identifier" in request.question.lower() or "test-doc" in request.question.lower():
        print(f"UNIQUE IDENTIFIER QUESTION DETECTED!")
    
    # Prepare context for the bot to understand returning users
    user_context = ""
    if "name" in session["user_data"] and session["user_data"]["name"]:
        user_context = f"The user's name is {session['user_data']['name']}. "
    if "email" in session["user_data"] and session["user_data"]["email"]:
        user_context += f"The user's email is {session['user_data']['email']}. "
    
    # If we have user context, modify the question to include it
    enhanced_query = request.question
    if user_context and "returning_user" in session["user_data"] and session["user_data"]["returning_user"]:
        print(f"Adding user context to query: {user_context}")
        enhanced_query = f"{user_context}The user, who you already know, asks: {request.question}"
    
    # Get response based on mode
    response = ask_bot(
        query=enhanced_query,  # Use enhanced query with user context
        mode=session["current_mode"],
        user_data=session["user_data"],  # Pass existing user data with conversation history
        available_slots=request.available_slots,
        session_id=request.session_id,
        api_key=org_api_key
    )
    
    # Check if we received an error response
    if "status" in response and response["status"] == "error":
        return response
    
    # Store in MongoDB - Only store in MongoDB, not in session
    add_conversation_message(
        organization_id=org_id,
        visitor_id=visitor["id"],
        session_id=request.session_id,
        role="user",
        content=request.question,
        metadata={"mode": session["current_mode"]}
    )
    
    add_conversation_message(
        organization_id=org_id,
        visitor_id=visitor["id"],
        session_id=request.session_id,
        role="assistant",
        content=response["answer"],
        metadata={"mode": session["current_mode"]}
    )
    
    # Check if the user data contains important profile information
    profile_keys = ["name", "email", "phone", "preferences"]
    profile_updated = False
    profile_to_save = {}
    
    # Extract profile data from user_data
    for key in profile_keys:
        if key in session["user_data"] and session["user_data"][key]:
            profile_updated = True
            profile_to_save[key] = session["user_data"][key]
    
    # Update profile if needed
    if profile_updated or (response.get("user_data") and any(key in response["user_data"] for key in profile_keys)):
        # Add additional profile data from response
        if "user_data" in response:
            for key in profile_keys:
                if key in response["user_data"] and response["user_data"][key]:
                    profile_to_save[key] = response["user_data"][key]
        
        # Save profile to dedicated collection
        if profile_to_save:
            save_user_profile(org_id, request.session_id, profile_to_save)
            print(f"Saved user profile: {profile_to_save}")
    
    # Update session user data if provided in response
    if "user_data" in response:
        # Get fresh conversation history from MongoDB after adding new messages
        fresh_conversations = get_conversation_history(org_id, request.session_id)
        fresh_formatted_history = []
        for msg in fresh_conversations:
            if "role" in msg and "content" in msg:
                fresh_formatted_history.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })
        
        # Update the user data from the response
        session["user_data"].update(response["user_data"])
        
        # Replace the conversation history with the fresh one from MongoDB
        session["user_data"]["conversation_history"] = fresh_formatted_history
        
        # Update visitor data
        update_visitor_data = {
            "metadata": {
                "mode": session["current_mode"],
                "user_data": session["user_data"]
            }
        }
        create_or_update_visitor(org_id, request.session_id, update_visitor_data)
    
    # Update session mode if it changed
    if "mode" in response and response["mode"] != session["current_mode"]:
        session["current_mode"] = response["mode"]
    
    # Get fresh conversation history for the response
    fresh_conversations = get_conversation_history(org_id, request.session_id)
    fresh_formatted_history = []
    for msg in fresh_conversations:
        if "role" in msg and "content" in msg:
            fresh_formatted_history.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })
    
    # Use the fresh conversation history in the response
    if "user_data" not in response:
        response["user_data"] = {}
    
    response["user_data"]["conversation_history"] = fresh_formatted_history
    
    return response

@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Retrieve chat history using session key"""
    # Get organization ID
    org_id = organization["id"]
    
    # Get fresh conversation data from MongoDB
    previous_conversations = get_conversation_history(org_id, session_id)
    
    # Get visitor information
    visitor = get_visitor(org_id, session_id)
    if not visitor:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get user profile from dedicated collection
    user_profile = get_user_profile(org_id, session_id)
    profile_data = {}
    
    if user_profile and "profile_data" in user_profile:
        profile_data = user_profile["profile_data"]
    
    # Convert MongoDB conversations to desired format for client
    formatted_history = []
    for msg in previous_conversations:
        if "role" in msg and "content" in msg:
            formatted_history.append({
                "role": msg.get("role"),
                "content": msg.get("content")
            })
    
    # Determine current mode from visitor metadata
    current_mode = "faq"  # Default mode
    if visitor and "metadata" in visitor and "mode" in visitor["metadata"]:
        current_mode = visitor["metadata"]["mode"]
    
    # Get last assistant answer (if available)
    last_answer = ""
    for msg in reversed(formatted_history):
        if msg["role"] == "assistant":
            last_answer = msg["content"]
            break
    
    # Build user data object with the most recent conversation history
    user_data = {
        **profile_data,
        "conversation_history": formatted_history,
        "returning_user": "name" in profile_data and bool(profile_data.get("name"))
    }
    
    # Construct response in the required format
    response = {
        "answer": last_answer,
        "mode": current_mode,
        "language": "en",  # Default language
        "user_data": user_data
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

@router.post("/upload_document")
async def upload_document(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    scrape_website: Optional[bool] = Form(False),
    max_pages: Optional[int] = Form(10),
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
    org_api_key = organization["api_key"]
    
    if file:
        # Save uploaded file temporarily
        file_path = f"temp_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Add to vectorstore with organization namespace
        result = add_document(file_path=file_path, api_key=org_api_key)
        
        # Clean up temporary file
        os.remove(file_path)
        
        return result
    
    elif url:
        # Check if we should scrape the entire website
        if scrape_website:
            # Append parameters to URL to indicate scraping
            scrape_url = f"{url}?scrape_website=true&max_pages={max_pages}"
            print(f"Scraping website: {url} with max_pages={max_pages}")
            return add_document(url=scrape_url, api_key=org_api_key)
        else:
            # Just process the single URL
            return add_document(url=url, api_key=org_api_key)
    
    elif text:
        return add_document(text=text, api_key=org_api_key)
    
    else:
        raise HTTPException(status_code=400, detail="No document source provided")

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
        # Update organization in MongoDB with chat widget settings
        from services.database import db
        result = db.organizations.update_one(
            {"_id": organization["_id"]},
            {"$set": {
                "chat_widget_settings": settings.dict()
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to save chat widget settings")
            
        return {
            "status": "success",
            "message": "Chat widget settings saved successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings")
async def get_chat_widget_settings(
    organization=Depends(get_organization_from_api_key)
):
    try:
        # Get organization from MongoDB
        from services.database import db
        org = db.organizations.find_one({"_id": organization["_id"]})
        
        if not org or "chat_widget_settings" not in org:
            return {
                "status": "success",
                "settings": {
                    "name": "Bay AI",
                    "selectedColor": "black",
                    "leadCapture": True,
                    "botBehavior": "2",
                    "avatarUrl": None
                }
            }
            
        return {
            "status": "success",
            "settings": org["chat_widget_settings"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
