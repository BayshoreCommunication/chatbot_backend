#!/usr/bin/env python3
"""
Test script to reproduce the name and email collection issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.conversation_flow import (
    extract_name_from_text, extract_email_from_text, 
    should_collect_contact_info, get_natural_contact_prompt
)

def test_name_email_issue():
    """Test the exact scenario from the user's conversation"""
    
    print("=== Testing Name and Email Collection Issue ===\n")
    
    # Simulate the conversation flow from the user's example
    conversation_history = [
        {"role": "assistant", "content": "I'd love to personalize our conversation better. What's your first name?"},
        {"role": "user", "content": "Sahak"},
        {"role": "assistant", "content": "Please provide a valid email address so I can better assist you. (or type 'skip' if you prefer not to share)"},
        {"role": "user", "content": "arsahak@gmail.com"}
    ]
    
    user_data = {}
    
    print("1. Testing name extraction from 'Sahak':")
    name, is_refusal = extract_name_from_text("Sahak")
    print(f"   Extracted name: {name}")
    print(f"   Is refusal: {is_refusal}")
    print()
    
    print("2. Testing email extraction from 'arsahak@gmail.com':")
    email, is_refusal = extract_email_from_text("arsahak@gmail.com")
    print(f"   Extracted email: {email}")
    print(f"   Is refusal: {is_refusal}")
    print()
    
    print("3. Testing should_collect_contact_info:")
    should_collect = should_collect_contact_info(conversation_history, "arsahak@gmail.com", user_data)
    print(f"   Should collect: {should_collect}")
    print()
    
    print("4. Testing natural contact prompt:")
    prompt = get_natural_contact_prompt(user_data, len(conversation_history))
    print(f"   Prompt: {prompt}")
    print()
    
    # Simulate what should happen
    print("5. Expected behavior:")
    print("   - Name 'Sahak' should be extracted and stored")
    print("   - Email 'arsahak@gmail.com' should be extracted and stored")
    print("   - Bot should acknowledge both and continue conversation")
    print()
    
    print("6. Actual behavior (from user's report):")
    print("   - Bot says: 'Nice to meet you, arsahak@gmail.com! Could you please share your email address...'")
    print("   - This suggests the email was treated as the name")
    print("   - The email prompt is repeated")
    print()

if __name__ == "__main__":
    test_name_email_issue()
