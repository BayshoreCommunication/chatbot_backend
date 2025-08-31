#!/usr/bin/env python3
"""
Test script for conversation progression logic
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.conversation_flow import (
    get_conversation_progression_response, get_contextual_response
)

def test_car_accident_conversation_flow():
    """Test the car accident conversation flow to prevent repetitive responses"""
    print("=== Testing Car Accident Conversation Flow ===")
    
    # Simulate the conversation from the user's example
    conversation_history = []
    user_data = {}
    
    # Message 1: "No schedule need. I have another question do you take car accident cases?"
    print("\n1. User: 'No schedule need. I have another question do you take car accident cases?'")
    response1 = get_contextual_response("do you take car accident cases", conversation_history, user_data)
    print(f"Bot: '{response1}'")
    
    # Add to conversation history
    conversation_history.extend([
        {"role": "user", "content": "do you take car accident cases"},
        {"role": "assistant", "content": response1}
    ])
    
    # Message 2: "Driverr"
    print("\n2. User: 'Driverr'")
    response2 = get_contextual_response("Driverr", conversation_history, user_data)
    print(f"Bot: '{response2}'")
    
    # Add to conversation history
    conversation_history.extend([
        {"role": "user", "content": "Driverr"},
        {"role": "assistant", "content": response2}
    ])
    
    # Message 3: "Yeah i receive attention what should next?"
    print("\n3. User: 'Yeah i receive attention what should next?'")
    progression_response = get_conversation_progression_response("Yeah i receive attention what should next?", conversation_history, user_data)
    print(f"Bot (progression): '{progression_response}'")
    
    # Test that it doesn't give the same medical attention response
    contextual_response = get_contextual_response("Yeah i receive attention what should next?", conversation_history, user_data)
    print(f"Bot (contextual): '{contextual_response}'")
    
    # Verify that progression response is different from the original medical attention response
    if progression_response and progression_response != response2:
        print("✅ SUCCESS: Conversation progression provided a different, appropriate response!")
    else:
        print("❌ FAILURE: Conversation progression gave the same response or no response")

def test_next_step_questions():
    """Test various 'next step' type questions"""
    print("\n=== Testing Next Step Questions ===")
    
    conversation_history = [
        {"role": "user", "content": "I was in a car accident"},
        {"role": "assistant", "content": "I'm sorry to hear about your car accident. Have you received medical attention for your injuries?"},
        {"role": "user", "content": "Yes, I went to the doctor"},
        {"role": "assistant", "content": "Good, that's important. How are you feeling now?"}
    ]
    
    user_data = {}
    
    next_step_questions = [
        "what should next",
        "what next",
        "next step",
        "what now",
        "what do i do",
        "how do i proceed",
        "what should i do"
    ]
    
    for question in next_step_questions:
        print(f"\nUser: '{question}'")
        response = get_conversation_progression_response(question, conversation_history, user_data)
        if response:
            print(f"Bot: '{response[:100]}...'")
        else:
            print("Bot: No progression response")

def test_follow_up_confirmations():
    """Test follow-up confirmations like 'yeah', 'yes', etc."""
    print("\n=== Testing Follow-up Confirmations ===")
    
    conversation_history = [
        {"role": "user", "content": "I was in a car accident"},
        {"role": "assistant", "content": "I'm sorry to hear about your car accident. Have you received medical attention for your injuries?"}
    ]
    
    user_data = {}
    
    follow_up_responses = [
        "yeah",
        "yes",
        "okay",
        "ok",
        "sure",
        "alright"
    ]
    
    for response in follow_up_responses:
        print(f"\nUser: '{response}'")
        progression_response = get_conversation_progression_response(response, conversation_history, user_data)
        if progression_response:
            print(f"Bot: '{progression_response[:100]}...'")
        else:
            print("Bot: No progression response")

if __name__ == "__main__":
    test_car_accident_conversation_flow()
    test_next_step_questions()
    test_follow_up_confirmations()
    
    print("\n=== All Conversation Progression Tests Completed ===")
