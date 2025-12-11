"""
Knowledge Base Routes - FastAPI Implementation
Handles all knowledge base CRUD operations and queries
No authentication required - uses userId and organizationId from request body
Uses OpenAI web search tools for automatic information gathering
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId
import logging

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
    query_vector_db
)

from models.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    Source
)

router = APIRouter(prefix="/api/knowledge-base", tags=["Knowledge Base"])
logger = logging.getLogger(__name__)


# ==========================================
# REQUEST/RESPONSE MODELS
# ==========================================

class CheckKnowledgeBaseRequest(BaseModel):
    user_id: str = Field(alias="userId")
    organization_id: str = Field(alias="organizationId")

    class Config:
        populate_by_name = True


class CreateKnowledgeBaseRequest(BaseModel):
    user_id: str = Field(alias="userId")
    organization_id: str = Field(alias="organizationId")
    company_name: str = Field(alias="companyName")
    website: Optional[str] = None  # Optional website URL for automatic scraping
    sources: Optional[List[Dict[str, Any]]] = None  # Optional manual sources
    structured_data: Optional[Dict[str, Any]] = Field(None, alias="structuredData")
    raw_content: Optional[str] = Field(None, alias="rawContent")

    class Config:
        populate_by_name = True


class UpdateKnowledgeBaseRequest(BaseModel):
    user_id: str = Field(alias="userId")
    organization_id: str = Field(alias="organizationId")
    sources: Optional[List[Dict[str, Any]]] = None
    structured_data: Optional[Dict[str, Any]] = Field(None, alias="structuredData")
    raw_content: Optional[str] = Field(None, alias="rawContent")
    vector_store_id: Optional[str] = Field(None, alias="vectorStoreId")
    file_ids: Optional[List[str]] = Field(None, alias="fileIds")
    status: Optional[str] = None

    class Config:
        populate_by_name = True


class QueryKnowledgeBaseRequest(BaseModel):
    user_id: str = Field(alias="userId")
    organization_id: str = Field(alias="organizationId")
    query: str
    top_k: int = Field(default=5, alias="topK")

    class Config:
        populate_by_name = True


class DeleteKnowledgeBaseRequest(BaseModel):
    user_id: str = Field(alias="userId")
    organization_id: str = Field(alias="organizationId")

    class Config:
        populate_by_name = True


# ==========================================
# KNOWLEDGE BASE CHECK
# ==========================================

@router.get("/check")
async def check_knowledge_base(
    user_id: str,
    organization_id: str
):
    """
    GET /api/knowledge-base/check
    Check if user has existing knowledge base
    - Uses user_id and organization_id from query params
    - Returns knowledge base status and quality
    """
    try:
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
async def create_knowledge_base(request: CreateKnowledgeBaseRequest):
    """
    POST /api/knowledge-base/
    Create new knowledge base with automatic information gathering
    
    - Provide: userId, organizationId, companyName, website (optional)
    - Automatically scrapes website
    - Performs intelligent web search using OpenAI
    - Extracts structured data
    - Stores in MongoDB
    - Returns quality score and structured information
    
    Example:
    {
      "userId": "675939fc72c39392b8e7ad51",
      "organizationId": "675939fc72c39392b8e7ad52",
      "companyName": "Carter Injury Law",
      "website": "https://carterinjurylaw.com"
    }
    """
    try:
        logger.info(f"🚀 Creating knowledge base for {request.company_name}")
        
        # Check if already exists
        existing = await check_knowledge_base_exists(request.user_id, request.organization_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base already exists. Use update endpoint instead."
            )
        
        # Build knowledge base automatically using OpenAI web search
        kb = await build_knowledge_base_auto(
            user_id=request.user_id,
            organization_id=request.organization_id,
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
    user_id: str,
    organization_id: str
):
    """
    GET /api/knowledge-base/
    Get knowledge base for user
    - Uses user_id and organization_id from query params
    - Retrieves from MongoDB
    """
    try:
        kb = await get_knowledge_base(user_id, organization_id)
        
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # Convert ObjectId to string for JSON serialization
        kb["_id"] = str(kb["_id"])
        kb["userId"] = str(kb["userId"])
        if "organizationId" in kb:
            kb["organizationId"] = str(kb["organizationId"])
        
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
async def update_knowledge_base_data(request: UpdateKnowledgeBaseRequest):
    """
    PUT /api/knowledge-base/
    Update existing knowledge base
    - Uses user_id and organization_id from request body
    - Adds new sources
    - Re-indexes in Pinecone (optional)
    - Updates MongoDB
    """
    try:
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
            user_id=request.user_id,
            organization_id=request.organization_id,
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
async def delete_knowledge_base_data(request: DeleteKnowledgeBaseRequest):
    """
    DELETE /api/knowledge-base/
    Delete knowledge base
    - Uses user_id and organization_id from request body
    - Removes from Pinecone (optional)
    - Archives in MongoDB
    """
    try:
        success = await delete_knowledge_base(request.user_id, request.organization_id)
        
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
async def query_knowledge_base_search(request: QueryKnowledgeBaseRequest):
    """
    POST /api/knowledge-base/query
    Query knowledge base with semantic search
    - Uses user_id and organization_id from request body
    - Searches Pinecone vectors (optional)
    - Returns relevant chunks
    """
    try:
        results = await query_knowledge_base(
            user_id=request.user_id,
            organization_id=request.organization_id,
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


@router.get("/stats")
async def get_knowledge_base_statistics(
    user_id: str,
    organization_id: str
):
    """
    GET /api/knowledge-base/stats
    Get knowledge base statistics
    - Uses user_id and organization_id from query params
    - Returns metrics about sources, quality, version history
    """
    try:
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
    user_id: str,
    organization_id: str,
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
    user_id: str,
    organization_id: str
):
    """
    GET /api/knowledge-base/chatbot/context
    Get complete formatted context for AI assistant
    
    - Returns all knowledge in conversational format
    - Ready to pass as system message to AI
    - Optimized for chatbot understanding
    """
    try:
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
    organization_id: str,
    query: str,
    top_k: int = 5
):
    """
    Search knowledge base using vector similarity (Pinecone)
    
    - Converts query to embedding
    - Searches Pinecone for similar content
    - Returns top_k most relevant chunks
    - Includes similarity scores
    """
    try:
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
