#!/usr/bin/env python3
"""
Test script for hardcoded FAQ filtering
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hardcoded_faq_responses import find_hardcoded_response

def test_hardcoded_filtering():
    """Test that hardcoded responses are filtered for next step questions"""
    print("=== Testing Hardcoded FAQ Filtering ===")
    
    # Test next step questions - should return None
    next_step_questions = [
        "what should next",
        "what next", 
        "next step",
        "what now",
        "what do i do",
        "how do i proceed",
        "what should i do",
        "what's next"
    ]
    
    print("\n--- Next Step Questions (should return None) ---")
    for question in next_step_questions:
        response = find_hardcoded_response(question)
        if response is None:
            print(f"✅ '{question}' -> None (correctly filtered)")
        else:
            print(f"❌ '{question}' -> {response['answer'][:50]}... (should be filtered)")
    
    # Test follow-up confirmations - should return None
    follow_up_questions = [
        "yeah",
        "yes",
        "okay", 
        "ok",
        "sure",
        "alright",
        "right",
        "correct"
    ]
    
    print("\n--- Follow-up Confirmations (should return None) ---")
    for question in follow_up_questions:
        response = find_hardcoded_response(question)
        if response is None:
            print(f"✅ '{question}' -> None (correctly filtered)")
        else:
            print(f"❌ '{question}' -> {response['answer'][:50]}... (should be filtered)")
    
    # Test regular questions - should return responses
    regular_questions = [
        "do you take car accident cases",
        "how much do you charge",
        "do you offer free consultations",
        "what services do you offer"
    ]
    
    print("\n--- Regular Questions (should return responses) ---")
    for question in regular_questions:
        response = find_hardcoded_response(question)
        if response is not None:
            print(f"✅ '{question}' -> {response['answer'][:50]}... (correctly returned)")
        else:
            print(f"❌ '{question}' -> None (should return response)")

if __name__ == "__main__":
    test_hardcoded_filtering()
    print("\n=== Hardcoded Filtering Tests Completed ===")
