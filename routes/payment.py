from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import stripe
import os
from dotenv import load_dotenv
from services.auth import update_user
from services.database import (
    get_user_by_email,
    get_organization_by_user_id,
    update_organization_subscription,
    create_subscription,
    get_subscription_by_stripe_id
)
from datetime import datetime

load_dotenv()

# Configure Stripe - Use hardcoded key for testing
stripe.api_key = "sk_test_51QCEQyP8UcLxbKnCosBh1PeLlk7yKSNtkoaERiMTqfJDKZLPXekSzsQaXZ3099U9EWHZT5DjJt97QXmT52TlAu4U00CJoNvgCt"

router = APIRouter()

class CheckoutSessionRequest(BaseModel):
    priceId: str
    successUrl: str
    cancelUrl: str
    customerEmail: str = None

class VerifySessionRequest(BaseModel):
    sessionId: str

@router.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutSessionRequest):
    """Create a Stripe checkout session for subscription payment"""
    try:
        # Debug: Print API key status
        print(f"Stripe API key set: {stripe.api_key[:20] + '...' if stripe.api_key else 'None'}")
        
        # Map price IDs to amounts
        price_map = {
            'price_starter_test': 2900,  # $29.00
            'price_professional_test': 7900,  # $79.00
            'price_enterprise_test': 19900,  # $199.00
        }
        
        plan_names = {
            'price_starter_test': 'AI Assistant - Starter Plan',
            'price_professional_test': 'AI Assistant - Professional Plan', 
            'price_enterprise_test': 'AI Assistant - Enterprise Plan',
        }
        
        amount = price_map.get(request.priceId, 2900)
        plan_name = plan_names.get(request.priceId, 'AI Assistant Subscription')
        
        print(f"Creating session for {plan_name} - ${amount/100}")
        
        # Create checkout session with dynamic pricing
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': plan_name,
                        'description': f'Monthly subscription to {plan_name}',
                    },
                    'unit_amount': amount,
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.successUrl + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.cancelUrl,
            customer_email=request.customerEmail,
            allow_promotion_codes=True,
        )
        
        print(f"Session created successfully: {session.id}")
        return {"sessionId": session.id}
    
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"General error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/verify-session")
async def verify_session(request: VerifySessionRequest):
    """Verify a completed Stripe checkout session"""
    try:
        print(f"Starting verify_session with sessionId: {request.sessionId}")
        
        # Retrieve the session
        session = stripe.checkout.Session.retrieve(request.sessionId)
        print(f"Session payment status: {session.payment_status}")
        
        if session.payment_status == 'paid':
            # Get subscription details from Stripe
            subscription = stripe.Subscription.retrieve(session.subscription)
            print(f"Subscription ID: {subscription.id}")
            
            # Check if subscription already exists in database
            existing_subscription = get_subscription_by_stripe_id(subscription.id)
            if existing_subscription:
                print(f"Subscription already exists in database: {existing_subscription}")
                return {
                    "success": True,
                    "subscriptionId": subscription.id,
                    "customerEmail": session.customer_details.email,
                    "message": "Payment already verified"
                }
            
            # Get customer email
            customer_email = session.customer_details.email
            print(f"Customer email: {customer_email}")
            
            # Get price information from the subscription's first item
            # List all subscription items
            items = stripe.SubscriptionItem.list(subscription=subscription.id)
            print(f"Found {len(items.data)} subscription items")
            
            if not items.data:
                raise HTTPException(status_code=400, detail="No subscription items found")
            
            # Get the first item
            first_item = items.data[0]
            print(f"First subscription item ID: {first_item.id}")
            
            # Get price information
            price = first_item.price
            payment_amount = price.unit_amount / 100  # Convert cents to dollars
            subscription_tier = price.nickname or "professional"
            print(f"Payment amount: ${payment_amount}")
            print(f"Subscription tier: {subscription_tier}")
            
            # Update user subscription status in database
            user = get_user_by_email(customer_email)
            print(f"Found user: {user}")
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Update user subscription status
            update_user(user["id"], {
                "has_paid_subscription": True,
                "subscription_id": subscription.id
            })
            print(f"Updated user subscription status")
            
            # Get organization and update subscription ID
            organization = get_organization_by_user_id(user["id"])
            print(f"Found organization: {organization}")
            if not organization:
                raise HTTPException(status_code=404, detail="Organization not found")

            # Update organization subscription
            update_organization_subscription(organization["id"], subscription.id)
            print(f"Updated organization subscription")
            
            # Create subscription record
            subscription_data = {
                "user_id": user["id"],
                "organization_id": organization["id"],
                "stripe_subscription_id": subscription.id,
                "payment_amount": payment_amount,
                "subscription_tier": subscription_tier,
                "current_period_start": datetime.fromtimestamp(first_item.current_period_start),
                "current_period_end": datetime.fromtimestamp(first_item.current_period_end)
            }
            print(f"Prepared subscription data: {subscription_data}")
            
            # Create subscription in database
            created_subscription = create_subscription(**subscription_data)
            print(f"Created subscription in database: {created_subscription}")
            
            return {
                "success": True,
                "subscriptionId": subscription.id,
                "customerEmail": customer_email,
                "message": "Payment verified successfully"
            }
        else:
            print(f"Payment not completed. Status: {session.payment_status}")
            return {
                "success": False,
                "message": "Payment not completed"
            }
    
    except stripe.error.StripeError as e:
        print(f"Stripe error in verify_session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error in verify_session: {str(e)}")
        print(f"Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-portal-session")
async def create_portal_session(customer_id: str, return_url: str):
    """Create a Stripe customer portal session for subscription management"""
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        
        return {"url": session.url}
    
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/subscription/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details"""
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "plan": {
                "id": subscription.items.data[0].price.id,
                "amount": subscription.items.data[0].price.unit_amount,
                "currency": subscription.items.data[0].price.currency,
                "interval": subscription.items.data[0].price.recurring.interval,
            }
        }
    
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") 