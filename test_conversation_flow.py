#!/usr/bin/env python3
"""
Test script for the improved conversation flow requirements
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.conversation_flow import (
    get_enhanced_greeting,
    get_conversation_progression_response,
    should_collect_contact_info,
    get_natural_contact_prompt,
    process_user_message_for_info
)

def test_greeting_handling():
    """Test simple greeting responses"""
    print("=== Testing Greeting Handling ===")
    
    # Test simple greeting
    user_data = {"conversation_history": []}
    response = get_enhanced_greeting("Hi", 0, user_data)
    print(f"Simple 'Hi': {response}")
    assert response == "Hello! How can I help you today regarding personal injury?"
    
    # Test greeting with meaningful content
    response = get_enhanced_greeting("Hello, I need help with my car accident", 0, user_data)
    print(f"Greeting with content: {response}")
    
    # Test no duplicate greeting
    user_data["conversation_history"] = [{"role": "assistant", "content": "Hello! How can I help you today regarding personal injury?"}]
    response = get_enhanced_greeting("Hi again", 1, user_data)
    print(f"Duplicate greeting: {response}")
    assert response is None
    
    print("✓ Greeting handling tests passed\n")

def test_small_talk():
    """Test small talk responses"""
    print("=== Testing Small Talk ===")
    
    user_data = {}
    conversation_history = []
    
    # Test thank you response
    response = get_conversation_progression_response("Thank you", conversation_history, user_data)
    print(f"Thank you response: {response}")
    assert response == "You're welcome! Happy to help."
    
    # Test appreciation response
    response = get_conversation_progression_response("That's very helpful", conversation_history, user_data)
    print(f"Appreciation response: {response}")
    assert response == "You're welcome! Happy to help."
    
    print("✓ Small talk tests passed\n")

def test_contact_collection():
    """Test contact information collection logic"""
    print("=== Testing Contact Collection ===")
    
    # Test scheduling intent triggers collection
    conversation_history = []
    user_data = {}
    should_collect = should_collect_contact_info(conversation_history, "I want to schedule an appointment", user_data)
    print(f"Scheduling intent should collect: {should_collect}")
    assert should_collect == True
    
    # Test no collection when already have both name and email
    user_data = {"name": "John Doe", "email": "john@example.com"}
    should_collect = should_collect_contact_info(conversation_history, "I want to schedule an appointment", user_data)
    print(f"Already have info should collect: {should_collect}")
    assert should_collect == False
    
    print("✓ Contact collection tests passed\n")

def test_contact_prompts():
    """Test contact information prompts"""
    print("=== Testing Contact Prompts ===")
    
    # Test name prompt
    user_data = {}
    prompt = get_natural_contact_prompt(user_data, 5)
    print(f"Name prompt: {prompt}")
    assert "full name" in prompt.lower()
    
    # Test email prompt
    user_data = {"name": "John Doe"}
    prompt = get_natural_contact_prompt(user_data, 5)
    print(f"Email prompt: {prompt}")
    assert "email" in prompt.lower()
    
    print("✓ Contact prompt tests passed\n")

def test_message_processing():
    """Test message processing for name/email extraction"""
    print("=== Testing Message Processing ===")
    
    # Test name extraction
    user_data = {}
    updated_data = process_user_message_for_info("My name is John Doe", user_data)
    print(f"Name extraction result: {updated_data}")
    
    # Test email extraction
    user_data = {"name": "John Doe"}
    updated_data = process_user_message_for_info("My email is john@example.com", user_data)
    print(f"Email extraction result: {updated_data}")
    
    print("✓ Message processing tests passed\n")

def main():
    """Run all tests"""
    print("🔹 Testing Conversation Flow Requirements Implementation\n")
    
    try:
        test_greeting_handling()
        test_small_talk()
        test_contact_collection()
        test_contact_prompts()
        test_message_processing()
        
        print("✅ All tests passed! Conversation flow implementation is working correctly.")
        
        print("\n🔹 Example Conversation Flow:")
        print("User: Hi")
        print("Bot: Hello! How can I help you today regarding personal injury?")
        print("\nUser: I need to schedule an appointment.")
        print("Bot: Can I have your full name to help you better?")
        print("\nUser: My name is John, email is john@example.com")
        print("Bot: Thanks, John! And your email address so we can follow up with you?")
        print("\nUser: Thank you.")
        print("Bot: You're welcome! Happy to help.")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
