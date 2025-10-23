from datetime import datetime
import uuid
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from pymongo.collection import Collection
from services.database import db
from bson import ObjectId
import logging

# Get logger instead of configuring it
logger = logging.getLogger(__name__)

# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Get users collection
users: Collection = db.users

# Initialize indexes
users.create_index("email", unique=True)
users.create_index("google_id", sparse=True)

def serialize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize user document for JSON response"""
    try:
        if user:
            # Convert ObjectId to string
            if "_id" in user:
                user["_id"] = str(user["_id"])
            # Remove sensitive data
            if "hashed_password" in user:
                del user["hashed_password"]
        return user
    except Exception as e:
        logger.error(f"Error serializing user: {str(e)}")
        return user

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    try:
        hashed = pwd_context.hash(password)
        logger.debug("Password hashed successfully")
        return hashed
    except Exception as e:
        logger.error(f"Error hashing password: {str(e)}")
        raise

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        logger.debug("Attempting to verify password")
        if not plain_password or not hashed_password:
            logger.error("Missing password or hash for verification")
            return False
        result = pwd_context.verify(plain_password, hashed_password)
        logger.debug(f"Password verification result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False

def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new user"""
    try:
        logger.debug(f"Creating new user with email: {user_data.get('email')}")
        
        # Generate user ID
        user_id = str(uuid.uuid4())
        
        # Prepare user document
        user_doc = {
            "id": user_id,
            "email": user_data["email"],
            "organization_name": user_data["name"],  # Changed from "name" to "organization_name"
            "website": user_data.get("website"),
            "company_organization_type": user_data.get("company_organization_type"),
            "has_paid_subscription": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Add password hash if it's a manual registration
        if "password" in user_data:
            logger.debug("Hashing password for new user")
            user_doc["hashed_password"] = get_password_hash(user_data["password"])
        
        # Add Google ID if it's a Google sign-in
        if "google_id" in user_data:
            user_doc["google_id"] = user_data["google_id"]
        
        # Insert into database
        logger.debug("Inserting new user into database")
        result = users.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        
        logger.info(f"Successfully created new user with ID: {user_id}")
        return serialize_user(user_doc)
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    try:
        logger.debug(f"Looking up user by email: {email}")
        user = users.find_one({"email": email})
        if user:
            logger.debug("User found in database")
            # Convert ObjectId and datetime to string before returning
            if "_id" in user:
                user["_id"] = str(user["_id"])
            for key, value in user.items():
                if isinstance(value, datetime):
                    user[key] = value.isoformat()
            return user
        else:
            logger.debug("No user found with this email")
            return None
    except Exception as e:
        logger.error(f"Error getting user by email: {str(e)}")
        return None

def get_user_by_google_id(google_id: str) -> Optional[Dict[str, Any]]:
    """Get user by Google ID"""
    try:
        logger.debug(f"Looking up user by Google ID: {google_id}")
        user = users.find_one({"google_id": google_id})
        if user:
            logger.debug("User found in database")
            return serialize_user(user)
        else:
            logger.debug("No user found with this Google ID")
            return None
    except Exception as e:
        logger.error(f"Error getting user by Google ID: {str(e)}")
        return None

def update_user(user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update user data"""
    try:
        logger.debug(f"Updating user with ID: {user_id}")
        # Always update the updated_at timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update the user
        users.update_one(
            {"id": user_id},
            {"$set": update_data}
        )
        
        # Get and return the updated user
        user = users.find_one({"id": user_id})
        if user:
            logger.debug("User successfully updated")
            return serialize_user(user)
        else:
            logger.warning("User not found after update")
            return None
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return None

def create_admin_user(email: str, password: str, name: str) -> Dict[str, Any]:
    """Create a new admin user"""
    try:
        logger.debug(f"Creating new admin user with email: {email}")
        
        # Check if admin already exists
        existing_admin = users.find_one({"email": email})
        if existing_admin:
            logger.info(f"Admin user already exists: {email}")
            return serialize_user(existing_admin)
        
        # Generate user ID
        user_id = str(uuid.uuid4())
        
        # Prepare admin user document
        admin_doc = {
            "id": user_id,
            "email": email,
            "organization_name": name,  # Changed from "name" to "organization_name"
            "role": "admin",
            "is_admin": True,
            "has_paid_subscription": True,  # Admins have full access
            "hashed_password": get_password_hash(password),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert into database
        logger.debug("Inserting new admin user into database")
        result = users.insert_one(admin_doc)
        admin_doc["_id"] = result.inserted_id
        
        logger.info(f"Successfully created new admin user with ID: {user_id}")
        return serialize_user(admin_doc)
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        raise

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    try:
        logger.debug(f"Looking up user by ID: {user_id}")
        user = users.find_one({"id": user_id})
        if user:
            logger.debug("User found in database")
            return serialize_user(user)
        else:
            logger.debug("No user found with this ID")
            return None
    except Exception as e:
        logger.error(f"Error getting user by ID: {str(e)}")
        return None

def is_admin_user(email: str) -> bool:
    """Check if user is an admin"""
    try:
        user = users.find_one({"email": email})
        return user and user.get("is_admin", False) and user.get("role") == "admin"
    except Exception as e:
        logger.error(f"Error checking admin status: {str(e)}")
        return False

def get_current_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Get current user by ID"""
    try:
        logger.debug(f"Getting current user by ID: {user_id}")
        user = users.find_one({"id": user_id})
        if user:
            logger.debug("Current user found in database")
            return serialize_user(user)
        else:
            logger.debug("No current user found with this ID")
            return None
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None

def seed_default_admin():
    """Seed default admin user if it doesn't exist"""
    try:
        default_admin_email = "admin@bayshoreai.com"
        default_admin_password = "admin123"  # Change this in production
        default_admin_name = "System Administrator"
        
        existing_admin = users.find_one({"email": default_admin_email})
        if not existing_admin:
            logger.info("Creating default admin user...")
            create_admin_user(default_admin_email, default_admin_password, default_admin_name)
            logger.info(f"Default admin user created: {default_admin_email}")
        else:
            logger.info("Default admin user already exists")
    except Exception as e:
        logger.error(f"Error seeding default admin: {str(e)}") 