from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from services.langchain.engine import ask_bot, add_document, escalate_to_human
from services.language_detect import detect_language
from typing import Optional
import json
import os
from pydantic import BaseModel

router = APIRouter()

# User session storage (in a real application, use a database or Redis)
user_sessions = {}

class ChatRequest(BaseModel):
    question: str
    session_id: str
    mode: Optional[str] = "faq"
    user_data: Optional[dict] = None
    available_slots: Optional[str] = None

@router.post("/ask")
async def ask_question(request: ChatRequest):
    # Get or create session
    session = user_sessions.get(request.session_id, {
        "conversation_history": [],
        "user_data": request.user_data or {},
        "current_mode": request.mode
    })
    
    # Update user session
    user_sessions[request.session_id] = session
    
    # Get response based on mode
    response = ask_bot(
        query=request.question,
        mode=session["current_mode"],
        user_data=session["user_data"],
        available_slots=request.available_slots,
        session_id=request.session_id
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
    
    # Update session user data if provided in response
    if "user_data" in response:
        session["user_data"].update(response["user_data"])
    
    # Update session mode if it changed
    if "mode" in response and response["mode"] != session["current_mode"]:
        session["current_mode"] = response["mode"]
    
    return response

@router.post("/change_mode")
async def change_mode(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    new_mode = data.get("mode")
    
    if not session_id or not new_mode:
        raise HTTPException(status_code=400, detail="Session ID and mode are required")
    
    # Get or create session
    session = user_sessions.get(session_id, {
        "conversation_history": [],
        "user_data": {},
        "current_mode": new_mode
    })
    
    # Update mode
    session["current_mode"] = new_mode
    user_sessions[session_id] = session
    
    return {"status": "success", "mode": new_mode}

@router.post("/upload_document")
async def upload_document(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None)
):
    if file:
        # Save uploaded file temporarily
        file_path = f"temp_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Add to vectorstore
        result = add_document(file_path=file_path)
        
        # Clean up temporary file
        os.remove(file_path)
        
        return result
    
    elif url:
        return add_document(url=url)
    
    elif text:
        return add_document(text=text)
    
    else:
        raise HTTPException(status_code=400, detail="No document source provided")

@router.post("/escalate")
async def escalate(request: Request):
    data = await request.json()
    query = data.get("question")
    user_info = data.get("user_info", {})
    
    if not query:
        raise HTTPException(status_code=400, detail="Question is required")
    
    return escalate_to_human(query, user_info)
