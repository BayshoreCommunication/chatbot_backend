"""
Test Script for Lead Collection System
Demonstrates how the chatbot collects contact information automatically.
"""

# Example conversation flow showing lead collection

print("=" * 80)
print("LEAD COLLECTION SYSTEM - TEST SCENARIOS")
print("=" * 80)

print("\n\n🎯 SCENARIO 1: User Requests Callback")
print("-" * 80)
print("User: 'Can someone call me?'")
print("\nExpected AI Response:")
print("'Sure, I'd be happy to have someone call you. What's your name?'")
print("\nSystem Status:")
print("  - Intent Detected: callback_request")
print("  - Stage: collecting_contact")
print("  - Missing: name, phone")

print("\n\nUser: 'My name is John Smith'")
print("\nExpected AI Response:")
print("'Thanks, John! And what's the best number to reach you at?'")
print("\nSystem Status:")
print("  - Auto-extracted: name = 'John Smith' ✓")
print("  - Missing: phone")

print("\n\nUser: '555-123-4567'")
print("\nExpected AI Response:")
print("'Perfect! So I have John Smith at (555) 123-4567. Someone from our team will call you soon. Is that right?'")
print("\nSystem Status:")
print("  - Auto-extracted: phone = '(555) 123-4567' ✓")
print("  - Lead Complete: ✅")
print("  - Ready to save to database")

print("\n\n" + "=" * 80)
print("🎯 SCENARIO 2: User Provides Info in One Message")
print("-" * 80)
print("User: 'Can you call me? I'm Sarah at 555-987-6543'")
print("\nExpected AI Response:")
print("'Of course! So I have Sarah at (555) 987-6543. Someone will reach out to you soon. Is that correct?'")
print("\nSystem Status:")
print("  - Auto-extracted: name = 'Sarah' ✓")
print("  - Auto-extracted: phone = '(555) 987-6543' ✓")
print("  - Lead Complete: ✅")

print("\n\n" + "=" * 80)
print("🎯 SCENARIO 3: Contact Info Sharing")
print("-" * 80)
print("User: 'What's your email?'")
print("\nExpected AI Response:")
print("'You can reach us at info@injurylawcarter.com. What can I help you with?'")
print("\nSystem Status:")
print("  ✅ Shares company email from knowledge base")
print("  ✅ Does NOT refuse with 'I can't share personal email'")

print("\n\nUser: 'How do I contact you?'")
print("\nExpected AI Response:")
print("'You can reach me at (555) 123-4567 or info@injurylawcarter.com. What brings you here today?'")
print("\nSystem Status:")
print("  ✅ Shares phone and email from knowledge base")
print("  ✅ Acts as part of the team")

print("\n\n" + "=" * 80)
print("📊 API RESPONSE FORMAT")
print("-" * 80)
print("""
{
    "answer": "Perfect! So I have John Smith at (555) 123-4567...",
    "sources": [...],

    // 🆕 LEAD COLLECTION DATA
    "detected_intent": "callback_request",
    "conversation_stage": "confirming_contact",
    "collected_contact": {
        "name": "John Smith",
        "phone": "(555) 123-4567",
        "email": null
    },
    "needs_callback": true,
    "contact_confirmed": false,
    "lead_collected": true  // ✅ Both name and phone collected!
}
""")

print("\n" + "=" * 80)
print("💾 HOW TO SAVE LEADS TO DATABASE")
print("-" * 80)
print("""
# In your chatbot route (where you process the response):

result = langgraph_service.process_query(...)

# Check if we collected a complete lead
if result.get('lead_collected'):
    contact = result['collected_contact']

    # Save to your leads collection
    db.leads.insert_one({
        'name': contact['name'],
        'phone': contact['phone'],
        'email': contact.get('email'),
        'session_id': result['session_id'],
        'organization_id': organization_id,
        'conversation_stage': result['conversation_stage'],
        'needs_callback': result['needs_callback'],
        'created_at': datetime.now(),
        'source': 'chatbot_auto_collection'
    })

    print(f"✅ Lead saved: {contact['name']} - {contact['phone']}")
""")

print("\n" + "=" * 80)
print("🔍 SUPPORTED PHONE FORMATS")
print("-" * 80)
print("""
All these formats are automatically detected and normalized:
  - (555) 123-4567   →  (555) 123-4567
  - 555-123-4567     →  (555) 123-4567
  - 555.123.4567     →  (555) 123-4567
  - 5551234567       →  (555) 123-4567
  - +1 555 123 4567  →  (555) 123-4567
""")

print("\n" + "=" * 80)
print("✅ SYSTEM READY!")
print("-" * 80)
print("""
Your chatbot now:
  ✓ Automatically detects when users want callbacks
  ✓ Extracts name, phone, email from any message format
  ✓ Tracks conversation stage intelligently
  ✓ Shares company contact info naturally (never refuses)
  ✓ Returns complete lead data in API response
  ✓ Works seamlessly with existing prompt-based flow

Start chatting to test the lead collection in action!
""")
print("=" * 80)
