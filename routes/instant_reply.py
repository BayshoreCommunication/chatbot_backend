from fastapi import APIRouter, HTTPException, Header
from services.database import get_organization_by_api_key, db

router = APIRouter()

@router.get("/")
async def get_instant_reply(x_api_key: str = Header(...)):
    """Get instant reply messages for an organization"""
    try:
        # Get organization from API key
        org = get_organization_by_api_key(x_api_key)
        if not org:
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        # Get instant reply settings
        reply = db.instant_reply.find_one({
            "organization_id": org["id"],
            "type": "instant_reply"
        })
        
        if not reply:
            return {
                "status": "success", 
                "data": {
                    "message": "",
                    "isActive": False
                }
            }
        
        # Return messages and active status
        messages = reply.get("messages", [])
        return {
            "status": "success",
            "data": {
                "message": messages[0] if messages else "",
                "isActive": reply.get("isActive", False)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 