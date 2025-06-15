from fastapi import APIRouter, HTTPException, Depends, Request, Header
from services.database import create_organization, get_organization_by_api_key, update_organization, get_organization_by_user_id
from models.organization import OrganizationCreate, OrganizationUpdate
from typing import Optional
import json

router = APIRouter()

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

@router.post("/register")
async def register_organization(organization_data: OrganizationCreate):
    """Register a new organization and generate API key"""
    try:
        print(f"Attempting to register organization with data: {organization_data}")
        
        if not organization_data.user_id:
            raise HTTPException(status_code=422, detail="user_id is required")
            
        # Check if user already has an organization
        existing_org = get_organization_by_user_id(organization_data.user_id)
        if existing_org:
            print(f"Found existing organization for user {organization_data.user_id}")
            # Convert ObjectId to string if present
            if "_id" in existing_org:
                existing_org["_id"] = str(existing_org["_id"])
            
            # Return the existing organization
            return {
                "status": "success",
                "message": "Found existing organization",
                "organization": existing_org
            }
        
        print(f"Creating new organization for user {organization_data.user_id}")
        org = create_organization(
            name=organization_data.name,
            subscription_tier=organization_data.subscription_tier,
            user_id=organization_data.user_id,
            stripe_subscription_id=organization_data.stripe_subscription_id if organization_data.stripe_subscription_id else None
        )
        
        print(f"Created organization: {org}")
        
        # Convert ObjectId to string if present
        if "_id" in org:
            org["_id"] = str(org["_id"])
        
        return {
            "status": "success",
            "message": "Organization registered successfully",
            "organization": org
        }
    except HTTPException as e:
        print(f"HTTP Exception in register_organization: {str(e)}")
        raise e
    except Exception as e:
        print(f"Error in register_organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
async def get_organization(organization=Depends(get_organization_from_api_key)):
    """Get organization details from API key"""
    response_org = {
        "id": organization["id"],
        "name": organization["name"],
        "subscription_tier": organization["subscription_tier"],
        "subscription_status": organization["subscription_status"],
        "pinecone_namespace": organization["pinecone_namespace"],
        "settings": organization.get("settings", {})
    }
    
    # Only include stripe_subscription_id if it exists
    if "stripe_subscription_id" in organization:
        response_org["stripe_subscription_id"] = organization["stripe_subscription_id"]
    
    return {
        "status": "success",
        "organization": response_org
    }

@router.put("/update")
async def update_organization_details(
    update_data: OrganizationUpdate, 
    organization=Depends(get_organization_from_api_key)
):
    """Update organization details"""
    try:
        # Convert update_data to dict and filter out None values
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        if not update_dict:
            return {
                "status": "error",
                "message": "No update data provided"
            }
        
        # Update organization
        updated_org = update_organization(organization["id"], update_dict)
        
        response_org = {
            "id": updated_org["id"],
            "name": updated_org["name"],
            "subscription_tier": updated_org["subscription_tier"],
            "subscription_status": updated_org["subscription_status"],
            "settings": updated_org.get("settings", {})
        }
        
        # Only include stripe_subscription_id if it exists
        if "stripe_subscription_id" in updated_org:
            response_org["stripe_subscription_id"] = updated_org["stripe_subscription_id"]
        
        return {
            "status": "success",
            "message": "Organization updated successfully",
            "organization": response_org
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage")
async def get_organization_usage(organization=Depends(get_organization_from_api_key)):
    """Get organization usage statistics"""
    # Get organization namespace
    org_id = organization["id"]
    namespace = organization["pinecone_namespace"]
    
    try:
        # Get vector store stats from Pinecone
        import os
        from datetime import datetime
        import json
        import traceback
        
        # Import directly from vectorstore module to avoid circular imports
        from pinecone import Pinecone
        from services.database import db
        
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX", "bayshoreai")
        
        print(f"Getting usage stats for organization {org_id} with namespace {namespace}")
        print(f"Connecting to Pinecone index: {index_name}")
        
        # Get total users (visitors) for this organization
        total_users = db.visitors.count_documents({"organization_id": org_id})
        
        # Get total conversations
        total_conversations = db.conversations.count_documents({"organization_id": org_id})
        
        # Get total API calls from conversations
        total_api_calls = total_conversations
        
        # Create a fresh Pinecone connection
        pc = Pinecone(api_key=pinecone_api_key)
        
        # Make sure we have a valid index
        try:
            # List available indexes to ensure they exist
            indexes = pc.list_indexes()
            index_names = [idx.name for idx in indexes.indexes]
            
            if index_name not in index_names:
                print(f"Warning: Index {index_name} not found. Available indexes: {index_names}")
                # Use first available index or default to bayshoreai
                if index_names:
                    index_name = index_names[0]
                    print(f"Using first available index: {index_name}")
                else:
                    index_name = "bayshoreai"
                    print(f"No indexes found, defaulting to: {index_name}")
            
            # Connect to the index
            index = pc.Index(index_name)
            
            # Get detailed stats
            stats = index.describe_index_stats()
            
            # Convert stats to dict for easier debugging
            stats_dict = {}
            try:
                stats_dict = stats.dict()
            except:
                # Fall back to manual extraction if dict() method not available
                if hasattr(stats, 'namespaces'):
                    stats_dict = {"namespaces": {}}
                    for ns_name, ns_data in stats.namespaces.items():
                        stats_dict["namespaces"][ns_name] = {
                            "vector_count": getattr(ns_data, "vector_count", 0)
                        }
                stats_dict["total_vector_count"] = getattr(stats, "total_vector_count", 0)
                stats_dict["dimension"] = getattr(stats, "dimension", 0)
                
            print(f"Full index stats: {json.dumps(stats_dict, default=str)}")
            
            # Try different ways to access namespace stats
            vector_count = 0
            dimensions = 0
            
            # Get namespace directly
            ns_data = None
            if hasattr(stats, 'namespaces') and namespace in stats.namespaces:
                ns_data = stats.namespaces[namespace]
                print(f"Found namespace stats for {namespace}")
                
                # Try to get vector count
                if hasattr(ns_data, 'vector_count'):
                    vector_count = ns_data.vector_count or 0
                    print(f"Vector count from namespace: {vector_count}")
                
                # Try to get dimensions
                if hasattr(ns_data, 'dimension'):
                    dimensions = ns_data.dimension or 0
            else:
                print(f"Namespace {namespace} not found in stats. Available namespaces: {list(stats.namespaces.keys() if hasattr(stats, 'namespaces') else [])}")
                    
            # If we didn't get any vectors but we know content is retrievable
            # set a minimum count for display purposes
            if vector_count == 0:
                # Do a direct count query if possible
                try:
                    # Try to count vectors directly with API (if available)
                    count_result = index.fetch(
                        ids=[], 
                        namespace=namespace
                    )
                    if hasattr(count_result, 'vectors') and count_result.vectors:
                        vector_count = len(count_result.vectors)
                        print(f"Direct count query found {vector_count} vectors")
                except Exception as e:
                    print(f"Error during direct count: {str(e)}")
                
                # If still zero, do a test query as fallback
                if vector_count == 0:
                    try:
                        from services.langchain.engine import get_org_vectorstore
                        from services.langchain.embeddings import initialize_embeddings
                        
                        # Initialize with correct dimension
                        os.environ["PINECONE_DIMENSION"] = "1024"
                        embeddings = initialize_embeddings()
                        org_vectorstore = get_org_vectorstore(organization["api_key"])
                        
                        if org_vectorstore:
                            results = org_vectorstore.similarity_search("test", k=1, namespace=namespace)
                            if results and len(results) > 0:
                                # If results found, set count to at least 1
                                vector_count = max(1, vector_count)
                                print(f"Test query found {len(results)} results, setting count to {vector_count}")
                    except Exception as e:
                        print(f"Error during verification search: {str(e)}")
            
            # Get dimension from index if not found in namespace
            if dimensions == 0:
                dimensions = getattr(stats, 'dimension', 1024)
                print(f"Using index dimension: {dimensions}")
            
            # Safe calculation with reasonable defaults
            storage_bytes = vector_count * (dimensions or 1024) * 4  # Float32 is 4 bytes
            
            # Count any documents that might be present
            document_count = 0
            try:
                # Import services here to avoid circular imports
                from services.database import get_organization_documents
                docs = get_organization_documents(org_id)
                document_count = len(docs) if docs else 0
                print(f"Found {document_count} documents for organization")
            except Exception as e:
                print(f"Error getting document count: {str(e)}")
            
            return {
                "status": "success",
                "usage": {
                    "api_calls": total_api_calls,
                    "vector_embeddings": vector_count,
                    "storage_used": storage_bytes,
                    "documents": document_count,
                    "total_users": total_users,
                    "total_conversations": total_conversations,
                    "last_updated": datetime.now().isoformat()
                }
            }
        except Exception as e:
            print(f"Error accessing Pinecone index: {str(e)}")
            traceback.print_exc()
            # Return fallback response
            return {
                "status": "success",
                "usage": {
                    "api_calls": total_api_calls,
                    "vector_embeddings": 0,
                    "storage_used": 0,
                    "documents": 0,
                    "total_users": total_users,
                    "total_conversations": total_conversations,
                    "last_updated": datetime.now().isoformat(),
                    "error": f"Error accessing vector database: {str(e)}"
                }
            }
            
    except Exception as e:
        print(f"Error getting usage statistics: {str(e)}")
        traceback.print_exc()
        return {
            "status": "success",
            "usage": {
                "api_calls": 0,
                "vector_embeddings": 0,
                "storage_used": 0,
                "documents": 0,
                "total_users": 0,
                "total_conversations": 0,
                "last_updated": datetime.now().isoformat(),
                "error": f"General error: {str(e)}"
            }
        }

@router.get("/user/{user_id}")
async def get_organization_by_user(user_id: str):
    """Get organization by user ID"""
    try:
        print(f"Fetching organization for user: {user_id}")
        
        # Use the database service function
        organization = get_organization_by_user_id(user_id)
        print(f"Found organization: {organization}")
        
        if not organization:
            print(f"No organization found for user: {user_id}")
            raise HTTPException(status_code=404, detail=f"No organization found for user: {user_id}")
        
        # Convert ObjectId to string
        organization["_id"] = str(organization["_id"])
        
        return organization
    except Exception as e:
        print(f"Error fetching organization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 