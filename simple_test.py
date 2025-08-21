#!/usr/bin/env python3
"""
Simple test script for chatbot responses without Unicode characters
"""

import requests
import json
import time

def test_chatbot():
    """Test the chatbot with the specific Q&A scenarios"""
    
    # Configuration
    base_url = "http://localhost:8000"
    api_key = "test_api_key"  # Update with your actual API key
    
    # Test questions and expected responses
    test_cases = [
        ("Do you handle personal injury cases?", "Yes, we handle personal injury cases"),
        ("Do you take car accident cases?", "Absolutely, we work with clients involved in car accidents"),
        ("How much do you charge?", "Many of our cases are handled on a contingency fee basis"),
        ("Do you offer free consultations?", "Yes, we offer free initial consultations"),
        ("How long will my case take?", "The timeline depends on the type of case"),
        ("What should I do right now?", "The best next step is to schedule a free consultation")
    ]
    
    print("Testing Chatbot Responses")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("Server is running")
        else:
            print("Server responded but not healthy")
            return
    except:
        print("Server is not running. Please start the server first:")
        print("python main.py")
        return
    
    # Test each question
    passed = 0
    total = len(test_cases)
    
    for i, (question, expected_pattern) in enumerate(test_cases):
        print(f"\nTest {i+1}: {question}")
        print("-" * 40)
        
        try:
            payload = {
                "question": question,
                "session_id": f"test_session_{i}",
                "mode": "faq",
                "user_data": {},
                "available_slots": []
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": api_key
            }
            
            response = requests.post(
                f"{base_url}/api/chatbot/ask",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                
                print(f"Response: {answer}")
                
                if expected_pattern.lower() in answer.lower():
                    print("PASS - Response matches expected pattern")
                    passed += 1
                else:
                    print("FAIL - Response doesn't match expected pattern")
                    print(f"Expected: {expected_pattern}")
                
            else:
                print(f"FAIL - HTTP {response.status_code}")
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"FAIL - Error: {str(e)}")
        
        time.sleep(1)  # Small delay between tests
    
    # Results
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("All tests passed! Your chatbot is working correctly.")
    else:
        print("Some tests failed. Check the responses above.")

if __name__ == "__main__":
    test_chatbot()
