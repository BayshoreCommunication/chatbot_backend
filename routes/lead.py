from fastapi import APIRouter, Request, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid
from services.database import create_lead, get_leads_by_organization, search_leads
from services.database import get_organization_by_api_key

# Load environment variables
load_dotenv()

router = APIRouter()

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Resolve organization using X-API-Key header (same pattern as unknown_questions routes)."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return organization

class Lead(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    inquiry: str
    source: Optional[str] = "chatbot"
    timestamp: Optional[str] = None
    lead_id: Optional[str] = None
    status: Optional[str] = "new"
    organization_id: Optional[str] = None
    session_id: Optional[str] = None

class LeadResponse(BaseModel):
    lead_id: str
    status: str
    message: str

class LeadSearchParams(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None

# Simple auth check for admin endpoints (in real app, use proper auth)
async def check_admin_auth(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {os.getenv('ADMIN_API_KEY', 'admin-secret-key')}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

@router.get("/leads-list-byorg")
async def leads_list_byorg(
    organization_id: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    organization=Depends(get_organization_from_api_key)
):
    """List leads for a single organization (user dashboard).
    Organization is resolved by explicit organization_id or by X-API-Key header.
    """
    try:
        org_id = organization_id or (organization["id"] if "id" in organization else str(organization.get("_id")))
        
        # Paginated/sorted list by organization
        leads_list = get_leads_by_organization(org_id, limit=limit, skip=skip)
        return {"organization_id": org_id, "leads": leads_list}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing organization leads: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list organization leads")

@router.get("/leads-list-all")
async def leads_list_all(organization_id: Optional[str] = None, group_by_org: Optional[bool] = False, _=Depends(check_admin_auth)):
    """Admin: list leads. If organization_id provided, returns that org; otherwise returns all.
    Optionally group results by organization.
    """
    try:
        from services.database import leads as leads_col
        if organization_id:
            leads_list = get_leads_by_organization(organization_id)
            return {"organization_id": organization_id, "leads": leads_list}
        
        cursor = leads_col.find({}).sort("timestamp", -1).limit(1000)
        all_leads = []
        for lead in cursor:
            if "_id" in lead:
                lead["_id"] = str(lead["_id"])
            if "timestamp" in lead and isinstance(lead["timestamp"], datetime):
                lead["timestamp"] = lead["timestamp"].isoformat()
            if "created_at" in lead and isinstance(lead["created_at"], datetime):
                lead["created_at"] = lead["created_at"].isoformat()
            if "updated_at" in lead and isinstance(lead["updated_at"], datetime):
                lead["updated_at"] = lead["updated_at"].isoformat()
            all_leads.append(lead)
        
        if group_by_org:
            grouped = {}
            for ld in all_leads:
                oid = ld.get("organization_id", "unknown")
                grouped.setdefault(oid, []).append(ld)
            return {"leads_by_organization": grouped}
        
        return {"leads": all_leads}
    except Exception as e:
        print(f"Error listing admin leads: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list leads")

@router.post("/search")
async def search_leads_endpoint(params: LeadSearchParams, organization_id: Optional[str] = None, _=Depends(check_admin_auth)):
    """Search leads by criteria (admin only)"""
    try:
        if not organization_id:
            raise HTTPException(status_code=400, detail="organization_id parameter is required")
            
        results = search_leads(
            organization_id=organization_id,
            name=params.name,
            email=params.email,
            status=params.status,
            date_from=params.date_from,
            date_to=params.date_to
        )
        
        return {"leads": results}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error searching leads: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search leads")