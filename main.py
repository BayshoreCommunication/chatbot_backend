from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes.chatbot import router as chatbot_router
from routes.lead import router as lead_router
from routes.appointment import router as appointment_router
from routes.sales import router as sales_router
from routes.organization import router as organization_router
import os
from dotenv import load_dotenv
from services.database import get_organization_by_api_key

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

# Include all routers
app.include_router(chatbot_router, prefix="/chatbot", tags=["Chatbot"])
app.include_router(lead_router, prefix="/lead", tags=["Lead Management"])
app.include_router(appointment_router, prefix="/appointment", tags=["Appointment Booking"])
app.include_router(sales_router, prefix="/sales", tags=["Sales Assistant"])
app.include_router(organization_router, prefix="/organization", tags=["Organization Management"])

@app.get("/")
def read_root():
    return {
        "message": "AI Chatbot SaaS Platform is running.",
        "documentation": "/docs",
        "features": [
            "Multi-tenant organization support",
            "AI FAQ Bot with knowledge base",
            "Lead Capture Mode",
            "Appointment & Booking Integration",
            "Sales Assistant Mode",
            "Language Support",
            "Live Chat Escalation"
        ]
    }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

# Create a new directory 'models/' if it doesn't exist
models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
if not os.path.exists(models_dir):
    os.makedirs(models_dir)
