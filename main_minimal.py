from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.payment import router as payment_router
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create the FastAPI app
app = FastAPI(
    title="AI Assistant SaaS Platform - Payment Service",
    description="Payment processing service for AI Assistant SaaS",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include payment router
app.include_router(payment_router, prefix="/payment", tags=["Payment Processing"])

@app.get("/")
def read_root():
    return {
        "message": "AI Assistant SaaS Payment Service is running.",
        "documentation": "/docs",
        "features": [
            "Stripe Payment Processing",
            "Subscription Management", 
            "Payment Verification",
            "Checkout Session Creation"
        ]
    }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "payment"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 