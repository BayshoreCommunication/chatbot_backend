#!/usr/bin/env python3
"""
Enhanced Natural Conversation Flow Controller for Carter Injury Law
Manages when and how to collect user information during conversations
"""

import re
import openai
from typing import Dict, Any, Optional, Tuple
import random

def get_enhanced_greeting(user_query: str, conversation_count: int, user_data: Dict[str, Any]) -> Optional[str]:
    """Generate smart, context-aware greetings that skip simple hellos and respond to meaningful questions"""
    
    # Clean the query for better matching
    clean_query = user_query.lower().strip()
    
    # Check for different types of greetings and meaningful content
    is_simple_greeting = any(word in clean_query for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"])
    is_law_firm_greeting = any(word in clean_query for word in ["carter injury law", "carter law", "injury law"])
    is_help_request = any(word in clean_query for word in ["help", "assist", "need help", "can you help"])
    
    # Check for meaningful content that indicates a real question or case
    has_meaningful_content = any(word in clean_query for word in [
        "accident", "injury", "hurt", "crash", "collision", "slip", "fall", "case", "legal", 
        "lawyer", "attorney", "sue", "claim", "compensation", "damages", "medical", "hospital",
        "insurance", "fault", "negligence", "settlement", "court", "lawsuit", "consultation",
        "appointment", "schedule", "meeting", "discuss", "talk", "advice", "question", "problem"
    ])
    
    # Check if we've already responded to a greeting in this session
    conversation_history = user_data.get("conversation_history", [])
    has_greeting_response = any(msg.get("content", "").startswith("Hello! 👋") for msg in conversation_history)
    
    # Smart logic: Only respond to greetings if they contain meaningful content or are law firm specific
    if (is_law_firm_greeting or (is_simple_greeting and has_meaningful_content)) and not has_greeting_response:
        # Use your preferred greeting
        return "Hello! 👋 Thanks for reaching out to Carter Injury Law. How can I assist you today?"
    
    # Skip simple greetings without meaningful content - let RAG system handle them
    if is_simple_greeting and not has_meaningful_content and not has_greeting_response:
        # Return a minimal acknowledgment that doesn't interrupt the flow
        return None
    
    # For all other cases, return None to let RAG system handle
    return None

def get_conversation_progression_response(user_query: str, conversation_history: list, user_data: Dict[str, Any]) -> Optional[str]:
    """
    Handle smart conversation progression including appreciation responses
    """
    clean_query = user_query.lower().strip()
    
    # Handle appreciation and thank you messages
    appreciation_patterns = [
        r'\b(thank you|thanks|appreciate|grateful|helpful|great|awesome|perfect|excellent)\b',
        r'\b(that\'s helpful|very helpful|exactly what i needed|perfect answer)\b',
        r'\b(you\'re welcome|no problem|my pleasure|happy to help)\b'
    ]
    
    is_appreciation = any(re.search(pattern, clean_query) for pattern in appreciation_patterns)
    
    if is_appreciation:
        # Smart appreciation responses based on context
        name = user_data.get("name", "")
        if name and name not in ["Anonymous User", "Guest User"]:
            responses = [
                f"You're very welcome, {name}! I'm glad I could help. Is there anything else you'd like to know about your legal situation?",
                f"Happy to help, {name}! Feel free to ask if you have any other questions about your case.",
                f"My pleasure, {name}! I'm here whenever you need assistance with your legal matters."
            ]
        else:
            responses = [
                "You're very welcome! I'm glad I could help. Is there anything else you'd like to know about your legal situation?",
                "Happy to help! Feel free to ask if you have any other questions about your case.",
                "My pleasure! I'm here whenever you need assistance with your legal matters."
            ]
        
        return random.choice(responses)
    
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
    """Determine if we should collect contact information naturally - DISABLED to let RAG handle"""
    # Return False to let RAG system handle contact requests naturally
    return False

def should_offer_calendar(conversation_history: list, user_query: str, user_data: Dict[str, Any]) -> bool:
    """Determine if we should offer calendar scheduling based on smart context analysis"""
    clean_query = user_query.lower().strip()
    
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
    
    return has_appointment_intent or (has_case_need and is_engaged)

def get_natural_contact_prompt(user_data: Dict[str, Any], conversation_count: int) -> str:
    """Generate natural prompts for contact information collection - DISABLED"""
    # Return None to let RAG system handle contact requests naturally
    return None

def get_natural_email_prompt(user_data: Dict[str, Any], conversation_count: int) -> str:
    """Generate natural prompts specifically for email collection"""
    
    name = user_data.get("name", "")
    
    if conversation_count < 10:
        # Early in conversation - very gentle
        if name:
            return f"Thanks, {name}! If you'd like me to send you some helpful information, what's your email address?"
        else:
            return "If you'd like me to send you some helpful information, what's your email address?"
    
    elif conversation_count < 15:
        # Mid-conversation - more direct but still friendly
        if name:
            return f"Thanks, {name}! If you'd like me to send you some helpful resources, what's your email address?"
        else:
            return "If you'd like me to send you some helpful resources, what's your email address?"
    
    else:
        # Later in conversation - more direct
        if name:
            return f"To send you helpful information, {name}, what's your email address?"
        else:
            return "To send you helpful information, what's your email address?"

def get_natural_name_prompt(user_data: Dict[str, Any], conversation_count: int) -> str:
    """Generate natural prompts specifically for name collection"""
    
    if conversation_count < 10:
        # Early in conversation - very gentle
        return "By the way, what should I call you? This helps me personalize our conversation."
    
    elif conversation_count < 15:
        # Mid-conversation - more direct but still friendly
        return "I'd love to personalize our conversation better. What's your first name?"
    
    else:
        # Later in conversation - more direct
        return "To better assist you, could you tell me your name?"

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
        Extract the person's name from the following text.
        
        Text: "{text}"
        
        Rules:
        1. If you find a name, return ONLY the name (first and last name if available)
        2. Remove any introductory phrases like "Hello this is", "My name is", "I am", etc.
        3. Remove location information like "from Texas", "in California", etc.
        4. If the person is refusing to share their name, return "REFUSED"
        5. If no clear name is found, return "NO_NAME"
        
        Examples:
        "My name is John" -> John
        "Hello this is sahak from texas" -> sahak
        "I am Alice Johnson" -> Alice Johnson
        "I don't want to share my name" -> REFUSED
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
    
    # Simple name patterns
    name_patterns = [
        r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)$',  # Capitalized words
        r'^([a-z]+(?:\s[a-z]+)*)$',  # All lowercase words
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            # Basic validation - should be 2-50 characters and not contain special chars
            if 2 <= len(name) <= 50 and re.match(r'^[A-Za-z\s]+$', name):
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
