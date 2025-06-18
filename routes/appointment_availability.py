from fastapi import APIRouter, Request, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
import pymongo
import requests
import json
import uuid
from services.database import get_organization_by_api_key, db

router = APIRouter()

# Initialize calendly settings collection
calendly_settings_collection = db.calendly_settings
calendly_settings_collection.create_index("organization_id", unique=True)

class CalendlySettings(BaseModel):
    calendly_url: Optional[str] = None
    calendly_access_token: str
    event_type_uri: Optional[str] = None
    auto_embed: Optional[bool] = True

class CalendlyTestConnectionRequest(BaseModel):
    access_token: str

class CalendlyEvent(BaseModel):
    uri: str
    name: str
    slug: str
    duration: int
    status: str
    booking_url: str

class AvailableSlot(BaseModel):
    start_time: str
    end_time: str
    scheduling_url: str

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

def make_calendly_api_request(endpoint: str, access_token: str, params: dict = None):
    """Make authenticated request to Calendly API"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(f'https://api.calendly.com/{endpoint}', headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Calendly API error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Calendly API error: {str(e)}")

@router.post("/calendly/settings")
async def save_calendly_settings(
    settings: CalendlySettings,
    organization=Depends(get_organization_from_api_key)
):
    """Save Calendly integration settings"""
    org_id = organization["id"]
    
    try:
        # Test the access token before saving
        user_data = make_calendly_api_request('users/me', settings.calendly_access_token)
        
        settings_data = {
            "organization_id": org_id,
            "calendly_url": settings.calendly_url,
            "calendly_access_token": settings.calendly_access_token,
            "event_type_uri": settings.event_type_uri,
            "auto_embed": settings.auto_embed,
            "user_uri": user_data.get('resource', {}).get('uri'),
            "updated_at": datetime.utcnow()
        }
        
        calendly_settings_collection.update_one(
            {"organization_id": org_id},
            {"$set": settings_data},
            upsert=True
        )
        
        return {
            "status": "success",
            "message": "Calendly settings saved successfully"
        }
        
    except Exception as e:
        print(f"Error saving Calendly settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendly/settings")
async def get_calendly_settings(
    organization=Depends(get_organization_from_api_key)
):
    """Get Calendly integration settings"""
    org_id = organization["id"]
    
    try:
        settings = calendly_settings_collection.find_one(
            {"organization_id": org_id},
            {"_id": 0}
        )
        
        if settings:
            # Don't expose the full access token in response
            safe_settings = {
                "calendly_url": settings.get("calendly_url"),
                "calendly_access_token": settings.get("calendly_access_token", ""),
                "event_type_uri": settings.get("event_type_uri"),
                "auto_embed": settings.get("auto_embed", True)
            }
            return {"settings": safe_settings}
        else:
            return {"settings": None}
            
    except Exception as e:
        print(f"Error getting Calendly settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calendly/test-connection")
async def test_calendly_connection(
    request: CalendlyTestConnectionRequest,
    organization=Depends(get_organization_from_api_key)
):
    """Test Calendly API connection"""
    try:
        user_data = make_calendly_api_request('users/me', request.access_token)
        
        return {
            "valid": True,
            "user": {
                "name": user_data.get('resource', {}).get('name'),
                "email": user_data.get('resource', {}).get('email'),
                "uri": user_data.get('resource', {}).get('uri')
            }
        }
        
    except HTTPException:
        return {"valid": False}
    except Exception as e:
        print(f"Error testing Calendly connection: {str(e)}")
        return {"valid": False}

@router.get("/calendly/events")
async def get_calendly_events(
    organization=Depends(get_organization_from_api_key)
):
    """Get user's event types from Calendly"""
    org_id = organization["id"]
    
    try:
        settings = calendly_settings_collection.find_one({"organization_id": org_id})
        if not settings or not settings.get("calendly_access_token"):
            raise HTTPException(status_code=400, detail="Calendly not configured")
        
        # Get user info first
        user_data = make_calendly_api_request('users/me', settings["calendly_access_token"])
        user_uri = user_data.get('resource', {}).get('uri')
        
        # Get event types
        event_types_data = make_calendly_api_request(
            'event_types',
            settings["calendly_access_token"],
            {'user': user_uri}
        )
        
        print(f"[CALENDLY EVENTS DEBUG] Raw event types data: {event_types_data}")
        
        events = []
        for event in event_types_data.get('collection', []):
            print(f"[CALENDLY EVENTS DEBUG] Processing event: {event}")
            events.append({
                "uri": event.get('uri'),
                "name": event.get('name'),
                "slug": event.get('slug'),
                "duration": event.get('duration'),
                "status": event.get('status'),
                "booking_url": event.get('scheduling_url')
            })
        
        print(f"[CALENDLY EVENTS DEBUG] Processed {len(events)} events")
        return {"events": events}
        
    except Exception as e:
        print(f"Error getting Calendly events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendly/availability")
async def get_calendly_availability(
    event_type_uri: str,
    organization=Depends(get_organization_from_api_key)
):
    """Get available time slots for a specific event type"""
    org_id = organization["id"]
    
    try:
        settings = calendly_settings_collection.find_one({"organization_id": org_id})
        if not settings or not settings.get("calendly_access_token"):
            raise HTTPException(status_code=400, detail="Calendly not configured")
        
        # Calculate date range - start from now + 30 seconds to ensure future time
        # and limit to 6 days 23 hours to stay under 7-day limit
        start_time = datetime.utcnow() + timedelta(seconds=30)
        end_time = start_time + timedelta(days=6, hours=23)
        
        # Format for Calendly API (ISO format with Z suffix)
        start_time_iso = start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        end_time_iso = end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        print(f"[CALENDLY] Requesting availability from {start_time_iso} to {end_time_iso}")
        print(f"[CALENDLY] Event type URI: {event_type_uri}")
        
        # Get available times from Calendly
        availability_data = make_calendly_api_request(
            'event_type_available_times',
            settings["calendly_access_token"],
            {
                'event_type': event_type_uri,
                'start_time': start_time_iso,
                'end_time': end_time_iso
            }
        )
        
        if not availability_data:
            return {"slots": []}
        
        slots = []
        for slot in availability_data.get('collection', []):
            slots.append({
                "start_time": slot.get('start_time'),
                "end_time": slot.get('end_time'),
                "scheduling_url": slot.get('scheduling_url')
            })
        
        print(f"[CALENDLY] Found {len(slots)} available slots")
        return {"slots": slots}
        
    except Exception as e:
        print(f"Error getting Calendly availability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendly/stats")
async def get_calendly_stats(
    organization=Depends(get_organization_from_api_key)
):
    """Get Calendly account statistics"""
    org_id = organization["id"]
    
    try:
        settings = calendly_settings_collection.find_one({"organization_id": org_id})
        if not settings or not settings.get("calendly_access_token"):
            return {"stats": {"total_events": 0, "active_events": 0, "upcoming_bookings": 0}}
        
        # Get user info first
        user_data = make_calendly_api_request('users/me', settings["calendly_access_token"])
        user_uri = user_data.get('resource', {}).get('uri')
        
        # Get event types
        event_types_data = make_calendly_api_request(
            'event_types',
            settings["calendly_access_token"],
            {'user': user_uri}
        )
        
        events = event_types_data.get('collection', [])
        total_events = len(events)
        
        # Debug: Log all events and their statuses
        print(f"[CALENDLY STATS DEBUG] Found {total_events} total events:")
        for i, event in enumerate(events):
            print(f"[CALENDLY STATS DEBUG] Event {i+1}: name='{event.get('name')}', status='{event.get('status')}', uri='{event.get('uri')}'")
        
        active_events = len([e for e in events if e.get('status') == 'active'])
        print(f"[CALENDLY STATS DEBUG] Active events count: {active_events}")
        
        # Note: Calendly API doesn't provide a direct way to count upcoming bookings
        # This would require iterating through all scheduled events
        upcoming_bookings = 0
        
        return {
            "stats": {
                "total_events": total_events,
                "active_events": active_events,
                "upcoming_bookings": upcoming_bookings
            }
        }
        
    except Exception as e:
        print(f"Error getting Calendly stats: {str(e)}")
        return {"stats": {"total_events": 0, "active_events": 0, "upcoming_bookings": 0}}

# For backward compatibility - these endpoints will return empty data or errors
@router.get("/availability")
async def legacy_get_availability(organization=Depends(get_organization_from_api_key)):
    """Legacy endpoint - redirects to Calendly integration"""
    return {
        "message": "This organization is using Calendly integration. Please configure Calendly settings.",
        "calendly_integration": True
    }

@router.post("/availability")
async def legacy_save_availability(organization=Depends(get_organization_from_api_key)):
    """Legacy endpoint - redirects to Calendly integration"""
    raise HTTPException(
        status_code=400,
        detail="This organization is using Calendly integration. Please use Calendly settings instead."
    )

@router.get("/bookings")
async def legacy_get_bookings(organization=Depends(get_organization_from_api_key)):
    """Legacy endpoint - redirects to Calendly integration"""
    return {
        "message": "This organization is using Calendly integration. Bookings are managed through Calendly.",
        "calendly_integration": True
    } 