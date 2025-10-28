#!/usr/bin/env python3
"""
Quick diagnostic to check if production server is working
Run this ON YOUR PRODUCTION SERVER after updating packages
"""

import sys

print("=" * 70)
print("PRODUCTION SERVER DIAGNOSTIC")
print("=" * 70)

# Check 1: Python version
print("\n✓ Check 1: Python Version")
print(f"  Python: {sys.version}")
if sys.version_info < (3, 9):
    print("  ⚠️  WARNING: Python 3.9+ recommended")

# Check 2: Langchain packages
print("\n✓ Check 2: Langchain Packages")
try:
    import langchain
    print(f"  ✅ langchain: {langchain.__version__}")
    
    import langchain_core
    print(f"  ✅ langchain-core: {langchain_core.__version__}")
    
    import langchain_openai
    print(f"  ✅ langchain-openai: installed")
    
    import langchain_community  
    print(f"  ✅ langchain-community: installed")
    
except ImportError as e:
    print(f"  ❌ MISSING PACKAGE: {e}")
    print("  Run: pip install --upgrade -r requirements.txt")
    sys.exit(1)

# Check 3: New imports
print("\n✓ Check 3: New Langchain Imports")
try:
    from langchain.chains.combine_documents import create_stuff_documents_chain
    print(f"  ✅ create_stuff_documents_chain available")
    
    from langchain_core.prompts import ChatPromptTemplate
    print(f"  ✅ ChatPromptTemplate available")
    
except ImportError as e:
    print(f"  ❌ IMPORT FAILED: {e}")
    print("  Your langchain version is too old!")
    print("  Run: pip install --upgrade langchain>=0.3.18 langchain-core>=0.3.33")
    sys.exit(1)

# Check 4: ask_bot import
print("\n✓ Check 4: Engine Import (ask_bot)")
try:
    from services.langchain.engine import ask_bot, add_document, escalate_to_human
    print(f"  ✅ ask_bot: {type(ask_bot).__name__}")
    print(f"  ✅ add_document: {type(add_document).__name__}")
    print(f"  ✅ escalate_to_human: {type(escalate_to_human).__name__}")
    
except Exception as e:
    print(f"  ❌ ENGINE IMPORT FAILED: {e}")
    print("\n  Full error:")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Check 5: Database connection
print("\n✓ Check 5: Database Connection")
try:
    from services.database import db, client
    if client is not None:
        client.admin.command('ping')
        print(f"  ✅ MongoDB connected")
    else:
        print(f"  ⚠️  MongoDB offline (degraded mode)")
except Exception as e:
    print(f"  ⚠️  MongoDB error: {e}")
    print(f"  (App may still work with cached/FAQ responses)")

# Check 6: SERVICES_AVAILABLE
print("\n✓ Check 6: Chatbot Routes")
try:
    from routes.chatbot import SERVICES_AVAILABLE
    if SERVICES_AVAILABLE:
        print(f"  ✅ SERVICES_AVAILABLE: True")
    else:
        print(f"  ❌ SERVICES_AVAILABLE: False")
        print(f"  This is why your API returns 500 error!")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ Cannot check: {e}")

print("\n" + "=" * 70)
print("✅ ALL CHECKS PASSED!")
print("=" * 70)
print("\nYour production server should be working now.")
print("Restart your application and test the API.")

