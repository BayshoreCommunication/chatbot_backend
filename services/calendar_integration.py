import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import requests
from typing import List, Dict, Any, Optional
import pymongo
import logging
import time

#Get logger for calendar integration
logger = logging.getLogger('calendly')

# Optional: Google Calendar API integration
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False

# Optional: Calendly integration
CALENDLY_AVAILABLE = True  # Just using their API, no special package needed

load_dotenv()

# Database connection for Calendly settings
try:
    from services.database import db
    calendly_settings_collection = db.calendly_settings
except:
    calendly_settings_collection = None

def get_calendly_settings_by_api_key(api_key: str) -> Dict[str, Any]:
    """Get Calendly settings for the organization"""
    if calendly_settings_collection is None or not api_key:
        logger.warning(f"Missing collection or API key")
        return {}
    
    try:
        # Get organization by API key first
        from services.database import get_organization_by_api_key
        org = get_organization_by_api_key(api_key)
        if not org:
            logger.warning(f"No organization found for API key")
            return {}
        
        logger.info(f"Found organization: {org.get('name')}")
        
        # Get Calendly settings for this organization
        settings = calendly_settings_collection.find_one({"organization_id": org["id"]})
        
        if settings is not None:  # Fix the MongoDB collection boolean issue
            logger.info(f"Calendly settings found - Token: {'✓' if settings.get('calendly_access_token') else '✗'}, Event URI: {'✓' if settings.get('event_type_uri') else '✗'}")
            # Remove MongoDB ObjectId if present
            if '_id' in settings:
                del settings['_id']
            return settings
        else:
            logger.warning(f"No Calendly settings found for organization")
            return {}
            
    except Exception as e:
        logger.error(f"Error getting Calendly settings: {str(e)}")
        return {}

def make_calendly_api_request(endpoint: str, access_token: str, params: dict = None):
    """Make authenticated request to Calendly API"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        logger.info(f"Making Calendly API request to endpoint: {endpoint}")
        response = requests.get(f'https://api.calendly.com/{endpoint}', headers=headers, params=params)
        response.raise_for_status()
        response_json = response.json()
        logger.debug(f"Calendly API response: {json.dumps(response_json, indent=2)}")
        return response_json
    except requests.exceptions.RequestException as e:
        logger.error(f"Calendly API error: {str(e)}")
        if e.response is not None:
            logger.error(f"Calendly API response body: {e.response.text}")
        raise Exception(f"Calendly API error: {str(e)}")

def get_available_slots(days_ahead: int = 7, service_type: str = "consultation", api_key: str = None) -> List[Dict[str, Any]]:
    """
    Get available appointment slots from Calendly only - no mock data
    """
    if not api_key:
        logger.error("No API key provided - cannot get slots")
        return []
    
    # Only try Calendly - no fallbacks to mock data
    calendly_slots = get_calendly_slots(days_ahead, service_type, api_key)
    
    if not calendly_slots:
        logger.warning("No Calendly slots available")
        return []
    
    logger.info(f"Successfully retrieved {len(calendly_slots)} slots")
    return calendly_slots

def get_google_calendar_slots(days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Get available slots from Google Calendar"""
    if not GOOGLE_CALENDAR_AVAILABLE:
        return []
    
    try:
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        
        if not credentials_path or not calendar_id:
            return []
        
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, 
            scopes=["https://www.googleapis.com/auth/calendar.readonly"]
        )
        
        service = build("calendar", "v3", credentials=credentials)
        
        # Calculate time bounds
        now = datetime.utcnow()
        end_time = now + timedelta(days=days_ahead)
        
        # Get busy times
        events_result = service.freebusy().query(
            body={
                "timeMin": now.isoformat() + "Z",
                "timeMax": end_time.isoformat() + "Z",
                "items": [{"id": calendar_id}]
            }
        ).execute()
        
        busy_slots = events_result["calendars"][calendar_id]["busy"]
        
        # Generate available slots
        available_slots = []
        current = now.replace(hour=9, minute=0, second=0, microsecond=0)  # Start at 9 AM
        
        while current < end_time:
            # Skip if outside of business hours (9 AM - 5 PM)
            if current.hour < 9 or current.hour >= 17:
                current += timedelta(hours=1)
                continue
            
            # Skip weekends
            if current.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
                current += timedelta(days=1)
                current = current.replace(hour=9, minute=0, second=0, microsecond=0)
                continue
            
            # Check if slot is busy
            slot_end = current + timedelta(hours=1)
            is_busy = any(
                datetime.fromisoformat(busy["start"].replace("Z", "+00:00")) <= current and
                datetime.fromisoformat(busy["end"].replace("Z", "+00:00")) >= slot_end
                for busy in busy_slots
            )
            
            if not is_busy:
                available_slots.append({
                    "start": current.isoformat(),
                    "end": slot_end.isoformat(),
                    "source": "google_calendar"
                })
            
            current += timedelta(hours=1)
        
        return available_slots
    
    except Exception as e:
        print(f"Error getting Google Calendar slots: {str(e)}")
        return []

def get_calendly_slots(days_ahead: int = 7, service_type: str = "consultation", api_key: str = None) -> List[Dict[str, Any]]:
    """Get available slots from Calendly using organization settings"""
    if not CALENDLY_AVAILABLE or not api_key:
        logger.error("API key required for Calendly integration")
        return []
    
    try:
        # Get Calendly settings from database
        logger.info(f"Getting calendly settings for api_key: {api_key[:10]}... ")
        settings = get_calendly_settings_by_api_key(api_key)
        if not settings:
            logger.error(f"Could not retrieve Calendly settings for api_key: {api_key[:10]}")
            return []

        calendly_token = settings.get("calendly_access_token")
        event_type_uri = settings.get("event_type_uri")
        
        if not calendly_token or not event_type_uri:
            logger.error("Missing access token or event type URI")
            return []
        
        # Calculate time bounds using time.time() for reliable current time
        current_timestamp = time.time()
        start_time = datetime.fromtimestamp(current_timestamp + 30)  # 30 seconds from now
        end_time = datetime.fromtimestamp(current_timestamp + (days_ahead * 24 * 60 * 60))  # days_ahead in seconds
        
        # Format for Calendly API (ISO format with Z suffix)
        start_time_iso = start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        end_time_iso = end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        logger.info(f"Requesting Calendly availability from {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
        logger.info(f"Event type URI: {event_type_uri}")
        
        # Get available times from Calendly using the exact same endpoint format as client
        headers = {
            'Authorization': f'Bearer {calendly_token}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'event_type': event_type_uri,
            'start_time': start_time_iso,
            'end_time': end_time_iso
        }
        
        logger.info(f"Making request with params: {params}")
        
        response = requests.get(
            'https://api.calendly.com/event_type_available_times',
            headers=headers,
            params=params
        )
        
        # Log the full response for debugging
        logger.info(f"Response status: {response.status_code}")
        try:
            availability_data = response.json()
            logger.info(f"Response data: {json.dumps(availability_data, indent=2)}")
        except:
            logger.error(f"Failed to parse response: {response.text}")
            return []
        
        if not availability_data:
            logger.warning("No availability data returned from Calendly API")
            return []
        
        slots = []
        for slot in availability_data.get('collection', []):
            logger.info(f"[CALENDLY] Processing slot: {json.dumps(slot, indent=2)}")
            
            start_time_str = slot.get('start_time')
            scheduling_url = slot.get('scheduling_url')
            status = slot.get('status')
            
            if start_time_str and scheduling_url and status == 'available':
                # Parse the datetime to create a proper slot ID
                try:
                    slot_datetime = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    # Calculate end time (30 minutes after start time)
                    end_time_str = (slot_datetime + timedelta(minutes=30)).isoformat() + 'Z'
                    
                    slot_id = f"slot_{slot_datetime.strftime('%A, %B %d')}_{slot_datetime.strftime('%I%M%p')}_{hash(start_time_str) % 1000:03d}"
                    
                    slots.append({
                        "start": start_time_str,
                        "end": end_time_str,
                        "source": "calendly",
                        "id": slot_id,
                        "available": True,
                        "scheduling_url": scheduling_url
                    })
                except Exception as e:
                    logger.error(f"Error parsing slot time {start_time_str}: {e}")
                    continue
        
        logger.info(f"Found {len(slots)} available slots")
        return slots
        
    except Exception as e:
        logger.error(f"Error getting Calendly slots: {str(e)}", exc_info=True)
        return []

# Remove all mock data functionality
def generate_mock_slots(days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Mock data functionality has been removed. This function will now raise an error."""
    logger.error("MOCK DATA FUNCTIONALITY HAS BEEN REMOVED. Configure Calendly integration instead.")
    raise NotImplementedError("Mock data functionality has been removed. Configure Calendly integration.")

def book_appointment(
    start_time: str,
    end_time: str,
    user_name: str,
    user_email: str,
    service_type: str = "consultation",
    source: str = "google_calendar"
) -> Dict[str, Any]:
    """Book an appointment in the specified calendar system"""
    logger.info(f"Booking appointment for {user_name} at {start_time} via {source}")
    try:
        if source == "google_calendar" and GOOGLE_CALENDAR_AVAILABLE:
            return book_google_calendar_appointment(
                start_time, end_time, user_name, user_email, service_type
            )
        elif source == "calendly" and CALENDLY_AVAILABLE:
            return book_calendly_appointment(
                start_time, end_time, user_name, user_email, service_type
            )
        else:
            logger.error(f"Booking failed: unsupported source {source} or integration unavailable.")
            raise NotImplementedError(f"Booking source '{source}' is not supported or not available.")
            
    except Exception as e:
        logger.error(f"Error booking appointment: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }

def book_google_calendar_appointment(
    start_time: str,
    end_time: str,
    user_name: str,
    user_email: str,
    service_type: str = "consultation"
) -> Dict[str, Any]:
    """Book an appointment in Google Calendar"""
    try:
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        
        if not credentials_path or not calendar_id:
            return {"status": "error", "message": "Google Calendar credentials missing"}
        
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, 
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        
        service = build("calendar", "v3", credentials=credentials)
        
        event = {
            'summary': f"{service_type.capitalize()} with {user_name}",
            'description': f"Booked by: {user_name} ({user_email})",
            'start': {
                'dateTime': start_time,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': user_email, 'displayName': user_name},
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }
        
        event = service.events().insert(calendarId=calendar_id, body=event).execute()
        
        return {
            "status": "success",
            "message": f"Appointment booked for {user_name} at {start_time}",
            "appointment_id": event.get("id"),
            "details": event
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def book_calendly_appointment(
    start_time: str,
    end_time: str,
    user_name: str,
    user_email: str,
    service_type: str = "consultation"
) -> Dict[str, Any]:
    """Book an appointment in Calendly"""
    try:
        calendly_token = os.getenv("CALENDLY_TOKEN")
        calendly_user = os.getenv("CALENDLY_USER")
        
        if not calendly_token or not calendly_user:
            return {"status": "error", "message": "Calendly credentials missing"}
        
        headers = {
            "Authorization": f"Bearer {calendly_token}",
            "Content-Type": "application/json"
        }
        
        # Get event types
        url = f"https://api.calendly.com/users/{calendly_user}/event_types"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return {"status": "error", "message": "Failed to get Calendly event types"}
        
        event_types = response.json()["collection"]
        
        # Find the right event type
        event_type_uri = None
        for event in event_types:
            if service_type.lower() in event["name"].lower():
                event_type_uri = event["uri"]
                break
        
        if not event_type_uri:
            event_type_uri = event_types[0]["uri"] if event_types else None
        
        if not event_type_uri:
            return {"status": "error", "message": "No suitable event type found"}
        
        # Schedule the event
        schedule_url = "https://api.calendly.com/scheduled_events"
        payload = {
            "event_type_uri": event_type_uri,
            "start_time": start_time,
            "end_time": end_time,
            "invitees": [
                {
                    "name": user_name,
                    "email": user_email
                }
            ]
        }
        
        schedule_response = requests.post(schedule_url, headers=headers, json=payload)
        
        if schedule_response.status_code not in (200, 201):
            return {
                "status": "error", 
                "message": f"Failed to schedule Calendly event: {schedule_response.text}"
            }
        
        event = schedule_response.json()
        
        return {
            "status": "success",
            "message": f"Appointment booked for {user_name} at {start_time}",
            "appointment_id": event.get("id", "unknown"),
            "details": event
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        } 