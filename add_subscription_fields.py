from services.database import db
from datetime import datetime

print("=== Adding Missing Subscription Fields to Existing Users ===\n")

# Update all users to have the new subscription fields with default values
result = db.users.update_many(
    {},  # Match all users
    {
        "$set": {
            "subscription_type": "free",
            "subscription_start_date": None,
            "subscription_end_date": None,
            "billing_cycle": None,
            "stripe_subscription_id": None,
            "stripe_customer_id": None,
            "free_trial_used": False,
            "last_reminder_sent": None,
            "updated_at": datetime.utcnow()
        }
    }
)

print(f"✅ Updated {result.modified_count} users with subscription fields")

# Show updated users
print("\n=== Verification ===")
users = list(db.users.find().limit(3))
for user in users:
    print(f"\nUser: {user.get('email')}")
    print(f"  subscription_type: {user.get('subscription_type')}")
    print(f"  subscription_start_date: {user.get('subscription_start_date')}")
    print(f"  subscription_end_date: {user.get('subscription_end_date')}")
    print(f"  billing_cycle: {user.get('billing_cycle')}")
    print(f"  stripe_subscription_id: {user.get('stripe_subscription_id')}")
    print(f"  stripe_customer_id: {user.get('stripe_customer_id')}")
    print(f"  free_trial_used: {user.get('free_trial_used')}")
    print(f"  last_reminder_sent: {user.get('last_reminder_sent')}")

print("\n✅ All users now have the subscription tracking fields!")
