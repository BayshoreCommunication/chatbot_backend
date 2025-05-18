from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routes.chatbot import router as chatbot_router
from routes.lead import router as lead_router
from routes.appointment import router as appointment_router
from routes.sales import router as sales_router
import os
from dotenv import load_dotenv

# API credentials are now hardcoded in the respective service files
# No need to load environment variables
# load_dotenv()

# Create the FastAPI app
app = FastAPI(
    title="AI Chatbot Backend",
    description="Backend services for an AI-powered business chatbot",
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

@app.get("/")
def read_root():
    return {
        "message": "AI Chatbot Backend is running.",
        "documentation": "/docs",
        "features": [
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
