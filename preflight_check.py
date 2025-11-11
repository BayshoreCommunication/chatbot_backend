"""
Pre-flight check before starting Stripe webhook testing
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("🚀 Stripe Webhook Pre-flight Check")
print("=" * 60)
print()

all_good = True

# Check 1: Stripe Keys
print("1️⃣  Checking Stripe Configuration...")
stripe_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

if stripe_key and stripe_key.startswith("sk_test_"):
    print("   ✅ STRIPE_SECRET_KEY is set (Test mode)")
else:
    print("   ❌ STRIPE_SECRET_KEY is missing or invalid")
    all_good = False

if webhook_secret and webhook_secret.startswith("whsec_"):
    print(f"   ✅ STRIPE_WEBHOOK_SECRET is set: {webhook_secret[:15]}...")
    print(f"      ⚠️  If using Stripe CLI, update this with the secret from 'stripe listen'")
else:
    print("   ❌ STRIPE_WEBHOOK_SECRET is missing or invalid")
    all_good = False

print()

# Check 2: SMTP Configuration
print("2️⃣  Checking Email Configuration...")
smtp_mail = os.getenv("SMPT_MAIL")
smtp_password = os.getenv("SMPT_PASSWORD")

if smtp_mail:
    print(f"   ✅ SMTP_MAIL is set: {smtp_mail}")
else:
    print("   ❌ SMTP_MAIL is missing")
    all_good = False

if smtp_password and len(smtp_password) > 10:
    print(f"   ✅ SMTP_PASSWORD is set ({len(smtp_password)} chars)")
else:
    print("   ❌ SMTP_PASSWORD is missing or too short")
    all_good = False

print()

# Check 3: MongoDB Connection
print("3️⃣  Checking Database Connection...")
try:
    from services.database import db
    db.command('ping')
    print("   ✅ MongoDB connection successful")
    
    # Check user count
    user_count = db.users.count_documents({})
    print(f"   ✅ Found {user_count} users in database")
except Exception as e:
    print(f"   ❌ MongoDB connection failed: {e}")
    all_good = False

print()

# Check 4: Required modules
print("4️⃣  Checking Python Dependencies...")
required_modules = [
    ('fastapi', 'FastAPI framework'),
    ('stripe', 'Stripe SDK'),
    ('pymongo', 'MongoDB driver'),
    ('pydantic', 'Data validation'),
    ('python-dotenv', 'Environment variables')
]

for module, name in required_modules:
    try:
        __import__(module)
        print(f"   ✅ {name} installed")
    except ImportError:
        print(f"   ❌ {name} missing - install with: pip install {module}")
        all_good = False

print()

# Check 5: Stripe CLI
print("5️⃣  Checking Stripe CLI...")
import subprocess
try:
    result = subprocess.run(['stripe', '--version'], 
                          capture_output=True, 
                          text=True, 
                          timeout=5)
    if result.returncode == 0:
        print(f"   ✅ Stripe CLI installed: {result.stdout.strip()}")
    else:
        print("   ❌ Stripe CLI not found")
        print("      Download: https://github.com/stripe/stripe-cli/releases/latest")
        all_good = False
except FileNotFoundError:
    print("   ❌ Stripe CLI not found in PATH")
    print("      Download: https://github.com/stripe/stripe-cli/releases/latest")
    all_good = False
except Exception as e:
    print(f"   ⚠️  Could not verify Stripe CLI: {e}")

print()
print("=" * 60)

if all_good:
    print("✅ All checks passed! You're ready to test webhooks.")
    print()
    print("📋 Next Steps:")
    print("   1. Start backend: uvicorn main:app --reload --port 8000")
    print("   2. Start listener: stripe listen --forward-to http://localhost:8000/payment/webhook")
    print("   3. Copy webhook secret and update .env")
    print("   4. Restart backend")
    print("   5. Test: stripe trigger checkout.session.completed")
    print()
    print("Or run: webhook_helper.bat (for interactive menu)")
else:
    print("❌ Some checks failed. Fix the issues above before proceeding.")
    print()
    print("📖 Read STRIPE_WEBHOOK_SETUP.md for detailed instructions")

print("=" * 60)
