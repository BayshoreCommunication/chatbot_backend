from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from services.database import get_database
from bson import ObjectId

router = APIRouter()

class UserProfileUpdate(BaseModel):
    fullName: str | None = None
    nickName: str | None = None
    gender: str | None = None
    country: str | None = None
    language: str | None = None
    timeZone: str | None = None
    email: str | None = None

@router.put("/profile/{user_id}")
async def update_user_profile(user_id: str, profile_data: UserProfileUpdate):
    db = get_database()
    users_collection = db["users"]
    
    # Convert string ID to ObjectId if necessary
    try:
        if len(user_id) == 24:  # If it's a hex string
            user_id_query = ObjectId(user_id)
        else:  # If it's a UUID string
            user_id_query = {"id": user_id}
    except:
        user_id_query = {"id": user_id}
    
    # Get existing user
    user = users_collection.find_one(user_id_query if isinstance(user_id_query, dict) else {"_id": user_id_query})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare update data
    update_data = {
        k: v for k, v in profile_data.dict(exclude_unset=True).items() if v is not None
    }
    
    if not update_data:
        return {"message": "No data to update"}
    
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update user profile
    result = users_collection.update_one(
        user_id_query if isinstance(user_id_query, dict) else {"_id": user_id_query},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Profile update failed")
    
    return {"message": "Profile updated successfully"}

@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str):
    db = get_database()
    users_collection = db["users"]
    
    # Convert string ID to ObjectId if necessary
    try:
        if len(user_id) == 24:  # If it's a hex string
            user_id_query = ObjectId(user_id)
        else:  # If it's a UUID string
            user_id_query = {"id": user_id}
    except:
        user_id_query = {"id": user_id}
    
    # Get user
    user = users_collection.find_one(user_id_query if isinstance(user_id_query, dict) else {"_id": user_id_query})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Convert ObjectId to string for JSON serialization
    if "_id" in user:
        user["_id"] = str(user["_id"])
    
    return user 