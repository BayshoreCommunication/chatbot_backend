from services.database import db
import json

print("=== Checking User Subscription Fields ===\n")

# Find users with paid subscriptions
users = list(db.users.find())
print(f"Total users in database: {len(users)}\n")

for user in users:
    print(f"User: {user.get('email')}")
    print(f"  has_paid_subscription: {user.get('has_paid_subscription')}")
    
    # Check for subscription fields
    sub_fields = [
        'subscription_type',
        'subscription_start_date', 
        'subscription_end_date',
        'billing_cycle',
        'stripe_subscription_id',
        'stripe_customer_id',
        'free_trial_used',
        'last_reminder_sent'
    ]
    
    missing_fields = []
    present_fields = []
    
    for field in sub_fields:
        if field in user:
            present_fields.append(f"{field}: {user[field]}")
        else:
            missing_fields.append(field)
    
    if present_fields:
        print(f"  ✅ Present fields:")
        for f in present_fields:
            print(f"     - {f}")
    
    if missing_fields:
        print(f"  ❌ Missing fields: {', '.join(missing_fields)}")
    
    print()

# Check Stripe webhook endpoint configuration
print("\n=== Stripe Webhook Configuration ===")
import os
from dotenv import load_dotenv
load_dotenv()

print(f"STRIPE_SECRET_KEY configured: {'Yes' if os.getenv('STRIPE_SECRET_KEY') else 'No'}")
print(f"STRIPE_WEBHOOK_SECRET configured: {'Yes' if os.getenv('STRIPE_WEBHOOK_SECRET') else 'No'}")
print(f"STRIPE_WEBHOOK_SECRET value: {os.getenv('STRIPE_WEBHOOK_SECRET', 'NOT SET')}")
