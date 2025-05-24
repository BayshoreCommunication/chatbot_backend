from datetime import datetime
import uuid
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from pymongo.collection import Collection
from services.database import db
from bson import ObjectId

# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Get users collection
users: Collection = db.users

# Initialize indexes
users.create_index("email", unique=True)
users.create_index("google_id", sparse=True)

def serialize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize user document for JSON response"""
    if user:
        # Convert ObjectId to string
        if "_id" in user:
            user["_id"] = str(user["_id"])
        # Remove sensitive data
        if "hashed_password" in user:
            del user["hashed_password"]
    return user

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new user"""
    # Generate user ID
    user_id = str(uuid.uuid4())
    
    # Prepare user document
    user_doc = {
        "id": user_id,
        "email": user_data["email"],
        "name": user_data["name"],
        "has_paid_subscription": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Add password hash if it's a manual registration
    if "password" in user_data:
        user_doc["hashed_password"] = get_password_hash(user_data["password"])
    
    # Add Google ID if it's a Google sign-in
    if "google_id" in user_data:
        user_doc["google_id"] = user_data["google_id"]
    
    # Insert into database
    result = users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    
    return serialize_user(user_doc)

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    user = users.find_one({"email": email})
    return serialize_user(user) if user else None

def get_user_by_google_id(google_id: str) -> Optional[Dict[str, Any]]:
    """Get user by Google ID"""
    user = users.find_one({"google_id": google_id})
    return serialize_user(user) if user else None

def update_user(user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update user data"""
    # Always update the updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update the user
    users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    # Get and return the updated user
    user = users.find_one({"id": user_id})
    return serialize_user(user) if user else None 