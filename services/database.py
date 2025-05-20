import os
import pymongo
from dotenv import load_dotenv
from models.organization import Organization
from models.visitor import Visitor, ConversationMessage
import uuid
import secrets
import datetime  # Import Python's datetime module
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
user_profiles = db.user_profiles  # New collection for user profiles

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
    
    # User profile indexes
    user_profiles.create_index("session_id", unique=True)
    user_profiles.create_index("organization_id")
    user_profiles.create_index([("organization_id", pymongo.ASCENDING), ("session_id", pymongo.ASCENDING)], unique=True)
    
    # Create documents collection if it doesn't exist
    if "documents" not in db.list_collection_names():
        db.create_collection("documents")
        db.documents.create_index("organization_id")
        db.documents.create_index([("organization_id", pymongo.ASCENDING), ("document_id", pymongo.ASCENDING)], unique=True)

# Documents collection
documents = db.documents

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
        "created_at": datetime.datetime.utcnow(),  # Explicitly set current timestamp
        "metadata": metadata or {}
    }
    
    conversations.insert_one(message)
    return message

def get_conversation_history(organization_id, session_id):
    """Retrieve conversation history from MongoDB for a specific session"""
    try:
        # Query MongoDB to get all messages for this session in chronological order
        result = conversations.find({
            "organization_id": organization_id,
            "session_id": session_id
        }).sort("created_at", pymongo.ASCENDING)
        
        # Convert cursor to list - maintain original document format
        conversation_history = []
        for doc in result:
            # Convert MongoDB _id to string representation
            if "_id" in doc:
                doc["_id"] = {"$oid": str(doc["_id"])}
            conversation_history.append(doc)
            
        return conversation_history
    except Exception as e:
        print(f"Error retrieving conversation history: {e}")
        return []

# Document tracking methods
def add_organization_document(organization_id: str, document_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a document to an organization"""
    if "document_id" not in document_data:
        document_data["document_id"] = str(uuid.uuid4())
    
    document_data["organization_id"] = organization_id
    document_data["created_at"] = document_data.get("created_at", datetime.datetime.utcnow())
    
    # Check if document already exists
    existing = documents.find_one({
        "organization_id": organization_id, 
        "document_id": document_data["document_id"]
    })
    
    if existing:
        # Update existing document
        documents.update_one(
            {"_id": existing["_id"]},
            {"$set": document_data}
        )
        return document_data
    else:
        # Insert new document
        result = documents.insert_one(document_data)
        document_data["_id"] = str(result.inserted_id)
        return document_data

def get_organization_documents(organization_id: str) -> List[Dict[str, Any]]:
    """Get all documents for an organization"""
    return list(documents.find({"organization_id": organization_id}))

def count_organization_documents(organization_id: str) -> int:
    """Count documents for an organization"""
    return documents.count_documents({"organization_id": organization_id})

def get_document(organization_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    """Get a document by id"""
    return documents.find_one({"organization_id": organization_id, "document_id": document_id})

def delete_organization_document(organization_id: str, document_id: str) -> bool:
    """Delete a document by id"""
    result = documents.delete_one({"organization_id": organization_id, "document_id": document_id})
    return result.deleted_count > 0

# User profile methods
def save_user_profile(organization_id: str, session_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update user profile data"""
    # Check if profile exists
    existing_profile = user_profiles.find_one({
        "organization_id": organization_id,
        "session_id": session_id
    })
    
    profile = {
        "organization_id": organization_id,
        "session_id": session_id,
        "updated_at": datetime.datetime.utcnow(),  # Use Python's datetime module
        "profile_data": profile_data
    }
    
    if existing_profile:
        # Update existing profile
        user_profiles.update_one(
            {"_id": existing_profile["_id"]},
            {"$set": profile}
        )
        profile["_id"] = existing_profile["_id"]
    else:
        # Create new profile
        profile["created_at"] = profile["updated_at"]
        result = user_profiles.insert_one(profile)
        profile["_id"] = result.inserted_id
    
    return profile

def get_user_profile(organization_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Get user profile by organization_id and session_id"""
    return user_profiles.find_one({
        "organization_id": organization_id,
        "session_id": session_id
    })

# Initialize database on module import
init_db() 