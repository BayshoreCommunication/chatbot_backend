import sys
sys.path.insert(0, '.')

print("=" * 60)
print("Checking SERVICES_AVAILABLE status...")
print("=" * 60)

try:
    # Import exactly what chatbot.py imports
    from services.langchain.engine import ask_bot, add_document, escalate_to_human
    print("✅ ask_bot imported successfully")
    SERVICES_AVAILABLE = True
except Exception as e:
    print(f"❌ Import failed: {e}")
    SERVICES_AVAILABLE = False
    import traceback
    traceback.print_exc()

print(f"\nSERVICES_AVAILABLE = {SERVICES_AVAILABLE}")
print("=" * 60)

