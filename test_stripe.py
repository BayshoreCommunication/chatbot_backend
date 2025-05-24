import stripe

# Set the API key
stripe.api_key = "sk_test_51QCEQyP8UcLxbKnCosBh1PeLlk7yKSNtkoaERiMTqfJDKZLPXekSzsQaXZ3099U9EWHZT5DjJt97QXmT52TlAu4U00CJoNvgCt"

print(f"Stripe API key set: {stripe.api_key[:20] + '...' if stripe.api_key else 'None'}")

try:
    # Test creating a checkout session with dynamic pricing (like our payment endpoint)
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': 'AI Assistant - Starter Plan',
                    'description': 'Monthly subscription to AI Assistant - Starter Plan',
                },
                'unit_amount': 2900,  # $29.00
                'recurring': {
                    'interval': 'month',
                },
            },
            'quantity': 1,
        }],
        mode='subscription',
        success_url='http://localhost:5173/payment-success?session_id={CHECKOUT_SESSION_ID}',
        cancel_url='http://localhost:5173/landing',
        allow_promotion_codes=True,
    )
    
    print(f"Success! Session ID: {session.id}")
    print(f"Session URL: {session.url}")
    
except stripe.error.StripeError as e:
    print(f"Stripe error: {str(e)}")
except Exception as e:
    print(f"General error: {str(e)}") 