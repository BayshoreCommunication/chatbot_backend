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
        found_slot = False
        
        date_to_match = slot_info["date"].strip()
        time_to_match = slot_info["time"].strip()
        
        # Convert date to a standard format for better matching
        clean_date = date_to_match.replace(",", "").replace(".", "")
        
        # Parse the slots format to find a matching date and time
        current_date_section = None
        for line in all_slots_str.split('\n'):
            if "📅" in line:
                current_date_section = line.replace("📅", "").strip()
            
            if current_date_section and current_date_section == date_to_match:
                if time_to_match in line and "ID: slot_" in line:
                    try:
                        slot_id = line.split("(ID: ")[1].split(")")[0].strip()
                        found_slot = True
                        break
                    except IndexError:
                        print(f"Error parsing slot ID from line: {line}")
                        continue
        
        # If we didn't find an exact match, try a fuzzy match
        if not found_slot:
            best_match_date = None
            best_match_time = None
            best_match_id = None
            best_match_score = 0
            
            current_date_section = None
            for line in all_slots_str.split('\n'):
                if "📅" in line:
                    current_date_section = line.replace("📅", "").strip()
                
                if current_date_section and "ID: slot_" in line:
                    date_score = sum(c1 == c2 for c1, c2 in zip(current_date_section.lower(), date_to_match.lower()))
                    
                    # Check for time match too if available
                    time_score = 0
                    if "AM" in line or "PM" in line:
                        time_parts = line.split("•")[1].split("(ID:")[0].strip() if "•" in line else ""
                        time_score = sum(c1 == c2 for c1, c2 in zip(time_parts.lower(), time_to_match.lower()))
                    
                    # Calculate combined score
                    match_score = date_score + time_score
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_date = current_date_section
                        try:
                            best_match_id = line.split("(ID: ")[1].split(")")[0].strip()
                            if "•" in line:
                                best_match_time = line.split("•")[1].split("(ID:")[0].strip()
                        except:
                            pass
            
            # If we found a reasonable match, use it
            if best_match_id and best_match_score > len(date_to_match) * 0.6:
                slot_id = best_match_id
                print(f"Using fuzzy matched slot: Date: {best_match_date}, Time: {best_match_time}, ID: {slot_id}")
    
    # If we found a valid slot ID
    if slot_id:
        # Book the appointment
        user_data["appointment_slot"] = slot_id
        
        # Extract date and time for confirmation
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
                
                confirmation = f"Great! I've booked your appointment for {formatted_date} at {formatted_time}. We'll send a confirmation to your email at {user_data.get('email', 'your email address')}. Is there anything else you'd like help with?"
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
        date_to_match = slot_info["date"].strip()
        
        # Extract available times for the specified date
        current_date_section = None
        for line in all_slots_str.split('\n'):
            if "📅" in line:
                current_date_section = line.replace("📅", "").strip()
            
            # Check for exact date match
            if current_date_section == date_to_match and "ID: slot_" in line:
                try:
                    if "•" in line:
                        time_part = line.split("•")[1].split("(ID:")[0].strip()
                        slot_id_part = line.split("(ID: ")[1].split(")")[0].strip()
                        matching_times.append((time_part, slot_id_part))
                except IndexError:
                    continue
        
        # If no exact matches, try fuzzy matching on the date
        if not matching_times:
            best_match_date = None
            best_match_score = 0
            
            for line in all_slots_str.split('\n'):
                if "📅" in line:
                    check_date = line.replace("📅", "").strip()
                    date_score = sum(c1 == c2 for c1, c2 in zip(check_date.lower(), date_to_match.lower()))
                    
                    if date_score > best_match_score:
                        best_match_score = date_score
                        best_match_date = check_date
            
            # If we found a reasonable match, use times from that date
            if best_match_date and best_match_score > len(date_to_match) * 0.6:
                print(f"Using fuzzy matched date: {best_match_date}")
                current_date_section = None
                for line in all_slots_str.split('\n'):
                    if "📅" in line:
                        current_date_section = line.replace("📅", "").strip()
                    
                    if current_date_section == best_match_date and "ID: slot_" in line:
                        try:
                            if "•" in line:
                                time_part = line.split("•")[1].split("(ID:")[0].strip()
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
        time_to_match = slot_info["time"].strip()
        
        # Find dates with the specified time
        current_date_section = None
        for line in all_slots_str.split('\n'):
            if "📅" in line:
                current_date_section = line.replace("📅", "").strip()
            
            if current_date_section and "ID: slot_" in line and time_to_match in line:
                try:
                    slot_id_part = line.split("(ID: ")[1].split(")")[0].strip()
                    matching_dates.append((current_date_section, slot_id_part))
                except IndexError:
                    continue
        
        # If no exact matches, try fuzzy matching on the time
        if not matching_dates:
            for line in all_slots_str.split('\n'):
                if "📅" in line:
                    current_date_section = line.replace("📅", "").strip()
                
                if current_date_section and "ID: slot_" in line and ("AM" in line or "PM" in line):
                    try:
                        # Try to extract and compare the time portion
                        if "•" in line:
                            time_part = line.split("•")[1].split("(ID:")[0].strip()
                            # Check for similarity
                            time_score = sum(c1 == c2 for c1, c2 in zip(time_part.lower(), time_to_match.lower()))
                            if time_score > len(time_to_match) * 0.6:
                                slot_id_part = line.split("(ID: ")[1].split(")")[0].strip()
                                matching_dates.append((current_date_section, slot_id_part))
                    except IndexError:
                        continue
        
        if matching_dates:
            dates_str = "\n".join([f"• {date} (ID: {id})" for date, id in matching_dates])
            response = f"I see you're interested in booking at {time_to_match}. What date would you prefer? Here are the available dates:\n\n{dates_str}\n\nPlease reply with your preferred date or the slot ID."
            
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
            response = f"I couldn't find any available slots at {time_to_match}. Here are all the available slots:\n\n{available_slots}\n\nPlease select a date and time from these options."
            
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