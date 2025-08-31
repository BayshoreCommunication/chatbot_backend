#!/usr/bin/env python3
"""
Test script to verify the name/email collection flow fix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.conversation_flow import (
    extract_name_from_text, extract_email_from_text, 
    get_natural_name_prompt, get_natural_email_prompt,
    should_collect_contact_info
)

def test_name_extraction():
    """Test name extraction functionality"""
    print("=== Testing Name Extraction ===")
    
    test_cases = [
        ("Sahak", "Sahak"),
        ("My name is John", "John"),
        ("I'm Alice Johnson", "Alice Johnson"),
        ("arsahak@gmail.com", None),  # Should not extract email as name
        ("skip", None),  # Should detect refusal
        ("no", None),  # Should detect refusal
    ]
    
    for input_text, expected in test_cases:
        extracted, is_refusal = extract_name_from_text(input_text)
        if is_refusal:
            result = "REFUSED"
        else:
            result = extracted
        
        status = "✓" if result == expected else "✗"
        print(f"{status} Input: '{input_text}' -> Expected: {expected}, Got: {result}")

def test_email_extraction():
    """Test email extraction functionality"""
    print("\n=== Testing Email Extraction ===")
    
    test_cases = [
        ("arsahak@gmail.com", "arsahak@gmail.com"),
        ("My email is john@example.com", "john@example.com"),
        ("skip", None),  # Should detect refusal
        ("no", None),  # Should detect refusal
        ("hello there", None),  # No email
    ]
    
    for input_text, expected in test_cases:
        extracted, is_refusal = extract_email_from_text(input_text)
        if is_refusal:
            result = "REFUSED"
        else:
            result = extracted
        
        status = "✓" if result == expected else "✗"
        print(f"{status} Input: '{input_text}' -> Expected: {expected}, Got: {result}")

def test_prompt_functions():
    """Test the new prompt functions"""
    print("\n=== Testing Prompt Functions ===")
    
    # Test name prompt
    user_data = {}
    name_prompt = get_natural_name_prompt(user_data, 5)
    print(f"Name prompt (early): {name_prompt}")
    
    name_prompt = get_natural_name_prompt(user_data, 12)
    print(f"Name prompt (mid): {name_prompt}")
    
    name_prompt = get_natural_name_prompt(user_data, 20)
    print(f"Name prompt (late): {name_prompt}")
    
    # Test email prompt
    user_data = {"name": "Sahak"}
    email_prompt = get_natural_email_prompt(user_data, 5)
    print(f"Email prompt (with name): {email_prompt}")
    
    user_data = {}
    email_prompt = get_natural_email_prompt(user_data, 5)
    print(f"Email prompt (no name): {email_prompt}")

def test_conversation_flow():
    """Test the complete conversation flow"""
    print("\n=== Testing Conversation Flow ===")
    
    # Simulate the user's reported conversation
    conversation_history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hello! I'm Miles from Carter Injury Law. How can I assist you today?"},
        {"role": "user", "content": "I have a question about car accidents"},
        {"role": "assistant", "content": "I'm sorry to hear about your car accident. Car accidents can be complex, and you may be entitled to compensation for medical bills, lost wages, and pain and suffering. Have you received medical attention for your injuries?"},
        {"role": "user", "content": "yes"},
        {"role": "assistant", "content": "Perfect! Since you've received medical attention, let's talk about your next steps. Have you been contacted by any insurance companies yet? And do you have any photos or documentation from the accident?"},
        {"role": "user", "content": "no"},
        {"role": "assistant", "content": "That's okay. Let me help you understand your options. First, I'd love to personalize our conversation better. What's your first name?"},
    ]
    
    user_data = {}
    user_query = "Sahak"
    
    # Test name extraction
    extracted_name, is_refusal = extract_name_from_text(user_query)
    print(f"User says: '{user_query}'")
    print(f"Extracted name: {extracted_name}, Is refusal: {is_refusal}")
    
    if extracted_name:
        user_data["name"] = extracted_name
        print(f"Updated user_data: {user_data}")
    
    # Simulate next message
    user_query = "arsahak@gmail.com"
    extracted_email, is_refusal = extract_email_from_text(user_query)
    print(f"\nUser says: '{user_query}'")
    print(f"Extracted email: {extracted_email}, Is refusal: {is_refusal}")
    
    if extracted_email:
        user_data["email"] = extracted_email
        print(f"Updated user_data: {user_data}")
    
    # Test that should_collect_contact_info returns False when both name and email are present
    has_name = "name" in user_data and user_data["name"] and user_data["name"] not in ["Anonymous User", "Guest User"]
    has_email = "email" in user_data and user_data["email"] and user_data["email"] != "anonymous@user.com"
    
    print(f"\nHas name: {has_name}, Has email: {has_email}")
    
    if has_name and has_email:
        should_collect = False
        print("✓ Contact info collection should be disabled (both name and email present)")
    else:
        should_collect = should_collect_contact_info(conversation_history, "next message", user_data)
        print(f"Should collect contact info: {should_collect}")

def test_edge_cases():
    """Test edge cases and potential issues"""
    print("\n=== Testing Edge Cases ===")
    
    # Test with empty user_data
    user_data = {}
    conversation_history = []
    
    # Test should_collect_contact_info with various states
    print("Testing should_collect_contact_info with different user_data states:")
    
    # No name, no email
    should_collect = should_collect_contact_info(conversation_history, "I need help", user_data)
    print(f"  No name, no email: {should_collect}")
    
    # Has name, no email
    user_data["name"] = "Sahak"
    should_collect = should_collect_contact_info(conversation_history, "I need help", user_data)
    print(f"  Has name, no email: {should_collect}")
    
    # Has name, has email
    user_data["email"] = "arsahak@gmail.com"
    should_collect = should_collect_contact_info(conversation_history, "I need help", user_data)
    print(f"  Has name, has email: {should_collect}")
    
    # Test with anonymous values
    user_data["name"] = "Anonymous User"
    user_data["email"] = "anonymous@user.com"
    should_collect = should_collect_contact_info(conversation_history, "I need help", user_data)
    print(f"  Anonymous name/email: {should_collect}")

if __name__ == "__main__":
    print("Testing Name/Email Collection Flow Fix")
    print("=" * 50)
    
    test_name_extraction()
    test_email_extraction()
    test_prompt_functions()
    test_conversation_flow()
    test_edge_cases()
    
    print("\n" + "=" * 50)
    print("Test completed!")
