from fastapi import APIRouter, HTTPException, Depends, Request, Header
from services.database import create_organization, get_organization_by_api_key, update_organization
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
        org = create_organization(
            name=organization_data.name,
            subscription_tier=organization_data.subscription_tier
        )
        
        # Return the organization with API key
        return {
            "status": "success",
            "message": "Organization registered successfully",
            "organization": {
                "id": org["id"],
                "name": org["name"],
                "api_key": org["api_key"],
                "subscription_tier": org["subscription_tier"],
                "subscription_status": org["subscription_status"],
                "pinecone_namespace": org["pinecone_namespace"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
async def get_organization(organization=Depends(get_organization_from_api_key)):
    """Get organization details from API key"""
    return {
        "status": "success",
        "organization": {
            "id": organization["id"],
            "name": organization["name"],
            "subscription_tier": organization["subscription_tier"],
            "subscription_status": organization["subscription_status"],
            "pinecone_namespace": organization["pinecone_namespace"],
            "settings": organization.get("settings", {})
        }
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
        
        return {
            "status": "success",
            "message": "Organization updated successfully",
            "organization": {
                "id": updated_org["id"],
                "name": updated_org["name"],
                "subscription_tier": updated_org["subscription_tier"],
                "subscription_status": updated_org["subscription_status"],
                "settings": updated_org.get("settings", {})
            }
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
        
        # Import directly from vectorstore module to avoid circular imports
        from pinecone import Pinecone
        
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX", "bayshoreai")
        
        print(f"Getting usage stats for organization {org_id} with namespace {namespace}")
        print(f"Connecting to Pinecone index: {index_name}")
        
        # Create a fresh Pinecone connection
        pc = Pinecone(api_key=pinecone_api_key)
        index = pc.Index(index_name)
        
        # Get detailed stats
        stats = index.describe_index_stats()
        print(f"Full index stats: {json.dumps(stats.dict(), default=str)}")
        
        # Try different ways to access namespace stats
        vector_count = 0
        dimensions = 0
        
        # Get namespace directly
        if hasattr(stats, 'namespaces') and namespace in stats.namespaces:
            namespace_stats = stats.namespaces[namespace]
            print(f"Found namespace stats: {json.dumps(namespace_stats, default=str)}")
            
            # Try to get vector count
            if hasattr(namespace_stats, 'vector_count'):
                vector_count = namespace_stats.vector_count or 0
            
            # Try to get dimensions
            if hasattr(namespace_stats, 'dimension'):
                dimensions = namespace_stats.dimension or 0
                
        # If we didn't get any vectors but we know content is retrievable
        # set a minimum count for display purposes
        if vector_count == 0:
            # Check if vectors exist by doing a simple query
            try:
                from services.langchain.engine import get_org_vectorstore
                from services.langchain.embeddings import initialize_embeddings
                
                embeddings = initialize_embeddings()
                org_vectorstore = get_org_vectorstore(organization["api_key"])
                
                if org_vectorstore:
                    results = org_vectorstore.similarity_search("test", k=1)
                    if results and len(results) > 0:
                        # If we get results but count shows 0, use at least 1
                        vector_count = max(1, vector_count)
                        print(f"Found {len(results)} results in search, setting minimum vector count to {vector_count}")
            except Exception as e:
                print(f"Error during verification search: {str(e)}")
        
        # Safe calculation - use default values if needed
        storage_bytes = vector_count * (dimensions or 1536) * 4  # Float32 is 4 bytes
        
        return {
            "status": "success",
            "usage": {
                "api_calls": organization.get("api_calls", 0),
                "vector_embeddings": vector_count,
                "storage_used": storage_bytes,
                "last_updated": datetime.now().isoformat()
            }
        }
    except Exception as e:
        print(f"Error getting usage statistics: {str(e)}")
        return {
            "status": "success",
            "usage": {
                "api_calls": 0,
                "vector_embeddings": 0,
                "storage_used": 0,
                "last_updated": datetime.now().isoformat()
            }
        } 