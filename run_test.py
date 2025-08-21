#!/usr/bin/env python3
"""
Comprehensive test runner for chatbot responses
This script will:
1. Add the test FAQs to the database
2. Start the backend server
3. Test the responses
"""

import subprocess
import time
import sys
import os
import requests
import json

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {str(e)}")
        return False

def test_single_response(base_url, api_key, question, expected_pattern):
    """Test a single question and verify the response"""
    try:
        payload = {
            "question": question,
            "session_id": f"test_session_{hash(question)}",
            "mode": "faq",
            "user_data": {},
            "available_slots": []
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }
        
        response = requests.post(
            f"{base_url}/ask",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")
            
            if expected_pattern.lower() in answer.lower():
                print(f"✅ '{question}' → Response matches pattern")
                return True
            else:
                print(f"⚠️  '{question}' → Response doesn't match pattern")
                print(f"   Expected: {expected_pattern}")
                print(f"   Got: {answer[:100]}...")
                return False
        else:
            print(f"❌ '{question}' → HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ '{question}' → Error: {str(e)}")
        return False

def main():
    """Main test runner"""
    print("🚀 Starting Comprehensive Chatbot Test")
    print("=" * 60)
    
    # Configuration
    base_url = "http://localhost:8000"
    api_key = "test_api_key"  # Update with your actual API key
    
    # Test questions and expected patterns
    test_cases = [
        ("Do you handle personal injury cases?", "Yes, we handle personal injury cases"),
        ("Do you take car accident cases?", "Absolutely, we work with clients involved in car accidents"),
        ("How much do you charge?", "Many of our cases are handled on a contingency fee basis"),
        ("Do you offer free consultations?", "Yes, we offer free initial consultations"),
        ("How long will my case take?", "The timeline depends on the type of case"),
        ("What should I do right now?", "The best next step is to schedule a free consultation")
    ]
    
    # Step 1: Add test FAQs
    print("\n📝 Step 1: Adding test FAQs to database")
    if not run_command("python add_test_faqs.py", "Adding test FAQs"):
        print("❌ Failed to add test FAQs. Exiting.")
        return
    
    # Step 2: Check if server is running
    print("\n🔍 Step 2: Checking if server is running")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is already running")
        else:
            print("⚠️  Server responded but not healthy")
    except:
        print("❌ Server is not running. Please start the server first:")
        print("   python main.py")
        return
    
    # Step 3: Test responses
    print("\n🧪 Step 3: Testing chatbot responses")
    print("-" * 40)
    
    passed_tests = 0
    total_tests = len(test_cases)
    
    for question, expected_pattern in test_cases:
        if test_single_response(base_url, api_key, question, expected_pattern):
            passed_tests += 1
        time.sleep(1)  # Small delay between tests
    
    # Results
    print("\n" + "=" * 60)
    print("📊 Test Results")
    print(f"Passed: {passed_tests}/{total_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Your chatbot is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the responses above.")
    
    print("\n💡 Next steps:")
    print("1. Test with your actual API key")
    print("2. Test with your actual organization ID")
    print("3. Test the chatbot widget integration")

if __name__ == "__main__":
    main()
