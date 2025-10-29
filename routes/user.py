from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from datetime import datetime
from services.database import get_database
from services.auth import get_user_by_email
from bson import ObjectId
import bcrypt
import jwt
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

async def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract and verify JWT token to get current user"""
    print(f"Authorization header: {authorization}")  # Debug logging
    
    if not authorization:
        print("No authorization header provided")
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        # Extract token from "Bearer <token>" format
        parts = authorization.split()
        if len(parts) != 2:
            print(f"Invalid authorization format: {authorization}")
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        scheme, token = parts
        if scheme.lower() != "bearer":
            print(f"Invalid scheme: {scheme}")
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        print(f"Token: {token[:20]}...")  # Debug logging (first 20 chars)
        
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        
        print(f"Decoded payload: {payload}")  # Debug logging
        
        if not email:
            print("No email in token payload")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user from database
        user = get_user_by_email(email)
        if not user:
            print(f"User not found for email: {email}")
            raise HTTPException(status_code=401, detail="User not found")
        
        print(f"User found: {user.get('email', 'No email')}")  # Debug logging
        
        # Convert ObjectId to string for JSON serialization
        if "_id" in user:
            user["_id"] = str(user["_id"])
        
        return user
        
    except jwt.ExpiredSignatureError:
        print("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError as e:
        print(f"JWT error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Authentication error: {str(e)}")  # Debug logging
        raise HTTPException(status_code=401, detail="Authentication failed")

class UserProfileUpdate(BaseModel):
    organization_name: str | None = None
    website: str | None = None
    company_organization_type: str | None = None
    email: str | None = None
    country: str | None = None
    language: str | None = None
    timeZone: str | None = None

class PasswordChange(BaseModel):
    oldPassword: str
    newPassword: str

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

@router.put("/change-password")
async def change_password(password_data: PasswordChange, current_user=Depends(get_current_user)):
    try:
        db = get_database()
        users_collection = db["users"]
        
        print(f"Current user data: {current_user}")  # Debug logging
        
        # Get the stored password hash
        stored_password = current_user.get('hashed_password')
        if not stored_password:
            print("No hashed_password field found in user document")
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # Verify old password
        if not bcrypt.checkpw(password_data.oldPassword.encode('utf-8'), stored_password.encode('utf-8')):
            print("Password verification failed")
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # Hash new password
        salt = bcrypt.gensalt()
        hashed_new_password = bcrypt.hashpw(password_data.newPassword.encode('utf-8'), salt)
        
        # Update password
        result = users_collection.update_one(
            {"_id": ObjectId(current_user["_id"])},
            {
                "$set": {
                    "hashed_password": hashed_new_password.decode('utf-8'),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"Update result: {result.modified_count} documents modified")
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Password update failed")
        
        return {
            "status": "success",
            "message": "Password updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Password change error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 