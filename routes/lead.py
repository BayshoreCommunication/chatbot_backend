from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
import pymongo
import os
from dotenv import load_dotenv
from services.notification import send_email_notification
from email_validator import validate_email, EmailNotValidError
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import json

# Optional CRM integrations
try:
    from hubspot import HubSpot
    HUBSPOT_AVAILABLE = True
except ImportError:
    HUBSPOT_AVAILABLE = False

try:
    from mailchimp3 import MailChimp
    MAILCHIMP_AVAILABLE = True
except ImportError:
    MAILCHIMP_AVAILABLE = False

load_dotenv()

router = APIRouter()
client = pymongo.MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client["chatbotDB"]
leads = db["leads"]

class LeadModel(BaseModel):
    name: str
    email: EmailStr
    phone: str
    inquiry: str
    source: Optional[str] = "chatbot"
    notes: Optional[str] = None
    
def validate_lead_data(data):
    """Validate lead data and return a cleaned version"""
    errors = []
    
    # Validate name
    if not data.get("name"):
        errors.append("Name is required")
    
    # Validate email
    try:
        if data.get("email"):
            valid = validate_email(data["email"])
            data["email"] = valid.normalized
        else:
            errors.append("Email is required")
    except EmailNotValidError:
        errors.append("Invalid email address")
    
    # Validate phone (basic validation)
    if not data.get("phone"):
        errors.append("Phone number is required")
    
    # Validate inquiry
    if not data.get("inquiry"):
        errors.append("Inquiry is required")
    
    if errors:
        return {"valid": False, "errors": errors}
    
    return {"valid": True, "data": data}

def add_to_hubspot(lead_data):
    """Add lead to HubSpot if available"""
    if not HUBSPOT_AVAILABLE:
        return {"status": "skipped", "message": "HubSpot integration not available"}
    
    try:
        hubspot_api_key = os.getenv("HUBSPOT_API_KEY")
        if not hubspot_api_key:
            return {"status": "skipped", "message": "HubSpot API key not set"}
        
        hubspot = HubSpot(api_key=hubspot_api_key)
        
        # Create a contact in HubSpot
        contact_data = {
            "email": lead_data["email"],
            "firstname": lead_data["name"].split(" ")[0],
            "lastname": lead_data["name"].split(" ")[-1] if len(lead_data["name"].split(" ")) > 1 else "",
            "phone": lead_data["phone"],
            "message": lead_data["inquiry"]
        }
        
        hubspot.crm.contacts.basic_api.create(contact_data)
        
        return {"status": "success", "message": "Lead added to HubSpot"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def add_to_mailchimp(lead_data):
    """Add lead to Mailchimp if available"""
    if not MAILCHIMP_AVAILABLE:
        return {"status": "skipped", "message": "Mailchimp integration not available"}
    
    try:
        mailchimp_api_key = os.getenv("MAILCHIMP_API_KEY")
        mailchimp_list_id = os.getenv("MAILCHIMP_LIST_ID")
        
        if not mailchimp_api_key or not mailchimp_list_id:
            return {"status": "skipped", "message": "Mailchimp credentials not set"}
        
        client = MailChimp(mc_api=mailchimp_api_key)
        
        # Add subscriber to list
        client.lists.members.create(mailchimp_list_id, {
            'email_address': lead_data["email"],
            'status': 'subscribed',
            'merge_fields': {
                'FNAME': lead_data["name"].split(" ")[0],
                'LNAME': lead_data["name"].split(" ")[-1] if len(lead_data["name"].split(" ")) > 1 else "",
                'PHONE': lead_data["phone"]
            },
        })
        
        return {"status": "success", "message": "Lead added to Mailchimp"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def process_lead(lead_data):
    """Process a lead with all integrations"""
    # Store lead in MongoDB
    lead_id = leads.insert_one(lead_data).inserted_id
    
    # Send email notification
    send_email_notification(
        "New Lead Captured", 
        f"Name: {lead_data['name']}\nEmail: {lead_data['email']}\nPhone: {lead_data['phone']}\nInquiry: {lead_data['inquiry']}"
    )
    
    # Add to CRM systems if configured
    crm_results = {
        "hubspot": add_to_hubspot(lead_data),
        "mailchimp": add_to_mailchimp(lead_data)
    }
    
    return {
        "lead_id": str(lead_id),
        "integrations": crm_results
    }

@router.post("/submit")
async def submit_lead(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    
    # Validate lead data
    validation = validate_lead_data(data)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail={"errors": validation["errors"]})
    
    # Process lead in background
    background_tasks.add_task(process_lead, validation["data"])
    
    return {"status": "success", "message": "Lead submitted successfully"}

@router.get("/list")
async def list_leads():
    """List all leads (admin only in a real app)"""
    all_leads = list(leads.find({}, {"_id": 0}))
    return {"leads": all_leads}

@router.post("/search")
async def search_leads(request: Request):
    """Search leads by any field"""
    data = await request.json()
    query = data.get("query", {})
    
    if not query:
        raise HTTPException(status_code=400, detail="Search query is required")
    
    results = list(leads.find(query, {"_id": 0}))
    return {"results": results}