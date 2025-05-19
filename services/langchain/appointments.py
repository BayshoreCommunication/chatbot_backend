import datetime
import random
import json
import openai

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
    
    # Group slots by date for better readability
    slots_by_date = {}
    for slot in available_slots:
        if slot["date_display"] not in slots_by_date:
            slots_by_date[slot["date_display"]] = []
        slots_by_date[slot["date_display"]].append(slot)
    
    # Format slots for display in chat
    slots_formatted = "Available appointment slots:\n\n"
    
    for date, date_slots in slots_by_date.items():
        slots_formatted += f"📅 {date}\n"
        
        morning_slots = [slot for slot in date_slots if slot["period"] == "morning"]
        if morning_slots:
            slots_formatted += "  Morning:\n"
            for slot in morning_slots:
                display_hour = int(slot["time"].split(":")[0])
                am_pm = "AM"
                slots_formatted += f"    • {display_hour}:00 {am_pm} (ID: {slot['id']})\n"
        
        afternoon_slots = [slot for slot in date_slots if slot["period"] == "afternoon"]
        if afternoon_slots:
            slots_formatted += "  Afternoon:\n"
            for slot in afternoon_slots:
                display_hour = int(slot["time"].split(":")[0])
                if display_hour > 12:
                    display_hour -= 12
                slots_formatted += f"    • {display_hour}:00 PM (ID: {slot['id']})\n"
        
        slots_formatted += "\n"
    
    return slots_formatted

def extract_slot_info(query, available_slots):
    """Extract date, time, or slot ID from user query"""
    # First, analyze available slots to understand the date/time format
    all_dates = []
    all_times = []
    all_slot_ids = []

    # Parse available slots to extract date, time and slot ID information
    if isinstance(available_slots, str):
        # Extract dates, times, and slot IDs from available_slots string
        for line in available_slots.split('\n'):
            if "📅" in line:
                date_match = line.replace("📅", "").strip()
                all_dates.append(date_match)
            if "ID: slot_" in line:
                slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                all_slot_ids.append(slot_id)
                # Extract time from this line too
                if "AM" in line or "PM" in line:
                    try:
                        time_part = line.split("•")[1].split("(ID:")[0].strip()
                        if time_part and time_part not in all_times:
                            all_times.append(time_part)
                    except:
                        pass
    
    # Build a comprehensive prompt that includes examples and knowledge about available options
    slot_selection_prompt = f"""
    Extract the date and time from the following user request for an appointment booking.
    If a specific slot or slot ID is mentioned, identify it.
    
    THIS IS CRITICAL: The user may have typos, or mention dates/times in an ambiguous format, 
    or use informal language like "tomorrow" or "next Tuesday". Use your best judgment to 
    determine what date and time they're referring to.
    
    User Request: "{query}"
    
    Available Dates: {', '.join(all_dates)}
    Available Times: {', '.join(all_times)}
    Available Slot IDs: {', '.join(all_slot_ids[:5])} (and more...)
    
    Full Available Slots:
    {available_slots}
    
    Examples of how to interpret user queries:
    - "I want May 21" → date: "May 21, 2025"
    - "Tuesday works" → date: identify corresponding date for Tuesday
    - "3 PM would be good" → time: "3:00 PM"
    - "May 21 3pm" → date: "May 21, 2025", time: "3:00 PM"
    - "May 21th" (typo) → date: "May 21, 2025"
    - "May 20 at 10 o'clock" → date: "May 20, 2025", time: "10:00 AM"
    - "slot_2025-05-21_14_00" → slot_id: "slot_2025-05-21_14_00"
    
    Consider ALL available slots when determining the match. If the user mentions a date that matches
    one of the available options, use the exact date format from available options.
    
    Respond in JSON format:
    {{
        "date": "exact date as it appears in the available slots, or null if not found or unclear",
        "time": "exact time as it appears in the available slots, or null if not found or unclear",
        "slot_id": "exact slot ID if identifiable, or null if not found",
        "confidence": "high/medium/low"
    }}
    """
    
    try:
        # Call OpenAI for slot detection - use GPT-4.1 for best accuracy
        slot_response = openai.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": slot_selection_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # Parse slot information
        slot_info = json.loads(slot_response.choices[0].message.content)
        print(f"AI Extracted Slot Info: {slot_info}")
        
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
        print(f"Error in extract_slot_info: {str(e)}")
        # Return an empty result as fallback
        return {
            "date": None,
            "time": None,
            "slot_id": None,
            "confidence": "low"
        }

def analyze_appointment_query(query):
    """
    Use AI to analyze the user's query related to appointment booking.
    
    Args:
        query (str): The user's query text
        
    Returns:
        dict: A dictionary containing the analysis results
    """
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
        "confidence": "high/medium/low"
    }}
    """
    
    try:
        # Call OpenAI for intent analysis
        intent_response = openai.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": intent_analysis_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # Parse intent information
        intent_info = json.loads(intent_response.choices[0].message.content)
        print(f"AI Intent Analysis: {intent_info}")
        return intent_info
        
    except Exception as e:
        print(f"Error in AI query analysis: {str(e)}")
        # Return a default intent if analysis fails
        return {
            "intent": "general_question",
            "specific_day": None,
            "specific_date": None,
            "specific_time": None,
            "clarification_needed": False,
            "is_weekend_query": False,
            "confidence": "low"
        }

def handle_booking(query, user_data, available_slots, language):
    """Handle the appointment booking process"""
    # If available_slots is not provided, get them
    if not available_slots:
        available_slots = get_available_slots()
    
    # First, analyze the user's query to determine intent
    query_analysis = analyze_appointment_query(query)
    intent = query_analysis.get("intent", "general_question")
    
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
    
    # Get detailed slot information if needed
    slot_info = None
    if intent in ["book_appointment", "ask_availability"]:
        slot_info = extract_slot_info(query, available_slots)
        print(f"Slot info extracted: {slot_info}")
    
    # Handle specific intents
    if intent == "book_appointment":
        # Check if we have enough information to book
        if slot_info and slot_info.get("confidence") in ["high", "medium"] and (
            slot_info.get("day") or slot_info.get("time") or slot_info.get("date")):
            
            # If we have a day and time, try to find the matching slot
            day_found = slot_info.get("day")
            time_found = slot_info.get("time")
            date_found = slot_info.get("date")
            
            # Parse available slots
            slots_by_day = {}
            current_day = None
            day_time_matches = []
            
            for line in available_slots.split('\n'):
                if "📅" in line:
                    current_day = line.replace("📅", "").strip()
                    slots_by_day[current_day] = []
                elif current_day and ("AM:" in line or "PM:" in line):
                    slots_by_day[current_day].append(line.strip())
            
            # Try to match day and time
            for day, slots in slots_by_day.items():
                # Check if the day matches
                day_matches = False
                if day_found and day_found.lower() in day.lower():
                    day_matches = True
                elif date_found and date_found.lower() in day.lower():
                    day_matches = True
                
                if day_matches:
                    # Day matches, now check for time
                    if not time_found:
                        # If no specific time, collect all slots for this day
                        for slot_line in slots:
                            day_time_matches.append((day, slot_line))
                    else:
                        # Check for time match
                        for slot_line in slots:
                            if time_found.upper() in slot_line:
                                day_time_matches.append((day, slot_line))
                                break
            
            # If we have matches
            if day_time_matches:
                # Take the first match
                matching_day, slot_times = day_time_matches[0]
                
                # Extract time from slot_times
                matching_time = None
                if time_found:
                    matching_time = time_found
                else:
                    # Take the first available time
                    try:
                        if "AM:" in slot_times:
                            am_times = slot_times.split("AM:")[1].split("|")[0].strip().split(",")
                            matching_time = am_times[0].strip()
                        elif "PM:" in slot_times:
                            pm_times = slot_times.split("PM:")[1].split("|")[0].strip().split(",")
                            matching_time = pm_times[0].strip()
                    except Exception as e:
                        print(f"Error extracting time: {str(e)}")
                
                if matching_time:
                    # Try to construct a slot ID
                    try:
                        # Extract year-month-day from matching_day
                        day_parts = matching_day.split(",")
                        month_day = day_parts[1].strip() if len(day_parts) > 1 else matching_day
                        
                        # Convert matching_time to 24-hour format
                        hour = int(matching_time.replace("AM", "").replace("PM", ""))
                        if "PM" in matching_time.upper() and hour < 12:
                            hour += 12
                        
                        # Try to construct a date string
                        today = datetime.datetime.now()
                        year = today.year
                        
                        # Format the slot ID
                        date_parts = month_day.strip().split(" ")
                        if len(date_parts) >= 2:
                            month_name = date_parts[0]  # May
                            day_num = date_parts[1]     # 26
                            
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
                            
                            if month_num and day_num:
                                # Create date string
                                date_str = f"{year}-{month_num:02d}-{int(day_num):02d}"
                                slot_id = f"slot_{date_str}_{hour:02d}_00"
                                
                                # Book the appointment
                                user_data["appointment_slot"] = slot_id
                                
                                # Format confirmation message
                                confirmation = f"Appointment booked for {matching_day} at {matching_time}. Confirmation sent to {user_data.get('email', 'your email')}. Need anything else?"
                                
                                # Add this interaction to history
                                user_data["conversation_history"].append({
                                    "role": "assistant", 
                                    "content": confirmation
                                })
                                
                                return {
                                    "answer": confirmation,
                                    "mode": "faq",  # Reset to FAQ mode after booking
                                    "language": language,
                                    "user_data": user_data,
                                    "appointment_confirmed": True,
                                    "selected_slot": slot_id
                                }
                    except Exception as e:
                        print(f"Error creating slot ID: {str(e)}")
        
        # If booking failed or we only have partial info, show times for a specific day
        specific_day = query_analysis.get("specific_day") or (slot_info and slot_info.get("day"))
        if specific_day:
            target_day = specific_day
            day_section = False
            matching_times = []
            
            for line in available_slots.split('\n'):
                if "📅" in line and target_day.lower() in line.lower():
                    # Found the day, now get the times
                    day_section = True
                    continue
                elif day_section and ("AM:" in line or "PM:" in line):
                    matching_times.append(line.strip())
                elif "📅" in line:
                    day_section = False
            
            if matching_times:
                response = f"Available times on {target_day}: {', '.join(matching_times)}. Which time works for you?"
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
        # Show availability for a specific day if mentioned
        if query_analysis.get("specific_day"):
            target_day = query_analysis["specific_day"]
            day_section = False
            matching_times = []
            
            for line in available_slots.split('\n'):
                if "📅" in line and target_day.lower() in line.lower():
                    # Found the day, now get the times
                    day_section = True
                    continue
                elif day_section and ("AM:" in line or "PM:" in line):
                    matching_times.append(line.strip())
                elif "📅" in line:
                    day_section = False
            
            if matching_times:
                response = f"Available times on {target_day}: {', '.join(matching_times)}. Which time works for you?"
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