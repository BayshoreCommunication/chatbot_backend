
from fastapi import APIRouter, HTTPException, Body, Depends, Header, Request
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId
import logging

from services.database import get_organization_by_api_key

from services.knowledge_base import (
    check_knowledge_base_exists,
    create_knowledge_base as create_knowledge_base_manual,
    get_knowledge_base,
    update_knowledge_base,
    delete_knowledge_base,
    query_knowledge_base,
    get_knowledge_base_stats
)
from services.langchain.knowledge_base import (
    build_knowledge_base_auto,
    get_chatbot_chunks_by_intent,
    get_all_chatbot_context,
    query_vector_db,
    add_document_to_knowledge_base
)

from models.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    Source
)

router = APIRouter(prefix="/api/knowledge-base", tags=["Knowledge Base"])
logger = logging.getLogger(__name__)

def get_org_id(organization: Dict[str, Any]) -> str:
    """Safely get organization ID from either 'id' or MongoDB '_id'."""
    org_id = organization.get("id")
    if not org_id:
        mongo_id = organization.get("_id")
        if mongo_id is not None:
            try:
                org_id = str(mongo_id)
            except Exception:
                org_id = None
    if not org_id:
        raise HTTPException(status_code=500, detail="Organization ID is missing")
    return org_id

async def get_organization_from_api_key(x_api_key: Optional[str] = Header(None)):
    """Dependency to get organization from API key"""
    if not x_api_key:
        logger.error("❌ No X-API-Key header provided")
        raise HTTPException(status_code=401, detail="API key is required in X-API-Key header")
    
    logger.info(f"🔑 Validating API key: {x_api_key[:20]}...")
    organization = get_organization_by_api_key(x_api_key)
    if not organization:
        logger.error(f"❌ Invalid API key: {x_api_key}")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    logger.info(f"✅ Organization validated: {organization.get('name')}")
    return organization


# ==========================================
# REQUEST/RESPONSE MODELS
# ==========================================

class CheckKnowledgeBaseRequest(BaseModel):
    user_id: Optional[str] = Field(None, alias="userId")
    organization_id: Optional[str] = Field(None, alias="organizationId")

    class Config:
        populate_by_name = True


class CreateKnowledgeBaseRequest(BaseModel):
    company_name: str = Field(alias="companyName")
    website: Optional[str] = None  # Optional website URL for automatic scraping
    sources: Optional[List[Dict[str, Any]]] = None  # Optional manual sources
    structured_data: Optional[Dict[str, Any]] = Field(None, alias="structuredData")
    raw_content: Optional[str] = Field(None, alias="rawContent")

    class Config:
        populate_by_name = True


class UpdateKnowledgeBaseRequest(BaseModel):
    sources: Optional[List[Dict[str, Any]]] = None
    structured_data: Optional[Dict[str, Any]] = Field(None, alias="structuredData")
    raw_content: Optional[str] = Field(None, alias="rawContent")
    vector_store_id: Optional[str] = Field(None, alias="vectorStoreId")
    file_ids: Optional[List[str]] = Field(None, alias="fileIds")
    status: Optional[str] = None

    class Config:
        populate_by_name = True


class QueryKnowledgeBaseRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, alias="topK")

    class Config:
        populate_by_name = True

class UploadDocumentRequest(BaseModel):
    file_path: Optional[str] = Field(None, alias="filePath")
    url: Optional[str] = None
    text: Optional[str] = None
    max_pages: Optional[int] = Field(1, alias="maxPages")

    class Config:
        populate_by_name = True

class DeleteKnowledgeBaseRequest(BaseModel):
    pass  # No fields needed - uses authenticated organization

    class Config:
        populate_by_name = True


# ==========================================
# KNOWLEDGE BASE CHECK
# ==========================================

@router.get("/check")
async def check_knowledge_base(
    request: Request,
    x_api_key: Optional[str] = Header(None, description="API Key for authentication")
):
    """
    GET /api/knowledge-base/check
    Check if user has existing knowledge base
    - Uses X-API-Key header for authentication
    - Returns knowledge base status and quality
    """
    try:
        logger.info(f"📥 Received check request from {request.client.host}")
        logger.info(f"🔑 Headers: {dict(request.headers)}")
        
        if not x_api_key:
            logger.error("❌ No X-API-Key header provided")
            raise HTTPException(status_code=401, detail="X-API-Key header is required")
        
        logger.info(f"🔑 Validating API key: {x_api_key[:20]}...")
        organization = get_organization_by_api_key(x_api_key)
        if not organization:
            logger.error(f"❌ Invalid API key")
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        logger.info(f"✅ Organization validated: {organization.get('name')}")
        user_id = organization.get("user_id")
        if not user_id:
            logger.error(f"❌ user_id not found in organization: {organization}")
            raise HTTPException(status_code=400, detail="User ID not found in organization")
        
        organization_id = get_org_id(organization)
        
        logger.info(f"🔍 Checking knowledge base for user {user_id}, org {organization_id}")
        kb = await check_knowledge_base_exists(user_id, organization_id)
        
        if not kb:
            return {
                "exists": False,
                "message": "No knowledge base found"
            }
        
        metadata = kb.get("metadata", {})
        return {
            "exists": True,
            "knowledgeBase": {
                "id": str(kb["_id"]),
                "companyName": kb.get("companyName"),
                "status": kb.get("status"),
                "quality": metadata.get("quality"),
                "qualityPercentage": metadata.get("qualityPercentage"),
                "totalSources": metadata.get("totalSources"),
                "version": metadata.get("version"),
                "lastUpdated": metadata.get("lastUpdated").isoformat() if metadata.get("lastUpdated") else None
            }
        }
    except Exception as e:
        logger.error(f"Error checking knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# KNOWLEDGE BASE CRUD OPERATIONS
# ==========================================

@router.post("/")
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    organization=Depends(get_organization_from_api_key)
):
    """
    POST /api/knowledge-base/
    Create new knowledge base with automatic information gathering
    
    - Authenticated request using X-API-Key
    - Automatically scrapes website
    - Performs intelligent web search using OpenAI
    - Extracts structured data
    - Stores in MongoDB
    - Returns quality score and structured information
    
    Example:
    {
      "companyName": "Carter Injury Law",
      "website": "https://carterinjurylaw.com"
    }
    """
    try:
        # Auto-detect user_id and organization_id from authenticated organization
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        logger.info(f"🚀 Creating knowledge base for {request.company_name}")
        logger.info(f"📍 User: {user_id}, Org: {organization_id}")
        
        # Check if already exists
        existing = await check_knowledge_base_exists(user_id, organization_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base already exists. Use update endpoint instead."
            )
        
        # Build knowledge base automatically using OpenAI web search
        kb = await build_knowledge_base_auto(
            user_id=user_id,
            organization_id=organization_id,
            company_name=request.company_name,
            website=request.website
        )
        
        metadata = kb.get("metadata", {})
        
        return {
            "success": True,
            "message": "Knowledge base created successfully using AI-powered web search",
            "knowledgeBase": {
                "id": str(kb["_id"]),
                "companyName": kb.get("companyName"),
                "status": kb.get("status"),
                "totalSources": metadata.get("totalSources", 0),
                "quality": metadata.get("quality"),
                "qualityPercentage": metadata.get("qualityPercentage"),
                "version": metadata.get("version"),
                "structuredData": kb.get("structuredData"),
                "createdAt": kb.get("createdAt").isoformat() if kb.get("createdAt") else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def get_knowledge_base_by_user(
    organization=Depends(get_organization_from_api_key)
):
    """
    GET /api/knowledge-base/
    Get knowledge base for user
    - Uses user_id and organization_id from authenticated request
    - Retrieves from MongoDB
    """
    try:
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        kb = await get_knowledge_base(user_id, organization_id)
        
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # Convert ObjectId to string for JSON serialization (only _id is ObjectId)
        if isinstance(kb.get("_id"), ObjectId):
            kb["_id"] = str(kb["_id"])
        # userId and organizationId are already strings (UUIDs), no conversion needed
        
        # Convert datetime objects
        if "createdAt" in kb and kb["createdAt"]:
            kb["createdAt"] = kb["createdAt"].isoformat()
        if "updatedAt" in kb and kb["updatedAt"]:
            kb["updatedAt"] = kb["updatedAt"].isoformat()
        if "metadata" in kb and "lastUpdated" in kb["metadata"]:
            kb["metadata"]["lastUpdated"] = kb["metadata"]["lastUpdated"].isoformat()
        
        return {
            "success": True,
            "knowledgeBase": kb
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/")
async def update_knowledge_base_data(
    request: UpdateKnowledgeBaseRequest,
    organization=Depends(get_organization_from_api_key)
):
    """
    PUT /api/knowledge-base/
    Update existing knowledge base
    - Uses user_id and organization_id from authenticated request
    - Adds new sources
    - Re-indexes in Pinecone (optional)
    - Updates MongoDB
    """
    try:
        # Auto-detect user_id and organization_id from authenticated organization
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        update_data = {}
        if request.sources:
            update_data["sources"] = request.sources
        if request.structured_data:
            update_data["structuredData"] = request.structured_data
        if request.raw_content:
            update_data["rawContent"] = request.raw_content
        if request.vector_store_id:
            update_data["vectorStoreId"] = request.vector_store_id
        if request.file_ids:
            update_data["fileIds"] = request.file_ids
        if request.status:
            update_data["status"] = request.status
        
        kb = await update_knowledge_base(
            user_id=user_id,
            organization_id=organization_id,
            update_data=update_data
        )
        
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        metadata = kb.get("metadata", {})
        return {
            "success": True,
            "message": "Knowledge base updated successfully",
            "knowledgeBase": {
                "id": str(kb["_id"]),
                "version": metadata.get("version"),
                "totalSources": metadata.get("totalSources"),
                "lastUpdated": metadata.get("lastUpdated").isoformat() if metadata.get("lastUpdated") else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/")
async def delete_knowledge_base_data(
    request: DeleteKnowledgeBaseRequest,
    organization=Depends(get_organization_from_api_key)
):
    """
    DELETE /api/knowledge-base/
    Delete knowledge base
    - Uses user_id and organization_id from authenticated request
    - Removes from Pinecone (optional)
    - Archives in MongoDB
    """
    try:
        # Auto-detect user_id and organization_id from authenticated organization
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        success = await delete_knowledge_base(user_id, organization_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        return {
            "success": True,
            "message": "Knowledge base archived successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# VECTOR SEARCH OPERATIONS
# ==========================================

@router.post("/query")
async def query_knowledge_base_search(
    request: QueryKnowledgeBaseRequest,
    organization=Depends(get_organization_from_api_key)
):
    """
    POST /api/knowledge-base/query
    Query knowledge base with semantic search
    - Uses user_id and organization_id from authenticated request
    - Searches Pinecone vectors (optional)
    - Returns relevant chunks
    """
    try:
        # Auto-detect user_id and organization_id from authenticated organization
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        results = await query_knowledge_base(
            user_id=user_id,
            organization_id=organization_id,
            query=request.query,
            top_k=request.top_k
        )
        
        return {
            "success": True,
            "query": request.query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error querying knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-document")
async def upload_knowledge_base_document(
    request: UploadDocumentRequest,
    organization=Depends(get_organization_from_api_key)
):
    """
    POST /api/knowledge-base/upload-document
    Upload document (URL, Text, or File Path) to Knowledge Base
    
    - Parses document
    - Chunks text
    - Embeds and stores in Pinecone
    - Updates MongoDB record
    """
    try:
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        company_name = organization.get("name", "Unknown Company")
        
        result = await add_document_to_knowledge_base(
            user_id=user_id,
            organization_id=organization_id,
            company_name=company_name,
            file_path=request.file_path,
            url=request.url,
            text=request.text,
            max_pages=request.max_pages or 1
        )
        
        return {
            "success": True,
            "message": "Document added successfully",
            "details": result
        }
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_knowledge_base_statistics(
    organization=Depends(get_organization_from_api_key)
):
    """
    GET /api/knowledge-base/stats
    Get knowledge base statistics
    - Uses user_id and organization_id from authenticated request
    - Returns metrics about sources, quality, version history
    """
    try:
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        stats = await get_knowledge_base_stats(user_id, organization_id)
        
        if not stats:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        return {
            "success": True,
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting knowledge base stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CHATBOT-SPECIFIC ENDPOINTS
# ==========================================

@router.get("/chatbot/chunks")
async def get_chatbot_chunks(
    organization=Depends(get_organization_from_api_key),
    intent: Optional[str] = None
):
    """
    GET /api/knowledge-base/chatbot/chunks
    Get AI-optimized chunks for chatbot responses
    
    - Use intent filter to get relevant chunks only
    - Returns conversational, ready-to-use content
    - Optimized for AI assistant context
    
    Example intents: contact, services, pricing, faq, process, team
    """
    try:
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        if intent:
            chunks = await get_chatbot_chunks_by_intent(user_id, organization_id, intent)
        else:
            # Get all chunks
            kb = await get_knowledge_base(user_id, organization_id)
            if not kb:
                raise HTTPException(status_code=404, detail="Knowledge base not found")
            chunks = kb.get("aiChunks", [])
        
        return {
            "success": True,
            "intent": intent or "all",
            "chunks": chunks,
            "count": len(chunks)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chatbot chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chatbot/context")
async def get_chatbot_context(
    organization=Depends(get_organization_from_api_key)
):
    """
    GET /api/knowledge-base/chatbot/context
    Get complete formatted context for AI assistant
    
    - Returns all knowledge in conversational format
    - Ready to pass as system message to AI
    - Optimized for chatbot understanding
    """
    try:
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        context = await get_all_chatbot_context(user_id, organization_id)
        
        return {
            "success": True,
            "context": context,
            "length": len(context),
            "message": "Context ready for AI assistant"
        }
    except Exception as e:
        logger.error(f"Error getting chatbot context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chatbot/vector-search")
async def search_knowledge_vectors(
    query: str,
    top_k: int = 5,
    organization=Depends(get_organization_from_api_key)
):
    """
    Search knowledge base using vector similarity (Pinecone)
    
    - Converts query to embedding
    - Searches Pinecone for similar content
    - Returns top_k most relevant chunks
    - Includes similarity scores
    """
    try:
        organization_id = get_org_id(organization)
        
        results = await query_vector_db(query, organization_id, top_k)
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "message": f"Found {len(results)} relevant chunks"
        }
    except Exception as e:
        logger.error(f"Error searching vectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild")
async def rebuild_knowledge_base(
    organization=Depends(get_organization_from_api_key)
):
    """
    POST /api/knowledge-base/rebuild
    Delete all vectors and rebuild knowledge base with correct embeddings
    
    This fixes embedding mismatch issues by:
    1. Deleting all vectors in the namespace
    2. Re-uploading with LangChain embeddings (matching query)
    """
    try:
        import os
        from pinecone import Pinecone
        
        user_id = organization.get("user_id")
        organization_id = get_org_id(organization)
        
        logger.info(f"🔧 Rebuilding knowledge base for user: {user_id}")
        
        # Get existing knowledge base
        kb = await get_knowledge_base(user_id, organization_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        vectorstore_id = kb.get("vectorStoreId")
        company_name = kb.get("companyName")
        
        if not vectorstore_id:
            raise HTTPException(status_code=400, detail="No vectorStoreId found")
        
        # Delete all vectors in namespace
        logger.info(f"🗑️  Deleting vectors in namespace: {vectorstore_id}")
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index_name = os.getenv("PINECONE_INDEX", "bayai")
        index = pc.Index(index_name)
        
        try:
            index.delete(delete_all=True, namespace=vectorstore_id)
            logger.info(f"✅ Deleted all vectors from namespace: {vectorstore_id}")
        except Exception as e:
            logger.warning(f"⚠️  Error deleting vectors: {e}")
        
        # Get website from sources
        website = None
        sources = kb.get("sources", [])
        for source in sources:
            if source.get("type") == "website" and source.get("url"):
                website = source["url"]
                break
        
        # Rebuild with correct embeddings
        logger.info(f"📤 Rebuilding knowledge base with LangChain embeddings...")
        result = await build_knowledge_base_auto(
            user_id=user_id,
            organization_id=organization_id,
            company_name=company_name,
            website=website
        )
        
        return {
            "success": True,
            "message": "Knowledge base rebuilt successfully with correct embeddings",
            "knowledgeBase": {
                "id": str(result["_id"]),
                "companyName": result.get("companyName"),
                "vectorStoreId": result.get("vectorStoreId"),
                "totalChunks": len(result.get("aiChunks", [])),
                "status": result.get("status")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rebuilding knowledge base: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
