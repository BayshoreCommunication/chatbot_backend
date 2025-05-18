import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import requests
from typing import List, Dict, Any, Optional

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

def get_available_slots(days_ahead: int = 7, service_type: str = "consultation") -> List[Dict[str, Any]]:
    """
    Get available appointment slots from calendar providers
    Supports multiple calendar providers (Google Calendar, Calendly)
    """
    available_slots = []
    
    # Try Google Calendar if configured
    google_slots = get_google_calendar_slots(days_ahead)
    if google_slots:
        available_slots.extend(google_slots)
    
    # Try Calendly if configured
    calendly_slots = get_calendly_slots(days_ahead, service_type)
    if calendly_slots:
        available_slots.extend(calendly_slots)
    
    # If no integrations are available, provide mock data
    if not available_slots:
        available_slots = generate_mock_slots(days_ahead)
    
    return available_slots

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

def get_calendly_slots(days_ahead: int = 7, service_type: str = "consultation") -> List[Dict[str, Any]]:
    """Get available slots from Calendly"""
    if not CALENDLY_AVAILABLE:
        return []
    
    try:
        calendly_token = os.getenv("CALENDLY_TOKEN")
        calendly_user = os.getenv("CALENDLY_USER")
        
        if not calendly_token or not calendly_user:
            return []
        
        headers = {
            "Authorization": f"Bearer {calendly_token}",
            "Content-Type": "application/json"
        }
        
        # Calculate time bounds
        now = datetime.utcnow()
        end_time = now + timedelta(days=days_ahead)
        
        # Call Calendly API to get available times
        url = f"https://api.calendly.com/users/{calendly_user}/event_types"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return []
        
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
            return []
        
        # Get available times for this event type
        availability_url = f"https://api.calendly.com/event_types/{event_type_uri}/available_times"
        params = {
            "start_time": now.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
        }
        
        avail_response = requests.get(availability_url, headers=headers, params=params)
        
        if avail_response.status_code != 200:
            return []
        
        available_times = avail_response.json()["collection"]
        
        return [
            {
                "start": slot["start_time"],
                "end": slot["end_time"],
                "source": "calendly"
            }
            for slot in available_times
        ]
    
    except Exception as e:
        print(f"Error getting Calendly slots: {str(e)}")
        return []

def generate_mock_slots(days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Generate mock available slots for testing"""
    available_slots = []
    now = datetime.now()
    
    for day in range(days_ahead):
        current_date = now + timedelta(days=day)
        
        # Skip weekends
        if current_date.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            continue
        
        # Add slots for 9 AM - 5 PM
        for hour in range(9, 17):
            slot_start = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(hours=1)
            
            available_slots.append({
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat(),
                "source": "mock"
            })
    
    return available_slots

def book_appointment(
    start_time: str,
    end_time: str,
    user_name: str,
    user_email: str,
    service_type: str = "consultation",
    source: str = "google_calendar"
) -> Dict[str, Any]:
    """Book an appointment in the specified calendar system"""
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
            # Mock booking for demonstration
            return {
                "status": "success",
                "message": f"Appointment booked for {user_name} at {start_time}",
                "appointment_id": "mock-appointment-id-" + datetime.now().isoformat(),
                "details": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "service_type": service_type,
                    "user_name": user_name,
                    "user_email": user_email
                }
            }
    except Exception as e:
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