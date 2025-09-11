#!/usr/bin/env python3
"""
Enhanced Natural Conversation Flow Controller for Carter Injury Law
Manages when and how to collect user information during conversations
"""

import re
import openai
from typing import Dict, Any, Optional, Tuple
import random
from datetime import datetime

def get_enhanced_greeting(user_query: str, conversation_count: int, user_data: Dict[str, Any]) -> Optional[str]:
    """Generate simple, clean greetings for first-time interactions"""
    
    # Clean the query for better matching
    clean_query = user_query.lower().strip()
    
    # Check for simple greetings
    is_simple_greeting = any(word in clean_query for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"])
    
    # Check if we've already responded to a greeting in this session
    conversation_history = user_data.get("conversation_history", [])
    has_greeting_response = any(
        msg.get("content", "").startswith(("Hello!", "Hi!", "Hey!")) 
        for msg in conversation_history if msg.get("role") == "assistant"
    )
    
    # Only respond to simple greetings on first interaction
    if is_simple_greeting and not has_greeting_response:
        # Simple, clean greeting without overwhelming information
        return "Hello! How can I help you today regarding personal injury?"
    
    # For all other cases, return None to let RAG system handle
    return None

def get_conversation_progression_response(user_query: str, conversation_history: list, user_data: Dict[str, Any]) -> Optional[str]:
    """
    Handle smart conversation progression including appreciation responses
    """
    clean_query = user_query.lower().strip()
    
    # Handle appreciation and thank you messages with simple, professional responses
    appreciation_patterns = [
        r'\b(thank you|thanks|appreciate|grateful)\b',
        r'\b(that\'s helpful|very helpful|exactly what i needed|perfect answer)\b'
    ]
    
    is_appreciation = any(re.search(pattern, clean_query) for pattern in appreciation_patterns)
    
    if is_appreciation:
        # Simple, professional thank you responses
        return "You're welcome! Happy to help."
    
    # Handle simple acknowledgments that don't need full responses
    simple_acknowledgments = [
        "ok", "okay", "alright", "sure", "yes", "no", "maybe", "i see", "got it", 
        "understood", "i understand", "makes sense", "sounds good"
    ]
    
    if clean_query in simple_acknowledgments and len(conversation_history) > 2:
        # Don't respond to simple acknowledgments - let conversation flow naturally
        return None
    
    # Return None to let RAG system handle other responses
    return None

def get_contextual_response(user_query: str, conversation_history: list, user_data: Dict[str, Any]) -> Optional[str]:
    """Generate contextual responses - DISABLED to let RAG system handle responses"""
    # Return None to let RAG system handle all responses
    return None

def should_collect_contact_info(conversation_history: list, user_query: str, user_data: Dict[str, Any]) -> bool:
    """Determine if we should collect contact information naturally"""
    # Check if we already have complete contact info
    has_name = user_data.get("name") and user_data.get("name") not in ["Anonymous User", "Guest User", "Unknown"]
    has_email = user_data.get("email") and user_data.get("email") not in ["anonymous@user.com", "No email"]
    
    # Don't collect if we already have both
    if has_name and has_email:
        return False
    
    # Check for scheduling/appointment requests
    scheduling_keywords = [
        "appointment", "schedule", "meeting", "consultation", "book", "reserve"
    ]
    
    # Check for case interest indicators
    case_interest_keywords = [
        "case", "lawsuit", "claim", "legal help", "representation", "attorney", "lawyer"
    ]
    
    clean_query = user_query.lower().strip()
    has_scheduling_intent = any(keyword in clean_query for keyword in scheduling_keywords)
    has_case_interest = any(keyword in clean_query for keyword in case_interest_keywords)
    
    # Collect info if user shows scheduling intent or strong case interest
    if has_scheduling_intent:
        return True
    
    # Collect after engaged conversation (4+ exchanges) with case interest
    conversation_count = len(conversation_history)
    if conversation_count >= 8 and has_case_interest:  # 4+ exchanges
        return True
    
    return False

def should_offer_calendar(conversation_history: list, user_query: str, user_data: Dict[str, Any]) -> bool:
    """Determine if we should offer calendar scheduling based on smart context analysis"""
    clean_query = user_query.lower().strip()
    
    # Don't offer if we already offered in this session
    if user_data.get("calendar_offered", False):
        print(f"[CALENDAR] Calendar already offered in this session - skipping")
        return False
    
    # Check for appointment/scheduling keywords
    appointment_keywords = [
        "appointment", "schedule", "meeting", "consultation", "talk", "discuss", 
        "book", "reserve", "available", "when can", "what time", "calendar",
        "meet", "see", "visit", "come in", "office", "call me", "contact me"
    ]
    
    # Check for legal case indicators that suggest they need consultation
    case_indicators = [
        "accident", "injury", "hurt", "crash", "collision", "slip", "fall",
        "case", "claim", "sue", "lawsuit", "compensation", "damages",
        "legal help", "need a lawyer", "attorney", "representation"
    ]
    
    has_appointment_intent = any(keyword in clean_query for keyword in appointment_keywords)
    has_case_need = any(indicator in clean_query for indicator in case_indicators)
    
    # Offer calendar if:
    # 1. User explicitly asks for appointment/scheduling
    # 2. User mentions a case/accident and shows interest in legal help
    # 3. Conversation has been going well and user seems engaged
    conversation_count = len(conversation_history)
    is_engaged = conversation_count > 4  # At least 2 exchanges
    
    should_offer = has_appointment_intent or (has_case_need and is_engaged)
    
    print(f"[CALENDAR] Query: '{clean_query}'")
    print(f"[CALENDAR] has_appointment_intent: {has_appointment_intent}")
    print(f"[CALENDAR] has_case_need: {has_case_need}")
    print(f"[CALENDAR] conversation_count: {conversation_count}")
    print(f"[CALENDAR] is_engaged: {is_engaged}")
    print(f"[CALENDAR] should_offer: {should_offer}")
    
    return should_offer

def get_natural_contact_prompt(user_data: Dict[str, Any], conversation_count: int) -> str:
    """Generate natural prompts for contact information collection"""
    has_name = user_data.get("name") and user_data.get("name") not in ["Anonymous User", "Guest User", "Unknown"]
    has_email = user_data.get("email") and user_data.get("email") not in ["anonymous@user.com", "No email"]
    
    if not has_name:
        return "Can I have your full name to help you better?"
    elif not has_email:
        return "And your email address so we can follow up with you?"
    
    return "Thank you for the information. How else can I assist you?"

def get_natural_email_prompt(user_data: Dict[str, Any], conversation_count: int) -> str:
    """Generate natural prompts specifically for email collection"""
    name = user_data.get("name", "")
    
    if name and name not in ["Anonymous User", "Guest User", "Unknown"]:
        return f"Thanks, {name}! And your email address so we can follow up with you?"
    else:
        return "And your email address so we can follow up with you?"

def get_natural_name_prompt(user_data: Dict[str, Any], conversation_count: int) -> str:
    """Generate natural prompts specifically for name collection"""
    return "Can I have your full name to help you better?"

def get_calendar_offer(user_data: Dict[str, Any]) -> str:
    """Generate smart calendar scheduling offer with context awareness"""
    name = user_data.get("name", "")
    conversation_history = user_data.get("conversation_history", [])
    
    # Analyze conversation context to personalize the offer
    recent_messages = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
    context_text = " ".join([msg.get("content", "") for msg in recent_messages if msg.get("role") == "user"])
    
    # Check for specific case types mentioned
    case_type = "your legal matter"
    if any(word in context_text.lower() for word in ["accident", "crash", "collision"]):
        case_type = "your accident case"
    elif any(word in context_text.lower() for word in ["slip", "fall"]):
        case_type = "your slip and fall case"
    elif any(word in context_text.lower() for word in ["medical", "malpractice"]):
        case_type = "your medical malpractice case"
    elif any(word in context_text.lower() for word in ["work", "workers"]):
        case_type = "your workers' compensation case"
    
    # Personalized greeting
    greeting = f"Hi {name}!" if name and name not in ["Anonymous User", "Guest User"] else "I'd be happy to help!"
    
    # Smart calendar offer based on context
    if "urgent" in context_text.lower() or "emergency" in context_text.lower():
        urgency_note = "I understand this is urgent, so I'll prioritize getting you scheduled quickly."
    else:
        urgency_note = "I'll make sure to find a time that works well for you."
    
    offer = f"""{greeting} I'd love to schedule a free consultation to discuss {case_type} in detail. 

Our experienced attorneys David J. Carter and Robert Johnson can provide you with personalized legal advice and explain your options. {urgency_note}

Would you like me to show you our available appointment times? The consultation is completely free and there's no obligation to hire us afterward."""

    return offer

def get_appointment_confirmation(user_data: Dict[str, Any], appointment_details: Dict[str, Any]) -> str:
    """Generate smart appointment confirmation message"""
    name = user_data.get("name", "")
    greeting = f"Perfect, {name}!" if name and name not in ["Anonymous User", "Guest User"] else "Perfect!"
    
    # Extract appointment details
    appointment_time = appointment_details.get("start", "")
    appointment_date = appointment_details.get("date", "")
    appointment_type = appointment_details.get("type", "consultation")
    
    # Format the confirmation message
    confirmation = f"""{greeting} Your free consultation has been scheduled!

📅 **Appointment Details:**
• Date & Time: {appointment_date} at {appointment_time}
• Type: Free Legal Consultation
• Attorneys: David J. Carter and Robert Johnson

📋 **What to Expect:**
• We'll discuss your case in detail
• Get personalized legal advice
• Learn about your rights and options
• No obligation to hire us afterward

📞 **Contact Information:**
• Phone: (813) 922-0228
• Address: 3114 N. Boulevard, Tampa, FL 33603

You'll receive a confirmation email shortly. If you need to reschedule or have any questions, just let me know!

Is there anything else I can help you with today?"""

    return confirmation

def extract_name_from_text(text: str) -> Tuple[Optional[str], bool]:
    """
    Extract name from user text using multiple methods
    Returns: (extracted_name, is_refusal)
    """
    text = text.strip()
    
    # Check if the text contains an email address - if so, it's not a name
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if re.search(email_pattern, text):
        return None, False
    
    # Check for refusal patterns first
    refusal_patterns = [
        r'\b(skip|no|don\'t|dont|won\'t|wont|refuse|not now|later|anonymous)\b',
        r'\bi don\'t want to share\b',
        r'\bi dont want to share\b',
        r'\bprefer not to\b',
        r'\brather not\b',
        r'\bno thank you\b'
    ]
    
    for pattern in refusal_patterns:
        if re.search(pattern, text.lower()):
            return None, True
    
    # Try to extract name using regex patterns
    name_patterns = [
        r'\b(?:hello|hi|hey|greetings)\s+(?:this\s+is\s+|i\s+am\s+|my\s+name\s+is\s+|i\'m\s+|im\s+)([a-zA-Z]+(?:\s+[a-zA-Z]+)*)',
        r'\b(?:this\s+is\s+|i\s+am\s+|my\s+name\s+is\s+|i\'m\s+|im\s+)([a-zA-Z]+(?:\s+[a-zA-Z]+)*)',
        r'\b(?:call\s+me\s+|name\'s\s+)([a-zA-Z]+(?:\s+[a-zA-Z]+)*)',
        r'\b([a-zA-Z]+(?:\s+[a-zA-Z]+)*)\s+(?:here|speaking)',
        r'my\s+name\s+is\s+([a-zA-Z]+)',  # "My name is sahak"
        r'my\s+name\s+([a-zA-Z]+)',  # "my name sahak"
        r'^(?:name\s+is\s+|name\s+)([a-zA-Z]+(?:\s+[a-zA-Z]+)*)$',  # "name sahak" or "name is sahak"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up the name
            name = re.sub(r'\b(?:from|in|at)\s+.*$', '', name, flags=re.IGNORECASE).strip()
            if len(name) > 1:  # Ensure it's not just a single character
                return name, False
    
    # If no pattern match, try to extract using OpenAI
    try:
        name_extraction_prompt = f"""
        Extract the person's name from the following text. Be very careful to extract ONLY actual names, not common words.
        
        Text: "{text}"
        
        Rules:
        1. If you find a name, return ONLY the name (first and last name if available)
        2. Remove any introductory phrases like "Hello this is", "My name is", "I am", etc.
        3. Remove location information like "from Texas", "in California", etc.
        4. If the person is refusing to share their name, return "REFUSED"
        5. If no clear name is found, return "NO_NAME"
        6. Do NOT extract common words like: okay, yes, no, help, fine, good, sure, maybe
        7. Names are typically proper nouns like: John, Sarah, Michael, sahak, etc.
        
        Examples:
        "My name is John" -> John
        "my name sahak" -> sahak
        "Hello this is sahak from texas" -> sahak
        "I am Alice Johnson" -> Alice Johnson
        "I don't want to share my name" -> REFUSED
        "I'm okay" -> NO_NAME
        "I need help" -> NO_NAME
        "hello there" -> NO_NAME
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": name_extraction_prompt}],
            max_tokens=20,
            temperature=0.1
        )
        
        extracted = response.choices[0].message.content.strip()
        
        if extracted == "REFUSED":
            return None, True
        elif extracted != "NO_NAME" and len(extracted) > 1:
            return extracted, False
        else:
            return None, False
            
    except Exception as e:
        print(f"Error in OpenAI name extraction: {e}")
        # Fall back to basic regex extraction
        return extract_name_with_regex_fallback(text), False

def extract_name_with_regex_fallback(text: str) -> Optional[str]:
    """Fallback name extraction using regex patterns"""
    text = text.strip()
    
    # Check for common non-name words first
    non_names = ['okay', 'yes', 'no', 'help', 'fine', 'good', 'sure', 'maybe', 'thanks', 'thank']
    if text.lower() in non_names:
        return None
    
    # Enhanced name patterns for better extraction
    name_patterns = [
        r'^my\s+name\s+is\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)$',  # "my name is sahak"
        r'^my\s+name\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)$',  # "my name sahak"
        r'^name\s+is\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)$',  # "name is sahak"
        r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)$',  # Capitalized words like "John Smith"
        r'^([a-z]{2,}(?:\s[a-z]{2,})*)$',  # All lowercase words (2+ chars) like "sahak"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Enhanced validation
            if (2 <= len(name) <= 50 and 
                re.match(r'^[A-Za-z\s]+$', name) and 
                name.lower() not in non_names):
                return name
    
    return None

def extract_email_from_text(text: str) -> Tuple[Optional[str], bool]:
    """
    Extract email from user text
    Returns: (extracted_email, is_refusal)
    """
    text = text.strip()
    
    # Check for refusal patterns first
    refusal_patterns = [
        r'\b(skip|no|don\'t|dont|won\'t|wont|refuse|not now|later|anonymous)\b',
        r'\bi don\'t want to share\b',
        r'\bi dont want to share\b',
        r'\bprefer not to\b',
        r'\brather not\b',
        r'\bno thank you\b'
    ]
    
    for pattern in refusal_patterns:
        if re.search(pattern, text.lower()):
            return None, True
    
    # Try to extract email using regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text)
    
    if email_match:
        return email_match.group(0), False
    
    # If no regex match, try OpenAI
    try:
        email_extraction_prompt = f"""
        Extract and validate an email address from the following text.
        
        Text: "{text}"
        
        Rules:
        1. If you find a valid email (format: username@domain.tld), return only the email
        2. If the person is refusing or wants to skip, return "REFUSED"
        3. If no valid email is found, return "NO_EMAIL"
        
        Examples:
        "My email is john@example.com" -> john@example.com
        "arsshak@gmail.com" -> arsshak@gmail.com
        "I don't want to share my email" -> REFUSED
        "hello there" -> NO_EMAIL
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": email_extraction_prompt}],
            max_tokens=30,
            temperature=0.1
        )
        
        extracted = response.choices[0].message.content.strip()
        
        if extracted == "REFUSED":
            return None, True
        elif "@" in extracted and "." in extracted:
            return extracted, False
        else:
            return None, False
            
    except Exception as e:
        print(f"Error in OpenAI email extraction: {e}")
        return None, False

def calculate_engagement_score(conversation_history, user_query):
    """Calculate user engagement based on conversation patterns"""
    if not conversation_history:
        return 0.0
    
    score = 0
    
    # Points for conversation length
    conversation_count = len(conversation_history)
    score += min(conversation_count * 0.1, 0.4)  # Max 0.4 for length
    
    # Points for question complexity
    if len(user_query.split()) > 5:
        score += 0.2
    
    # Points for showing interest keywords
    interest_keywords = [
        "consultation", "appointment", "help", "case", "injured", 
        "accident", "legal", "lawyer", "attorney", "sue", "claim",
        "my case", "my accident", "my injury", "i was hurt"
    ]
    
    if any(keyword in user_query.lower() for keyword in interest_keywords):
        score += 0.3
    
    # Points for asking follow-up questions
    recent_user_messages = [msg for msg in conversation_history[-6:] if msg.get('role') == 'user']
    if len(recent_user_messages) >= 2:
        score += 0.2
    
    return min(score, 1.0)  # Cap at 1.0

def should_collect_information(conversation_history, user_query, current_mode):
    """Determine if we should collect user information at this point"""
    conversation_count = len(conversation_history)
    
    # Never collect in first 4 exchanges (8 messages total)
    if conversation_count < 8:
        return False
    
    # Always collect if user is trying to book appointment
    if current_mode == "appointment":
        return True
    
    # Collect if user shows high engagement
    engagement = calculate_engagement_score(conversation_history, user_query)
    if engagement > 0.6:
        return True
    
    # Collect if conversation is getting long (user is invested)
    if conversation_count > 12:  # 6+ exchanges
        return True
    
    return False

def get_natural_collection_prompt(user_context, info_type="name"):
    """Generate natural prompts for information collection"""
    conversation_count = len(user_context.get("conversation_history", []))
    
    if info_type == "name":
        if conversation_count > 10:
            return "I'd love to personalize our conversation better. What's your first name?"
        else:
            return "By the way, what should I call you?"
    
    elif info_type == "email":
        if user_context.get("name"):
            return f"Thanks, {user_context['name']}! If you'd like me to send you some helpful information, what's your email address?"
        else:
            return "If you'd like me to send you some helpful resources, what's your email address?"
    
    return "Could you share your contact information so I can better assist you?"

def process_user_message_for_info(user_query: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process user message to extract name and email information
    Returns updated user_data with any extracted information
    """
    updated_data = user_data.copy() if user_data else {}
    
    # Extract name if not already present
    if not updated_data.get("name") or updated_data.get("name") in ["Anonymous User", "Guest User"]:
        extracted_name, is_refusal = extract_name_from_text(user_query)
        if extracted_name:
            updated_data["name"] = extracted_name
            print(f"[INFO] Extracted name: {extracted_name}")
        elif is_refusal:
            updated_data["name"] = "Anonymous User"
            print("[INFO] User refused to share name")
    
    # Extract email if not already present
    if not updated_data.get("email") or updated_data.get("email") in ["anonymous@user.com"]:
        extracted_email, is_refusal = extract_email_from_text(user_query)
        if extracted_email:
            updated_data["email"] = extracted_email
            print(f"[INFO] Extracted email: {extracted_email}")
        elif is_refusal:
            updated_data["email"] = "anonymous@user.com"
            print("[INFO] User refused to share email")
    
    return updated_data

def clear_conversation_cache(session_id, org_id):
    """Clear any cached conversation data"""
    try:
        from services.cache import cache
        
        # Clear various cache keys that might be storing conversation state
        cache_keys = [
            f"conversation:{org_id}:{session_id}",
            f"user_data:{org_id}:{session_id}",
            f"session:{org_id}:{session_id}",
            f"visitor:{org_id}:{session_id}"
        ]
        
        for key in cache_keys:
            try:
                cache.delete(key)
                print(f"[CACHE] Cleared cache key: {key}")
            except Exception as e:
                print(f"[CACHE] Error clearing key {key}: {str(e)}")
        
        return True
    except Exception as e:
        print(f"[CACHE] Error in clear_conversation_cache: {str(e)}")
        return False

def reset_user_session(org_id, session_id):
    """Reset user session data to start fresh"""
    try:
        from services.database import db
        
        # Clear visitor data
        db.visitors.update_one(
            {"organization_id": org_id, "session_id": session_id},
            {"$unset": {"profile_data": "", "metadata.user_data": ""}}
        )
        
        # Clear user profiles
        db.user_profiles.delete_many({
            "organization_id": org_id, 
            "session_id": session_id
        })
        
        print(f"[SESSION] Reset session data for {org_id}:{session_id}")
        return True
    except Exception as e:
        print(f"[SESSION] Error resetting session: {str(e)}")
        return False

def store_contact_info_in_vector_db(org_id: str, name: str, email: str, api_key: str = None) -> bool:
    """Store contact information in the vector database for the organization"""
    try:
        # Import here to avoid circular imports
        from services.langchain.engine import add_document
        
        # Create a document with contact information
        contact_document = f"""
        Contact Information:
        Name: {name}
        Email: {email}
        Organization ID: {org_id}
        Type: Visitor Contact Information
        Stored: {datetime.now().isoformat()}
        
        This visitor has provided their contact information and should not be asked for it again.
        """
        
        # Store in vector database using the organization's API key
        result = add_document(text=contact_document, api_key=api_key)
        
        if result and result.get("status") == "success":
            print(f"[VECTOR_DB] Successfully stored contact info for {name} ({email})")
            return True
        else:
            print(f"[VECTOR_DB] Failed to store contact info: {result}")
            return False
            
    except Exception as e:
        print(f"[VECTOR_DB] Error storing contact info: {str(e)}")
        return False

def check_returning_visitor_contact(org_id: str, name: str = None, email: str = None, api_key: str = None) -> Dict[str, Any]:
    """Check if a visitor's contact info is already stored in vector database"""
    try:
        # Import here to avoid circular imports
        from services.langchain.engine import get_org_vectorstore
        
        # Get organization's vectorstore
        vectorstore = get_org_vectorstore(api_key)
        if not vectorstore:
            return {"found": False, "name": None, "email": None}
        
        # Search for contact information
        search_queries = []
        if name:
            search_queries.append(f"Contact Information Name: {name}")
        if email:
            search_queries.append(f"Contact Information Email: {email}")
        
        for query in search_queries:
            try:
                docs = vectorstore.similarity_search(query, k=3)
                for doc in docs:
                    if "Contact Information:" in doc.page_content:
                        # Extract name and email from the document
                        content = doc.page_content
                        stored_name = None
                        stored_email = None
                        
                        # Parse the contact information
                        lines = content.split('\n')
                        for line in lines:
                            if line.strip().startswith("Name:"):
                                stored_name = line.split(":", 1)[1].strip()
                            elif line.strip().startswith("Email:"):
                                stored_email = line.split(":", 1)[1].strip()
                        
                        if stored_name and stored_email:
                            print(f"[VECTOR_DB] Found returning visitor: {stored_name} ({stored_email})")
                            return {
                                "found": True,
                                "name": stored_name,
                                "email": stored_email
                            }
            except Exception as e:
                print(f"[VECTOR_DB] Error searching for contact: {str(e)}")
                continue
        
        return {"found": False, "name": None, "email": None}
        
    except Exception as e:
        print(f"[VECTOR_DB] Error checking returning visitor: {str(e)}")
        return {"found": False, "name": None, "email": None}
