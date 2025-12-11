"""
Knowledge Base Service - Python FastAPI Implementation
Handles knowledge base CRUD operations with MongoDB and OpenAI integration
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from services.database import db
from models.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseInDB,
    Source,
    Metadata,
    UpdateHistory
)

logger = logging.getLogger(__name__)

# MongoDB collection
knowledge_bases = db.knowledge_bases


async def check_knowledge_base_exists(user_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if knowledge base exists for user/organization
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        
    Returns:
        Knowledge base document or None
    """
    try:
        kb = knowledge_bases.find_one({
            "userId": ObjectId(user_id),
            "status": {"$ne": "archived"}
        })
        return kb
    except Exception as e:
        logger.error(f"Error checking knowledge base: {e}")
        return None


async def create_knowledge_base(
    user_id: str,
    organization_id: str,
    company_name: str,
    sources: List[Dict[str, Any]],
    structured_data: Optional[Dict[str, Any]] = None,
    raw_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create new knowledge base
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        company_name: Company name
        sources: List of knowledge sources
        structured_data: Structured company data
        raw_content: Raw text content
        
    Returns:
        Created knowledge base document
    """
    try:
        now = datetime.now()
        
        kb_data = {
            "userId": ObjectId(user_id),
            "organizationId": ObjectId(organization_id),
            "companyName": company_name,
            "sources": sources,
            "structuredData": structured_data or {},
            "rawContent": raw_content or "",
            "vectorStoreId": None,
            "fileIds": [],
            "metadata": {
                "totalSources": len(sources),
                "lastUpdated": now,
                "version": 1,
                "model": "gpt-4",
                "tokenCount": 0,
                "quality": "medium",
                "qualityPercentage": 0.0,
                "updateHistory": []
            },
            "status": "processing",
            "createdAt": now,
            "updatedAt": now
        }
        
        result = knowledge_bases.insert_one(kb_data)
        kb_data["_id"] = result.inserted_id
        
        logger.info(f"✅ Created knowledge base for user {user_id}: {result.inserted_id}")
        return kb_data
        
    except Exception as e:
        logger.error(f"Error creating knowledge base: {e}")
        raise


async def get_knowledge_base(user_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
    """
    Get knowledge base for user/organization
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        
    Returns:
        Knowledge base document or None
    """
    try:
        kb = knowledge_bases.find_one({
            "userId": ObjectId(user_id),
            "status": {"$ne": "archived"}
        })
        return kb
    except Exception as e:
        logger.error(f"Error getting knowledge base: {e}")
        return None


async def update_knowledge_base(
    user_id: str,
    organization_id: str,
    update_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Update existing knowledge base
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        update_data: Fields to update
        
    Returns:
        Updated knowledge base document or None
    """
    try:
        # Get existing KB
        kb = await get_knowledge_base(user_id, organization_id)
        if not kb:
            return None
        
        now = datetime.now()
        
        # Prepare update
        update_dict = {"updatedAt": now}
        
        # Handle sources update
        if "sources" in update_data:
            new_sources = update_data["sources"]
            existing_sources = kb.get("sources", [])
            update_dict["sources"] = existing_sources + new_sources
            
        # Handle other fields
        if "structuredData" in update_data:
            update_dict["structuredData"] = update_data["structuredData"]
        if "rawContent" in update_data:
            update_dict["rawContent"] = update_data["rawContent"]
        if "vectorStoreId" in update_data:
            update_dict["vectorStoreId"] = update_data["vectorStoreId"]
        if "fileIds" in update_data:
            update_dict["fileIds"] = update_data["fileIds"]
        if "status" in update_data:
            update_dict["status"] = update_data["status"]
            
        # Update metadata
        metadata = kb.get("metadata", {})
        old_version = metadata.get("version", 1)
        new_version = old_version + 1
        
        # Add to update history
        update_history = metadata.get("updateHistory", [])
        update_history.append({
            "version": new_version,
            "updatedAt": now,
            "totalSources": len(update_dict.get("sources", kb.get("sources", []))),
            "quality": metadata.get("quality", "medium"),
            "qualityPercentage": metadata.get("qualityPercentage", 0.0),
            "changes": f"Updated knowledge base with {len(update_data.get('sources', []))} new sources"
        })
        
        update_dict["metadata"] = {
            **metadata,
            "lastUpdated": now,
            "version": new_version,
            "totalSources": len(update_dict.get("sources", kb.get("sources", []))),
            "updateHistory": update_history
        }
        
        # Perform update
        result = knowledge_bases.find_one_and_update(
            {"_id": kb["_id"]},
            {"$set": update_dict},
            return_document=True
        )
        
        logger.info(f"✅ Updated knowledge base {kb['_id']} to version {new_version}")
        return result
        
    except Exception as e:
        logger.error(f"Error updating knowledge base: {e}")
        raise


async def delete_knowledge_base(user_id: str, organization_id: str) -> bool:
    """
    Delete (archive) knowledge base
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        result = knowledge_bases.update_one(
            {
                "userId": ObjectId(user_id),
                "status": {"$ne": "archived"}
            },
            {
                "$set": {
                    "status": "archived",
                    "updatedAt": datetime.now()
                }
            }
        )
        
        success = result.modified_count > 0
        if success:
            logger.info(f"✅ Archived knowledge base for user {user_id}")
        return success
        
    except Exception as e:
        logger.error(f"Error deleting knowledge base: {e}")
        return False


async def query_knowledge_base(
    user_id: str,
    organization_id: str,
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Query knowledge base with semantic search
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        query: Search query
        top_k: Number of results to return
        
    Returns:
        List of relevant content chunks
    """
    try:
        kb = await get_knowledge_base(user_id, organization_id)
        if not kb:
            return []
        
        # For now, return raw content - you can integrate Pinecone/vector search here
        sources = kb.get("sources", [])
        results = []
        
        for source in sources[:top_k]:
            results.append({
                "content": source.get("content", ""),
                "type": source.get("type", ""),
                "url": source.get("url"),
                "score": 0.9  # Placeholder - use actual vector similarity
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error querying knowledge base: {e}")
        return []


async def get_knowledge_base_stats(user_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
    """
    Get knowledge base statistics
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        
    Returns:
        Statistics dictionary or None
    """
    try:
        kb = await get_knowledge_base(user_id, organization_id)
        if not kb:
            return None
        
        metadata = kb.get("metadata", {})
        
        return {
            "knowledgeBase": {
                "id": str(kb["_id"]),
                "companyName": kb.get("companyName"),
                "status": kb.get("status"),
                "createdAt": kb.get("createdAt").isoformat() if kb.get("createdAt") else None,
            },
            "sources": {
                "total": metadata.get("totalSources", 0),
                "breakdown": _get_source_breakdown(kb.get("sources", []))
            },
            "quality": {
                "rating": metadata.get("quality", "medium"),
                "percentage": metadata.get("qualityPercentage", 0.0)
            },
            "metadata": {
                "version": metadata.get("version", 1),
                "lastUpdated": metadata.get("lastUpdated").isoformat() if metadata.get("lastUpdated") else None,
                "model": metadata.get("model", "gpt-4"),
                "tokenCount": metadata.get("tokenCount", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting knowledge base stats: {e}")
        return None


def _get_source_breakdown(sources: List[Dict[str, Any]]) -> Dict[str, int]:
    """Get breakdown of source types"""
    breakdown = {"website": 0, "web_search": 0, "manual": 0, "document": 0}
    for source in sources:
        source_type = source.get("type", "manual")
        breakdown[source_type] = breakdown.get(source_type, 0) + 1
    return breakdown
