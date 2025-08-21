#!/usr/bin/env python3
"""
Natural Conversation Flow Controller for Carter Injury Law
Manages when and how to collect user information during conversations
"""

import re
import openai
from typing import Dict, Any, Optional, Tuple

def get_natural_greeting(user_query: str, conversation_count: int) -> str:
    """Generate natural, lawyer-like greetings"""
    greetings = [
        "Hello! I'm here to help with your legal questions. How can I assist you today?",
        "Hi there! I'm ready to help with any personal injury or legal questions you might have. What brings you here today?",
        "Welcome! I'm here to provide legal guidance. How may I help you today?",
        "Hello! I'm here to assist with your legal concerns. What can I help you with?",
        "Hi! I'm ready to help with any questions about personal injury law or your legal situation. What's on your mind?"
    ]
    
    # For first message, use a warm greeting
    if conversation_count == 0:
        return "Hello! I'm here to help with your legal questions. How can I assist you today?"
    
    # For subsequent messages, be more conversational
    return "I'm here to help. What else would you like to know?"

def get_lawyer_response_tone(user_query: str, context: Dict[str, Any]) -> str:
    """Generate responses with a professional lawyer tone"""
    
    # Check if user is asking about specific legal topics
    legal_keywords = [
        "accident", "injury", "hurt", "pain", "damage", "claim", "sue", "lawsuit",
        "insurance", "medical", "hospital", "doctor", "treatment", "settlement",
        "compensation", "money", "damages", "fault", "negligence", "liability"
    ]
    
    has_legal_context = any(keyword in user_query.lower() for keyword in legal_keywords)
    
    if has_legal_context:
        return "professional_caring"
    else:
        return "friendly_professional"

def should_collect_contact_info(conversation_history: list, user_query: str, user_data: Dict[str, Any]) -> bool:
    """Determine if we should collect contact information naturally"""
    conversation_count = len(conversation_history)
    
    # Never collect in first 4 exchanges (8 messages total)
    if conversation_count < 8:
        return False
    
    # Check if user shows serious interest
    serious_keywords = [
        "consultation", "appointment", "meet", "talk", "speak", "call", "contact",
        "help me", "need help", "serious", "urgent", "emergency", "immediately"
    ]
    
    shows_serious_interest = any(keyword in user_query.lower() for keyword in serious_keywords)
    
    # Collect if user shows serious interest OR conversation is getting long
    if shows_serious_interest:
        return True
    
    # After 10-12 exchanges, consider collecting info
    if conversation_count > 20:
        return True
    
    return False

def should_offer_calendar(conversation_history: list, user_query: str, user_data: Dict[str, Any]) -> bool:
    """Determine if we should offer calendar scheduling"""
    conversation_count = len(conversation_history)
    
    # Only offer after 10-12 exchanges (20+ messages)
    if conversation_count < 20:
        return False
    
    # Check if user is ready for next step
    ready_keywords = [
        "next step", "what now", "how do I", "appointment", "meet", "consultation",
        "talk to lawyer", "speak with", "schedule", "book", "set up"
    ]
    
    shows_readiness = any(keyword in user_query.lower() for keyword in ready_keywords)
    
    return shows_readiness

def get_natural_contact_prompt(user_data: Dict[str, Any], conversation_count: int) -> str:
    """Generate natural prompts for contact information collection"""
    
    if conversation_count < 10:
        # Early in conversation - very gentle
        if not user_data.get("name"):
            return "By the way, what should I call you? This helps me personalize our conversation."
        else:
            return f"Thanks, {user_data['name']}! If you'd like me to send you some helpful information, what's your email address?"
    
    elif conversation_count < 15:
        # Mid-conversation - more direct but still friendly
        if not user_data.get("name"):
            return "I'd love to personalize our conversation better. What's your first name?"
        else:
            return f"Thanks, {user_data['name']}! If you'd like me to send you some helpful resources, what's your email address?"
    
    else:
        # Later in conversation - more direct
        if not user_data.get("name"):
            return "To better assist you, could you tell me your name?"
        else:
            return f"To send you helpful information, {user_data['name']}, what's your email address?"

def get_calendar_offer(user_data: Dict[str, Any]) -> str:
    """Generate natural calendar scheduling offer"""
    
    name = user_data.get("name", "")
    greeting = f"Hi {name}!" if name else "Hi there!"
    
    offers = [
        f"{greeting} I'd be happy to schedule a free consultation with one of our attorneys to discuss your case in detail. Would you like to book an appointment?",
        f"{greeting} If you'd like to speak directly with one of our attorneys about your situation, I can help you schedule a free consultation. Would that be helpful?",
        f"{greeting} To better understand your case and provide specific legal advice, I'd recommend speaking with one of our attorneys. Would you like to schedule a free consultation?"
    ]
    
    import random
    return random.choice(offers)

def extract_name_from_text(text: str) -> Tuple[Optional[str], bool]:
    """
    Extract name from user text using multiple methods
    Returns: (extracted_name, is_refusal)
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
        return None, False

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
        "accident", "legal", "lawyer", "attorney", "sue", "claim"
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
