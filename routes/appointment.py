from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from services.langchain.appointments import get_available_slots
import json
import os
from datetime import datetime

router = APIRouter()

class AppointmentSlot(BaseModel):
    id: str
    date: str
    time: str
    available: bool

class BookingRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    service: str
    slot_id: str
    date: str
    time: str
    notes: Optional[str] = None

@router.get("/available-slots")
async def get_slots():
    """Get available appointment slots"""
    # Get the formatted slots string from the engine
    slots_text = get_available_slots()
    
    # Parse the formatted text into actual slot objects
    import re
    import datetime
    
    slots = []
    lines = slots_text.strip().split('\n')
    
    # Skip the header line
    for line in lines[2:]:  # Skip first two lines (title and blank line)
        if line:
            # Parse the line in format "• YYYY-MM-DD at HH:MM (ID: slot_id)"
            match = re.match(r'• (\d{4}-\d{2}-\d{2}) at (\d{1,2}:\d{2}) \(ID: (.*?)\)', line)
            if match:
                date_str, time_str, slot_id = match.groups()
                slots.append({
                    "id": slot_id,
                    "date": date_str,
                    "time": time_str,
                    "available": True
                })
    
    return {"slots": slots}

@router.post("/book")
async def book_appointment(request: BookingRequest):
    """Book an appointment"""
    # In a real application, you would:
    # 1. Check if the slot is still available
    # 2. Create the appointment in your calendar system
    # 3. Update the slot to be unavailable
    # 4. Send confirmation email
    
    # For demo purposes, we'll just return success
    booking_info = {
        "name": request.name,
        "email": request.email,
        "phone": request.phone,
        "service": request.service,
        "slot_id": request.slot_id,
        "date": request.date,
        "time": request.time,
        "booking_reference": f"BOOK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "status": "confirmed"
    }
    
    return {
        "status": "success",
        "message": "Appointment booked successfully",
        "booking_info": booking_info
    }

@router.get("/services")
async def get_services():
    """Get available service types"""
    # In a real application, fetch from database
    # For demo purposes, return mock data
    services = [
        {"id": "legal_consultation", "name": "Legal Consultation", "duration": 60, "price": 200},
        {"id": "document_review", "name": "Document Review", "duration": 30, "price": 100},
        {"id": "case_evaluation", "name": "Case Evaluation", "duration": 90, "price": 300},
        {"id": "will_testament", "name": "Will & Testament", "duration": 60, "price": 250},
    ]
    
    return {"services": services} 