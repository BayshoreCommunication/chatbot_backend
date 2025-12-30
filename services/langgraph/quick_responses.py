"""
Quick response patterns for common conversational inputs.
Handles greetings, confirmations, and farewells with smart context awareness.
"""

import re
from typing import Optional, List
from datetime import datetime, timedelta

# Patterns for quick responses
GREETING_PATTERNS = [
    r'\b(hi|hello|hey|hiya|greetings|howdy)\b',
]

FAREWELL_PATTERNS = [
    r'\b(bye|goodbye|see you|talk later|cheers|take care)\b',
]

THANK_YOU_PATTERNS = [
    r'\b(thanks|thank you|thx|ty)\b',
]

SHORT_CONFIRMATION_PATTERNS = [
    r'^(yes|yeah|yep|yup|ok|okay|sure|alright|fine|good|cool)\.?$',
    r'^(no|nope|nah|not really)\.?$',
]

def is_greeting(text: str) -> bool:
    """Check if message is a greeting"""
    text_lower = text.lower().strip()
    return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in GREETING_PATTERNS) and len(text.split()) <= 3

def is_farewell(text: str) -> bool:
    """Check if message is a farewell"""
    text_lower = text.lower().strip()
    return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in FAREWELL_PATTERNS) and len(text.split()) <= 5

def is_thank_you(text: str) -> bool:
    """Check if message is a thank you"""
    text_lower = text.lower().strip()
    return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in THANK_YOU_PATTERNS) and len(text.split()) <= 5

def is_short_confirmation(text: str) -> bool:
    """Check if message is just a short yes/no/okay"""
    text_lower = text.lower().strip()
    return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in SHORT_CONFIRMATION_PATTERNS)

def is_returning_user(chat_history: List) -> bool:
    """Check if user is returning after a gap"""
    if not chat_history or len(chat_history) < 2:
        return False
    
    # Check if there's significant history (indicates returning user)
    return len(chat_history) >= 4

def get_engaging_greeting(company_name: str = "our company", has_kb_context: bool = True) -> str:
    """
    Get an engaging greeting that mentions services.
    
    Args:
        company_name: Organization name
        has_kb_context: Whether KB has service information
        
    Returns:
        Engaging greeting message
    """
    # Clean up company name if it has awkward formatting
    if "'s Organization" in company_name or "'s organization" in company_name:
        company_name = company_name.replace("'s Organization", "").replace("'s organization", "")
    
    return (
        f"Hello! I'm here to help you. "
        "I can assist with questions about our services, pricing, availability, and more. What brings you here today?"
    )

def get_quick_response(
    text: str, 
    company_name: str = "our company",
    chat_history: List = None,
    has_kb_data: bool = True
) -> Optional[str]:
    """
    Get quick response for common conversational patterns.
    Returns None if this needs full KB/AI processing.
    
    Args:
        text: User's message
        company_name: Organization name
        chat_history: Conversation history
        has_kb_data: Whether knowledge base has data
        
    Returns:
        Quick response string or None
    """
    text_clean = text.strip()
    chat_history = chat_history or []
    
    # Let LangGraph handle ALL questions including greetings with KB context
    # This allows smart, contextual responses based on your knowledge base
    
    # Only handle true farewells with quick response
    if is_farewell(text_clean):
        return "Feel free to reach out anytime. Have a great day!"
    
    # Everything else (including greetings, questions, thank you) goes through LangGraph
    # This ensures responses are aligned with your knowledge base content
    return None

def needs_quick_response(text: str) -> bool:
    """Check if message can be handled with quick response"""
    # Only farewells get quick response now
    return is_farewell(text)
