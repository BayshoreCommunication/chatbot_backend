from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Optional, Dict, Any
from services.database import get_organization_by_api_key, get_database, get_user_profile
from models.conversation import Conversation
from bson import ObjectId
from datetime import datetime

router = APIRouter()

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

@router.get("/conversations")
async def get_conversations(organization: dict = Depends(get_organization_from_api_key)):
    """
    Get all conversations for the organization grouped by session with user names
    """
    print("=== Starting get_conversations ===")
    print(f"Organization: {organization}")
    
    if not organization:
        print("No organization found")
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    try:
        print(f"Organization ID: {organization.get('_id')}")
        print(f"Organization ID type: {type(organization.get('_id'))}")
        
        # Get database instance
        db = get_database()
        print(f"Database instance: {db}")
        
        # Get organization ID and handle both ObjectId and string formats
        org_id = organization.get("_id")
        if isinstance(org_id, ObjectId):
            org_id_str = str(org_id)
        else:
            org_id_str = org_id
        
        print(f"Looking for conversations with org_id: {org_id_str}")
        
        # Try to find conversations with both ObjectId and string formats
        conversations = list(db.conversations.find(
            {"organization_id": org_id_str}
        ).sort("created_at", -1))
        
        # If no conversations found with string format, try ObjectId format
        if not conversations and isinstance(org_id, ObjectId):
            print(f"No conversations found with string format, trying ObjectId format")
            conversations = list(db.conversations.find(
                {"organization_id": org_id}
            ).sort("created_at", -1))
        
        print(f"Found {len(conversations)} conversations")
        
        # Group conversations by session_id
        grouped_conversations = {}
        
        for conv in conversations:
            session_id = conv.get("session_id")
            if not session_id:
                continue
                
            if session_id not in grouped_conversations:
                # Get user profile for this session
                user_profile = get_user_profile(organization.get("_id"), session_id)
                user_name = None
                user_email = None
                
                if user_profile and "profile_data" in user_profile:
                    profile_data = user_profile["profile_data"]
                    user_name = profile_data.get("name")
                    user_email = profile_data.get("email")
                
                # Initialize group with conversation data
                grouped_conversations[session_id] = {
                    "session_id": session_id,
                    "visitor_id": conv.get("visitor_id"),
                    "user_name": user_name or f"Visitor {session_id[:8]}",
                    "user_email": user_email,
                    "last_message": conv.get("content", ""),
                    "last_message_role": conv.get("role", ""),
                    "last_message_time": conv.get("created_at"),
                    "message_count": 1,
                    "created_at": conv.get("created_at"),
                    "organization_id": conv.get("organization_id"),
                    "id": conv.get("id"),
                    "role": conv.get("role"),
                    "content": conv.get("content"),
                    "metadata": conv.get("metadata", {})
                }
            else:
                # Update message count and potentially last message if newer
                grouped_conversations[session_id]["message_count"] += 1
                
                # Update last message if this conversation is newer
                current_time = conv.get("created_at")
                last_time = grouped_conversations[session_id]["last_message_time"]
                
                if current_time and (not last_time or current_time > last_time):
                    grouped_conversations[session_id]["last_message"] = conv.get("content", "")
                    grouped_conversations[session_id]["last_message_role"] = conv.get("role", "")
                    grouped_conversations[session_id]["last_message_time"] = current_time
        
        # Convert to list and sort by last message time
        result = list(grouped_conversations.values())
        result.sort(key=lambda x: x.get("last_message_time") or datetime.min, reverse=True)
        
        # Convert ObjectId and datetime to string for JSON serialization
        for conv in result:
            if "_id" in conv:
                conv["_id"] = str(conv["_id"])
            if "created_at" in conv and conv["created_at"]:
                conv["created_at"] = conv["created_at"].isoformat() if hasattr(conv["created_at"], 'isoformat') else str(conv["created_at"])
            if "last_message_time" in conv and conv["last_message_time"]:
                conv["last_message_time"] = conv["last_message_time"].isoformat() if hasattr(conv["last_message_time"], 'isoformat') else str(conv["last_message_time"])
        
        print(f"Returning {len(result)} grouped conversations")
        return result
        
    except Exception as e:
        print(f"Error in get_conversations: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    organization: dict = Depends(get_organization_from_api_key)
):
    """
    Get a specific conversation by ID
    """
    print("=== Starting get_conversation ===")
    print(f"Conversation ID: {conversation_id}")
    print(f"Organization: {organization}")
    
    if not organization:
        print("No organization found")
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    try:
        print(f"Organization ID: {organization.get('_id')}")
        
        # Get database instance
        db = get_database()
        print(f"Database instance: {db}")
        
        # Get organization ID and handle both ObjectId and string formats
        org_id = organization.get("_id")
        if isinstance(org_id, ObjectId):
            org_id_str = str(org_id)
        else:
            org_id_str = org_id
        
        # Try to find by UUID id field first (most common case)
        conversation = db.conversations.find_one({
            "id": conversation_id,
            "organization_id": org_id_str
        })
        
        # If not found by UUID, try ObjectId _id field
        if not conversation:
            try:
                conversation = db.conversations.find_one({
                    "_id": ObjectId(conversation_id),
                    "organization_id": org_id_str
                })
            except Exception:
                # Invalid ObjectId format, continue with UUID search
                pass
        
        # If still not found with string format, try ObjectId format for org_id
        if not conversation and isinstance(org_id, ObjectId):
            conversation = db.conversations.find_one({
                "id": conversation_id,
                "organization_id": org_id
            })
            
            if not conversation:
                try:
                    conversation = db.conversations.find_one({
                        "_id": ObjectId(conversation_id),
                        "organization_id": org_id
                    })
                except Exception:
                    # Invalid ObjectId format, continue
                    pass
        
        print(f"Found conversation: {conversation}")
        
        if not conversation:
            print("Conversation not found")
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        if "_id" in conversation:
            conversation["_id"] = str(conversation["_id"])
            print(f"Converted _id: {conversation['_id']}")
                
        print("=== Returning conversation ===")
        return conversation
    except Exception as e:
        print(f"Error in get_conversation: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# New endpoint to get conversations by session_id
@router.get("/conversations/session/{session_id}")
async def get_conversations_by_session(
    session_id: str,
    organization: dict = Depends(get_organization_from_api_key)
):
    """
    Get all conversations for a specific session
    """
    print(f"=== Getting conversations for session: {session_id} ===")
    
    try:
        db = get_database()
        
        # Get organization ID and handle both ObjectId and string formats
        org_id = organization.get("_id")
        if isinstance(org_id, ObjectId):
            org_id_str = str(org_id)
        else:
            org_id_str = org_id
        
        # Get all conversations for this session
        conversations = list(db.conversations.find({
            "organization_id": org_id_str,
            "session_id": session_id
        }).sort("created_at", 1))  # Sort chronologically
        
        # If no conversations found with string format, try ObjectId format
        if not conversations and isinstance(org_id, ObjectId):
            conversations = list(db.conversations.find({
                "organization_id": org_id,
                "session_id": session_id
            }).sort("created_at", 1))  # Sort chronologically
        
        # Get user profile for this session
        user_profile = get_user_profile(organization.get("_id"), session_id)
        user_name = None
        user_email = None
        
        if user_profile and "profile_data" in user_profile:
            profile_data = user_profile["profile_data"]
            user_name = profile_data.get("name")
            user_email = profile_data.get("email")
        
        # Convert ObjectId to string for JSON serialization
        for conv in conversations:
            if "_id" in conv:
                conv["_id"] = str(conv["_id"])
            if "created_at" in conv and conv["created_at"]:
                conv["created_at"] = conv["created_at"].isoformat() if hasattr(conv["created_at"], 'isoformat') else str(conv["created_at"])
        
        return {
            "session_id": session_id,
            "user_name": user_name,
            "user_email": user_email,
            "conversations": conversations,
            "message_count": len(conversations)
        }
        
    except Exception as e:
        print(f"Error getting conversations by session: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e)) 