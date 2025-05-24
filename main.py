from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Try to import routers, skip problematic ones
try:
    from routes.chatbot import router as chatbot_router
    chatbot_available = True
except Exception as e:
    print(f"Warning: Chatbot router failed to import: {e}")
    chatbot_available = False

try:
    from routes.lead import router as lead_router
    lead_available = True
except Exception as e:
    print(f"Warning: Lead router failed to import: {e}")
    lead_available = False

try:
    from routes.appointment import router as appointment_router
    appointment_available = True
except Exception as e:
    print(f"Warning: Appointment router failed to import: {e}")
    appointment_available = False

try:
    from routes.sales import router as sales_router
    sales_available = True
except Exception as e:
    print(f"Warning: Sales router failed to import: {e}")
    sales_available = False

try:
    from routes.organization import router as organization_router
    organization_available = True
except Exception as e:
    print(f"Warning: Organization router failed to import: {e}")
    organization_available = False

# Payment router should always work
from routes.payment import router as payment_router

try:
    from services.database import get_organization_by_api_key
    database_available = True
except Exception as e:
    print(f"Warning: Database service failed to import: {e}")
    database_available = False

# API credentials are now hardcoded in the respective service files
# But we still need to load environment variables for configuration
load_dotenv()

# Create the FastAPI app
app = FastAPI(
    title="AI Chatbot SaaS Platform",
    description="Multi-tenant SaaS platform for AI-powered business chatbots",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include available routers
available_features = []

if chatbot_available:
    app.include_router(chatbot_router, prefix="/chatbot", tags=["Chatbot"])
    available_features.append("AI FAQ Bot with knowledge base")

if lead_available:
    app.include_router(lead_router, prefix="/lead", tags=["Lead Management"])
    available_features.append("Lead Capture Mode")

if appointment_available:
    app.include_router(appointment_router, prefix="/appointment", tags=["Appointment Booking"])
    available_features.append("Appointment & Booking Integration")

if sales_available:
    app.include_router(sales_router, prefix="/sales", tags=["Sales Assistant"])
    available_features.append("Sales Assistant Mode")

if organization_available:
    app.include_router(organization_router, prefix="/organization", tags=["Organization Management"])
    available_features.append("Multi-tenant organization support")

# Payment router is always included
app.include_router(payment_router, prefix="/payment", tags=["Payment Processing"])
available_features.append("Stripe Payment Processing")

@app.get("/")
def read_root():
    return {
        "message": "AI Chatbot SaaS Platform is running.",
        "documentation": "/docs",
        "features": available_features,
        "status": "Partial functionality - some AI features may be unavailable due to dependencies"
    }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

# Create a new directory 'models/' if it doesn't exist
models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
if not os.path.exists(models_dir):
    os.makedirs(models_dir)
