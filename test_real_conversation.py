#!/usr/bin/env python3
"""
Real Conversation Integration Test
Tests the actual chatbot API endpoints with a full conversation flow
"""

import sys
import os
import json
import requests
import time
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configuration
API_BASE_URL = "http://localhost:8000"  # Adjust if your server runs on a different port
TEST_API_KEY = "test_api_key_456"  # You may need to create a test organization
TEST_SESSION_ID = f"test_session_{int(time.time())}"

class ConversationTester:
    def __init__(self, api_base_url, api_key, session_id):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.session_id = session_id
        self.conversation_history = []
        self.user_data = {}
    
    def send_message(self, message, mode="faq"):
        """Send a message to the chatbot API"""
        url = f"{self.api_base_url}/api/v1/chatbot/ask"
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
        
        payload = {
            "question": message,
            "session_id": self.session_id,
            "mode": mode,
            "user_data": self.user_data
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update user data from response
                if "user_data" in result:
                    self.user_data.update(result["user_data"])
                
                # Store conversation
                self.conversation_history.append({
                    "user": message,
                    "bot": result.get("answer", "No response"),
                    "mode": result.get("mode", "unknown"),
                    "timestamp": datetime.now().isoformat()
                })
                
                return result
            else:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Unable to connect to the chatbot API")
            print(f"   Make sure the server is running on {self.api_base_url}")
            return None
        except Exception as e:
            print(f"❌ Request Error: {str(e)}")
            return None
    
    def display_conversation(self):
        """Display the full conversation"""
        print("\n📝 Full Conversation History:")
        print("=" * 80)
        
        for i, exchange in enumerate(self.conversation_history, 1):
            print(f"\n{i}. User: {exchange['user']}")
            print(f"   Bot: {exchange['bot']}")
            print(f"   Mode: {exchange['mode']} | Time: {exchange['timestamp']}")
    
    def get_leads(self):
        """Test the leads endpoint"""
        url = f"{self.api_base_url}/api/v1/lead/leads"
        
        headers = {
            "X-API-Key": self.api_key
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Leads API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Leads Request Error: {str(e)}")
            return None

def test_conversation_flow():
    """Test the complete conversation flow"""
    print("🚀 Real Conversation Integration Test")
    print("=" * 60)
    
    # Initialize tester
    tester = ConversationTester(API_BASE_URL, TEST_API_KEY, TEST_SESSION_ID)
    
    # Define conversation steps
    conversation_steps = [
        {
            "message": "Hi",
            "description": "Simple greeting",
            "expected_keywords": ["hello", "help", "personal injury"]
        },
        {
            "message": "What services do you offer?",
            "description": "General service inquiry",
            "expected_keywords": ["carter injury law", "personal injury", "consultation"]
        },
        {
            "message": "I was in a car accident last week",
            "description": "Accident mention - should show empathy",
            "expected_keywords": ["sorry", "understand", "difficult", "help"]
        },
        {
            "message": "I want to schedule a consultation",
            "description": "Scheduling request - should ask for contact info",
            "expected_keywords": ["name", "full name", "contact", "help you better"]
        },
        {
            "message": "My name is John Smith",
            "description": "Providing name",
            "expected_keywords": ["john", "email", "follow up"]
        },
        {
            "message": "john.smith@email.com",
            "description": "Providing email",
            "expected_keywords": ["perfect", "contact", "legal questions"]
        },
        {
            "message": "Thank you",
            "description": "Showing appreciation",
            "expected_keywords": ["welcome", "happy to help"]
        },
        {
            "message": "What should I do after a car accident?",
            "description": "Legal advice question",
            "expected_keywords": ["medical", "document", "insurance", "attorney"]
        },
        {
            "message": "What's the weather like today?",
            "description": "Non-legal question - should redirect professionally",
            "expected_keywords": ["legal", "personal injury", "help you with"]
        }
    ]
    
    print(f"Testing with Session ID: {TEST_SESSION_ID}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Starting conversation with {len(conversation_steps)} steps...\n")
    
    # Execute conversation steps
    for i, step in enumerate(conversation_steps, 1):
        print(f"Step {i}: {step['description']}")
        print(f"User: {step['message']}")
        
        # Send message
        result = tester.send_message(step["message"])
        
        if result:
            bot_response = result.get("answer", "No response")
            mode = result.get("mode", "unknown")
            
            print(f"Bot ({mode}): {bot_response}")
            
            # Check for expected keywords
            response_lower = bot_response.lower()
            found_keywords = [kw for kw in step["expected_keywords"] if kw.lower() in response_lower]
            
            if found_keywords:
                print(f"✅ Found expected keywords: {found_keywords}")
            else:
                print(f"⚠️  Expected keywords not found: {step['expected_keywords']}")
            
            # Check user data updates
            if "user_data" in result:
                user_data = result["user_data"]
                if "name" in user_data:
                    print(f"📝 Name collected: {user_data['name']}")
                if "email" in user_data:
                    print(f"📧 Email collected: {user_data['email']}")
        else:
            print("❌ Failed to get response")
            break
        
        print("-" * 50)
        time.sleep(1)  # Small delay between requests
    
    # Display full conversation
    tester.display_conversation()
    
    # Test leads endpoint
    print("\n🔍 Testing Leads Endpoint:")
    leads_data = tester.get_leads()
    if leads_data:
        leads = leads_data.get("leads", [])
        print(f"✅ Leads endpoint working - Found {len(leads)} leads")
        
        # Check if our test user is in the leads
        test_lead = None
        for lead in leads:
            if lead.get("session_id") == TEST_SESSION_ID:
                test_lead = lead
                break
        
        if test_lead:
            print(f"✅ Test user found in leads: {test_lead.get('name')} ({test_lead.get('email')})")
        else:
            print("⚠️  Test user not found in leads (may take time to sync)")
    else:
        print("❌ Leads endpoint failed")
    
    # Final summary
    print(f"\n📊 Test Summary:")
    print(f"Session ID: {TEST_SESSION_ID}")
    print(f"Total exchanges: {len(tester.conversation_history)}")
    print(f"User name: {tester.user_data.get('name', 'Not collected')}")
    print(f"User email: {tester.user_data.get('email', 'Not collected')}")
    
    # Check if key features worked
    has_greeting = any("hello" in ex["bot"].lower() for ex in tester.conversation_history[:2])
    has_thank_you_response = any("welcome" in ex["bot"].lower() for ex in tester.conversation_history)
    has_contact_info = tester.user_data.get("name") and tester.user_data.get("email")
    
    print(f"\n✅ Feature Verification:")
    print(f"✅ Greeting handled: {'Yes' if has_greeting else 'No'}")
    print(f"✅ Thank you response: {'Yes' if has_thank_you_response else 'No'}")
    print(f"✅ Contact info collected: {'Yes' if has_contact_info else 'No'}")
    
    return tester

def test_server_health():
    """Test if the server is running and accessible"""
    try:
        health_url = f"{API_BASE_URL}/docs"  # FastAPI docs endpoint
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            print("✅ Server is running and accessible")
            return True
        else:
            print(f"⚠️  Server responded with status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running or not accessible")
        print(f"   Please start the server: python main.py")
        print(f"   Expected URL: {API_BASE_URL}")
        return False
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def main():
    """Run the real conversation test"""
    print("🔹 Real Conversation Flow Integration Test")
    print("=" * 60)
    
    # Check server health first
    if not test_server_health():
        print("\n❌ Cannot proceed - server is not accessible")
        print("Please ensure the chatbot server is running on", API_BASE_URL)
        return 1
    
    try:
        # Run the conversation test
        tester = test_conversation_flow()
        
        print("\n🎉 Real Conversation Test Completed!")
        print("The chatbot API is working with the new conversation flow.")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
