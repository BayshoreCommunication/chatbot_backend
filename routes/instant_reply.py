from fastapi import APIRouter, HTTPException, Header, Body
from services.database import get_organization_by_api_key, db
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

router = APIRouter()

class InstantReplyMessage(BaseModel):
    id: Optional[str] = None
    message: str
    order: int

class InstantReplyUpdate(BaseModel):
    messages: List[InstantReplyMessage]
    isActive: bool

@router.post("/")
async def set_instant_reply(
    x_api_key: str = Header(...),
    data: InstantReplyUpdate = Body(...)
):
    try:
        org = get_organization_by_api_key(x_api_key)
        if not org:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Check if an instant reply already exists for this org
        existing_reply = db.instant_reply.find_one({
            "organization_id": str(org["_id"]), 
            "type": "instant_reply"
        })
        
        current_time = datetime.utcnow()
        
        # Prepare messages for storage
        messages_data = []
        for idx, msg in enumerate(data.messages):
            messages_data.append({
                "message": msg.message,
                "order": msg.order if msg.order is not None else idx + 1
            })
        
        if existing_reply:
            # Update existing reply
            db.instant_reply.update_one(
                {"_id": existing_reply["_id"]},
                {
                    "$set": {
                        "messages": messages_data,
                        "isActive": data.isActive,
                        "updated_at": current_time
                    }
                }
            )
            return {"status": "success", "message": "Instant reply updated successfully"}
        
        # Create new instant reply
        new_reply = {
            "organization_id": str(org["_id"]),
            "type": "instant_reply",
            "messages": messages_data,
            "isActive": data.isActive,
            "created_at": current_time,
            "updated_at": current_time
        }
        db.instant_reply.insert_one(new_reply)
        
        return {"status": "success", "message": "Instant reply set successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def get_instant_reply(x_api_key: str = Header(...)):
    try:
        org = get_organization_by_api_key(x_api_key)
        if not org:
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        reply = db.instant_reply.find_one({
            "organization_id": str(org["_id"]),
            "type": "instant_reply"
        })
        
        if not reply:
            return {
                "status": "success", 
                "data": {
                    "messages": [],
                    "isActive": False
                }
            }
        
        # Handle backward compatibility for existing single message format
        if "message" in reply and "messages" not in reply:
            # Convert old single message format to new multiple messages format
            messages = [{"message": reply["message"], "order": 1}] if reply["message"] else []
        else:
            # Use new messages format
            messages = reply.get("messages", [])
            
        return {
            "status": "success",
            "data": {
                "messages": messages,
                "isActive": reply.get("isActive", False)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/")
async def delete_instant_reply(x_api_key: str = Header(...)):
    try:
        org = get_organization_by_api_key(x_api_key)
        if not org:
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        # Find and delete the instant reply document
        result = db.instant_reply.delete_one({
            "organization_id": str(org["_id"]),
            "type": "instant_reply"
        })
            
        return {"status": "success", "message": "Instant reply deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 


