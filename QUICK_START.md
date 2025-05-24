# Quick Start Guide - AI Assistant SaaS with Payment Integration

## Your Stripe Credentials
I've already configured your Stripe test keys in the code:

- **Publishable Key**: `pk_test_51QCEQyP8UcLxbKnCXzg48ysRmhBHDnf4N4gzPtBNpc8Hmnk9dtlt4HGdv92JLjRgw57UHqT6EQUHli5yETB9Gbro00bCBEQ8UT`
- **Secret Key**: `sk_test_51QCEQyP8UcLxbKnCosBh1PeLlk7yKSNtkoaERiMTqfJDKZLPXekSzsQaXZ3099U9EWHZT5DjJt97QXmT52TlAu4U00CJoNvgCt`

## Backend Setup (AI_Py folder)

1. **Install Python dependencies**:
   ```bash
   pip install fastapi uvicorn stripe python-dotenv
   ```

2. **Create .env file** (optional, as keys are hardcoded for testing):
   ```
   STRIPE_SECRET_KEY=sk_test_51QCEQyP8UcLxbKnCosBh1PeLlk7yKSNtkoaERiMTqfJDKZLPXekSzsQaXZ3099U9EWHZT5DjJt97QXmT52TlAu4U00CJoNvgCt
   ```

3. **Start the server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

## Frontend Setup (AI_user_dashboard folder)

1. **Install dependencies** (already done):
   ```bash
   npm install
   ```

2. **Start the development server**:
   ```bash
   npm run dev
   ```

## Testing the Payment Flow

1. **Visit the landing page**: http://localhost:5173/
2. **Choose a pricing plan** and click "Get Started"
3. **Use Stripe test card**: `4242 4242 4242 4242`
   - Any future expiry date (e.g., 12/25)
   - Any CVC (e.g., 123)
   - Any postal code (e.g., 12345)

## Stripe Dashboard Setup

1. Go to https://dashboard.stripe.com/test/products
2. Create 3 test products with these exact Price IDs:
   - **Starter Plan**: Create a product, then add a price with ID `price_starter_test` ($29/month)
   - **Professional Plan**: Create a product, then add a price with ID `price_professional_test` ($79/month)  
   - **Enterprise Plan**: Create a product, then add a price with ID `price_enterprise_test` ($199/month)

**OR** update the frontend code with your actual Stripe Price IDs from your dashboard.

## Current Features Working

✅ **Landing Page**: Beautiful modern design with pricing table
✅ **Stripe Integration**: Payment processing configured
✅ **User Context**: Tracks subscription status
✅ **Route Protection**: Dashboard access based on payment
✅ **Payment Success**: Handles successful payments
✅ **Responsive Design**: Works on all devices

## API Endpoints Available

- `GET /` - Root endpoint
- `POST /payment/create-checkout-session` - Create payment session
- `POST /payment/verify-session` - Verify payment completion
- `GET /payment/subscription/{id}` - Get subscription details

## Troubleshooting

If you get errors:
1. Make sure both servers are running
2. Check browser console for any errors
3. Verify Stripe Price IDs match your dashboard
4. Use only Stripe test cards for testing

## Next Steps

Once everything is working:
1. Create real products in Stripe
2. Switch to production Stripe keys
3. Implement user database
4. Add webhooks for subscription events
5. Deploy to production 