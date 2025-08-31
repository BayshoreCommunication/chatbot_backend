from fastapi import APIRouter, Request, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid
import logging
from services.database import get_organization_by_api_key, db, get_user_profile

# Load environment variables
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)

class Lead(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    inquiry: str
    source: Optional[str] = "chatbot"
    timestamp: Optional[str] = None
    lead_id: Optional[str] = None
    status: Optional[str] = "new"

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

class LeadResponse(BaseModel):
    name: str
    email: str
    session_id: str
    created_at: datetime
    organization_id: str

class LeadsResponse(BaseModel):
    leads: List[LeadResponse]
    total_count: int

async def get_org_from_api_key(api_key: str = Header(..., alias="X-API-Key")):
    """Get organization from API key"""
    org = get_organization_by_api_key(api_key)
    if not org:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return org

# Simple auth check for admin endpoints (in real app, use proper auth)
async def check_admin_auth(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {os.getenv('ADMIN_API_KEY', 'admin-secret-key')}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

@router.get("/leads", response_model=LeadsResponse)
async def get_all_leads(org: Dict[str, Any] = Depends(get_org_from_api_key)):
    """
    Get all leads (name and email) for an organization
    This endpoint retrieves all stored leads from user profiles
    """
    try:
        org_id = org["id"]
        
        # Get all user profiles for this organization
        user_profiles = db.user_profiles.find({
            "organization_id": org_id
        }).sort("created_at", -1)  # Sort by creation date, newest first
        
        leads = []
        for profile in user_profiles:
            profile_data = profile.get("profile_data", {})
            name = profile_data.get("name", "Unknown")
            email = profile_data.get("email", "No email")
            
            # Skip leads without proper contact info
            if name in ["Anonymous User", "Guest User", "Unknown"] or email in ["anonymous@user.com", "No email"]:
                continue
                
            lead = LeadResponse(
                name=name,
                email=email,
                session_id=profile.get("session_id", ""),
                created_at=profile.get("created_at", datetime.now()),
                organization_id=org_id
            )
            leads.append(lead)
        
        return LeadsResponse(
            leads=leads,
            total_count=len(leads)
        )
        
    except Exception as e:
        logger.error(f"Error retrieving leads: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/leads/{session_id}", response_model=LeadResponse)
async def get_lead_by_session(
    session_id: str,
    org: Dict[str, Any] = Depends(get_org_from_api_key)
):
    """
    Get a specific lead by session ID
    """
    try:
        org_id = org["id"]
        
        # Get user profile for this session
        profile = get_user_profile(org_id, session_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        profile_data = profile.get("profile_data", {})
        name = profile_data.get("name", "Unknown")
        email = profile_data.get("email", "No email")
        
        return LeadResponse(
            name=name,
            email=email,
            session_id=session_id,
            created_at=profile.get("created_at", datetime.now()),
            organization_id=org_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving lead: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/leads/stats")
async def get_leads_stats(org: Dict[str, Any] = Depends(get_org_from_api_key)):
    """
    Get leads statistics for an organization
    """
    try:
        org_id = org["id"]
        
        # Get all user profiles for this organization
        user_profiles = list(db.user_profiles.find({"organization_id": org_id}))
        
        total_profiles = len(user_profiles)
        valid_leads = 0
        leads_with_email = 0
        leads_with_name = 0
        
        for profile in user_profiles:
            profile_data = profile.get("profile_data", {})
            name = profile_data.get("name", "")
            email = profile_data.get("email", "")
            
            if name and name not in ["Anonymous User", "Guest User", "Unknown"]:
                leads_with_name += 1
                
            if email and email not in ["anonymous@user.com", "No email"]:
                leads_with_email += 1
                
            if (name and name not in ["Anonymous User", "Guest User", "Unknown"] and 
                email and email not in ["anonymous@user.com", "No email"]):
                valid_leads += 1
        
        return {
            "total_profiles": total_profiles,
            "valid_leads": valid_leads,
            "leads_with_email": leads_with_email,
            "leads_with_name": leads_with_name,
            "organization_id": org_id
        }
        
    except Exception as e:
        logger.error(f"Error retrieving leads stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Keep the original submit endpoint for backward compatibility
@router.post("/submit")
async def submit_lead(lead: Lead):
    """Submit a new lead (legacy endpoint)"""
    # Generate timestamp and ID
    lead.timestamp = datetime.now().isoformat()
    lead.lead_id = str(uuid.uuid4())
    
    # In a real application, you would save to database
    # For now, we'll just return success
    return {
        "lead_id": lead.lead_id,
        "status": "success",
        "message": "Lead submitted successfully"
    }