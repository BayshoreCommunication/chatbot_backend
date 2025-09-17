from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid

# Load environment variables
load_dotenv()

router = APIRouter()

# Mock database for leads (in a real app, use an actual database)
lead_database = []

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

# Simple auth check for admin endpoints (in real app, use proper auth)
async def check_admin_auth(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {os.getenv('ADMIN_API_KEY', 'admin-secret-key')}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

@router.post("/submit")
async def submit_lead(lead: Lead):
    """Submit a new lead"""
    # Generate timestamp and ID
    lead.timestamp = datetime.now().isoformat()
    lead.lead_id = str(uuid.uuid4())
    
    # Save to "database"
    lead_database.append(lead.dict())
    
    # In a real application, you would:
    # 1. Save to database
    # 2. Send notifications
    # 3. Integrate with CRM systems
    
    return LeadResponse(
        lead_id=lead.lead_id,
        status="success",
        message="Lead submitted successfully"
    )

@router.get("/list")
async def list_leads(_=Depends(check_admin_auth)):
    """List all leads (admin only)"""
    return {"leads": lead_database}

@router.post("/search")
async def search_leads(params: LeadSearchParams, _=Depends(check_admin_auth)):
    """Search leads by criteria (admin only)"""
    results = lead_database.copy()
    
    # Filter based on params
    if params.name:
        results = [lead for lead in results if params.name.lower() in lead["name"].lower()]
    
    if params.email:
        results = [lead for lead in results if params.email.lower() in lead["email"].lower()]
    
    if params.status:
        results = [lead for lead in results if lead["status"] == params.status]
    
    if params.date_from:
        date_from = datetime.fromisoformat(params.date_from)
        results = [lead for lead in results if datetime.fromisoformat(lead["timestamp"]) >= date_from]
    
    if params.date_to:
        date_to = datetime.fromisoformat(params.date_to)
        results = [lead for lead in results if datetime.fromisoformat(lead["timestamp"]) <= date_to]
    
    return {"leads": results}