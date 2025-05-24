# AI Assistant SaaS - Payment Integration Setup

## Prerequisites

1. Python 3.8+ installed
2. Node.js 16+ installed
3. Stripe account (for payment processing)

## Backend Setup

1. Navigate to the AI_Py directory:
   ```bash
   cd AI_Py
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your configuration:
   ```env
   STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key_here
   STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   PINECONE_API_KEY=your_pinecone_api_key_here
   PINECONE_ENVIRONMENT=your_pinecone_environment_here
   ```

5. Start the backend server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## Frontend Setup

1. Navigate to the AI_user_dashboard directory:
   ```bash
   cd AI_user_dashboard
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env` file with your configuration:
   ```env
   VITE_STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key_here
   VITE_API_BASE_URL=http://localhost:8000
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

## Stripe Configuration

1. Create a Stripe account at https://stripe.com
2. Get your API keys from the Stripe dashboard
3. Create test products and prices in Stripe dashboard:
   - Starter Plan: $29/month (price_starter_test)
   - Professional Plan: $79/month (price_professional_test)
   - Enterprise Plan: $199/month (price_enterprise_test)

## Usage

1. Visit the landing page at `http://localhost:5173/landing`
2. Browse the pricing plans and features
3. Click "Get Started" on any plan to initiate payment
4. Complete the test payment using Stripe test cards
5. After successful payment, you'll be redirected to the payment success page
6. Access the dashboard with your paid subscription

## Test Cards

Use these test card numbers for testing:
- Success: 4242 4242 4242 4242
- Decline: 4000 0000 0000 0002
- Requires authentication: 4000 0025 0000 3155

## Features Implemented

- ✅ Beautiful landing page with pricing table
- ✅ Stripe payment integration
- ✅ Payment success/failure handling
- ✅ User authentication state management
- ✅ Conditional dashboard access based on subscription
- ✅ Responsive design with dark/light theme support
- ✅ Backend payment processing endpoints
- ✅ Payment verification and subscription management

## API Endpoints

### Payment Routes
- `POST /payment/create-checkout-session` - Create Stripe checkout session
- `POST /payment/verify-session` - Verify completed payment
- `POST /payment/create-portal-session` - Create customer portal session
- `GET /payment/subscription/{subscription_id}` - Get subscription details

## Next Steps

1. Set up a production Stripe account
2. Configure webhooks for subscription events
3. Implement user database integration
4. Add email notifications for successful payments
5. Implement subscription management features
6. Add analytics and reporting 