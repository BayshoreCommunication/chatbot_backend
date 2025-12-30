"""
Entity Extraction Module
Automatically extracts contact information (name, phone, email) from user messages.
This helps the chatbot collect callback information intelligently.
"""

import re
from typing import Dict, Optional, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


def extract_phone_number(text: str) -> Optional[str]:
    """
    Extract phone number from text using regex patterns.

    Supports formats:
    - (123) 456-7890
    - 123-456-7890
    - 123.456.7890
    - 1234567890
    - +1 123 456 7890

    Args:
        text: Input text to search for phone numbers

    Returns:
        Extracted phone number or None
    """
    # Remove common words that might interfere
    text = text.replace("call me at", "").replace("my number is", "")

    # Phone number patterns
    patterns = [
        r'\+?1?\s*\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})',  # (123) 456-7890 or 123-456-7890
        r'\b(\d{3})[\s.-](\d{3})[\s.-](\d{4})\b',  # 123.456.7890
        r'\b(\d{10})\b',  # 1234567890
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Format the phone number consistently
            if len(match.groups()) == 3:
                return f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
            elif len(match.groups()) == 1 and len(match.group(1)) == 10:
                phone = match.group(1)
                return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"

    return None


def extract_email(text: str) -> Optional[str]:
    """
    Extract email address from text.

    Args:
        text: Input text to search for email

    Returns:
        Extracted email or None
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None


def extract_name(text: str, chat_history: List[BaseMessage] = None) -> Optional[str]:
    """
    Extract name from text using pattern matching and context.

    Looks for patterns like:
    - "My name is John"
    - "I'm Sarah"
    - "This is Mike"
    - "John Doe" (when asked for name)

    Args:
        text: Input text to extract name from
        chat_history: Previous conversation for context

    Returns:
        Extracted name or None
    """
    text = text.strip()

    # Check if assistant recently asked for name
    asking_for_name = False
    if chat_history and len(chat_history) >= 1:
        last_message = chat_history[-1]
        if isinstance(last_message, AIMessage):
            asking_keywords = ["what's your name", "what is your name", "your name", "may i have your name"]
            if any(keyword in last_message.content.lower() for keyword in asking_keywords):
                asking_for_name = True

    # If we just asked for name, treat the whole response as the name (cleaned)
    if asking_for_name:
        # Remove common phrases
        name = text.lower()
        name = re.sub(r'^(my name is|i am|i\'m|this is|it\'s|its)\s+', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+(here|sir|ma\'am)$', '', name, flags=re.IGNORECASE)

        # Capitalize words
        name = ' '.join(word.capitalize() for word in name.split())

        # Basic validation - should be 1-4 words, mostly letters
        words = name.split()
        if 1 <= len(words) <= 4 and all(re.match(r'^[A-Za-z\'-]+$', word) for word in words):
            return name

    # Pattern-based extraction
    patterns = [
        r"(?:my name is|i am|i'm|this is|it's|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})$",  # Just a name (1-3 words)
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            # Validate it's not too long and looks like a name
            if 2 <= len(name) <= 50:
                return name

    return None


def extract_contact_info(text: str, chat_history: List[BaseMessage] = None) -> Dict[str, Optional[str]]:
    """
    Extract all contact information from text.

    Args:
        text: Input text to extract from
        chat_history: Previous conversation for context

    Returns:
        Dictionary with 'name', 'phone', 'email' keys
    """
    return {
        "name": extract_name(text, chat_history),
        "phone": extract_phone_number(text),
        "email": extract_email(text)
    }


def has_contact_info(text: str) -> bool:
    """
    Quick check if text contains any contact information.

    Args:
        text: Input text to check

    Returns:
        True if text contains phone, email, or looks like a name
    """
    phone = extract_phone_number(text)
    email = extract_email(text)

    # Check if it looks like it could be a name (capitalized words)
    name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
    has_name_pattern = bool(re.search(name_pattern, text))

    return bool(phone or email or has_name_pattern)


def get_missing_contact_fields(collected_info: Dict[str, Optional[str]], required_fields: List[str] = None) -> List[str]:
    """
    Determine which contact fields are still missing.

    Args:
        collected_info: Dictionary with collected contact information
        required_fields: List of required fields (default: ['name', 'phone'])

    Returns:
        List of missing field names
    """
    if required_fields is None:
        required_fields = ['name', 'phone']  # Default: only need name and phone for callback

    missing = []
    for field in required_fields:
        if not collected_info.get(field):
            missing.append(field)

    return missing


# Example usage and testing
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "My name is John Smith",
        "Call me at (555) 123-4567",
        "You can reach me at 555-123-4567",
        "I'm Sarah Johnson and my number is 5551234567",
        "Email me at john@example.com",
        "My name is John and my phone is (555) 123-4567"
    ]

    print("Testing Entity Extraction:")
    print("=" * 60)

    for test in test_cases:
        info = extract_contact_info(test)
        print(f"\nInput: {test}")
        print(f"  Name:  {info['name']}")
        print(f"  Phone: {info['phone']}")
        print(f"  Email: {info['email']}")
