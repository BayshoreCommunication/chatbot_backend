from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid
from services.database import create_lead, get_leads_by_organization, search_leads

# Load environment variables
load_dotenv()

router = APIRouter()

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

@router.post("/submit")
async def submit_lead(lead: Lead):
    """Submit a new lead"""
    try:
        # Ensure we have required organization_id
        if not lead.organization_id:
            raise HTTPException(status_code=400, detail="organization_id is required")
        
        # Create lead in MongoDB
        created_lead = create_lead(
            organization_id=lead.organization_id,
            session_id=lead.session_id or str(uuid.uuid4()),
            name=lead.name,
            email=lead.email,
            phone=lead.phone,
            inquiry=lead.inquiry,
            source=lead.source
        )
        
        return LeadResponse(
            lead_id=created_lead["lead_id"],
            status="success",
            message="Lead submitted successfully"
        )
    except Exception as e:
        print(f"Error submitting lead: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit lead")

@router.get("/list")
async def list_leads(organization_id: Optional[str] = None, _=Depends(check_admin_auth)):
    """List all leads (admin only)"""
    try:
        if organization_id:
            # Get leads for specific organization
            leads_list = get_leads_by_organization(organization_id)
        else:
            # For admin dashboard, get all leads from all organizations
            from services.database import leads
            cursor = leads.find({}).sort("timestamp", -1).limit(100)
            
            leads_list = []
            for lead in cursor:
                # Convert ObjectId to string for JSON serialization
                if "_id" in lead:
                    lead["_id"] = str(lead["_id"])
                # Convert datetime to ISO string
                if "timestamp" in lead and isinstance(lead["timestamp"], datetime):
                    lead["timestamp"] = lead["timestamp"].isoformat()
                if "created_at" in lead and isinstance(lead["created_at"], datetime):
                    lead["created_at"] = lead["created_at"].isoformat()
                if "updated_at" in lead and isinstance(lead["updated_at"], datetime):
                    lead["updated_at"] = lead["updated_at"].isoformat()
                leads_list.append(lead)
        
        return {"leads": leads_list}
    except Exception as e:
        print(f"Error listing leads: {str(e)}")
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