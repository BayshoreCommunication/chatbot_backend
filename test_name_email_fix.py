#!/usr/bin/env python3
"""
Test script to verify the name and email collection fix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.conversation_flow import (
    extract_name_from_text, extract_email_from_text, 
    should_collect_contact_info, get_natural_contact_prompt
)

def test_name_email_fix():
    """Test the fix for name and email collection"""
    
    print("=== Testing Name and Email Collection Fix ===\n")
    
    # Test 1: Name extraction
    print("1. Testing name extraction:")
    test_cases = [
        ("Sahak", "Should extract 'Sahak' as name"),
        ("John Smith", "Should extract 'John Smith' as name"),
        ("arsahak@gmail.com", "Should NOT extract email as name"),
        ("john.doe@example.com", "Should NOT extract email as name"),
        ("skip", "Should detect refusal"),
        ("no thanks", "Should detect refusal"),
    ]
    
    for text, description in test_cases:
        name, is_refusal = extract_name_from_text(text)
        print(f"   Input: '{text}' - {description}")
        print(f"   Result: name='{name}', is_refusal={is_refusal}")
        print()
    
    # Test 2: Email extraction
    print("2. Testing email extraction:")
    email_test_cases = [
        ("arsahak@gmail.com", "Should extract email"),
        ("john.doe@example.com", "Should extract email"),
        ("not an email", "Should NOT extract"),
        ("skip", "Should detect refusal"),
    ]
    
    for text, description in email_test_cases:
        email, is_refusal = extract_email_from_text(text)
        print(f"   Input: '{text}' - {description}")
        print(f"   Result: email='{email}', is_refusal={is_refusal}")
        print()
    
    # Test 3: Simulate the user's conversation flow
    print("3. Simulating user's conversation flow:")
    conversation_history = [
        {"role": "assistant", "content": "I'd love to personalize our conversation better. What's your first name?"},
        {"role": "user", "content": "Sahak"},
        {"role": "assistant", "content": "Please provide a valid email address so I can better assist you. (or type 'skip' if you prefer not to share)"},
        {"role": "user", "content": "arsahak@gmail.com"}
    ]
    
    user_data = {}
    
    # Step 1: Process name
    print("   Step 1: Processing 'Sahak' as name...")
    name, is_refusal = extract_name_from_text("Sahak")
    if name:
        user_data["name"] = name
        print(f"   ✓ Name stored: {name}")
    else:
        print(f"   ✗ Name extraction failed: {name}")
    print()
    
    # Step 2: Process email
    print("   Step 2: Processing 'arsahak@gmail.com' as email...")
    email, is_refusal = extract_email_from_text("arsahak@gmail.com")
    if email:
        user_data["email"] = email
        print(f"   ✓ Email stored: {email}")
    else:
        print(f"   ✗ Email extraction failed: {email}")
    print()
    
    # Step 3: Check final state
    print("   Step 3: Final user data state:")
    print(f"   Name: {user_data.get('name', 'Not set')}")
    print(f"   Email: {user_data.get('email', 'Not set')}")
    print()
    
    # Test 4: Verify the fix prevents the original issue
    print("4. Verifying the fix prevents the original issue:")
    print("   Original issue: Email was treated as name")
    print("   Fix: Email addresses are now properly excluded from name extraction")
    
    # Test that email is NOT extracted as name
    name_from_email, _ = extract_name_from_text("arsahak@gmail.com")
    if name_from_email is None:
        print("   ✓ Email is correctly NOT extracted as name")
    else:
        print(f"   ✗ Email is still being extracted as name: {name_from_email}")
    
    # Test that name is still extracted correctly
    name_from_name, _ = extract_name_from_text("Sahak")
    if name_from_name == "Sahak":
        print("   ✓ Name is still extracted correctly")
    else:
        print(f"   ✗ Name extraction broken: {name_from_name}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_name_email_fix()
