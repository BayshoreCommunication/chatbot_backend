#!/usr/bin/env python3
"""
Test script to check API endpoints
"""

import requests
import json

# Test configuration
BASE_URL = "http://localhost:8000"
API_KEY = "test_key_123"  # This will be invalid, but let's see the response

def test_endpoints():
    """Test the main endpoints that the frontend uses"""
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    endpoints = [
        "/api/faq/list",
        "/api/instant-reply", 
        "/api/chatbot/upload_history"
    ]
    
    print("Testing API endpoints...")
    print("=" * 50)
    
    for endpoint in endpoints:
        try:
            print(f"\nTesting: {endpoint}")
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
            if response.status_code == 401:
                print("✅ Endpoint is working but requires valid API key")
            elif response.status_code == 200:
                print("✅ Endpoint is working!")
            else:
                print(f"❌ Endpoint returned status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection error - server not running")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_endpoints()
