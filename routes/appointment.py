from fastapi import APIRouter, Request, HTTPException
from services.calendar_integration import get_available_slots, book_appointment
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

router = APIRouter()

class AppointmentRequest(BaseModel):
    start_time: str
    end_time: str
    user_name: str
    user_email: EmailStr
    service_type: Optional[str] = "consultation"
    source: Optional[str] = None  # calendar source (google_calendar, calendly, etc.)

@router.get("/available-slots")
async def available_slots(days_ahead: int = 7, service_type: str = "consultation"):
    """Get available appointment slots"""
    slots = get_available_slots(days_ahead, service_type)
    
    # Format the response
    formatted_slots = []
    for slot in slots:
        # Parse ISO datetime into a more readable format
        start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
        
        formatted_slots.append({
            "id": f"{slot['source']}_{start_dt.strftime('%Y%m%d%H%M')}",
            "start": slot["start"],
            "end": slot["end"],
            "start_readable": start_dt.strftime("%A, %B %d, %Y at %I:%M %p"),
            "end_readable": end_dt.strftime("%I:%M %p"),
            "source": slot["source"]
        })
    
    return {"slots": formatted_slots}

@router.post("/book")
async def book(request: AppointmentRequest):
    """Book an appointment"""
    result = book_appointment(
        start_time=request.start_time,
        end_time=request.end_time,
        user_name=request.user_name,
        user_email=request.user_email,
        service_type=request.service_type,
        source=request.source
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to book appointment"))
    
    return result

@router.get("/services")
async def available_services():
    """List available service types for appointments"""
    # This could be loaded from a database in a real application
    services = [
        {"id": "consultation", "name": "General Consultation", "duration": 60},
        {"id": "onboarding", "name": "New Client Onboarding", "duration": 90},
        {"id": "follow_up", "name": "Follow-up Meeting", "duration": 30},
        {"id": "technical", "name": "Technical Support", "duration": 45}
    ]
    
    return {"services": services} 