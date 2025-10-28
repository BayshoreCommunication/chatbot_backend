#!/usr/bin/env python3
import sys
import os

# Set the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("TESTING IMPORT")
print("=" * 70)

print("\n1. Testing imports that chatbot.py does...")

try:
    print("   Importing ask_bot...")
    from services.langchain.engine import ask_bot, add_document, escalate_to_human
    print("   ✅ SUCCESS!")
    print(f"   ask_bot type: {type(ask_bot)}")
    
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    print("\n   Full error:")
    import traceback
    traceback.print_exc()
    
print("\n" + "=" * 70)

