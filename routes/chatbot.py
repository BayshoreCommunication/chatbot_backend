from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, Header, Body
from services.langchain.engine import ask_bot, add_document, escalate_to_human
from services.language_detect import detect_language
from services.database import get_organization_by_api_key, create_or_update_visitor, add_conversation_message, get_visitor, get_conversation_history, save_user_profile, get_user_profile, db
from typing import Optional, Dict, Any
import json
import os
from pydantic import BaseModel
from datetime import datetime
import pymongo
from services.faq_matcher import find_matching_faq, get_suggested_faqs
from services.langchain.user_management import handle_name_collection, handle_email_collection
import re
import openai

router = APIRouter()

# Initialize instant replies collection and indexes
instant_replies = db.instant_reply
instant_replies.create_index("org_id")
instant_replies.create_index([("org_id", pymongo.ASCENDING), ("is_active", pymongo.ASCENDING)])

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
    """Process a chat message and return a response"""
    org_id = organization["id"]
    org_api_key = organization.get("api_key")
    namespace = organization.get("pinecone_namespace", "")

    try:
        print(f"[DEBUG] Processing message: {request.question}")
        print(f"[DEBUG] Session ID: {request.session_id}")

        # Check if this is the first message BEFORE creating any records
        is_first = is_first_message(org_id, request.session_id)
        print(f"[DEBUG] Is first message: {is_first}")

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

        if is_first:
            print("[DEBUG] Checking for instant reply")
            instant_reply = instant_replies.find_one({
                "organization_id": org_id,
                "type": "instant_reply",
                "isActive": True
            })
            print(f"[DEBUG] Found instant reply: {instant_reply}")
            
            if instant_reply:
                print("[DEBUG] Processing instant reply")
                # Store the user's first message
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="user",
                    content=request.question,
                    metadata={"mode": "faq"}
                )
                request.user_data["conversation_history"].append({
                    "role": "user",
                    "content": request.question
                })

                # Store the instant reply
                add_conversation_message(
                    organization_id=org_id,
                    visitor_id=visitor["id"],
                    session_id=request.session_id,
                    role="assistant",
                    content=instant_reply["message"],
                    metadata={"mode": "faq", "type": "instant_reply"}
                )
                request.user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": instant_reply["message"]
                })

                print("[DEBUG] Returning instant reply")
                return {
                    "answer": instant_reply["message"],
                    "mode": "faq",
                    "language": "en",
                    "user_data": request.user_data
                }
        else:
            # Add current user message to history if not first message
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

        print("[DEBUG] Checking user information collection")
        # Check if we need to collect user information
        if "name" not in request.user_data or not request.user_data["name"]:
            print("[DEBUG] Name not found, processing name collection")
            # Use OpenAI to validate and extract name
            name_extraction_prompt = f"""
            Extract the person's name from the following text or detect if they are refusing to share their name.
            
            Text: "{request.question}"
            
            Rules:
            1. If you find a name, return only the name
            2. If the person is refusing to share their name (using words like "skip", "no", "don't want to", "won't", "refuse", etc.), return "REFUSED"
            3. If no clear name or refusal is found, return "NO_NAME"
            
            Examples:
            "My name is John" -> John
            "I don't want to share my name" -> REFUSED
            "skip this" -> REFUSED
            "hello there" -> NO_NAME
            """
            
            try:
                name_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": name_extraction_prompt}],
                    max_tokens=20,
                    temperature=0.1
                )
                
                extracted_name = name_response.choices[0].message.content.strip()
                print(f"[DEBUG] Extracted name response: {extracted_name}")
                
                if extracted_name == "REFUSED":
                    print("[DEBUG] User refused to share name")
                    request.user_data["name"] = "Anonymous User"
                    save_user_profile(org_id, request.session_id, request.user_data)
                    
                    # Ask for email politely
                    email_prompt = "That's perfectly fine! Would you mind sharing your email address so we can better assist you? You can also skip this if you prefer."
                    
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
                    
                    return {
                        "answer": email_prompt,
                        "mode": "faq",
                        "language": "en",
                        "user_data": request.user_data
                    }
                elif extracted_name != "NO_NAME":
                    print("[DEBUG] Valid name found")
                    request.user_data["name"] = extracted_name
                    save_user_profile(org_id, request.session_id, request.user_data)
                    
                    # Ask for email
                    email_prompt = f"Nice to meet you, {extracted_name}! Would you mind sharing your email address? You can skip this if you prefer."
                    
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
                    
                    return {
                        "answer": email_prompt,
                        "mode": "faq",
                        "language": "en",
                        "user_data": request.user_data
                    }
                else:
                    print("[DEBUG] No valid name found")
                    name_prompt = "Before proceeding, could you please tell me your name? You can skip this if you prefer not to share."
                    
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
                    
                    return {
                        "answer": name_prompt,
                        "mode": "faq",
                        "language": "en",
                        "user_data": request.user_data
                    }
                    
            except Exception as e:
                print(f"[DEBUG] Error in AI name extraction: {str(e)}")
                return handle_name_collection(request.question, request.user_data, "faq", "en")
                
        elif "email" not in request.user_data or not request.user_data["email"]:
            # Use OpenAI to validate and extract email
            email_extraction_prompt = f"""
            Extract and validate an email address from the following text or detect refusal.
            
            Text: "{request.question}"
            
            Rules:
            1. If you find a valid email (format: username@domain.tld), return only the email
            2. If the person is refusing or wants to skip (using words like "skip", "no", "don't want to", "won't", "refuse", etc.), return "REFUSED"
            3. If no valid email or clear refusal is found, return "INVALID"
            """
            
            try:
                email_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": email_extraction_prompt}],
                    max_tokens=20,
                    temperature=0.1
                )
                
                extracted_email = email_response.choices[0].message.content.strip()
                print(f"[DEBUG] Extracted email response: {extracted_email}")
                
                if "@" in extracted_email and "." in extracted_email:
                    request.user_data["email"] = extracted_email
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
                    
                    return {
                        "answer": welcome,
                        "mode": "faq",
                        "language": "en",
                        "user_data": request.user_data
                    }
                elif extracted_email == "REFUSED":
                    request.user_data["email"] = "anonymous@user.com"
                    save_user_profile(org_id, request.session_id, request.user_data)
                    
                    welcome = f"No problem at all{' ' + request.user_data['name'] if request.user_data.get('name') and request.user_data['name'] != 'Anonymous User' else ''}! How can I assist you today?"
                    
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
                    
                    return {
                        "answer": welcome,
                        "mode": "faq",
                        "language": "en",
                        "user_data": request.user_data
                    }
                else:
                    email_prompt = "Please provide a valid email address or just type 'skip' if you prefer not to share."
                    
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
                    
                    return {
                        "answer": email_prompt,
                        "mode": "faq",
                        "language": "en",
                        "user_data": request.user_data
                    }

            except Exception as e:
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
            # Store the user's message
            add_conversation_message(
                organization_id=org_id,
                visitor_id=visitor["id"],
                session_id=request.session_id,
                role="user",
                content=request.question,
                metadata={"mode": "faq"}
            )

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
            request.user_data["conversation_history"].extend([
                {"role": "user", "content": request.question},
                {"role": "assistant", "content": matching_faq["response"]}
            ])

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

        # If no FAQ match, proceed with normal chatbot flow
        # Prepare context for the bot
        user_context = ""
        if "name" in request.user_data and request.user_data["name"]:
            user_context = f"The user's name is {request.user_data['name']}. "
        if "email" in request.user_data and request.user_data["email"]:
            user_context += f"The user's email is {request.user_data['email']}. "

        # Enhance query with user context if needed
        enhanced_query = request.question
        if user_context and request.user_data.get("returning_user"):
            enhanced_query = f"{user_context}The user, who you already know, asks: {request.question}"

        response = ask_bot(
            query=enhanced_query,
            mode=request.mode,
            user_data=request.user_data,
            available_slots=request.available_slots,
            session_id=request.session_id,
            api_key=org_api_key
        )

        # Store messages in MongoDB
        add_conversation_message(
            organization_id=org_id,
            visitor_id=visitor["id"],
            session_id=request.session_id,
            role="user",
            content=request.question,
            metadata={"mode": request.mode}
        )

        add_conversation_message(
            organization_id=org_id,
            visitor_id=visitor["id"],
            session_id=request.session_id,
            role="assistant",
            content=response["answer"],
            metadata={"mode": request.mode}
        )

        # Update conversation history
        request.user_data["conversation_history"].extend([
            {"role": "user", "content": request.question},
            {"role": "assistant", "content": response["answer"]}
        ])

        # Get suggested FAQs
        suggested_faqs = get_suggested_faqs(org_id)
        response["suggested_faqs"] = suggested_faqs
        response["user_data"] = request.user_data

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
    previous_conversations = get_conversation_history(org_id, session_id)
    
    # Get visitor information
    visitor = get_visitor(org_id, session_id)
    if not visitor:
        raise HTTPException(status_code=404, detail="Session not found")
    
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
    current_mode = "faq"
    if visitor and "metadata" in visitor and "mode" in visitor["metadata"]:
        current_mode = visitor["metadata"]["mode"]
    
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
        "suggested_faqs": suggested_faqs
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
