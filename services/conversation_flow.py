#!/usr/bin/env python3
"""
Enhanced Natural Conversation Flow Controller for Carter Injury Law
Manages when and how to collect user information during conversations
"""

import re
import openai
from typing import Dict, Any, Optional, Tuple
import random

def get_enhanced_greeting(user_query: str, conversation_count: int, user_data: Dict[str, Any]) -> str:
    """Generate natural, lawyer-like greetings with personality"""
    
    # Clean the query for better matching
    clean_query = user_query.lower().strip()
    
    # Check for different types of greetings
    is_simple_greeting = any(word in clean_query for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"])
    is_law_firm_greeting = any(word in clean_query for word in ["carter injury law", "carter law", "injury law"])
    is_help_request = any(word in clean_query for word in ["help", "assist", "need help", "can you help"])
    
    # Get user name if available
    user_name = user_data.get("name", "")
    
    # Different greeting strategies based on conversation stage
    if conversation_count == 0:
        # First message - warm, professional greeting
        if is_simple_greeting:
            greetings = [
                "Hello! Welcome to Carter Injury Law. I'm Miles, your legal assistant. How can I help you today?",
                "Hi there! I'm Miles from Carter Injury Law. I'm here to assist you with any legal questions or concerns you might have.",
                "Hello! Thanks for reaching out to Carter Injury Law. I'm Miles, and I'm ready to help you with your legal needs.",
                "Hi! Welcome to Carter Injury Law. I'm Miles, your dedicated legal assistant. What brings you here today?"
            ]
        elif is_law_firm_greeting:
            greetings = [
                "Hello! Yes, you've reached Carter Injury Law. I'm Miles, your legal assistant. How can I assist you today?",
                "Hi there! You're speaking with Miles from Carter Injury Law. I'm here to help with any legal questions or concerns.",
                "Hello! Welcome to Carter Injury Law. I'm Miles, and I'm ready to assist you with your legal needs."
            ]
        elif is_help_request:
            greetings = [
                "Absolutely! I'm Miles from Carter Injury Law, and I'm here to help. What legal questions or concerns do you have?",
                "Of course! I'm Miles, your legal assistant at Carter Injury Law. I'm ready to assist you with any legal matters.",
                "I'd be happy to help! I'm Miles from Carter Injury Law. What can I assist you with today?"
            ]
        else:
            # Generic first greeting
            greetings = [
                "Hello! I'm Miles from Carter Injury Law. How can I assist you today?",
                "Hi there! I'm Miles, your legal assistant at Carter Injury Law. What brings you here today?",
                "Hello! Welcome to Carter Injury Law. I'm Miles, and I'm here to help with your legal needs."
            ]
        
        return random.choice(greetings)
    
    else:
        # Subsequent messages - more conversational
        if user_name:
            responses = [
                f"Hi {user_name}! How else can I help you?",
                f"Hello {user_name}! What other questions do you have?",
                f"Hi there {user_name}! Is there anything else you'd like to know?"
            ]
        else:
            responses = [
                "Hi! How else can I help you?",
                "Hello! What other questions do you have?",
                "Hi there! Is there anything else you'd like to know?"
            ]
        
        return random.choice(responses)

def get_conversation_progression_response(user_query: str, conversation_history: list, user_data: Dict[str, Any]) -> Optional[str]:
    """
    Handle conversation progression and prevent repetitive responses
    by providing appropriate next steps based on conversation context
    """
    clean_query = user_query.lower().strip()
    
    # Check for "next step" or "what next" type questions
    next_step_indicators = [
        "what should next", "what next", "next step", "what now", "what do i do",
        "how do i", "what should i do", "next steps", "what's next"
    ]
    
    if any(indicator in clean_query for indicator in next_step_indicators):
        # Analyze conversation context to provide appropriate next steps
        recent_messages = conversation_history[-6:] if len(conversation_history) >= 6 else conversation_history
        
        # Check if user mentioned car accident and medical attention
        has_car_accident = any("car accident" in msg.get("content", "").lower() for msg in recent_messages)
        has_medical_attention = any("medical attention" in msg.get("content", "").lower() or 
                                  "doctor" in msg.get("content", "").lower() or
                                  "checked" in msg.get("content", "").lower() for msg in recent_messages)
        
        if has_car_accident and has_medical_attention:
            return "Great! Since you've received medical attention, the next important step is to document everything. Here's what you should do:\n\n1. **Document the accident** - Take photos of your injuries, damage to your vehicle, and the accident scene if possible\n2. **Keep all medical records** - Save all bills, prescriptions, and doctor's notes\n3. **Don't talk to insurance companies** - Let us handle all communications\n4. **Schedule a consultation** - We can review your case and explain your rights\n\nWould you like to schedule a free consultation to discuss your case in detail?"
        
        # Check if user mentioned injury or accident
        has_injury = any("injury" in msg.get("content", "").lower() or 
                        "hurt" in msg.get("content", "").lower() or
                        "pain" in msg.get("content", "").lower() for msg in recent_messages)
        
        if has_injury:
            return "I understand you've been injured. Here are the next steps:\n\n1. **Continue medical treatment** - Follow your doctor's recommendations\n2. **Document everything** - Keep records of all medical visits, medications, and how the injury affects your daily life\n3. **Don't sign anything** - Insurance companies may try to get you to sign documents that limit your rights\n4. **Contact us** - We can help you understand your legal options and fight for the compensation you deserve\n\nWould you like to schedule a free consultation to discuss your case?"
        
        # Generic next steps for legal help
        return "Here are the next steps to get you the help you need:\n\n1. **Schedule a free consultation** - We'll review your case and explain your options\n2. **Gather documentation** - Any relevant documents, photos, or evidence you have\n3. **Don't delay** - There may be time limits on your case\n4. **We'll handle the rest** - Our experienced attorneys will fight for your rights\n\nWould you like to schedule a consultation? I can help you book a time that works for you."
    
    # Check for follow-up questions after initial responses
    follow_up_indicators = [
        "yeah", "yes", "okay", "ok", "sure", "alright", "right", "correct"
    ]
    
    if any(indicator in clean_query for indicator in follow_up_indicators):
        # Check recent conversation context
        recent_messages = conversation_history[-4:] if len(conversation_history) >= 4 else conversation_history
        
        # If user just confirmed they received medical attention
        if any("medical attention" in msg.get("content", "").lower() for msg in recent_messages[-2:]):
            return "Perfect! Since you've received medical attention, let's talk about your next steps. Have you been contacted by any insurance companies yet? And do you have any photos or documentation from the accident?"
        
        # If user just confirmed they were in a car accident
        if any("car accident" in msg.get("content", "").lower() for msg in recent_messages[-2:]):
            return "I'm sorry you're going through this. Car accidents can be overwhelming. Have you received any medical attention for your injuries? And do you have any documentation from the accident scene?"
    
    return None

def get_contextual_response(user_query: str, conversation_history: list, user_data: Dict[str, Any]) -> Optional[str]:
    """Generate contextual responses for common patterns"""
    
    clean_query = user_query.lower().strip()
    conversation_count = len(conversation_history)
    
    # First check for conversation progression
    progression_response = get_conversation_progression_response(user_query, conversation_history, user_data)
    if progression_response:
        return progression_response
    
    # Common question patterns and their responses
    common_patterns = {
        # Identity questions
        r"who are you": "I'm Miles, your legal assistant at Carter Injury Law. I'm here to help you with legal questions and guide you through our services.",
        r"what do you do": "I'm a legal assistant at Carter Injury Law, specializing in personal injury cases. I help answer questions, provide information about our services, and assist with scheduling consultations.",
        r"are you a lawyer": "I'm a legal assistant, not a lawyer. I can answer general questions and help connect you with our experienced attorneys, David J. Carter and Robert Johnson, who handle all legal matters.",
        
        # Service questions
        r"what services": "Carter Injury Law specializes in personal injury cases including auto accidents, slip and falls, medical malpractice, and more. We offer free consultations and work on a no-fee-unless-we-win basis.",
        r"what cases": "We handle all types of personal injury cases: car accidents, slip and falls, medical malpractice, wrongful death, and more. Our experienced attorneys have helped hundreds of clients recover compensation.",
        r"do you handle": "Yes, Carter Injury Law handles a wide range of personal injury cases. Our attorneys, David J. Carter and Robert Johnson, have extensive experience in personal injury law and have helped many clients.",
        
        # Location questions
        r"where are you": "Carter Injury Law is located in Tampa, Florida, but we handle cases throughout the state. We can meet with clients in their homes or at other convenient locations.",
        r"do you serve": "Yes, we serve clients throughout Florida. While we're based in Tampa, our attorneys can travel to meet with you wherever is most convenient.",
        
        # Cost questions
        r"how much": "We offer free initial consultations and work on a contingency fee basis, meaning you don't pay anything unless we win your case. There are no upfront costs or fees.",
        r"cost": "Our consultations are completely free, and we work on a no-fee-unless-we-win basis. This means you only pay if we successfully recover compensation for you.",
        r"fee": "We work on a contingency fee basis, which means no upfront costs. You only pay if we win your case and recover compensation for you.",
        
        # Appointment questions
        r"consultation": "We offer free consultations where you can discuss your case with one of our experienced attorneys. Would you like to schedule a consultation?",
        r"appointment": "I'd be happy to help you schedule a free consultation with one of our attorneys. When would be a good time for you?",
        r"meet": "Absolutely! We offer free consultations and can meet with you at our office, your home, or another convenient location. Would you like to schedule a meeting?",
        
        # Experience questions
        r"experience": "Our attorneys, David J. Carter and Robert Johnson, have decades of combined experience in personal injury law. They've successfully handled hundreds of cases and recovered millions in compensation for our clients.",
        r"how long": "Carter Injury Law has been serving clients for many years. Our attorneys have extensive experience and have helped hundreds of clients recover the compensation they deserve.",
        
        # Urgency questions
        r"urgent": "I understand this is urgent. Personal injury cases often have time limits, so it's important to act quickly. Let me help you schedule a consultation as soon as possible.",
        r"emergency": "If this is a medical emergency, please call 911 immediately. For legal matters, I can help you schedule a consultation right away to discuss your case.",
    }
    
    # Check for pattern matches
    for pattern, response in common_patterns.items():
        if re.search(pattern, clean_query):
            return response
    
    # Check for specific injury types
    injury_types = {
        r"car accident": "I'm sorry to hear about your car accident. Car accidents can be complex, and you may be entitled to compensation for medical bills, lost wages, and pain and suffering. Have you received medical attention for your injuries?",
        r"slip and fall": "Slip and fall accidents can result in serious injuries. Property owners have a duty to maintain safe conditions. Let me help you understand your rights and options.",
        r"medical malpractice": "Medical malpractice cases are complex and require specialized knowledge. Our attorneys have experience handling these cases and can evaluate whether you have a valid claim.",
        r"wrongful death": "I'm so sorry for your loss. Wrongful death cases are among the most difficult, and our attorneys handle them with the compassion and expertise they require.",
    }
    
    for pattern, response in injury_types.items():
        if re.search(pattern, clean_query):
            return response
    
    return None

def should_collect_contact_info(conversation_history: list, user_query: str, user_data: Dict[str, Any]) -> bool:
    """Determine if we should collect contact information naturally"""
    conversation_count = len(conversation_history)
    
    # Never collect in first 4 exchanges (8 messages total)
    if conversation_count < 8:
        return False
    
    # Check if user shows serious interest
    serious_keywords = [
        "consultation", "appointment", "meet", "talk", "speak", "call", "contact",
        "help me", "need help", "serious", "urgent", "emergency", "immediately",
        "my case", "my accident", "my injury", "i was hurt", "i was injured"
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
    
    # Only offer after 8-10 exchanges (16+ messages)
    if conversation_count < 16:
        return False
    
    # Check if user is ready for next step
    ready_keywords = [
        "next step", "what now", "how do I", "appointment", "meet", "consultation",
        "talk to lawyer", "speak with", "schedule", "book", "set up", "when can",
        "available", "free time", "convenient"
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
