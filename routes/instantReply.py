from fastapi import APIRouter, HTTPException, Header, Body
from services.database import get_organization_by_api_key, db
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

class InstantReplyUpdate(BaseModel):
    message: str
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
            "organization_id": org["id"], 
            "type": "instant_reply"
        })
        
        current_time = datetime.utcnow()
        
        if existing_reply:
            # Update existing reply
            db.instant_reply.update_one(
                {"_id": existing_reply["_id"]},
                {
                    "$set": {
                        "message": data.message,
                        "isActive": data.isActive,
                        "updated_at": current_time
                    }
                }
            )
            return {"status": "success", "message": "Instant reply updated successfully"}
        
        # Create new instant reply
        new_reply = {
            "organization_id": org["id"],
            "type": "instant_reply",
            "message": data.message,
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
            "organization_id": org["id"],
            "type": "instant_reply"
        })
        
        if not reply:
            return {
                "status": "success", 
                "data": {
                    "message": None,
                    "isActive": False
                }
            }
            
        return {
            "status": "success",
            "data": {
                "message": reply["message"],
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
            
        # Find and update the active instant reply
        result = db.train_ai.update_one(
            {
                "organization_id": org["id"],
                "type": "instant_reply",
                "is_active": True
            },
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
            
        return {"status": "success", "message": "Instant reply deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 