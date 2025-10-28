#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing import...")
try:
    from services.langchain.engine import ask_bot
    print("✅ SUCCESS - ask_bot imported!")
    print(f"Type: {type(ask_bot)}")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()

