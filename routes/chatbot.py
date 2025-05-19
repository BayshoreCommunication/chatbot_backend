from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, Header
from services.langchain.engine import ask_bot, add_document, escalate_to_human
from services.language_detect import detect_language
from services.database import get_organization_by_api_key, create_or_update_visitor, add_conversation_message, get_visitor
from typing import Optional, Dict, Any
import json
import os
from pydantic import BaseModel

router = APIRouter()

# User session storage (in a real application, use Redis for temporary storage)
user_sessions = {}

class ChatRequest(BaseModel):
    question: str
    session_id: str
    mode: Optional[str] = "faq"
    user_data: Optional[dict] = None
    available_slots: Optional[str] = None

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
    
    # Get or create session (in-memory for now)
    session_key = f"{org_id}:{request.session_id}"
    session = user_sessions.get(session_key, {
        "conversation_history": [],
        "user_data": request.user_data or {},
        "current_mode": request.mode
    })
    
    # Update user session
    user_sessions[session_key] = session
    
    # Print debugging info about the question
    print(f"Question: '{request.question}'")
    if "unique identifier" in request.question.lower() or "test-doc" in request.question.lower():
        print(f"UNIQUE IDENTIFIER QUESTION DETECTED!")
    
    # Get response based on mode
    response = ask_bot(
        query=request.question,
        mode=session["current_mode"],
        user_data=session["user_data"],
        available_slots=request.available_slots,
        session_id=request.session_id,
        api_key=org_api_key
    )
    
    # Check if we received an error response
    if "status" in response and response["status"] == "error":
        # Just return the error response directly
        return response
    
    # Add to conversation history
    session["conversation_history"].append({
        "user": request.question,
        "bot": response["answer"]
    })
    
    # Store in MongoDB
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
    
    # Update session user data if provided in response
    if "user_data" in response:
        session["user_data"].update(response["user_data"])
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
    organization=Depends(get_organization_from_api_key)
):
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
