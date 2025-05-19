import os
import pymongo
from dotenv import load_dotenv
from models.organization import Organization
from models.visitor import Visitor, ConversationMessage
import uuid
import secrets
from typing import List, Dict, Any, Optional

# Load environment variables
load_dotenv()

# Get MongoDB connection string
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client.saas_chatbot_db

# Collections
organizations = db.organizations
visitors = db.visitors
conversations = db.conversations
api_keys = db.api_keys

# Initialize the database with indexes
def init_db():
    """Initialize database with necessary indexes"""
    # Organization indexes
    organizations.create_index("api_key", unique=True)
    
    # Visitor indexes
    visitors.create_index("organization_id")
    visitors.create_index("session_id")
    visitors.create_index([("organization_id", pymongo.ASCENDING), ("session_id", pymongo.ASCENDING)], unique=True)
    
    # Conversation indexes
    conversations.create_index("organization_id")
    conversations.create_index("visitor_id")
    conversations.create_index("session_id")
    conversations.create_index([("organization_id", pymongo.ASCENDING), ("session_id", pymongo.ASCENDING)])

# Organization methods
def create_organization(name: str, subscription_tier: str = "free") -> Dict[str, Any]:
    """Create a new organization with a unique API key"""
    # Generate unique API key with org_ prefix
    api_key = f"org_sk_{secrets.token_hex(16)}"
    # Generate unique namespace for vector DB
    pinecone_namespace = f"org_{uuid.uuid4().hex}"
    
    org_data = {
        "id": str(uuid.uuid4()),
        "name": name,
        "api_key": api_key,
        "subscription_tier": subscription_tier,
        "subscription_status": "active",
        "pinecone_namespace": pinecone_namespace,
        "settings": {}
    }
    
    # Insert into database
    result = organizations.insert_one(org_data)
    org_data["_id"] = str(result.inserted_id)
    
    return org_data

def get_organization_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Get organization by API key"""
    org = organizations.find_one({"api_key": api_key})
    return org

def update_organization(org_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update organization data"""
    organizations.update_one({"id": org_id}, {"$set": update_data})
    return organizations.find_one({"id": org_id})

# Visitor methods
def create_or_update_visitor(organization_id: str, session_id: str, visitor_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new visitor or update existing one"""
    # Check if visitor exists
    visitor = visitors.find_one({
        "organization_id": organization_id,
        "session_id": session_id
    })
    
    if visitor:
        # Update existing visitor
        visitors.update_one(
            {"organization_id": organization_id, "session_id": session_id},
            {"$set": {**visitor_data, "last_active": visitor_data.get("last_active", None)}}
        )
        return visitors.find_one({"organization_id": organization_id, "session_id": session_id})
    else:
        # Create new visitor
        visitor_id = str(uuid.uuid4())
        new_visitor = {
            "id": visitor_id,
            "organization_id": organization_id,
            "session_id": session_id,
            **visitor_data
        }
        visitors.insert_one(new_visitor)
        return new_visitor

def get_visitor(organization_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Get visitor by organization_id and session_id"""
    return visitors.find_one({"organization_id": organization_id, "session_id": session_id})

# Conversation methods
def add_conversation_message(
    organization_id: str,
    visitor_id: str,
    session_id: str,
    role: str,
    content: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Add a message to the conversation history"""
    message = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "visitor_id": visitor_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": None,  # Server will set this
        "metadata": metadata or {}
    }
    
    conversations.insert_one(message)
    return message

def get_conversation_history(organization_id: str, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get conversation history for a session"""
    return list(
        conversations.find(
            {"organization_id": organization_id, "session_id": session_id}
        ).sort("created_at", pymongo.ASCENDING).limit(limit)
    )

# Initialize database on module import
init_db() 