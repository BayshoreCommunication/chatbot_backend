import datetime
import random
import json
import openai
import re
from functools import lru_cache
import hashlib
import time as time_module
import uuid
import requests
from dotenv import load_dotenv

# Add database imports for Calendly settings
from services.database import get_organization_by_api_key, db

# Add caching for API calls to prevent repeated requests
_analysis_cache = {}
_slot_extraction_cache = {}
_calendly_cache = {}
_cache_timestamps = {}

def get_cache_key(query, available_slots=None):
    """Generate a cache key for the query and slots"""
    content = query
    if available_slots:
        content += str(available_slots)
    return hashlib.md5(content.encode()).hexdigest()

def cleanup_cache():
    """Clean up old cache entries (older than 1 hour)"""
    current_time = time_module.time()
    expired_keys = []
    
    for key, timestamp in _cache_timestamps.items():
        if current_time - timestamp > 3600:  # 1 hour
            expired_keys.append(key)
    
    for key in expired_keys:
        _analysis_cache.pop(key, None)
        _slot_extraction_cache.pop(key, None)
        _calendly_cache.pop(key, None)
        _cache_timestamps.pop(key, None)
    
    if expired_keys:
        print(f"[CACHE] Cleaned up {len(expired_keys)} expired cache entries")

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
        return None

def get_calendly_settings(api_key):
    """Get Calendly settings for organization"""
    try:
        organization = get_organization_by_api_key(api_key)
        if not organization:
            return None
        
        org_id = organization["id"]
        calendly_settings_collection = db.calendly_settings
        
        settings = calendly_settings_collection.find_one(
            {"organization_id": org_id},
            {"_id": 0}
        )
        
        return settings
    except Exception as e:
        print(f"Error getting Calendly settings: {str(e)}")
        return None

def get_available_slots(api_key=None):
    """Get available appointment slots from Calendly or return mock data if not configured"""
    if not api_key:
        print("[APPOINTMENT] No API key provided, using mock data")
        return get_mock_slots()
    
    try:
        # Get Calendly settings
        settings = get_calendly_settings(api_key)
        if not settings or not settings.get("calendly_access_token") or not settings.get("event_type_uri"):
            print("[APPOINTMENT] Calendly not configured, using mock data")
            return get_mock_slots()
        
        # Check cache first
        cache_key = f"calendly_availability_{settings['event_type_uri']}"
        if cache_key in _calendly_cache:
            cache_time = _cache_timestamps.get(cache_key, 0)
            if time_module.time() - cache_time < 300:  # 5 minutes cache
                print("[APPOINTMENT] Using cached Calendly availability")
                return _calendly_cache[cache_key]
        
        print("[APPOINTMENT] Fetching availability from Calendly")
        
        # Calculate date range - start from now + 30 seconds to ensure future time
        # and limit to 6 days 23 hours to stay under 7-day limit
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
        end_time = start_time + datetime.timedelta(days=6, hours=23)
        
        # Format for Calendly API (ISO format with Z suffix)
        start_time_iso = start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        end_time_iso = end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        print(f"[APPOINTMENT] Requesting availability from {start_time_iso} to {end_time_iso}")
        
        # Get available times from Calendly
        availability_data = make_calendly_api_request(
            'event_type_available_times',
            settings["calendly_access_token"],
            {
                'event_type': settings["event_type_uri"],
                'start_time': start_time_iso,
                'end_time': end_time_iso
            }
        )
        
        if not availability_data:
            print("[APPOINTMENT] Failed to fetch from Calendly, using mock data")
            return get_mock_slots()
        
        slots = availability_data.get('collection', [])
        if not slots:
            return "I apologize, but there are currently no appointment slots available. Please check back later or contact us directly to schedule an appointment."
        
        # Format slots for display (without booking URLs)
        formatted_slots = "Available appointment slots:\n\n"
        
        # Group slots by date
        slots_by_date = {}
        for slot in slots:
            start_time_str = slot.get('start_time')
            if not start_time_str:
                continue
                
            try:
                slot_datetime = datetime.datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                date_key = slot_datetime.strftime("%A, %B %d, %Y")
                
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = {"morning": [], "afternoon": []}
                
                # Format time for display (without booking URL)
                time_display = slot_datetime.strftime("%I:%M %p").lstrip('0')
                
                slot_line = f"    • {time_display}"
                
                # Determine if morning or afternoon
                if slot_datetime.hour < 12:
                    slots_by_date[date_key]["morning"].append({
                        "display": slot_line,
                        "start_time": start_time_str,
                        "date": date_key,
                        "time": time_display
                    })
                else:
                    slots_by_date[date_key]["afternoon"].append({
                        "display": slot_line,
                        "start_time": start_time_str,
                        "date": date_key,
                        "time": time_display
                    })
                    
            except Exception as e:
                print(f"Error parsing slot time {start_time_str}: {e}")
                continue
        
        # Build formatted output
        for date_display, periods in slots_by_date.items():
            formatted_slots += f"📅 {date_display}\n"
            if periods["morning"]:
                formatted_slots += "  Morning:\n" + "\n".join([slot["display"] for slot in periods["morning"]]) + "\n"
            if periods["afternoon"]:
                formatted_slots += "  Afternoon:\n" + "\n".join([slot["display"] for slot in periods["afternoon"]]) + "\n"
            formatted_slots += "\n"
        
        formatted_slots += "Please tell me which date and time you'd prefer, and I'll book that slot for you!"
        
        # Cache the result
        _calendly_cache[cache_key] = formatted_slots.strip()
        _cache_timestamps[cache_key] = time_module.time()
        
        print(f"[APPOINTMENT] Successfully formatted {len(slots)} Calendly slots")
        return formatted_slots.strip()
        
    except Exception as e:
        print(f"[APPOINTMENT] Error fetching Calendly availability: {str(e)}")
        print("[APPOINTMENT] Falling back to mock data")
        return get_mock_slots()

def get_mock_slots():
    """Get mock appointment slots (fallback when Calendly not available)"""
    print("[APPOINTMENT] Generating mock appointment slots")
    
    today = datetime.datetime.now()
    slots = []
    
    # Generate slots for the next 7 days
    for i in range(1, 8):
        date = today + datetime.timedelta(days=i)
        # Skip weekends
        if date.weekday() >= 5:
            continue
            
        date_str = date.strftime("%Y-%m-%d")
        date_display = date.strftime("%A, %B %d, %Y")
        
        # Add morning slots
        for hour in [9, 10, 11]:
            time_display = f"{hour}:00 AM"
            slots.append({
                "date_display": date_display,
                "time_display": time_display,
                "period": "morning"
            })
        
        # Add afternoon slots
        for hour in [13, 14, 15, 16]:
            display_hour = hour if hour <= 12 else hour - 12
            time_display = f"{display_hour}:00 PM"
            slots.append({
                "date_display": date_display,
                "time_display": time_display,
                "period": "afternoon"
            })
    
    # Randomly remove some slots to simulate real availability
    available_slots = random.sample(slots, min(len(slots) - 3, len(slots)))
    
    # Format slots for display (without booking URLs)
    formatted_slots = "Available appointment slots:\n\n"
    
    # Group by date
    slots_by_date = {}
    for slot in available_slots:
        date_display = slot["date_display"]
        if date_display not in slots_by_date:
            slots_by_date[date_display] = {"morning": [], "afternoon": []}
        
        period = slot["period"]
        slots_by_date[date_display][period].append(f"    • {slot['time_display']}")
    
    # Build formatted output
    for date_display, periods in slots_by_date.items():
        formatted_slots += f"📅 {date_display}\n"
        if periods["morning"]:
            formatted_slots += "  Morning:\n" + "\n".join(periods["morning"]) + "\n"
        if periods["afternoon"]:
            formatted_slots += "  Afternoon:\n" + "\n".join(periods["afternoon"]) + "\n"
        formatted_slots += "\n"
    
    formatted_slots += "Please tell me which date and time you'd prefer, and I'll book that slot for you!"
    return formatted_slots.strip()

def extract_slot_info(query, available_slots):
    """Extract date, time, or Calendly URL from user query with enhanced AI analysis"""
    
    cleanup_cache()
    
    cache_key = get_cache_key(query, available_slots)
    if cache_key in _slot_extraction_cache:
        print(f"[CACHE] Using cached slot extraction for query: {query[:50]}...")
        return _slot_extraction_cache[cache_key]
    
    print(f"[API] Extracting slot info from query: {query}")
    
    # Look for Calendly URLs (fallback)
    calendly_url_pattern = r'https://calendly\.com/[^\s)]+'
    calendly_urls = re.findall(calendly_url_pattern, query + " " + available_slots)
    
    # Enhanced AI-powered slot extraction
    slot_selection_prompt = f"""
    Analyze the user's message to determine if they are selecting a specific appointment slot.

    USER MESSAGE: "{query}"

    AVAILABLE SLOTS:
    {available_slots}

    Your task is to determine:
    1. Is the user trying to select/book/confirm a specific appointment slot?
    2. If yes, which exact date and time are they referring to?

    Look for patterns like:
    - "Saturday at 1 PM" 
    - "June 21 at 1:00 PM"
    - "confirm this one: Saturday, June 21, 2025 1:00 PM"
    - "book the 1:00 PM slot on Saturday"
    - "I want Wednesday 2:30 PM"
    - "aturday, June 21, 2025 1:00 PM" (handle typos like "aturday" = "Saturday")

    Rules for matching:
    1. Be flexible with date formats and typos (e.g., "aturday" = "Saturday")
    2. Match partial dates (e.g., "Saturday" should match "Saturday, June 21, 2025")
    3. Match time formats (e.g., "1 PM" = "1:00 PM")
    4. Only return exact matches from the available slots list
    5. If multiple matches possible, pick the most specific one

    Respond in JSON format:
    {{
        "date": "exact date as it appears in available slots (e.g., 'Saturday, June 21, 2025') or null",
        "time": "exact time as it appears in available slots (e.g., '1:00 PM') or null", 
        "is_booking_confirmation": true/false,
        "confidence": "high/medium/low",
        "reasoning": "brief explanation of why you picked this slot or why no match found"
    }}

    Examples:
    - "Saturday at 1 PM" → {{"date": "Saturday, June 21, 2025", "time": "1:00 PM", "is_booking_confirmation": true, "confidence": "high"}}
    - "aturday, June 21, 2025 1:00 PM" → {{"date": "Saturday, June 21, 2025", "time": "1:00 PM", "is_booking_confirmation": true, "confidence": "high"}}
    - "what slots are available?" → {{"date": null, "time": null, "is_booking_confirmation": false, "confidence": "high"}}
    """
    
    try:
        slot_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": slot_selection_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        slot_info = json.loads(slot_response.choices[0].message.content)
        print(f"AI Enhanced Slot Extraction: {slot_info}")
        
        # Add any found Calendly URLs
        if calendly_urls:
            slot_info["booking_url"] = calendly_urls[0]
            slot_info["confidence"] = "high"
            slot_info["is_booking_confirmation"] = True
        
        # Validate that the extracted date and time actually exist in available slots
        if slot_info.get("date") and slot_info.get("time"):
            date = slot_info["date"]
            time = slot_info["time"]
            
            # Check if this combination exists in available slots
            if f"📅 {date}" in available_slots and f"• {time}" in available_slots:
                # Double-check by looking for the date and time in the same section
                lines = available_slots.split('\n')
                current_date = None
                found_valid_combo = False
                
                for line in lines:
                    if "📅" in line:
                        current_date = line.replace("📅", "").strip()
                    elif current_date == date and f"• {time}" in line:
                        found_valid_combo = True
                        break
                
                if not found_valid_combo:
                    print(f"[WARNING] Date/time combo not found in same section: {date} at {time}")
                    slot_info["date"] = None
                    slot_info["time"] = None
                    slot_info["confidence"] = "low"
                    slot_info["reasoning"] = "Date and time combination not found in available slots"
            else:
                print(f"[WARNING] Date or time not found in available slots: {date} at {time}")
                slot_info["date"] = None
                slot_info["time"] = None
                slot_info["confidence"] = "low"
                slot_info["reasoning"] = "Requested date or time not available"
        
        _slot_extraction_cache[cache_key] = slot_info
        _cache_timestamps[cache_key] = time_module.time()
        
        return slot_info
        
    except Exception as e:
        print(f"Error in AI slot extraction: {str(e)}")
        
        # Fallback to basic regex matching
        fallback_result = {
            "date": None,
            "time": None,
            "booking_url": calendly_urls[0] if calendly_urls else None,
            "is_booking_confirmation": bool(calendly_urls),
            "confidence": "high" if calendly_urls else "low",
            "reasoning": "AI extraction failed, used basic pattern matching"
        }
        
        # Try basic regex patterns as fallback
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(AM|PM)',
            r'(\d{1,2})\s*(AM|PM)',
        ]
        
        for pattern in time_patterns:
            time_match = re.search(pattern, query.upper())
            if time_match:
                if len(time_match.groups()) == 3:  # HH:MM AM/PM
                    hour, minute, period = time_match.groups()
                    fallback_time = f"{hour}:{minute} {period}"
                else:  # H AM/PM
                    hour, period = time_match.groups()
                    fallback_time = f"{hour}:00 {period}"
                
                # Check if this time exists in available slots
                if f"• {fallback_time}" in available_slots:
                    fallback_result["time"] = fallback_time
                    fallback_result["confidence"] = "medium"
                    break
        
        # Try to find day names
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days:
            if day in query.lower() or day[:-1] in query.lower():  # Also check "saturda" for "saturday"
                # Find matching date in available slots
                for line in available_slots.split('\n'):
                    if "📅" in line and day.capitalize() in line:
                        fallback_result["date"] = line.replace("📅", "").strip()
                        fallback_result["confidence"] = "medium"
                        break
                break
        
        _slot_extraction_cache[cache_key] = fallback_result
        _cache_timestamps[cache_key] = time_module.time()
        return fallback_result

def analyze_appointment_query(query):
    """Analyze user query to determine intent with caching"""
    
    cleanup_cache()
    
    cache_key = get_cache_key(query)
    if cache_key in _analysis_cache:
        print(f"[CACHE] Using cached analysis for query: {query[:50]}...")
        return _analysis_cache[cache_key]
    
    print(f"[API] Analyzing appointment query: {query}")
    
    intent_analysis_prompt = f"""
    Analyze the following user message in the context of Calendly appointment scheduling:
    
    USER MESSAGE: "{query}"
    
    Determine the user's intent and extract any relevant information.
    
    Respond in JSON format:
    {{
        "intent": "one of: ask_availability, book_appointment, check_weekends, reschedule, cancel, general_question",
        "specific_day": "weekday mentioned (if any) or null",
        "specific_date": "date mentioned (if any) or null",
        "specific_time": "time mentioned (if any) or null",
        "clarification_needed": true/false,
        "is_weekend_query": true/false,
        "confidence": "high/medium/low",
        "is_day_specific_query": true/false
    }}
    """
    
    try:
        intent_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": intent_analysis_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        intent_info = json.loads(intent_response.choices[0].message.content)
        print(f"AI Intent Analysis: {intent_info}")
        
        _analysis_cache[cache_key] = intent_info
        _cache_timestamps[cache_key] = time_module.time()
        
        return intent_info
        
    except Exception as e:
        print(f"Error in AI query analysis: {str(e)}")
        fallback_result = {
            "intent": "general_question",
            "specific_day": None,
            "specific_date": None,
            "specific_time": None,
            "clarification_needed": False,
            "is_weekend_query": False,
            "confidence": "low",
            "is_day_specific_query": False
        }
        
        _analysis_cache[cache_key] = fallback_result
        _cache_timestamps[cache_key] = time_module.time()
        return fallback_result

def handle_booking(query, user_data, available_slots, language, api_key=None):
    """Handle the appointment booking process with programmatic Calendly booking"""
    
    if "api_call_count" not in user_data:
        user_data["api_call_count"] = 0
    
    user_data["api_call_count"] += 1
    
    if user_data["api_call_count"] > 3:
        print(f"[CIRCUIT_BREAKER] Too many API calls, returning simple response")
        
        if not available_slots:
            available_slots = get_available_slots(api_key)
        
        simple_response = f"I'd be happy to help you schedule an appointment. Here are the available slots:\n\n{available_slots}"
        
        user_data["api_call_count"] = 0
        
        return {
            "answer": simple_response,
            "mode": "appointment",
            "language": language,
            "user_data": user_data,
            "available_slots": available_slots
        }
    
    print(f"[DEBUG] handle_booking called with query: '{query[:100]}...'")
    
    if not available_slots:
        available_slots = get_available_slots(api_key)
    
    if "appointment_context" not in user_data:
        user_data["appointment_context"] = {}
    
    # Check for simple booking intent first
    simple_booking_phrases = [
        "book an appointment", "book appointment", "schedule appointment", 
        "make an appointment", "make appointment", "i want to book", "help me book"
    ]
    
    if any(phrase in query.lower() for phrase in simple_booking_phrases):
        has_specific_details = any([
            re.search(r'\d+:\d+', query),
            re.search(r'\d+\s*(am|pm)', query.lower()),
            any(day in query.lower() for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]),
        ])
        
        if not has_specific_details:
            response = f"I'd be happy to help you schedule an appointment! Here are the available slots:\n\n{available_slots}"
            
            user_data["api_call_count"] = 0
            
            return {
                "answer": response,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "available_slots": available_slots
            }
    
    # Analyze the query and extract slot information
    query_analysis = analyze_appointment_query(query)
    slot_info = extract_slot_info(query, available_slots)
    
    # Check if user is providing email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_matches = re.findall(email_pattern, query)
    
    if email_matches:
        # User provided email, update user_data
        new_email = email_matches[0]
        user_data["email"] = new_email
        user_data["appointment_context"]["email_provided"] = True
        
        # Check if we have a pending booking
        if user_data["appointment_context"].get("pending_booking"):
            pending = user_data["appointment_context"]["pending_booking"]
            date = pending["date"]
            time = pending["time"]
            
            # Proceed with providing booking link
            slot_details = find_slot_by_datetime(date, time, available_slots, api_key)
            
            if slot_details and slot_details.get("scheduling_url"):
                booking_url = slot_details["scheduling_url"]
                
                confirmation = f"Perfect! Here is the direct link to book your appointment for {date} at {time}:\n\n[Book Now]({booking_url})\n\nThis link will take you to Calendly to confirm your details."
                
                # Clear appointment context
                user_data["appointment_context"] = {}
                user_data["api_call_count"] = 0
                
                return {
                    "answer": confirmation,
                    "mode": "faq",
                    "language": language,
                    "user_data": user_data,
                    "appointment_confirmed": True
                }
            else:
                error_response = f"Sorry, the slot for {date} at {time} is no longer available. Please choose a different time from the available slots."
                
                user_data["appointment_context"] = {}
                
                return {
                    "answer": error_response,
                    "mode": "appointment",
                    "language": language,
                    "user_data": user_data,
                    "available_slots": available_slots
                }
        else:
            # Email provided but no pending booking
            response = f"Thanks for providing your email! Please let me know which date and time you'd like to book from the available slots:\n\n{available_slots}"
            
            return {
                "answer": response,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "available_slots": available_slots
            }
    
    # If we have date and time selected
    if slot_info.get("date") and slot_info.get("time"):
        date = slot_info["date"]
        time = slot_info["time"]
        
        print(f"[BOOKING] User selected slot: {date} at {time}")
        print(f"[BOOKING] Confidence: {slot_info.get('confidence', 'unknown')}")
        print(f"[BOOKING] Reasoning: {slot_info.get('reasoning', 'No reasoning provided')}")
        
        # Check if user has valid email
        user_email = get_user_email(user_data)
        
        if not user_email:
            # Store the selected slot and ask for email
            user_data["appointment_context"]["pending_booking"] = {
                "date": date,
                "time": time
            }
            
            email_request = f"Great! I found the slot for {date} at {time}.\n\nTo complete your booking, I'll need your email address. Please provide your email so I can send you the direct booking link."
            
            return {
                "answer": email_request,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "email_required": True
            }
        else:
            # User has email, provide direct booking link
            print(f"[BOOKING] User has email: {user_email}, providing direct booking link")
            slot_details = find_slot_by_datetime(date, time, available_slots, api_key)
            
            if slot_details and slot_details.get("scheduling_url"):
                booking_url = slot_details["scheduling_url"]
                
                confirmation = f"Perfect! Here is the direct link to book your appointment for {date} at {time}:\n\n[Book Now]({booking_url})\n\nThis link will take you to Calendly to confirm your details."
                
                # Clear appointment context
                user_data["appointment_context"] = {}
                user_data["api_call_count"] = 0
                
                return {
                    "answer": confirmation,
                    "mode": "faq",
                    "language": language,
                    "user_data": user_data,
                    "appointment_confirmed": True
                }
            else:
                print(f"[BOOKING] Could not find slot details or scheduling URL for {date} at {time}")
                error_response = f"Sorry, the slot for {date} at {time} is no longer available. Please choose a different time from the available slots."
                
                return {
                    "answer": error_response,
                    "mode": "appointment",
                    "language": language,
                    "user_data": user_data,
                    "available_slots": available_slots
                }
    
    # Check if user seems to be making a selection but we couldn't parse it
    selection_keywords = ["confirm", "book", "schedule", "want", "choose", "select", "pick", "take"]
    if any(keyword in query.lower() for keyword in selection_keywords):
        clarification = f"I understand you want to book an appointment, but I couldn't identify the specific date and time from your message.\n\nPlease tell me exactly which slot you'd like by saying something like:\n• 'Saturday at 1:00 PM'\n• 'June 21 at 1:00 PM'\n• 'I want the 1:00 PM slot on Saturday'\n\nHere are the available slots again:\n\n{available_slots}"
        
        return {
            "answer": clarification,
            "mode": "appointment", 
            "language": language,
            "user_data": user_data,
            "available_slots": available_slots
        }
    
    # Default response - show available slots
    response = f"I'd be happy to help you schedule an appointment. Here are the available slots:\n\n{available_slots}"
    
    return {
        "answer": response,
        "mode": "appointment",
        "language": language,
        "user_data": user_data,
        "available_slots": available_slots
    }

def handle_specific_day_query(query, user_data, available_slots, language, api_key=None):
    """Handle a query asking for slots on a specific day"""
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    target_day = None
    
    for day in days_of_week:
        if day in query.lower():
            target_day = day.capitalize()
            break
    
    if not target_day:
        return handle_booking(query, user_data, available_slots, language, api_key)
            
    # Find the matching day in available slots
    matching_day = None
    for line in available_slots.split('\n'):
        if "📅" in line and target_day in line:
            matching_day = line.replace("📅", "").strip()
            break
            
    if matching_day:
        if "appointment_context" not in user_data:
            user_data["appointment_context"] = {}
        user_data["appointment_context"]["last_discussed_day"] = matching_day
        
        # Extract the slots for this day
        day_section = False
        matching_slots = []
        
        for line in available_slots.split('\n'):
            if "📅" in line and matching_day in line:
                day_section = True
                continue
            elif day_section and "• " in line:
                matching_slots.append(line.strip())
            elif day_section and "📅" in line:
                day_section = False
        
        if matching_slots:
            morning_slots = [t for t in matching_slots if "AM" in t]
            afternoon_slots = [t for t in matching_slots if "PM" in t]
            
            response = f"Here are the available appointment slots for {matching_day}:\n\n"
            
            if morning_slots:
                response += "Morning:\n" + "\n".join([f"  {slot}" for slot in morning_slots]) + "\n\n"
            
            if afternoon_slots:
                response += "Afternoon:\n" + "\n".join([f"  {slot}" for slot in afternoon_slots]) + "\n\n"
            
            response += "Please tell me which time you'd prefer, and I'll book that slot for you."
            
            return {
                "answer": response,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "available_slots": available_slots
            }
    
    return handle_booking(query, user_data, available_slots, language, api_key)

def handle_rescheduling(user_data, available_slots, language, api_key=None):
    """Handle rescheduling - redirect to new booking"""
    response = f"I can help you schedule a new appointment. Here are the available slots:\n\n{available_slots}\n\nPlease tell me which date and time you'd prefer, and I'll book that slot for you."
    
    return {
        "answer": response,
        "mode": "appointment",
        "language": language,
        "user_data": user_data,
        "available_slots": available_slots
    }

def handle_cancellation(user_data, language):
    """Handle cancellation - redirect to Calendly"""
    response = "To cancel or reschedule an existing appointment, please use the link in your Calendly confirmation email, or contact us directly for assistance."
    
    return {
        "answer": response,
        "mode": "faq",
        "language": language,
        "user_data": user_data
    }

def handle_appointment_info(user_data, language):
    """Handle appointment info requests - redirect to Calendly"""
    response = "To view or manage your existing appointments, please check your Calendly confirmation email or contact us directly for assistance."
    
    return {
        "answer": response,
        "mode": "faq",
        "language": language,
        "user_data": user_data
    }

def get_user_email(user_data):
    """Get user email from user_data, return None if anonymous or missing"""
    email = user_data.get("email", "")
    if not email or email.lower() == "anonymous@gmail.com":
        return None
    return email

def find_slot_by_datetime(date, time, available_slots, api_key):
    """Find the exact slot information for booking"""
    try:
        settings = get_calendly_settings(api_key)
        if not settings:
            return None
            
        # Get fresh availability data
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
        end_time = start_time + datetime.timedelta(days=6, hours=23)
        
        start_time_iso = start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        end_time_iso = end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        availability_data = make_calendly_api_request(
            'event_type_available_times',
            settings["calendly_access_token"],
            {
                'event_type': settings["event_type_uri"],
                'start_time': start_time_iso,
                'end_time': end_time_iso
            }
        )
        
        if not availability_data:
            return None
            
        slots = availability_data.get('collection', [])
        
        # Find matching slot
        for slot in slots:
            start_time_str = slot.get('start_time')
            if not start_time_str:
                continue
                
            try:
                slot_datetime = datetime.datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                slot_date = slot_datetime.strftime("%A, %B %d, %Y")
                slot_time = slot_datetime.strftime("%I:%M %p").lstrip('0')
                
                if slot_date == date and slot_time == time:
                    return {
                        "start_time": start_time_str,
                        "event_type_uri": settings["event_type_uri"],
                        "access_token": settings["calendly_access_token"],
                        "scheduling_url": slot.get("scheduling_url")
                    }
                    
            except Exception as e:
                print(f"Error parsing slot: {e}")
                continue
                
        return None
        
    except Exception as e:
        print(f"Error finding slot: {e}")
        return None