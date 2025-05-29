from fastapi import APIRouter, HTTPException, Depends, Body, Header
from services.database import db, get_organization_by_api_key
from typing import Optional, List
from pydantic import BaseModel
import pymongo
from bson.errors import InvalidId
from bson.objectid import ObjectId
from datetime import datetime

router = APIRouter()

# Initialize FAQ collection and indexes
faq_collection = db.faqs
faq_collection.create_index("org_id")
faq_collection.create_index([("org_id", pymongo.ASCENDING), ("is_active", pymongo.ASCENDING)])

class FAQItem(BaseModel):
    question: str
    response: str
    is_active: bool = True
    persistent_menu: bool = False

class FAQResponse(BaseModel):
    id: Optional[str]
    question: str
    response: str
    is_active: bool
    persistent_menu: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

async def get_organization_from_api_key(api_key: str = Header(..., alias="X-API-Key")):
    """Dependency to get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

@router.post("/create", response_model=FAQResponse)
async def create_faq(
    faq: FAQItem,
    organization=Depends(get_organization_from_api_key)
):
    """Create a new FAQ item"""
    org_id = organization["id"]
    
    faq_data = {
        "org_id": org_id,
        "question": faq.question,
        "response": faq.response,
        "is_active": faq.is_active,
        "persistent_menu": faq.persistent_menu,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = faq_collection.insert_one(faq_data)
    
    if result.inserted_id:
        faq_data["id"] = str(result.inserted_id)
        return faq_data
    
    raise HTTPException(status_code=500, detail="Failed to create FAQ")

@router.get("/list", response_model=List[FAQResponse])
async def list_faqs(
    organization=Depends(get_organization_from_api_key),
    active_only: bool = False
):
    """List all FAQs for an organization"""
    org_id = organization["id"]
    
    query = {"org_id": org_id}
    if active_only:
        query["is_active"] = True
    
    faqs = []
    for faq in faq_collection.find(query):
        faq["id"] = str(faq.pop("_id"))
        faqs.append(faq)
    
    return faqs

@router.get("/{faq_id}", response_model=FAQResponse)
async def get_faq(
    faq_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Get a specific FAQ by ID"""
    org_id = organization["id"]
    
    try:
        faq = faq_collection.find_one({
            "_id": ObjectId(faq_id),
            "org_id": org_id
        })
    except:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    faq["id"] = str(faq.pop("_id"))
    return faq

@router.put("/{faq_id}", response_model=FAQResponse)
async def update_faq(
    faq_id: str,
    faq: FAQItem,
    organization=Depends(get_organization_from_api_key)
):
    """Update an existing FAQ"""
    org_id = organization["id"]
    
    try:
        # First verify if the FAQ exists and belongs to this org
        existing_faq = faq_collection.find_one({
            "_id": ObjectId(faq_id),
            "org_id": org_id
        })
        
        if not existing_faq:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        update_data = {
            "question": faq.question,
            "response": faq.response,
            "is_active": faq.is_active,
            "persistent_menu": faq.persistent_menu,
            "updated_at": datetime.utcnow()
        }
        
        result = faq_collection.find_one_and_update(
            {
                "_id": ObjectId(faq_id),
                "org_id": org_id
            },
            {"$set": update_data},
            return_document=pymongo.ReturnDocument.AFTER
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update FAQ")
        
        result["id"] = str(result.pop("_id"))
        return result
        
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid FAQ ID format")
    except Exception as e:
        print(f"Error updating FAQ: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{faq_id}")
async def delete_faq(
    faq_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Delete a FAQ"""
    org_id = organization["id"]
    
    try:
        result = faq_collection.delete_one({
            "_id": ObjectId(faq_id),
            "org_id": org_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        return {"status": "success", "message": "FAQ deleted successfully"}
        
    except:
        raise HTTPException(status_code=404, detail="FAQ not found")

@router.put("/{faq_id}/toggle", response_model=FAQResponse)
async def toggle_faq(
    faq_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Toggle FAQ active status"""
    org_id = organization["id"]
    
    try:
        # First verify if the FAQ exists and belongs to this org
        faq = faq_collection.find_one({
            "_id": ObjectId(faq_id),
            "org_id": org_id
        })
        
        if not faq:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        # Toggle the is_active status
        new_status = not faq.get("is_active", True)
        
        result = faq_collection.find_one_and_update(
            {
                "_id": ObjectId(faq_id),
                "org_id": org_id
            },
            {
                "$set": {
                    "is_active": new_status,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=pymongo.ReturnDocument.AFTER
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update FAQ status")
        
        result["id"] = str(result.pop("_id"))
        return result
        
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid FAQ ID format")
    except Exception as e:
        print(f"Error toggling FAQ status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 