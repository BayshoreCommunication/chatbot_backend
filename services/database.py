import os
import pymongo
from dotenv import load_dotenv
from models.organization import Organization, Subscription
from models.visitor import Visitor, ConversationMessage
from models.conversation import Conversation
import uuid
import secrets
import datetime  # Import Python's datetime module
from typing import List, Dict, Any, Optional
from bson import ObjectId

# Load environment variables
load_dotenv()

# Get MongoDB connection string
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client.saas_chatbot_db

def get_database():
    """Return the database instance"""
    return db

# Collections
organizations = db.organizations
visitors = db.visitors
conversations = db.conversations
api_keys = db.api_keys
user_profiles = db.user_profiles  # New collection for user profiles
users = db.users  # Added users collection
subscriptions = db.subscriptions  # Add subscriptions collection
leads = db.leads  # Collection for storing leads

# Initialize the database with indexes
def init_db():
    """Initialize database with necessary indexes"""
    # Organization indexes
    organizations.create_index("api_key", unique=True)
    
    # Visitor indexes
    visitors.create_index("organization_id")
    visitors.create_index("session_id")
    visitors.create_index([("organization_id", pymongo.ASCENDING), ("session_id", pymongo.ASCENDING)], unique=True)
    visitors.create_index("is_agent_mode")  # New index for agent mode queries
    visitors.create_index([("organization_id", pymongo.ASCENDING), ("is_agent_mode", pymongo.ASCENDING)])  # Compound index
    
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
    
    # Subscription indexes
    subscriptions.create_index("stripe_subscription_id", unique=True)
    subscriptions.create_index("user_id")
    subscriptions.create_index("organization_id")
    subscriptions.create_index([("user_id", pymongo.ASCENDING), ("organization_id", pymongo.ASCENDING)])
    
    # Lead indexes
    leads.create_index("organization_id")
    leads.create_index("session_id")
    leads.create_index("email")
    leads.create_index("timestamp")
    leads.create_index("visitor_id")
    leads.create_index([("organization_id", pymongo.ASCENDING), ("email", pymongo.ASCENDING)])
    leads.create_index([("organization_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)])

# Documents collection
documents = db.documents

# Lead methods
def create_lead(organization_id: str, session_id: str, name: str, email: str, phone: str = None, inquiry: str = "", source: str = "chatbot") -> Dict[str, Any]:
    """Create or update a lead in MongoDB.
    - Accepts partial info (email or phone). Name may be empty and updated later.
    - Upserts by (organization_id + visitor_id) when available, else by (organization_id + session_id).
    """
    current_time = datetime.datetime.utcnow()
    
    lead_data = {
        "lead_id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "session_id": session_id,
        "name": name or "",
        "email": email or "",
        "phone": phone,
        "inquiry": inquiry,
        "source": source,
        "status": "new",
        "timestamp": current_time,
        "created_at": current_time,
        "updated_at": current_time
    }
    
    try:
        # Prefer linking by visitor_id when available
        visitor = visitors.find_one({"organization_id": organization_id, "session_id": session_id})
        visitor_id = visitor.get("id") if visitor else None

        # Check if lead already exists for this session/visitor to avoid duplicates
        existing_query = {"organization_id": organization_id}
        if visitor_id:
            existing_query["visitor_id"] = visitor_id
        else:
            existing_query["session_id"] = session_id

        existing_lead = leads.find_one(existing_query)
        
        if existing_lead:
            # Update existing lead with new information
            update_data = {
                "updated_at": current_time
            }
            if name:
                update_data["name"] = name
            if email:
                update_data["email"] = email
            if phone:
                update_data["phone"] = phone
            if inquiry:
                update_data["inquiry"] = inquiry
            if not existing_lead.get("status"):
                update_data["status"] = "new"
                
            leads.update_one(
                {"_id": existing_lead["_id"]},
                {"$set": update_data}
            )
            existing_lead.update(update_data)
            return existing_lead
        else:
            # Create new lead
            if visitor_id:
                lead_data["visitor_id"] = visitor_id
            # Ensure at least one contact field exists
            if not lead_data.get("email") and not lead_data.get("phone"):
                # Without any contact, store as minimal lead with session linkage
                lead_data["status"] = "prospect"
            result = leads.insert_one(lead_data)
            lead_data["_id"] = result.inserted_id
            return lead_data
            
    except Exception as e:
        print(f"Error creating lead: {str(e)}")
        raise e

def get_leads_by_organization(organization_id: str, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
    """Get all leads for an organization"""
    try:
        cursor = leads.find(
            {"organization_id": organization_id}
        ).sort("timestamp", -1).limit(limit).skip(skip)
        
        lead_list = []
        for lead in cursor:
            # Convert ObjectId to string for JSON serialization
            if "_id" in lead:
                lead["_id"] = str(lead["_id"])
            # Convert datetime to ISO string
            if "timestamp" in lead and isinstance(lead["timestamp"], datetime.datetime):
                lead["timestamp"] = lead["timestamp"].isoformat()
            if "created_at" in lead and isinstance(lead["created_at"], datetime.datetime):
                lead["created_at"] = lead["created_at"].isoformat()
            if "updated_at" in lead and isinstance(lead["updated_at"], datetime.datetime):
                lead["updated_at"] = lead["updated_at"].isoformat()
            lead_list.append(lead)
            
        return lead_list
    except Exception as e:
        print(f"Error getting leads: {str(e)}")
        return []

def search_leads(organization_id: str, name: str = None, email: str = None, status: str = None, date_from: str = None, date_to: str = None) -> List[Dict[str, Any]]:
    """Search leads by criteria"""
    try:
        # Build query
        query = {"organization_id": organization_id}
        
        if name:
            query["name"] = {"$regex": name, "$options": "i"}
        if email:
            query["email"] = {"$regex": email, "$options": "i"}
        if status:
            query["status"] = status
            
        # Date range filtering
        if date_from or date_to:
            date_query = {}
            if date_from:
                date_query["$gte"] = datetime.datetime.fromisoformat(date_from)
            if date_to:
                date_query["$lte"] = datetime.datetime.fromisoformat(date_to)
            query["timestamp"] = date_query
        
        cursor = leads.find(query).sort("timestamp", -1)
        
        lead_list = []
        for lead in cursor:
            # Convert ObjectId to string for JSON serialization
            if "_id" in lead:
                lead["_id"] = str(lead["_id"])
            # Convert datetime to ISO string
            if "timestamp" in lead and isinstance(lead["timestamp"], datetime.datetime):
                lead["timestamp"] = lead["timestamp"].isoformat()
            if "created_at" in lead and isinstance(lead["created_at"], datetime.datetime):
                lead["created_at"] = lead["created_at"].isoformat()
            if "updated_at" in lead and isinstance(lead["updated_at"], datetime.datetime):
                lead["updated_at"] = lead["updated_at"].isoformat()
            lead_list.append(lead)
            
        return lead_list
    except Exception as e:
        print(f"Error searching leads: {str(e)}")
        return []

# Organization methods
def create_organization(name: str, subscription_tier: str = "free", user_id: str = None, stripe_subscription_id: str | None = None) -> Dict[str, Any]:
    """Create a new organization with a unique API key"""
    # Generate unique API key with org_ prefix
    api_key = f"org_sk_{secrets.token_hex(16)}"
    # Generate unique namespace for vector DB
    pinecone_namespace = f"org_{uuid.uuid4().hex}"
    
    current_time = datetime.datetime.utcnow()
    
    org_data = {
        "id": str(uuid.uuid4()),
        "name": name,
        "api_key": api_key,
        "user_id": user_id,
        "subscription_tier": subscription_tier,
        "subscription_status": "active",
        "pinecone_namespace": pinecone_namespace,
        "settings": {},
        "created_at": current_time,
        "updated_at": current_time
    }
    
    # Only add stripe_subscription_id if it's not None
    if stripe_subscription_id is not None:
        org_data["stripe_subscription_id"] = stripe_subscription_id
    
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
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.datetime.utcnow()
    
    organizations.update_one({"id": org_id}, {"$set": update_data})
    return organizations.find_one({"id": org_id})

def get_organization_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get organization by user ID"""
    return organizations.find_one({"user_id": user_id})

def update_organization_subscription(org_id: str, stripe_subscription_id: str | None) -> Optional[Dict[str, Any]]:
    """Update organization's Stripe subscription ID"""
    update_data = {}
    if stripe_subscription_id is not None:
        update_data["stripe_subscription_id"] = stripe_subscription_id
    
    if update_data:
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
            {"$set": {**visitor_data, "last_active": visitor_data.get("last_active", datetime.datetime.utcnow())}}
        )
        return visitors.find_one({"organization_id": organization_id, "session_id": session_id})
    else:
        # Create new visitor
        visitor_id = str(uuid.uuid4())
        new_visitor = {
            "id": visitor_id,
            "organization_id": organization_id,
            "session_id": session_id,
            "created_at": datetime.datetime.utcnow(),  # Add created_at timestamp
            "last_active": visitor_data.get("last_active", datetime.datetime.utcnow()),
            **visitor_data
        }
        visitors.insert_one(new_visitor)
        return new_visitor

def get_visitor(organization_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Get visitor by organization_id and session_id"""
    return visitors.find_one({"organization_id": organization_id, "session_id": session_id})

def set_agent_mode(organization_id: str, session_id: str, agent_id: str = None) -> Dict[str, Any]:
    """Set a visitor's chat to agent mode (manual handling)"""
    visitor = get_visitor(organization_id, session_id)
    if not visitor:
        raise ValueError("Visitor not found")
    
    update_data = {
        "is_agent_mode": True,
        "agent_takeover_at": datetime.datetime.utcnow(),
        "agent_id": agent_id
    }
    
    visitors.update_one(
        {"organization_id": organization_id, "session_id": session_id},
        {"$set": update_data}
    )
    
    return visitors.find_one({"organization_id": organization_id, "session_id": session_id})

def set_bot_mode(organization_id: str, session_id: str) -> Dict[str, Any]:
    """Set a visitor's chat back to bot mode (automatic handling)"""
    visitor = get_visitor(organization_id, session_id)
    if not visitor:
        raise ValueError("Visitor not found")
    
    update_data = {
        "is_agent_mode": False,
        "agent_takeover_at": None,
        "agent_id": None
    }
    
    visitors.update_one(
        {"organization_id": organization_id, "session_id": session_id},
        {"$set": update_data}
    )
    
    return visitors.find_one({"organization_id": organization_id, "session_id": session_id})

def is_chat_in_agent_mode(organization_id: str, session_id: str) -> bool:
    """Check if a chat is currently being handled by an agent"""
    visitor = get_visitor(organization_id, session_id)
    return visitor.get("is_agent_mode", False) if visitor else False

# Conversation methods
def add_conversation_message(
    organization_id: str,
    visitor_id: str,
    session_id: str,
    role: str,
    content: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Add a message to the conversation history using the Conversation model"""
    
    # Use Pydantic model to create/validate the message
    conversation = Conversation(
        id=str(uuid.uuid4()),
        organization_id=organization_id,
        visitor_id=visitor_id or "anonymous", # Handle None visitor_id
        session_id=session_id,
        role=role,
        content=content,
        created_at=datetime.datetime.utcnow(),
        metadata=metadata or {}
    )
    
    # Convert to dict for MongoDB
    message_dict = conversation.model_dump()
    
    conversations.insert_one(message_dict)
    return message_dict

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
        seen_ids = set()  # Use a set to track seen message IDs
        
        for doc in result:
            # Skip duplicates (if any)
            if doc["id"] in seen_ids:
                continue
                
            # Track this ID
            seen_ids.add(doc["id"])
                
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
    # Resolve visitor for linkage
    visitor_for_link = visitors.find_one({
        "organization_id": organization_id,
        "session_id": session_id
    })

    # Check if profile exists
    existing_profile = user_profiles.find_one({
        "organization_id": organization_id,
        "session_id": session_id
    })
    
    profile = {
        "organization_id": organization_id,
        "session_id": session_id,
        "visitor_id": visitor_for_link.get("id") if visitor_for_link else None,
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

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email address"""
    user = users.find_one({"email": email})
    return user if user else None

def create_subscription(
    user_id: str,
    organization_id: str,
    stripe_subscription_id: str,
    payment_amount: float,
    subscription_tier: str,
    current_period_start: datetime.datetime,
    current_period_end: datetime.datetime
) -> Dict[str, Any]:
    """Create a new subscription record"""
    # Verify user and organization exist
    user = users.find_one({"id": user_id})
    organization = organizations.find_one({"id": organization_id})
    
    if not user or not organization:
        raise ValueError("User or organization not found")
    
    subscription_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "organization_id": organization_id,
        "stripe_subscription_id": stripe_subscription_id,
        "payment_amount": payment_amount,
        "subscription_tier": subscription_tier,
        "subscription_status": "active",
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow()
    }
    
    result = subscriptions.insert_one(subscription_data)
    subscription_data["_id"] = str(result.inserted_id)
    
    return subscription_data

def serialize_subscription(subscription: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Serialize subscription document for JSON response"""
    if subscription:
        # Convert ObjectId to string
        if "_id" in subscription:
            subscription["_id"] = str(subscription["_id"])
    return subscription

def get_subscription_by_stripe_id(stripe_subscription_id: str) -> Optional[Dict[str, Any]]:
    """Get subscription by Stripe subscription ID"""
    subscription = subscriptions.find_one({"stripe_subscription_id": stripe_subscription_id})
    return serialize_subscription(subscription) if subscription else None

def get_user_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    """Get subscription for a user"""
    subscription = subscriptions.find_one({"user_id": user_id})
    return serialize_subscription(subscription) if subscription else None

def get_organization_subscription(organization_id: str) -> Optional[Dict[str, Any]]:
    """Get active subscription for an organization"""
    return subscriptions.find_one({
        "organization_id": organization_id,
        "subscription_status": "active"
    })

def update_subscription_status(stripe_subscription_id: str, status: str) -> Optional[Dict[str, Any]]:
    """Update subscription status"""
    subscriptions.update_one(
        {"stripe_subscription_id": stripe_subscription_id},
        {
            "$set": {
                "subscription_status": status,
                "updated_at": datetime.datetime.utcnow()
            }
        }
    )
    return get_subscription_by_stripe_id(stripe_subscription_id)

def update_subscription_period(
    stripe_subscription_id: str,
    current_period_start: datetime.datetime,
    current_period_end: datetime.datetime
) -> Optional[Dict[str, Any]]:
    """Update subscription period dates"""
    subscriptions.update_one(
        {"stripe_subscription_id": stripe_subscription_id},
        {
            "$set": {
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "updated_at": datetime.datetime.utcnow()
            }
        }
    )
    return get_subscription_by_stripe_id(stripe_subscription_id)

# Initialize database on module import
init_db() 