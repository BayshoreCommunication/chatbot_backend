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
    slot_selection_prompt = f"""
    Extract the date and time from the following user request for an appointment booking.
    If a specific slot is mentioned, identify its ID.
    
    User Request: "{query}"
    
    Available Slots:
    {available_slots}
    
    Respond in JSON format:
    {{
        "date": "date mentioned or null",
        "time": "time mentioned or null",
        "slot_id": "slot ID if identifiable or null",
        "confidence": "high/medium/low"
    }}
    """
    
    # Call OpenAI for slot detection
    slot_response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": slot_selection_prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    # Parse slot information
    return json.loads(slot_response.choices[0].message.content)

def handle_booking(query, user_data, available_slots, language):
    """Handle the appointment booking process"""
    # If available_slots is not provided, get them
    if not available_slots:
        available_slots = get_available_slots()
    
    # Extract slot info
    slot_info = extract_slot_info(query, available_slots)
    print(f"Slot Info: {slot_info}")
    
    # If we have a slot ID or can extract date and time
    slot_id = None
    
    # Check for direct slot ID in the parsed info
    if slot_info.get("slot_id") and slot_info["slot_id"] != "null":
        slot_id = slot_info["slot_id"]
    
    # If we don't have a slot ID but have date and time, look for matching slot
    elif slot_info.get("date") and slot_info["date"] != "null" and slot_info.get("time") and slot_info["time"] != "null":
        # Try to find a matching slot
        all_slots_str = available_slots if isinstance(available_slots, str) else "No slots available"
        
        for line in all_slots_str.split('\n'):
            if slot_info["date"] in line and slot_info["time"] in line and "ID: slot_" in line:
                try:
                    slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                    break
                except IndexError:
                    print(f"Error parsing slot ID from line: {line}")
                    continue
    
    # If we found a valid slot ID
    if slot_id:
        # Book the appointment
        user_data["appointment_slot"] = slot_id
        
        # Extract date and time for confirmation
        try:
            parts = slot_id.split("_")
            if len(parts) >= 4:
                date = parts[1]
                hour = parts[2]
                minute = parts[3]
                time = f"{hour}:{minute}"
                confirmation = f"Great! I've booked your appointment for {date} at {time}. We'll send a confirmation to your email at {user_data.get('email', 'your email address')}. Is there anything else you'd like help with?"
            else:
                confirmation = f"Great! I've booked your appointment with slot ID: {slot_id}. We'll send a confirmation to your email. Is there anything else you'd like help with?"
        except Exception as e:
            print(f"Error formatting confirmation: {str(e)}")
            confirmation = f"Great! I've booked your appointment. We'll send a confirmation to your email at {user_data.get('email', 'your email address')}. Is there anything else you'd like help with?"
        
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
    # If we only have date information
    elif slot_info.get("date") and slot_info["date"] != "null":
        # Show available times for that date
        all_slots_str = available_slots if isinstance(available_slots, str) else "No slots available"
        matching_times = []
        
        for line in all_slots_str.split('\n'):
            if slot_info["date"] in line and "ID: slot_" in line:
                try:
                    time_part = line.split("at ")[1].split(" (ID")[0].strip()
                    slot_id_part = line.split("(ID: ")[1].split(")")[0].strip()
                    matching_times.append((time_part, slot_id_part))
                except IndexError:
                    continue
        
        if matching_times:
            times_str = "\n".join([f"• {time} (ID: {id})" for time, id in matching_times])
            response = f"I see you're interested in booking on {slot_info['date']}. What time would you prefer? Here are the available times:\n\n{times_str}\n\nPlease reply with your preferred time or the slot ID."
            
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
            response = f"I couldn't find any available slots on {slot_info['date']}. Here are all the available slots:\n\n{available_slots}\n\nPlease select a date and time from these options."
            
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
    # If we only have time information
    elif slot_info.get("time") and slot_info["time"] != "null":
        # Show available dates for that time
        all_slots_str = available_slots if isinstance(available_slots, str) else "No slots available"
        matching_dates = []
        
        for line in all_slots_str.split('\n'):
            if slot_info["time"] in line and "ID: slot_" in line:
                try:
                    date_part = line.split("at ")[0].strip().rstrip("•").strip()
                    slot_id_part = line.split("(ID: ")[1].split(")")[0].strip()
                    matching_dates.append((date_part, slot_id_part))
                except IndexError:
                    continue
        
        if matching_dates:
            dates_str = "\n".join([f"• {date} (ID: {id})" for date, id in matching_dates])
            response = f"I see you're interested in booking at {slot_info['time']}. What date would you prefer? Here are the available dates:\n\n{dates_str}\n\nPlease reply with your preferred date or the slot ID."
            
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
            response = f"I couldn't find any available slots at {slot_info['time']}. Here are all the available slots:\n\n{available_slots}\n\nPlease select a date and time from these options."
            
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
    
    # If no specific slot info, show all available slots
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
    user_data.pop("appointment_slot")
    
    # Get available slots
    if not available_slots:
        available_slots = get_available_slots()
    
    response = f"I see you'd like to reschedule your appointment. Your previous booking ({previous_slot}) has been canceled. Here are the available slots:\n\n{available_slots}\n\nPlease select a new time."
    
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
    parts = slot_id.split("_")
    if len(parts) >= 4:
        date = parts[1]
        hour = parts[2]
        minute = parts[3]
        appointment_details = f"{date} at {hour}:{minute}"
    else:
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
    parts = slot_id.split("_")
    if len(parts) >= 4:
        date = parts[1]
        hour = parts[2]
        minute = parts[3]
        appointment_details = f"{date} at {hour}:{minute}"
    else:
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