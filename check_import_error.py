#!/usr/bin/env python3
"""Check what error happens during import"""
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("CHECKING IMPORT ERROR")
print("=" * 70)

print("\n1. Simulating chatbot.py import exactly as it does...")

try:
    from services.langchain.engine import ask_bot, add_document, escalate_to_human
    from services.language_detect import detect_language
    from services.database import (
        get_organization_by_api_key, create_or_update_visitor, add_conversation_message, 
        get_visitor, get_conversation_history, save_user_profile, get_user_profile, db,
        set_agent_mode, set_bot_mode, is_chat_in_agent_mode, create_lead, get_leads_by_organization
    )
    from services.auth import (
        create_user, get_user_by_email, get_user_by_id, update_user
    )
    from services.faq_matcher import find_matching_faq, get_suggested_faqs
    from services.langchain.user_management import handle_name_collection, handle_email_collection
    
    print("✅ ALL IMPORTS SUCCESSFUL!")
    print("SERVICES_AVAILABLE would be: True")
    
except Exception as e:
    print(f"❌ IMPORT FAILED!")
    print(f"Error: {str(e)}")
    print(f"Error type: {type(e).__name__}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("\nSERVICES_AVAILABLE would be: False")
    print("This is why you get the 500 error!")

print("\n" + "=" * 70)

