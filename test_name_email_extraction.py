#!/usr/bin/env python3
"""
Test script for name and email extraction functions
"""

from services.conversation_flow import extract_name_from_text, extract_email_from_text

def test_name_extraction():
    """Test name extraction with various inputs"""
    test_cases = [
        ("Hello this is sahak from texas", "sahak"),
        ("My name is John Smith", "John Smith"),
        ("I am Alice Johnson", "Alice Johnson"),
        ("This is David speaking", "David"),
        ("Call me Mike", "Mike"),
        ("I don't want to share my name", None),  # Should be refused
        ("skip", None),  # Should be refused
        ("hello there", None),  # No name found
        ("Hi, I'm Sarah from California", "Sarah"),
    ]
    
    print("🧪 Testing Name Extraction:")
    print("=" * 50)
    
    for text, expected in test_cases:
        extracted_name, is_refusal = extract_name_from_text(text)
        status = "✅ PASS" if extracted_name == expected else "❌ FAIL"
        print(f"{status} Input: '{text}'")
        print(f"   Expected: {expected}, Got: {extracted_name}, Refused: {is_refusal}")
        print()

def test_email_extraction():
    """Test email extraction with various inputs"""
    test_cases = [
        ("My email is arsshak@gmail.com", "arsshak@gmail.com"),
        ("arsshak@gmail.com", "arsshak@gmail.com"),
        ("Contact me at john@example.com", "john@example.com"),
        ("I don't want to share my email", None),  # Should be refused
        ("skip", None),  # Should be refused
        ("hello there", None),  # No email found
        ("My email address is test@domain.org", "test@domain.org"),
    ]
    
    print("🧪 Testing Email Extraction:")
    print("=" * 50)
    
    for text, expected in test_cases:
        extracted_email, is_refusal = extract_email_from_text(text)
        status = "✅ PASS" if extracted_email == expected else "❌ FAIL"
        print(f"{status} Input: '{text}'")
        print(f"   Expected: {expected}, Got: {extracted_email}, Refused: {is_refusal}")
        print()

if __name__ == "__main__":
    test_name_extraction()
    test_email_extraction()
    print("🎉 Testing complete!")
