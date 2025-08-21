#!/usr/bin/env python3
"""
Test script to verify chatbot responses with the new FAQ data
"""

import sys
import os
import requests
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_chatbot_responses():
    """Test the chatbot with the specific Q&A scenarios"""
    
    # Test configuration
    base_url = "http://localhost:8000"  # Update if your server runs on different port
    api_key = "test_api_key"  # Update with your actual API key
    
    # Test questions from the Q&A pairs
    test_questions = [
        "Do you handle personal injury cases?",
        "Do you take car accident cases?",
        "Do you handle family law cases like divorce or custody?",
        "How much do you charge?",
        "Do you offer free consultations?",
        "How long will my case take?",
        "What information do I need to start?",
        "How do I contact my lawyer?",
        "How quickly do you respond?",
        "Do you only work in California?",
        "Can you represent me if I live out of state?",
        "What should I do right now?",
        "Can I bring documents or photos?"
    ]
    
    # Expected response patterns (partial matches)
    expected_patterns = [
        "Yes, we handle personal injury cases",
        "Absolutely, we work with clients involved in car accidents",
        "Yes, we handle family law matters",
        "Many of our cases are handled on a contingency fee basis",
        "Yes, we offer free initial consultations",
        "The timeline depends on the type of case",
        "Typically, details like the date of the incident",
        "You can reach us by phone, email",
        "We aim to respond within 24 hours",
        "We are licensed in",
        "In some cases, yes",
        "The best next step is to schedule a free consultation",
        "Yes, please do. Documents, photos"
    ]
    
    print("🤖 Testing Chatbot Responses")
    print("=" * 50)
    
    session_id = f"test_session_{hash('test')}"
    
    for i, (question, expected_pattern) in enumerate(zip(test_questions, expected_patterns)):
        print(f"\nTest {i+1}: {question}")
        print("-" * 40)
        
        try:
            # Prepare the request
            payload = {
                "question": question,
                "session_id": session_id,
                "mode": "faq",
                "user_data": {},
                "available_slots": []
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": api_key
            }
            
            # Make the request
            response = requests.post(
                f"{base_url}/ask",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                
                print(f"✅ Response received:")
                print(f"   {answer}")
                
                # Check if response contains expected pattern
                if expected_pattern.lower() in answer.lower():
                    print(f"✅ Response matches expected pattern")
                else:
                    print(f"⚠️  Response doesn't match expected pattern")
                    print(f"   Expected: {expected_pattern}")
                
                # Check mode
                mode = data.get("mode", "")
                print(f"   Mode: {mode}")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🎯 Testing Complete!")
    print("\nTo run this test:")
    print("1. Make sure your chatbot backend is running")
    print("2. Update the base_url and api_key variables")
    print("3. Run: python test_chatbot_responses.py")

if __name__ == "__main__":
    test_chatbot_responses()
