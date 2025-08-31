#!/usr/bin/env python3
"""
Test script for enhanced conversation flow
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.conversation_flow import (
    get_enhanced_greeting, get_contextual_response, process_user_message_for_info,
    should_collect_contact_info, should_offer_calendar, get_natural_contact_prompt,
    get_calendar_offer
)

def test_enhanced_greetings():
    """Test enhanced greeting responses"""
    print("=== Testing Enhanced Greetings ===")
    
    # Test first message greetings
    test_cases = [
        ("Hello", 0, {}),
        ("Hi there", 0, {}),
        ("Hello, Carter Injury Law", 0, {}),
        ("Can you help me?", 0, {}),
        ("I need assistance", 0, {}),
    ]
    
    for query, count, user_data in test_cases:
        response = get_enhanced_greeting(query, count, user_data)
        print(f"Query: '{query}' -> Response: '{response}'")
    
    # Test subsequent messages
    user_data_with_name = {"name": "John"}
    test_cases_subsequent = [
        ("Hello", 5, user_data_with_name),
        ("Hi", 10, user_data_with_name),
        ("Hey", 15, {}),
    ]
    
    print("\n--- Subsequent Messages ---")
    for query, count, user_data in test_cases_subsequent:
        response = get_enhanced_greeting(query, count, user_data)
        print(f"Query: '{query}' (count: {count}) -> Response: '{response}'")

def test_contextual_responses():
    """Test contextual response patterns"""
    print("\n=== Testing Contextual Responses ===")
    
    test_cases = [
        ("Who are you?", []),
        ("What do you do?", []),
        ("Are you a lawyer?", []),
        ("What services do you offer?", []),
        ("Do you handle car accidents?", []),
        ("Where are you located?", []),
        ("How much do you charge?", []),
        ("Do you offer consultations?", []),
        ("I was in a car accident", []),
        ("I had a slip and fall", []),
        ("This is urgent", []),
    ]
    
    user_data = {}
    for query, history in test_cases:
        response = get_contextual_response(query, history, user_data)
        if response:
            print(f"Query: '{query}' -> Response: '{response}'")
        else:
            print(f"Query: '{query}' -> No contextual response")

def test_information_collection():
    """Test information collection logic"""
    print("\n=== Testing Information Collection ===")
    
    # Test name extraction
    test_cases = [
        ("My name is John", {}),
        ("I'm Sarah Johnson", {}),
        ("Call me Mike", {}),
        ("This is David from Tampa", {}),
        ("I don't want to share my name", {}),
    ]
    
    for query, user_data in test_cases:
        updated_data = process_user_message_for_info(query, user_data)
        print(f"Query: '{query}' -> Updated data: {updated_data}")

def test_collection_timing():
    """Test when to collect information"""
    print("\n=== Testing Collection Timing ===")
    
    # Test early conversation (should not collect)
    early_history = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]
    should_collect_early = should_collect_contact_info(early_history, "What services do you offer?", {})
    print(f"Early conversation (2 messages): Should collect = {should_collect_early}")
    
    # Test later conversation (should collect)
    later_history = [{"role": "user", "content": "Hello"}] * 20  # 20 messages
    should_collect_later = should_collect_contact_info(later_history, "I need help with my case", {})
    print(f"Later conversation (20 messages): Should collect = {should_collect_later}")
    
    # Test with serious interest
    serious_history = [{"role": "user", "content": "Hello"}] * 10
    should_collect_serious = should_collect_contact_info(serious_history, "I need to schedule a consultation", {})
    print(f"Serious interest (10 messages): Should collect = {should_collect_serious}")

def test_calendar_offers():
    """Test calendar offer logic"""
    print("\n=== Testing Calendar Offers ===")
    
    # Test early conversation (should not offer)
    early_history = [{"role": "user", "content": "Hello"}] * 10
    should_offer_early = should_offer_calendar(early_history, "What services do you offer?", {})
    print(f"Early conversation (10 messages): Should offer calendar = {should_offer_early}")
    
    # Test later conversation with readiness
    later_history = [{"role": "user", "content": "Hello"}] * 20
    should_offer_later = should_offer_calendar(later_history, "What's the next step?", {})
    print(f"Later conversation with readiness (20 messages): Should offer calendar = {should_offer_later}")
    
    # Test calendar offer generation
    user_data = {"name": "John"}
    calendar_offer = get_calendar_offer(user_data)
    print(f"Calendar offer for John: '{calendar_offer}'")

if __name__ == "__main__":
    test_enhanced_greetings()
    test_contextual_responses()
    test_information_collection()
    test_collection_timing()
    test_calendar_offers()
    
    print("\n=== All Tests Completed ===")
