from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import stripe
import os
from dotenv import load_dotenv

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
        # Retrieve the session
        session = stripe.checkout.Session.retrieve(request.sessionId)
        
        if session.payment_status == 'paid':
            # Get subscription details
            subscription_id = session.subscription
            customer_email = session.customer_details.email
            
            # Here you would typically:
            # 1. Update user record in database
            # 2. Activate subscription
            # 3. Send confirmation email
            
            return {
                "success": True,
                "subscriptionId": subscription_id,
                "customerEmail": customer_email,
                "message": "Payment verified successfully"
            }
        else:
            return {
                "success": False,
                "message": "Payment not completed"
            }
    
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

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