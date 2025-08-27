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
        
        # Get organization ID - use the 'id' field (UUID string) that conversations are saved with
        org_id = organization.get("id")  # This is the UUID string that conversations use
        org_id_str = org_id
        
        print(f"Looking for conversations with org_id: {org_id_str}")
        print(f"Organization object: {organization}")
        
        # Find conversations using the correct organization ID
        conversations = list(db.conversations.find(
            {"organization_id": org_id_str}
        ).sort("created_at", -1))
        print(f"Found {len(conversations)} conversations with correct org_id")
        
        # Debug: Show all conversations in database for this org
        print(f"=== DEBUG: All conversations in database ===")
        all_convs = list(db.conversations.find({}).sort("created_at", -1))
        print(f"Total conversations in database: {len(all_convs)}")
        for i, conv in enumerate(all_convs[:10]):  # Show first 10
            print(f"Conversation {i+1}: org_id={conv.get('organization_id')}, session_id={conv.get('session_id')}, role={conv.get('role')}")
        
        print(f"Final conversations found: {len(conversations)}")
        
        # Group conversations by session_id
        grouped_conversations = {}
        
        for conv in conversations:
            session_id = conv.get("session_id")
            if not session_id:
                print(f"[DEBUG] Skipping conversation without session_id: {conv.get('id', 'unknown')}")
                continue
                
            print(f"[DEBUG] Processing conversation for session: {session_id}")
            print(f"[DEBUG] Conversation details: role={conv.get('role')}, content={conv.get('content', '')[:50]}...")
                
            if session_id not in grouped_conversations:
                # Get user profile for this session
                user_profile = get_user_profile(org_id_str, session_id)
                user_name = None
                user_email = None
                
                if user_profile and "profile_data" in user_profile:
                    profile_data = user_profile["profile_data"]
                    user_name = profile_data.get("name")
                    user_email = profile_data.get("email")
                
                print(f"[DEBUG] User profile for session {session_id}: name={user_name}, email={user_email}")
                
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
                print(f"[DEBUG] Created new conversation group for session {session_id}")
            else:
                # Update message count and potentially last message if newer
                grouped_conversations[session_id]["message_count"] += 1
                print(f"[DEBUG] Updated message count for session {session_id}: {grouped_conversations[session_id]['message_count']}")
                
                # Update last message if this conversation is newer
                current_time = conv.get("created_at")
                last_time = grouped_conversations[session_id]["last_message_time"]
                
                if current_time and (not last_time or current_time > last_time):
                    grouped_conversations[session_id]["last_message"] = conv.get("content", "")
                    grouped_conversations[session_id]["last_message_role"] = conv.get("role", "")
                    grouped_conversations[session_id]["last_message_time"] = current_time
                    print(f"[DEBUG] Updated last message for session {session_id}")
        
        # Convert to list and sort by last message time
        result = list(grouped_conversations.values())
        result.sort(key=lambda x: x.get("last_message_time") or datetime.min, reverse=True)
        
        print(f"[DEBUG] Final result: {len(result)} grouped conversations")
        for i, conv in enumerate(result):
            print(f"[DEBUG] Result {i+1}: session={conv['session_id']}, user={conv['user_name']}, messages={conv['message_count']}")
        
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
    Get a specific conversation by ID saved in the database
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
    # Clean the session_id by removing any whitespace or newlines
    session_id = session_id.strip()
    """
    Get all conversations for a specific session sahak islalm
    """
    print(f"=== Getting conversations for session: {session_id} ===")
    
    try:
        db = get_database()
        
        # Get organization ID - use the 'id' field (UUID string) that conversations are saved with
        org_id = organization.get("id")  # This is the UUID string that conversations use
        org_id_str = org_id
        print(f"[DEBUG] Using organization ID: {org_id_str}")
        print(f"[DEBUG] Organization object: {organization}")
        
        # Get all conversations for this session
        print(f"[DEBUG] Querying conversations for org_id: {org_id_str}, session_id: '{session_id}'")
        print(f"[DEBUG] Session ID length: {len(session_id)}")
        print(f"[DEBUG] Session ID bytes: {session_id.encode()}")
        
        # First, let's check what conversations exist in the database
        all_conversations = list(db.conversations.find({}).sort("created_at", -1))
        print(f"[DEBUG] Total conversations in database: {len(all_conversations)}")
        
        # Check for any conversations with similar session_ids
        for conv in all_conversations[:10]:  # Check first 10
            conv_session_id = conv.get("session_id", "")
            conv_org_id = conv.get("organization_id", "")
            if conv_session_id:
                print(f"[DEBUG] Found conversation with session_id: '{conv_session_id}' (length: {len(conv_session_id)})")
                print(f"[DEBUG] Conversation org_id: '{conv_org_id}' vs query org_id: '{org_id_str}'")
                if session_id in conv_session_id or conv_session_id in session_id:
                    print(f"[DEBUG] Potential match found!")
        
        conversations = list(db.conversations.find({
            "organization_id": org_id_str,
            "session_id": session_id
        }).sort("created_at", 1))  # Sort chronologically
        
        print(f"[DEBUG] Found {len(conversations)} conversations with correct org_id")
        
        # If still no conversations, try a partial match on session_id
        if not conversations:
            print(f"[DEBUG] Trying partial match on session_id")
            # Try to find conversations where session_id contains our cleaned session_id
            conversations = list(db.conversations.find({
                "organization_id": org_id_str,
                "session_id": {"$regex": session_id.replace("\\n", "").replace("\n", "")}
            }).sort("created_at", 1))
            print(f"[DEBUG] Found {len(conversations)} conversations with partial match")
        
        # Get user profile for this session
        user_profile = get_user_profile(org_id_str, session_id)
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
        
        # Debug: Print the response structure
        response_data = {
            "session_id": session_id,
            "user_name": user_name,
            "user_email": user_email,
            "conversations": conversations,
            "message_count": len(conversations)
        }
        
        print(f"[DEBUG] API Response for session {session_id}:")
        print(f"[DEBUG] Conversations count: {len(conversations)}")
        print(f"[DEBUG] First conversation structure: {conversations[0] if conversations else 'No conversations'}")
        
        return response_data
        
    except Exception as e:
        print(f"Error getting conversations by session: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/debug/conversations")
async def debug_conversations(organization: dict = Depends(get_organization_from_api_key)):
    """
    Debug endpoint to check all conversations in the database
    """
    print("=== Debug conversations endpoint ===")
    
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    try:
        db = get_database()
        
        # Get organization ID and handle both ObjectId and string formats
        org_id = organization.get("_id")
        if isinstance(org_id, ObjectId):
            org_id_str = str(org_id)
        else:
            org_id_str = org_id
        
        print(f"Looking for conversations with org_id: {org_id_str}")
        
        # Get all conversations for this organization
        all_conversations = list(db.conversations.find(
            {"organization_id": org_id_str}
        ).sort("created_at", -1))
        
        print(f"Found {len(all_conversations)} total conversations")
        
        # Group by session_id for debugging
        session_groups = {}
        for conv in all_conversations:
            session_id = conv.get("session_id")
            if session_id:
                if session_id not in session_groups:
                    session_groups[session_id] = []
                session_groups[session_id].append({
                    "id": conv.get("id"),
                    "role": conv.get("role"),
                    "content": conv.get("content", "")[:50] + "...",
                    "created_at": conv.get("created_at"),
                    "visitor_id": conv.get("visitor_id")
                })
        
        debug_data = {
            "organization_id": org_id_str,
            "total_conversations": len(all_conversations),
            "unique_sessions": len(session_groups),
            "session_groups": session_groups
        }
        
        print(f"Debug data: {debug_data}")
        return debug_data
        
    except Exception as e:
        print(f"Error in debug_conversations: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e)) 