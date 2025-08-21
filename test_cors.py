"""
CORS Test Script for Chatbot Backend

This script tests if the server is properly configured to allow requests from any origin.
It sends a request with a custom origin header and checks if the response includes the
correct CORS headers.

Usage:
    python test_cors.py

Requirements:
    - requests library (pip install requests)
    - The backend server must be running
"""

import requests
import sys
import os
from urllib.parse import urljoin

# Default server URL
SERVER_URL = "http://localhost:8000"

def test_cors(server_url=SERVER_URL):
    """Test CORS configuration by sending a request with a custom origin."""
    # Test endpoint - health check is a good simple endpoint to test
    endpoint = "/health"
    url = urljoin(server_url, endpoint)
    
    # Custom origin that wouldn't normally be allowed
    test_origin = "https://example-test-domain.com"
    
    # Headers with custom origin
    headers = {
        "Origin": test_origin
    }
    
    try:
        # Send OPTIONS request (preflight)
        print(f"Sending OPTIONS request to {url} with origin: {test_origin}")
        options_response = requests.options(url, headers=headers)
        
        # Send GET request
        print(f"Sending GET request to {url} with origin: {test_origin}")
        get_response = requests.get(url, headers=headers)
        
        # Check preflight response headers
        print("\n--- OPTIONS (Preflight) Response ---")
        check_cors_headers(options_response, test_origin)
        
        # Check actual response headers
        print("\n--- GET Response ---")
        check_cors_headers(get_response, test_origin)
        
        # Check if the request was successful
        if get_response.status_code == 200:
            print(f"\n✅ Request successful! Status code: {get_response.status_code}")
            print(f"Response: {get_response.json()}")
        else:
            print(f"\n❌ Request failed with status code: {get_response.status_code}")
            print(f"Response: {get_response.text}")
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Connection error: Could not connect to {server_url}")
        print("Make sure the server is running.")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False
    
    return True

def check_cors_headers(response, expected_origin):
    """Check if the response contains the expected CORS headers."""
    cors_headers = {
        "Access-Control-Allow-Origin": expected_origin,
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Credentials": "true"
    }
    
    all_headers_present = True
    print("CORS Headers Check:")
    
    for header, expected_value in cors_headers.items():
        if header in response.headers:
            actual_value = response.headers[header]
            if header == "Access-Control-Allow-Origin" and (actual_value == "*" or actual_value == expected_origin):
                print(f"  ✅ {header}: {actual_value}")
            elif header != "Access-Control-Allow-Origin" and actual_value:
                print(f"  ✅ {header}: {actual_value}")
            else:
                print(f"  ❌ {header}: {actual_value} (Expected: {expected_value})")
                all_headers_present = False
        else:
            print(f"  ❌ {header}: Missing")
            all_headers_present = False
    
    if all_headers_present:
        print("\n✅ All required CORS headers are present!")
    else:
        print("\n❌ Some CORS headers are missing or incorrect.")

if __name__ == "__main__":
    # Allow custom server URL as command line argument
    if len(sys.argv) > 1:
        SERVER_URL = sys.argv[1]
    
    print(f"Testing CORS configuration for server: {SERVER_URL}")
    test_cors(SERVER_URL)
