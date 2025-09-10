#!/usr/bin/env python3
"""
Manual Conversation Test
Interactive test to manually verify conversation flow
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def manual_conversation_test():
    """Interactive manual test of conversation features"""
    print("🔹 Manual Conversation Flow Test")
    print("=" * 60)
    print("This will test the conversation flow functions interactively.")
    print("Press Enter after each test to continue...\n")
    
    from services.conversation_flow import (
        get_enhanced_greeting,
        get_conversation_progression_response,
        should_collect_contact_info,
        get_natural_contact_prompt,
        process_user_message_for_info,
        extract_name_from_text,
        extract_email_from_text
    )
    
    # Test 1: Greeting
    print("TEST 1: Greeting Handling")
    print("-" * 30)
    
    user_data = {"conversation_history": []}
    
    greetings = ["Hi", "Hello", "Good morning", "Hey there"]
    for greeting in greetings:
        response = get_enhanced_greeting(greeting, 0, user_data)
        print(f"User: {greeting}")
        print(f"Bot: {response if response else '[No specific greeting response]'}")
        print()
    
    input("Press Enter to continue to Test 2...")
    
    # Test 2: Thank You Responses
    print("\nTEST 2: Thank You Responses")
    print("-" * 30)
    
    thank_you_messages = ["Thank you", "Thanks", "I appreciate it", "That's helpful"]
    for message in thank_you_messages:
        response = get_conversation_progression_response(message, [], {})
        print(f"User: {message}")
        print(f"Bot: {response if response else '[No specific response]'}")
        print()
    
    input("Press Enter to continue to Test 3...")
    
    # Test 3: Contact Collection Logic
    print("\nTEST 3: Contact Collection Logic")
    print("-" * 30)
    
    test_queries = [
        "I want to schedule an appointment",
        "Can I book a consultation?",
        "What are your services?",
        "I need help with my case"
    ]
    
    for query in test_queries:
        user_data = {}
        should_collect = should_collect_contact_info([], query, user_data)
        print(f"Query: {query}")
        print(f"Should collect contact info: {should_collect}")
        
        if should_collect:
            prompt = get_natural_contact_prompt(user_data, 5)
            print(f"Contact prompt: {prompt}")
        print()
    
    input("Press Enter to continue to Test 4...")
    
    # Test 4: Name Extraction
    print("\nTEST 4: Name Extraction")
    print("-" * 30)
    
    name_inputs = [
        "My name is John Smith",
        "I'm Sarah Johnson", 
        "Call me Mike",
        "This is Dr. Emily Brown",
        "I don't want to share my name"
    ]
    
    for name_input in name_inputs:
        try:
            extracted_name, is_refusal = extract_name_from_text(name_input)
            print(f"Input: {name_input}")
            if is_refusal:
                print("Result: User refused to share name")
            else:
                print(f"Extracted name: {extracted_name}")
            print()
        except Exception as e:
            print(f"Input: {name_input}")
            print(f"Error: {str(e)}")
            print()
    
    input("Press Enter to continue to Test 5...")
    
    # Test 5: Email Extraction
    print("\nTEST 5: Email Extraction")
    print("-" * 30)
    
    email_inputs = [
        "john@example.com",
        "My email is sarah.johnson@gmail.com",
        "Contact me at mike.brown@company.org",
        "I don't want to share my email",
        "No email here"
    ]
    
    for email_input in email_inputs:
        try:
            extracted_email, is_refusal = extract_email_from_text(email_input)
            print(f"Input: {email_input}")
            if is_refusal:
                print("Result: User refused to share email")
            else:
                print(f"Extracted email: {extracted_email}")
            print()
        except Exception as e:
            print(f"Input: {email_input}")
            print(f"Error: {str(e)}")
            print()
    
    input("Press Enter to continue to Test 6...")
    
    # Test 6: Complete Message Processing
    print("\nTEST 6: Complete Message Processing")
    print("-" * 30)
    
    user_data = {}
    
    messages = [
        "Hi, my name is John Smith",
        "My email is john@example.com",
        "Thank you for your help"
    ]
    
    for message in messages:
        print(f"Processing: {message}")
        user_data = process_user_message_for_info(message, user_data)
        print(f"Updated user data: {user_data}")
        
        # Check what response we should give
        if "name" in user_data and user_data["name"] not in ["Anonymous User", "Guest User"]:
            if "email" not in user_data or user_data["email"] in ["anonymous@user.com"]:
                response_type = "Ask for email"
            else:
                response_type = "Complete - have both name and email"
        else:
            response_type = "Ask for name"
        
        print(f"Next action: {response_type}")
        print()
    
    print("✅ Manual Test Complete!")
    print("\nSummary of Features Tested:")
    print("✅ Simple greeting responses")
    print("✅ Thank you message handling")
    print("✅ Smart contact collection logic")
    print("✅ Name extraction from text")
    print("✅ Email extraction from text")
    print("✅ Complete message processing flow")

def interactive_conversation():
    """Interactive conversation simulator"""
    print("\n🗣️  Interactive Conversation Simulator")
    print("=" * 60)
    print("Type messages to test the conversation flow.")
    print("Type 'quit' to exit.\n")
    
    from services.conversation_flow import (
        get_enhanced_greeting,
        get_conversation_progression_response,
        should_collect_contact_info,
        get_natural_contact_prompt,
        process_user_message_for_info
    )
    
    user_data = {"conversation_history": []}
    conversation_count = 0
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        
        if not user_input:
            continue
        
        conversation_count += 1
        
        # Add user message to history
        user_data["conversation_history"].append({
            "role": "user",
            "content": user_input
        })
        
        # Process for name/email extraction
        user_data = process_user_message_for_info(user_input, user_data)
        
        # Check for greeting
        greeting_response = get_enhanced_greeting(user_input, conversation_count, user_data)
        if greeting_response:
            print(f"Bot: {greeting_response}")
            user_data["conversation_history"].append({"role": "assistant", "content": greeting_response})
            continue
        
        # Check for thank you
        thank_you_response = get_conversation_progression_response(user_input, user_data["conversation_history"], user_data)
        if thank_you_response:
            print(f"Bot: {thank_you_response}")
            user_data["conversation_history"].append({"role": "assistant", "content": thank_you_response})
            continue
        
        # Check if should collect contact info
        should_collect = should_collect_contact_info(user_data["conversation_history"], user_input, user_data)
        if should_collect:
            prompt = get_natural_contact_prompt(user_data, conversation_count)
            print(f"Bot: {prompt}")
            user_data["conversation_history"].append({"role": "assistant", "content": prompt})
            continue
        
        # Default response
        has_name = user_data.get("name") and user_data.get("name") not in ["Anonymous User", "Guest User"]
        has_email = user_data.get("email") and user_data.get("email") not in ["anonymous@user.com"]
        
        if has_name and has_email:
            response = f"Thank you, {user_data['name']}. How can I help you with your legal questions today?"
        else:
            response = "Thank you for your message. How can I assist you with your personal injury legal needs?"
        
        print(f"Bot: {response}")
        user_data["conversation_history"].append({"role": "assistant", "content": response})
        
        # Show current user data
        if user_data.get("name") or user_data.get("email"):
            print(f"[Info: Name: {user_data.get('name', 'None')}, Email: {user_data.get('email', 'None')}]")
    
    print("\nConversation ended. Final user data:")
    print(f"Name: {user_data.get('name', 'Not collected')}")
    print(f"Email: {user_data.get('email', 'Not collected')}")
    print(f"Total exchanges: {len(user_data['conversation_history']) // 2}")

def main():
    """Main test menu"""
    print("🔹 Conversation Flow Test Suite")
    print("=" * 60)
    print("Choose a test option:")
    print("1. Manual function tests")
    print("2. Interactive conversation simulator")
    print("3. Both")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        manual_conversation_test()
    elif choice == "2":
        interactive_conversation()
    elif choice == "3":
        manual_conversation_test()
        interactive_conversation()
    else:
        print("Invalid choice. Running manual tests...")
        manual_conversation_test()
    
    print("\n🎉 Testing complete!")

if __name__ == "__main__":
    main()
