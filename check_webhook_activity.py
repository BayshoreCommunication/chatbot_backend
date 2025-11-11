from services.database import db
import json

print("=== Recent Webhook Activity Check ===\n")

# Check most recent user updates
users = list(db.users.find().sort("updated_at", -1).limit(5))

print(f"Last 5 updated users:\n")
for user in users:
    print(f"Email: {user.get('email')}")
    print(f"  Updated: {user.get('updated_at')}")
    print(f"  has_paid_subscription: {user.get('has_paid_subscription')}")
    print(f"  subscription_type: {user.get('subscription_type', 'NOT SET')}")
    print(f"  stripe_subscription_id: {user.get('stripe_subscription_id', 'NOT SET')}")
    print()

# Check subscriptions collection
print("\n=== Subscriptions Collection ===")
subscriptions = list(db.subscriptions.find().sort("created_at", -1).limit(5))
print(f"Total subscriptions: {db.subscriptions.count_documents({})}")

if subscriptions:
    print("\nRecent subscriptions:")
    for sub in subscriptions:
        print(f"  User ID: {sub.get('user_id')}")
        print(f"  Stripe ID: {sub.get('stripe_subscription_id')}")
        print(f"  Tier: {sub.get('subscription_tier')}")
        print(f"  Created: {sub.get('created_at')}")
        print()
else:
    print("  No subscriptions found in database")
