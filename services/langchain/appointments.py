import datetime
import random
import json
import openai
import re
from functools import lru_cache
import hashlib
import time

# Add caching for API calls to prevent repeated requests
_analysis_cache = {}
_slot_extraction_cache = {}
_cache_timestamps = {}

def get_cache_key(query, available_slots=None):
    """Generate a cache key for the query and slots"""
    content = query
    if available_slots:
        content += str(available_slots)
    return hashlib.md5(content.encode()).hexdigest()

def cleanup_cache():
    """Clean up old cache entries (older than 1 hour)"""
    current_time = time.time()
    expired_keys = []
    
    for key, timestamp in _cache_timestamps.items():
        if current_time - timestamp > 3600:  # 1 hour
            expired_keys.append(key)
    
    for key in expired_keys:
        _analysis_cache.pop(key, None)
        _slot_extraction_cache.pop(key, None)
        _cache_timestamps.pop(key, None)
    
    if expired_keys:
        print(f"[CACHE] Cleaned up {len(expired_keys)} expired cache entries")

def get_available_slots():
    """Get available appointment slots from calendar or return mock data"""
    # In a real implementation, you would fetch from a calendar service
    # For demo purposes, we'll return mock data
    
    today = datetime.datetime.now()
    slots = []
    
    # Generate slots for the next 7 days
    for i in range(1, 8):
        date = today + datetime.timedelta(days=i)
        # Skip weekends
        if date.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            continue
            
        date_str = date.strftime("%Y-%m-%d")
        date_display = date.strftime("%A, %B %d, %Y")  # e.g., "Monday, September 15, 2023"
        
        # Add morning slots
        for hour in [9, 10, 11]:
            slot_id = f"slot_{date_str}_{hour}_00"
            slots.append({
                "id": slot_id,
                "date": date_str,
                "date_display": date_display,
                "time": f"{hour}:00",
                "period": "morning",
                "available": True
            })
        
        # Add afternoon slots
        for hour in [13, 14, 15, 16]:
            slot_id = f"slot_{date_str}_{hour}_00"
            display_hour = hour if hour <= 12 else hour - 12
            am_pm = "AM" if hour < 12 else "PM"
            slots.append({
                "id": slot_id,
                "date": date_str,
                "date_display": date_display,
                "time": f"{hour}:00",
                "time_display": f"{display_hour}:00 {am_pm}",
                "period": "afternoon",
                "available": True
            })
    
    # Randomly mark some slots as unavailable (in a real app, this would come from actual calendar)
    for slot in random.sample(slots, min(5, len(slots))):
        slot["available"] = False
    
    # Filter out unavailable slots
    available_slots = [slot for slot in slots if slot["available"]]
    
    # Format slots for display
    formatted_slots = "Available appointment slots:\n\n"
    
    # Group by date
    slots_by_date = {}
    for slot in available_slots:
        date_display = slot["date_display"]
        if date_display not in slots_by_date:
            slots_by_date[date_display] = {"morning": [], "afternoon": []}
        
        # Format time for display
        hour = int(slot["time"].split(":")[0])
        display_hour = hour if hour <= 12 else hour - 12
        am_pm = "AM" if hour < 12 else "PM"
        time_display = f"{display_hour}:00 {am_pm}"
        
        period = "morning" if hour < 12 else "afternoon"
        slots_by_date[date_display][period].append(f"    • {time_display} (ID: {slot['id']})")
    
    # Build formatted output
    for date_display, periods in slots_by_date.items():
        formatted_slots += f"📅 {date_display}\n"
        if periods["morning"]:
            formatted_slots += "  Morning:\n" + "\n".join(periods["morning"]) + "\n"
        if periods["afternoon"]:
            formatted_slots += "  Afternoon:\n" + "\n".join(periods["afternoon"]) + "\n"
        formatted_slots += "\n"
    
    return formatted_slots.strip()

def extract_slot_info(query, available_slots):
    """Extract date, time, or slot ID from user query with caching"""
    
    # Clean up old cache entries periodically
    cleanup_cache()
    
    # Check cache first
    cache_key = get_cache_key(query, available_slots)
    if cache_key in _slot_extraction_cache:
        print(f"[CACHE] Using cached slot extraction for query: {query[:50]}...")
        return _slot_extraction_cache[cache_key]
    
    print(f"[API] Extracting slot info from query: {query}")
    
    # First, analyze available slots to understand the date/time format
    all_dates = []
    all_times = []
    all_slot_ids = []
    
    # Parse available slots string to extract available options
    lines = available_slots.split('\n')
    for line in lines:
        if "📅" in line:
            # Extract date
            date_part = line.replace("📅", "").strip()
            all_dates.append(date_part)
        elif "• " in line and "ID: " in line:
            # Extract time and slot ID
            try:
                time_match = re.search(r'(\d+:\d+\s*(?:AM|PM))', line)
                if time_match:
                    all_times.append(time_match.group(1))
                
                slot_id_match = re.search(r'ID:\s*(slot_[^)]+)', line)
                if slot_id_match:
                    all_slot_ids.append(slot_id_match.group(1))
            except:
                pass
    
    # Remove duplicates while preserving order
    all_dates = list(dict.fromkeys(all_dates))
    all_times = list(dict.fromkeys(all_times))
    all_slot_ids = list(dict.fromkeys(all_slot_ids))
    
    # Extract available days and months from dates
    available_days = []
    available_months = []
    for date_str in all_dates:
        try:
            # Parse date string like "Tuesday, June 17, 2025"
            day_match = re.search(r'^(\w+),', date_str)
            if day_match:
                available_days.append(day_match.group(1))
            
            month_match = re.search(r',\s*(\w+)\s+\d+,', date_str)
            if month_match:
                available_months.append(month_match.group(1))
        except:
            pass
    
    # Remove duplicates
    available_days = list(dict.fromkeys(available_days))
    available_months = list(dict.fromkeys(available_months))
    
    # Look for direct slot ID match first (most reliable)
    slot_id_pattern = r'\b(slot_\d{4}-\d{2}-\d{2}_\d+_\d+)\b'
    slot_id_match = re.search(slot_id_pattern, query)
    
    # Build comprehensive prompt for slot extraction
    slot_selection_prompt = f"""
    Extract the date and time from the following user request for an appointment booking.
    If a specific slot or slot ID is mentioned, identify it.
    
    THIS IS CRITICAL: The user may have typos, or mention dates/times in an ambiguous format, 
    or use informal language like "tomorrow" or "next Tuesday". The user may also be selecting 
    or confirming a specific slot with phrases like "I'll take the 4pm on Monday" or "I'll pick the slot on May 26 at 4pm".
    
    User Request: "{query}"
    
    Available Dates: {', '.join(all_dates)}
    Available Days: {', '.join(available_days)}
    Available Months: {', '.join(available_months)}
    Available Times: {', '.join(all_times)}
    Available Slot IDs: {', '.join(all_slot_ids[:5])} (and more...)
    
    Full Available Slots:
    {available_slots}
    
    Examples of how to interpret user queries:
    - "I want May 21" → date: "Wednesday, May 21, 2025"
    - "Tuesday works" → date: identify corresponding date for Tuesday
    - "3 PM would be good" → time: "3:00 PM"
    - "May 21 3pm" → date: "Wednesday, May 21, 2025", time: "3:00 PM"
    - "May 21th" (typo) → date: "Wednesday, May 21, 2025"
    - "May 20 at 10 o'clock" → date: "Tuesday, May 20, 2025", time: "10:00 AM"
    - "slot_2025-05-21_14_00" → slot_id: "slot_2025-05-21_14_00"
    - "I will pick the 4 pm on 26 may" → date: "Monday, May 26, 2025", time: "4:00 PM"
    - "ok i will pick the 4 pm on 26 may" → date: "Monday, May 26, 2025", time: "4:00 PM"
    - "give me the slot for monday at 4" → date: identify Monday date, time: "4:00 PM"
    
    Consider ALL available slots when determining the match. If the user mentions a date that matches
    one of the available options, use the exact date format from available options.
    
    Pay special attention to phrases indicating the user is choosing or confirming a slot, such as:
    - "I'll take..."
    - "I will pick..."
    - "book me for..."
    - "let's do..."
    - "ok..."
    - "want to book..."
    - "confirm the slot..."
    
    Respond in JSON format:
    {{
        "date": "exact date as it appears in the available slots, or null if not found or unclear",
        "time": "exact time as it appears in the available slots, or null if not found or unclear",
        "slot_id": "exact slot ID if identifiable, or null if not found",
        "is_booking_confirmation": true/false,
        "confidence": "high/medium/low"
    }}
    """
    
    try:
        # Call OpenAI for slot detection - use gpt-3.5-turbo for best accuracy
        slot_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": slot_selection_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # Parse slot information
        slot_info = json.loads(slot_response.choices[0].message.content)
        print(f"AI Extracted Slot Info: {slot_info}")
        
        # Cache the result with timestamp
        _slot_extraction_cache[cache_key] = slot_info
        _cache_timestamps[cache_key] = time.time()
        
        # If we have a direct slot ID match from regex, use it with high confidence
        if slot_id_match:
            slot_info["slot_id"] = slot_id_match.group(1)
            slot_info["confidence"] = "high"
            slot_info["is_booking_confirmation"] = True
            print(f"Found direct slot ID match: {slot_id_match.group(1)}")
            return slot_info
        
        # Double-check the date against available options to improve matching
        if slot_info.get("date") and slot_info["date"] != "null":
            best_match = None
            best_score = 0
            target_date = slot_info["date"].lower()
            
            for available_date in all_dates:
                # Calculate similarity score (simple approach)
                score = sum(c1 == c2 for c1, c2 in zip(target_date, available_date.lower()))
                if score > best_score:
                    best_score = score
                    best_match = available_date
            
            # Update with best match if confidence is high enough
            if best_match and best_score > len(target_date) * 0.7:
                slot_info["date"] = best_match
                slot_info["confidence"] = "high"
                print(f"Improved date match: {target_date} → {best_match}")
        
        return slot_info
        
    except Exception as e:
        print(f"Error in AI slot extraction: {str(e)}")
        # Return basic extraction as fallback
        fallback_result = {
            "date": None,
            "time": None,
            "slot_id": slot_id_match.group(1) if slot_id_match else None,
            "is_booking_confirmation": bool(slot_id_match),
            "confidence": "high" if slot_id_match else "low"
        }
        
        # Cache the fallback result too
        _slot_extraction_cache[cache_key] = fallback_result
        _cache_timestamps[cache_key] = time.time()
        return fallback_result

def analyze_appointment_query(query):
    """Analyze user query to determine intent with caching"""
    
    # Clean up old cache entries periodically
    cleanup_cache()
    
    # Check cache first
    cache_key = get_cache_key(query)
    if cache_key in _analysis_cache:
        print(f"[CACHE] Using cached analysis for query: {query[:50]}...")
        return _analysis_cache[cache_key]
    
    print(f"[API] Analyzing appointment query: {query}")
    
    # Pattern-based pre-analysis for common day queries
    specific_day = None
    has_day_specific_query = False
    day_query_patterns = [
        r"(?:show|list|display|get|give|what)(?:\s+\w+){0,3}\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        r"(?:available|show|slots?)(?:\s+\w+){0,3}\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+\w+){0,3}(?:slots?|times?|appointments?)"
    ]
    
    weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
    # Check if query mentions a specific day
    for day in weekday_names:
        if day in query.lower():
            specific_day = day
            has_day_specific_query = True
            break
    
    for pattern in day_query_patterns:
        matches = re.findall(pattern, query.lower())
        if matches:
            has_day_specific_query = True
            specific_day = matches[0].capitalize() if isinstance(matches[0], str) else matches[0][0].capitalize()
            break
    
    # Build a prompt for AI analysis of the query
    intent_analysis_prompt = f"""
    Analyze the following user message in the context of appointment scheduling:
    
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
        # Call OpenAI for intent analysis
        intent_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": intent_analysis_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # Parse intent information
        intent_info = json.loads(intent_response.choices[0].message.content)
        print(f"AI Intent Analysis: {intent_info}")
        
        # Add our pattern-based day-specific flag
        intent_info["is_day_specific_query"] = has_day_specific_query
        intent_info["specific_day"] = specific_day or intent_info.get("specific_day")
        
        # Cache the result with timestamp
        _analysis_cache[cache_key] = intent_info
        _cache_timestamps[cache_key] = time.time()
        
        return intent_info
        
    except Exception as e:
        print(f"Error in AI query analysis: {str(e)}")
        # Return a default intent if analysis fails
        fallback_result = {
            "intent": "general_question",
            "specific_day": specific_day,
            "specific_date": None,
            "specific_time": None,
            "clarification_needed": False,
            "is_weekend_query": False,
            "confidence": "low",
            "is_day_specific_query": has_day_specific_query
        }
        
        # Cache the fallback result too
        _analysis_cache[cache_key] = fallback_result
        _cache_timestamps[cache_key] = time.time()
        return fallback_result

def handle_booking(query, user_data, available_slots, language):
    """Handle the appointment booking process with loop prevention"""
    
    # Circuit breaker - prevent infinite loops
    if "api_call_count" not in user_data:
        user_data["api_call_count"] = 0
    
    user_data["api_call_count"] += 1
    
    # If we've made too many API calls, return a simple response
    if user_data["api_call_count"] > 3:
        print(f"[CIRCUIT_BREAKER] Too many API calls ({user_data['api_call_count']}), returning simple response")
        
        simple_response = f"I'd be happy to help you schedule an appointment. Here are the available slots:\n\n{available_slots}\n\nPlease reply with your preferred date and time."
        
        # Reset counter for next conversation
        user_data["api_call_count"] = 0
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": simple_response
        })
        
        return {
            "answer": simple_response,
            "mode": "appointment",
            "language": language,
            "user_data": user_data,
            "available_slots": available_slots
        }
    
    print(f"[DEBUG] handle_booking called with query: '{query[:100]}...' (API call #{user_data['api_call_count']})")
    
    # If available_slots is not provided, get them
    if not available_slots:
        available_slots = get_available_slots()
    
    # Track conversation context (what day was just discussed)
    # Initialize appointment context if not present
    if "appointment_context" not in user_data:
        user_data["appointment_context"] = {}
    
    # Debug information
    print(f"Current appointment context before processing: {user_data.get('appointment_context', {})}")
    
    # Check for simple booking intent first - if user says "book appointment" without specifics, show slots
    simple_booking_phrases = [
        "book an appointment", "book appointment", "schedule appointment", 
        "make an appointment", "make appointment", "i want to book", "help me book",
        "can you help me book", "book me", "schedule me"
    ]
    
    if any(phrase in query.lower() for phrase in simple_booking_phrases):
        # Check if the query is just asking for help booking without specific details
        has_specific_details = any([
            re.search(r'\d+:\d+', query),  # Has time like 10:30
            re.search(r'\d+\s*(am|pm)', query.lower()),  # Has time like 10 am
            any(day in query.lower() for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]),
            re.search(r'slot_\d{4}-\d{2}-\d{2}_\d+_\d+', query),  # Has slot ID
        ])
        
        if not has_specific_details:
            print(f"[DEBUG] Simple booking request without specifics - showing available slots")
            
            response = f"I'd be happy to help you schedule an appointment! Here are the available slots:\n\n{available_slots}\n\nPlease let me know which date and time works best for you."
            
            # Add this interaction to history
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": response
            })
            
            # Reset API call counter since we handled this without API calls
            user_data["api_call_count"] = 0
            
            return {
                "answer": response,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "available_slots": available_slots
            }
    
    # TIME SELECTION DETECTION
    # Before analyzing intent, check if this is a direct time selection based on context
    last_discussed_day = user_data["appointment_context"].get("last_discussed_day")
    
    if last_discussed_day:
        print(f"Found last_discussed_day in context: {last_discussed_day}")
        
        # Simple regex patterns to detect time selection
        time_patterns = [
            r"(?:can\s+i|i'll|i\s+will|let\s+me)\s+(?:pick|take|choose|book|have|get)\s+(?:the)?\s*(\d{1,2}(?:[\.:]\d{2})?\s*(?:am|pm|AM|PM))",
            r"(?:book|reserve|schedule)\s+(?:the)?\s*(\d{1,2}(?:[\.:]\d{2})?\s*(?:am|pm|AM|PM))",
            r"(?:pick|take|choose)\s+(?:the)?\s*(\d{1,2}(?:[\.:]\d{2})?\s*(?:am|pm|AM|PM))",
            r"(?:^|\s+)(\d{1,2}(?:[\.:]\d{2})?\s*(?:am|pm|AM|PM))(?:$|\s+)",  # Just the time by itself
            r"(?:the\s+)?(\d{1,2}(?:[\.:]\d{2})?\s*(?:am|pm|AM|PM))\s+(?:slot|time|appointment)",  # The 4PM slot/time
            r"(?:can\s+i|i'll|i\s+will|let\s+me)\s+(?:pick|take|choose|book|have|get)\s+(?:the|a|an)?\s*(?:[a-zA-Z]+\s+)?(\d{1,2}(?:[\.:]\d{2})?)(?:\s*|\.)(?:am|pm|AM|PM)"  # Special case for "can i pick 4.00PM"
        ]
        
        for pattern in time_patterns:
            time_match = re.search(pattern, query, re.IGNORECASE)
            if time_match:
                selected_time = time_match.group(1)
                print(f"Detected direct time selection: {selected_time} for day: {last_discussed_day}")
                
                # Find this time slot on the last discussed day
                day_section = False
                matching_slot_id = None
                
                for line in available_slots.split('\n'):
                    if "📅" in line and last_discussed_day in line:
                        day_section = True
                        continue
                    elif day_section and "ID: slot_" in line:
                        # Try to match the selected time with flexible comparison
                        hour_match = re.search(r'(\d{1,2})', selected_time)
                        if hour_match:
                            hour = hour_match.group(1)
                            
                            # Figure out if this is AM or PM
                            is_pm = False
                            if "PM" in selected_time.upper():
                                is_pm = True
                            
                            print(f"Trying to match hour: {hour}, is_pm: {is_pm}")
                            
                            # Check if this line contains this hour and period
                            if hour in line and ((is_pm and "PM" in line) or (not is_pm and "AM" in line)):
                                try:
                                    matching_slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                                    print(f"Found matching slot ID for time selection: {matching_slot_id}")
                                    break
                                except Exception as e:
                                    print(f"Error extracting slot ID: {e}")
                                    pass
                    elif day_section and "📅" in line:
                        day_section = False
                
                if matching_slot_id:
                    # Book the identified slot
                    user_data["appointment_slot"] = matching_slot_id
                    
                    confirmation = f"Appointment booked for {last_discussed_day} at {selected_time}. Confirmation sent to {user_data.get('email', 'your email')}. Need anything else?"
                    
                    # Add this interaction to history
                    user_data["conversation_history"].append({
                        "role": "assistant", 
                        "content": confirmation
                    })
                    
                    # Clear appointment context since booking is complete
                    user_data["appointment_context"] = {}
                    
                    # Reset API call counter after successful booking
                    user_data["api_call_count"] = 0
                    
                    return {
                        "answer": confirmation,
                        "mode": "faq",  # Reset to FAQ mode after booking
                        "language": language,
                        "user_data": user_data,
                        "appointment_confirmed": True,
                        "selected_slot": matching_slot_id
                    }
    
    # First, analyze the user's query to determine intent
    query_analysis = analyze_appointment_query(query)
    intent = query_analysis.get("intent", "general_question")
    print(f"Query analysis: {intent}")
    
    # Extract slot information
    slot_info = extract_slot_info(query, available_slots)
    print(f"Slot info extracted: {slot_info}")
    
    # Check for time selection with context from previous message
    is_booking_confirmation = slot_info.get("is_booking_confirmation", False)
    has_slot_details = (slot_info.get("date") or slot_info.get("time") or slot_info.get("slot_id"))
    good_confidence = slot_info.get("confidence") in ["high", "medium"]
    
    # Check if this might be selecting a time for a previously discussed day
    last_discussed_day = user_data["appointment_context"].get("last_discussed_day")
    
    # If user is selecting a time without specifying a date, use the last discussed day
    if slot_info.get("time") and not slot_info.get("date") and last_discussed_day:
        print(f"Using conversation context - last discussed day: {last_discussed_day}")
        slot_info["date"] = last_discussed_day
        slot_info["is_booking_confirmation"] = True
        is_booking_confirmation = True
        has_slot_details = True
        print(f"Updated slot info with context: {slot_info}")
    
    # If we have a booking confirmation or sufficient slot info with good confidence, try to book
    if (is_booking_confirmation and has_slot_details and good_confidence) or (
        intent == "book_appointment" and has_slot_details and good_confidence):
        
        # If we have a direct slot ID, use it
        if slot_info.get("slot_id"):
            slot_id = slot_info["slot_id"]
            
            # Extract date and time for confirmation message
            try:
                parts = slot_id.split("_")
                if len(parts) >= 4:
                    date_str = parts[1]
                    hour = int(parts[2])
                    minute = parts[3]
                    
                    # Format date and time
                    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    formatted_date = dt.strftime("%A, %B %d, %Y")
                    
                    # Convert hour to 12-hour format
                    hour_12 = hour if hour <= 12 else hour - 12
                    am_pm = "AM" if hour < 12 else "PM"
                    formatted_time = f"{hour_12}:00 {am_pm}"
                    
                    # Book the appointment
                    user_data["appointment_slot"] = slot_id
                    
                    confirmation = f"Appointment booked for {formatted_date} at {formatted_time}. Confirmation sent to {user_data.get('email', 'your email')}. Need anything else?"
                    
                    # Add this interaction to history
                    user_data["conversation_history"].append({
                        "role": "assistant", 
                        "content": confirmation
                    })
                    
                    # Clear appointment context since booking is complete
                    user_data["appointment_context"] = {}
                    
                    # Reset API call counter after successful booking
                    user_data["api_call_count"] = 0
                    
                    return {
                        "answer": confirmation,
                        "mode": "faq",  # Reset to FAQ mode after booking
                        "language": language,
                        "user_data": user_data,
                        "appointment_confirmed": True,
                        "selected_slot": slot_id
                    }
                
            except Exception as e:
                print(f"Error formatting direct slot ID confirmation: {str(e)}")
    
    # Now check if this is a day-specific query, but only if we didn't already process a booking confirmation
    if query_analysis.get("is_day_specific_query") and query_analysis.get("specific_day"):
        print(f"Detected day-specific query for {query_analysis.get('specific_day')}")
        return handle_specific_day_query(query, user_data, available_slots, language)
    
    # Handle weekend queries
    if query_analysis.get("is_weekend_query", False) or ("saturday" in query.lower() or "sunday" in query.lower()):
        # Get available days from slots
        available_days = []
        for line in available_slots.split('\n'):
            if "📅" in line:
                try:
                    day = line.replace("📅", "").strip().split(",")[0].strip()
                    if day and day not in available_days:
                        available_days.append(day)
                except:
                    continue
        
        # Create a user-friendly response
        response = f"I'm sorry, but I don't have appointments available on weekends. I'm available on {', '.join(available_days)}. Here are the available slots:\n\n{available_slots}"
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": response
        })
        
        return {
            "answer": response,
            "mode": "appointment",
            "language": language,
            "user_data": user_data,
            "available_slots": available_slots
        }
    
    # If we have a booking confirmation or sufficient slot info with good confidence, try to book
    if (is_booking_confirmation and has_slot_details and good_confidence) or (
        intent == "book_appointment" and has_slot_details and good_confidence):
        
        # If we have a direct slot ID, use it
        if slot_info.get("slot_id"):
            slot_id = slot_info["slot_id"]
            
            # Extract date and time for confirmation message
            try:
                parts = slot_id.split("_")
                if len(parts) >= 4:
                    date_str = parts[1]
                    hour = int(parts[2])
                    minute = parts[3]
                    
                    # Format date and time
                    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    formatted_date = dt.strftime("%A, %B %d, %Y")
                    
                    # Convert hour to 12-hour format
                    hour_12 = hour if hour <= 12 else hour - 12
                    am_pm = "AM" if hour < 12 else "PM"
                    formatted_time = f"{hour_12}:00 {am_pm}"
                    
                    # Book the appointment
                    user_data["appointment_slot"] = slot_id
                    
                    confirmation = f"Appointment booked for {formatted_date} at {formatted_time}. Confirmation sent to {user_data.get('email', 'your email')}. Need anything else?"
                    
                    # Add this interaction to history
                    user_data["conversation_history"].append({
                        "role": "assistant", 
                        "content": confirmation
                    })
                    
                    # Clear appointment context since booking is complete
                    user_data["appointment_context"] = {}
                    
                    # Reset API call counter after successful booking
                    user_data["api_call_count"] = 0
                    
                    return {
                        "answer": confirmation,
                        "mode": "faq",  # Reset to FAQ mode after booking
                        "language": language,
                        "user_data": user_data,
                        "appointment_confirmed": True,
                        "selected_slot": slot_id
                    }
                
            except Exception as e:
                print(f"Error formatting direct slot ID confirmation: {str(e)}")
        
        # If we have date and time, find the matching slot
        if slot_info.get("date") and slot_info.get("time"):
            matching_date = slot_info["date"]
            matching_time = slot_info["time"]
            print(f"Looking for slot with date={matching_date} and time={matching_time}")
            
            # Parse slot details from the available slots
            current_date = None
            found_slot_id = None
            
            for line in available_slots.split('\n'):
                if "📅" in line:
                    current_date = line.replace("📅", "").strip()
                elif current_date == matching_date and "ID: slot_" in line:
                    # Check if this line has the matching time
                    if matching_time in line:
                        try:
                            found_slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                            print(f"Found matching slot ID: {found_slot_id}")
                            break
                        except:
                            pass
                    else:
                        # Try to match with more flexible time comparison
                        # Convert "4:00 PM" to match with "4 PM" and vice versa
                        try:
                            time_in_line = re.search(r'(\d+:\d+\s*(?:AM|PM)|\d+\s*(?:AM|PM))', line).group(0)
                            hour_match = re.search(r'(\d+)', matching_time).group(1)
                            period_match = re.search(r'(AM|PM)', matching_time, re.IGNORECASE).group(1)
                            if (hour_match in time_in_line and 
                                period_match.upper() in time_in_line.upper()):
                                found_slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                                print(f"Found matching slot ID with flexible time match: {found_slot_id}")
                                break
                        except Exception as e:
                            print(f"Error in flexible time matching: {e}")
                            pass
            
            if found_slot_id:
                # Book the appointment
                user_data["appointment_slot"] = found_slot_id
                
                confirmation = f"Appointment booked for {matching_date} at {matching_time}. Confirmation sent to {user_data.get('email', 'your email')}. Need anything else?"
                
                # Add this interaction to history
                user_data["conversation_history"].append({
                    "role": "assistant", 
                    "content": confirmation
                })
                
                # Clear appointment context since booking is complete
                user_data["appointment_context"] = {}
                
                # Reset API call counter after successful booking
                user_data["api_call_count"] = 0
                
                return {
                    "answer": confirmation,
                    "mode": "faq",  # Reset to FAQ mode after booking
                    "language": language,
                    "user_data": user_data,
                    "appointment_confirmed": True,
                    "selected_slot": found_slot_id
                }
            
            # If we can't find an exact slot ID but have a date and time, construct it
            try:
                # Try to parse the date and time to construct a slot ID
                date_parts = matching_date.split(",")
                
                if len(date_parts) >= 2:
                    # Extract month and day
                    month_day = date_parts[1].strip()
                    month_name = month_day.split(" ")[0]  # May
                    day_num = month_day.split(" ")[1]     # 26
                    
                    # Get the year from the date or use current year
                    year = None
                    if len(date_parts) >= 3:
                        year_part = date_parts[2].strip()
                        if year_part.isdigit():
                            year = int(year_part)
                    
                    if not year:
                        # Use current year if not specified
                        year = datetime.datetime.now().year
                    
                    # Convert month name to number
                    month_map = {
                        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
                    }
                    
                    month_num = None
                    for abbr, num in month_map.items():
                        if month_name.lower().startswith(abbr):
                            month_num = num
                            break
                    
                    # Convert time to 24-hour format
                    hour = 0
                    if ":" in matching_time:
                        time_parts = matching_time.split(":")
                        hour = int(time_parts[0])
                    else:
                        # Handle format like "3 PM"
                        time_parts = matching_time.split(" ")
                        hour = int(time_parts[0])
                    
                    # Adjust for PM
                    if "PM" in matching_time.upper() and hour < 12:
                        hour += 12
                    
                    if month_num and day_num:
                        # Create the slot ID
                        date_str = f"{year}-{month_num:02d}-{int(day_num):02d}"
                        constructed_slot_id = f"slot_{date_str}_{hour:02d}_00"
                        
                        # Book the appointment
                        user_data["appointment_slot"] = constructed_slot_id
                        
                        confirmation = f"Appointment booked for {matching_date} at {matching_time}. Confirmation sent to {user_data.get('email', 'your email')}. Need anything else?"
                        
                        # Add this interaction to history
                        user_data["conversation_history"].append({
                            "role": "assistant", 
                            "content": confirmation
                        })
                        
                        # Clear appointment context since booking is complete
                        user_data["appointment_context"] = {}
                        
                        # Reset API call counter after successful booking
                        user_data["api_call_count"] = 0
                        
                        return {
                            "answer": confirmation,
                            "mode": "faq",  # Reset to FAQ mode after booking
                            "language": language,
                            "user_data": user_data,
                            "appointment_confirmed": True,
                            "selected_slot": constructed_slot_id
                        }
                
            except Exception as e:
                print(f"Error constructing slot ID: {str(e)}")
        
        # If we only have a date, show available times for that day
        if slot_info.get("date"):
            target_day = slot_info["date"]
            day_section = False
            matching_times = []
            
            # Set this day as the last discussed day in context
            user_data["appointment_context"]["last_discussed_day"] = target_day
            
            for line in available_slots.split('\n'):
                if "📅" in line and target_day in line:
                    # Found the day, now get the times
                    day_section = True
                    continue
                elif day_section and "ID: slot_" in line:
                    try:
                        time_part = re.search(r'(\d+:\d+\s*(?:AM|PM)|\d+\s*(?:AM|PM))', line).group(0)
                        slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                        matching_times.append(f"{time_part} (ID: {slot_id})")
                    except:
                        pass
                elif day_section and "📅" in line:
                    day_section = False
            
            if matching_times:
                response = f"Available times on {target_day}:\n" + "\n".join([f"• {time}" for time in matching_times]) + "\n\nWhich time works for you?"
            else:
                response = f"No slots available on {target_day}. Here are other options:\n{available_slots}"
            
            # Add this interaction to history
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": response
            })
            
            return {
                "answer": response,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "available_slots": available_slots
            }
            
    elif intent == "ask_availability":
        # Handle availability queries
        if query_analysis.get("specific_day") or slot_info.get("date"):
            target_day = query_analysis.get("specific_day") or slot_info.get("date")
            
            # Find the matching day in available slots
            matching_day = None
            for date in available_slots.split('\n'):
                if "📅" in date and target_day.lower() in date.lower():
                    matching_day = date.replace("📅", "").strip()
                    break
            
            if not matching_day:
                # Try to find by day of week
                days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                for day in days_of_week:
                    if day in target_day.lower():
                        for date in available_slots.split('\n'):
                            if "📅" in date and day.capitalize() in date:
                                matching_day = date.replace("📅", "").strip()
                                break
                        if matching_day:
                            break
            
            if matching_day:
                # Set conversation context to remember the day just discussed
                user_data["appointment_context"]["last_discussed_day"] = matching_day
                
                day_section = False
                matching_times = []
                
                for line in available_slots.split('\n'):
                    if "📅" in line and matching_day in line:
                        # Found the day, now get the times
                        day_section = True
                        continue
                    elif day_section and "ID: slot_" in line:
                        try:
                            time_part = re.search(r'(\d+:\d+\s*(?:AM|PM)|\d+\s*(?:AM|PM))', line).group(0)
                            slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                            matching_times.append(f"{time_part} (ID: {slot_id})")
                        except:
                            pass
                    elif day_section and "📅" in line:
                        day_section = False
                
                if matching_times:
                    response = f"Available times on {matching_day}:\n" + "\n".join([f"• {time}" for time in matching_times]) + "\n\nWhich time works for you?"
                else:
                    response = f"No slots available on {matching_day}. Here are other options:\n{available_slots}"
                
                # Add this interaction to history
                user_data["conversation_history"].append({
                    "role": "assistant", 
                    "content": response
                })
                
                return {
                    "answer": response,
                    "mode": "appointment",
                    "language": language,
                    "user_data": user_data,
                    "available_slots": available_slots
                }
            else:
                # If we couldn't find a matching day, show all available slots
                response = f"I couldn't find availability for {target_day}. Here are all available appointment slots:\n\n{available_slots}\n\nPlease let me know which date and time works for you."
                
                # Add this interaction to history
                user_data["conversation_history"].append({
                    "role": "assistant", 
                    "content": response
                })
                
                return {
                    "answer": response,
                    "mode": "appointment",
                    "language": language,
                    "user_data": user_data,
                    "available_slots": available_slots
                }
        else:
            # Show all available slots
            response = f"Here are all available appointment slots:\n\n{available_slots}\n\nPlease let me know which date and time works for you."
            
            # Add this interaction to history
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": response
            })
            
            return {
                "answer": response,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "available_slots": available_slots
            }
    
    # Default response for other intents or if booking/availability handling failed
    response = f"I'd be happy to help you schedule an appointment. Here are the available slots:\n\n{available_slots}\n\nPlease reply with the date and time you prefer, or the slot ID directly (e.g., 'slot_2023-09-15_10_00')."
    
    # Add this interaction to history
    user_data["conversation_history"].append({
        "role": "assistant", 
        "content": response
    })
    
    return {
        "answer": response,
        "mode": "appointment",
        "language": language,
        "user_data": user_data,
        "available_slots": available_slots
    }

def handle_rescheduling(user_data, available_slots, language):
    """Handle rescheduling an existing appointment"""
    # Save old appointment details for reference
    previous_slot = user_data["appointment_slot"]
    
    # Extract date and time for confirmation
    try:
        parts = previous_slot.split("_")
        if len(parts) >= 4:
            date_str = parts[1]
            hour = int(parts[2])
            minute = parts[3]
            
            # Format the date and time nicely
            try:
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                formatted_date = dt.strftime("%A, %B %d, %Y")
            except:
                formatted_date = date_str
            
            # Convert hour to 12-hour format
            hour_12 = hour if hour <= 12 else hour - 12
            am_pm = "AM" if hour < 12 else "PM"
            formatted_time = f"{hour_12}:{minute if minute != '00' else '00'} {am_pm}"
            
            previous_appointment = f"{formatted_date} at {formatted_time}"
        else:
            previous_appointment = previous_slot
    except Exception as e:
        print(f"Error formatting previous appointment: {str(e)}")
        previous_appointment = previous_slot
    
    # Remove the old appointment
    user_data.pop("appointment_slot")
    
    # Get available slots
    if not available_slots:
        available_slots = get_available_slots()
    
    response = f"I see you'd like to reschedule your appointment. Your previous booking for {previous_appointment} has been canceled. Here are the available slots:\n\n{available_slots}\n\nPlease select a new time."
    
    # Add this interaction to history
    user_data["conversation_history"].append({
        "role": "assistant", 
        "content": response
    })
    
    return {
        "answer": response,
        "mode": "appointment",
        "language": language,
        "user_data": user_data,
        "available_slots": available_slots
    }

def handle_cancellation(user_data, language):
    """Handle cancelling an existing appointment"""
    # Get appointment details for confirmation
    slot_id = user_data["appointment_slot"]
    
    # Format the date and time nicely
    try:
        parts = slot_id.split("_")
        if len(parts) >= 4:
            date_str = parts[1]
            hour = int(parts[2])
            minute = parts[3]
            
            # Format the date and time nicely
            try:
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                formatted_date = dt.strftime("%A, %B %d, %Y")
            except:
                formatted_date = date_str
            
            # Convert hour to 12-hour format
            hour_12 = hour if hour <= 12 else hour - 12
            am_pm = "AM" if hour < 12 else "PM"
            formatted_time = f"{hour_12}:{minute if minute != '00' else '00'} {am_pm}"
            
            appointment_details = f"{formatted_date} at {formatted_time}"
        else:
            appointment_details = slot_id
    except Exception as e:
        print(f"Error formatting appointment details: {str(e)}")
        appointment_details = slot_id
    
    # Remove the appointment
    user_data.pop("appointment_slot")
    
    response = f"I've canceled your appointment for {appointment_details}. If you'd like to book a new appointment in the future, just let me know."
    
    # Add this interaction to history
    user_data["conversation_history"].append({
        "role": "assistant", 
        "content": response
    })
    
    return {
        "answer": response,
        "mode": "faq",
        "language": language,
        "user_data": user_data
    }

def handle_appointment_info(user_data, language):
    """Handle providing information about an existing appointment"""
    # Get appointment details
    slot_id = user_data["appointment_slot"]
    
    # Format the date and time nicely
    try:
        parts = slot_id.split("_")
        if len(parts) >= 4:
            date_str = parts[1]
            hour = int(parts[2])
            minute = parts[3]
            
            # Format the date and time nicely
            try:
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                formatted_date = dt.strftime("%A, %B %d, %Y")
            except:
                formatted_date = date_str
            
            # Convert hour to 12-hour format
            hour_12 = hour if hour <= 12 else hour - 12
            am_pm = "AM" if hour < 12 else "PM"
            formatted_time = f"{hour_12}:{minute if minute != '00' else '00'} {am_pm}"
            
            appointment_details = f"{formatted_date} at {formatted_time}"
        else:
            appointment_details = slot_id
    except Exception as e:
        print(f"Error formatting appointment details: {str(e)}")
        appointment_details = slot_id
    
    response = f"You have an appointment scheduled for {appointment_details}. We'll send a reminder to your email at {user_data.get('email', 'your email address')}. If you need to reschedule or cancel, just let me know."
    
    # Add this interaction to history
    user_data["conversation_history"].append({
        "role": "assistant", 
        "content": response
    })
    
    return {
        "answer": response,
        "mode": "faq",
        "language": language,
        "user_data": user_data
    }

def handle_specific_day_query(query, user_data, available_slots, language):
    """Handle a query asking for slots on a specific day"""
    # Parse out the day from the query
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    target_day = None
    
    # Simple pattern matching for day names
    for day in days_of_week:
        if day in query.lower():
            target_day = day.capitalize()
            break
    
    if not target_day:
        # No specific day found, show all slots
        return handle_booking(query, user_data, available_slots, language)
    
    # Find the matching day in available slots
    matching_day = None
    for line in available_slots.split('\n'):
        if "📅" in line and target_day in line:
            matching_day = line.replace("📅", "").strip()
            break
    
    if matching_day:
        # CRITICAL: Save this day in the appointment context
        if "appointment_context" not in user_data:
            user_data["appointment_context"] = {}
        user_data["appointment_context"]["last_discussed_day"] = matching_day
        print(f"Setting last_discussed_day to: {matching_day}")
        
        # Extract the slots for this day
        day_section = False
        matching_times = []
        
        for line in available_slots.split('\n'):
            if "📅" in line and matching_day in line:
                day_section = True
                continue
            elif day_section and "ID: slot_" in line:
                try:
                    time_part = re.search(r'(\d+:\d+\s*(?:AM|PM)|\d+\s*(?:AM|PM))', line).group(0)
                    slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                    matching_times.append(f"• {time_part} (ID: {slot_id})")
                except:
                    pass
            elif day_section and "📅" in line:
                day_section = False
        
        if matching_times:
            # Group slots into morning and afternoon
            morning_slots = [t for t in matching_times if "AM" in t]
            afternoon_slots = [t for t in matching_times if "PM" in t]
            
            response = f"Here are the available appointment slots for {matching_day}:\n\n"
            
            if morning_slots:
                response += "Morning:\n" + "\n".join(morning_slots) + "\n\n"
            
            if afternoon_slots:
                response += "Afternoon:\n" + "\n".join(afternoon_slots) + "\n\n"
            
            response += "Please let me know which slot you'd like to book, or provide the slot ID for your preferred time."
            
            # Add this interaction to history
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": response
            })
            
            return {
                "answer": response,
                "mode": "appointment",
                "language": language,
                "user_data": user_data,
                "available_slots": available_slots
            }
    
    # If we didn't find matching slots, fall back to showing all slots
    return handle_booking(query, user_data, available_slots, language) 