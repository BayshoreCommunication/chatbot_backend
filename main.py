# Configure logging first before importing other modules
import logging_config

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
from routes.auth import router as auth_router
from routes.user import router as user_router
from routes.dashboard import router as dashboard_router
from fastapi.responses import JSONResponse
from bson import ObjectId
import json
from pathlib import Path
import traceback
from routes import instant_reply
from services.auth import seed_default_admin
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import json
import traceback
import os
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers - will be imported individually below
from services.auth import seed_default_admin
from services.cache import cache

# Check feature availability
chatbot_available = os.getenv("OPENAI_API_KEY") is not None
conversations_available = os.getenv("MONGODB_URI") is not None
faq_available = os.getenv("PINECONE_API_KEY") is not None
instant_reply_available = True  # Always available
lead_available = True  # Always available
appointment_available = os.getenv("CALENDLY_API_KEY") is not None
appointment_availability_available = True  # Always available
sales_available = True  # Always available
organization_available = os.getenv("MONGODB_URI") is not None
upload_available = os.getenv("MONGODB_URI") is not None
admin_available = os.getenv("MONGODB_URI") is not None

# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    seed_default_admin()
    yield
    # Shutdown
    # Note: Cache service handles its own connection cleanup

# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Chatbot SaaS Platform",
    description="A comprehensive AI-powered chatbot platform with multi-tenant support",
    version="2.0.0",
    lifespan=lifespan
)

# Try to import routers, skip problematic ones
try:
    from routes.chatbot import router as chatbot_router, init_socketio
    chatbot_available = True
    # Initialize socket.io with the app - this returns the socket app wrapper
    socket_app = init_socketio(app)
    print("Successfully initialized socket.io")
except Exception as e:
    print(f"Warning: Chatbot router failed to import: {e}")
    print(traceback.format_exc())
    chatbot_available = False

try:
    from routes.faq import router as faq_router
    faq_available = True
except Exception as e:
    print(f"Warning: FAQ router failed to import: {e}")
    faq_available = False

try:
    from routes.instantReply import router as instant_reply_router
    instant_reply_available = True
except Exception as e:
    print(f"Warning: Instant Reply router failed to import: {e}")
    instant_reply_available = False

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
    from routes.appointment_availability import router as appointment_availability_router
    appointment_availability_available = True
except Exception as e:
    print(f"Warning: Appointment Availability router failed to import: {e}")
    appointment_availability_available = False

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

# Dashboard router should always work
from routes.dashboard import router as dashboard_router

# Auth router should always work
from routes.auth import router as auth_router

# User router should always work
from routes.user import router as user_router

# Admin router
try:
    from routes.admin import router as admin_router
    admin_available = True
except Exception as e:
    print(f"Warning: Admin router failed to import: {e}")
    admin_available = False

try:
    from services.database import get_organization_by_api_key
    database_available = True
except Exception as e:
    print(f"Warning: Database service failed to import: {e}")
    database_available = False

try:
    from routes.upload import router as upload_router
    upload_available = True
except Exception as e:
    print(f"Warning: Upload router failed to import: {e}")
    upload_available = False

try:
    from routes.conversations import router as conversations_router
    conversations_available = True
except Exception as e:
    print(f"Warning: Conversations router failed to import: {e}")
    conversations_available = False

# API credentials are now hardcoded in the respective service files
# But we still need to load environment variables for configuration
load_dotenv()

# Mount uploads directory for static file serving
uploads_dir = Path("uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configure CORS with more specific settings
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://checkout.stripe.com",
    "https://js.stripe.com",
    "https://hooks.stripe.com",
    "https://accounts.google.com",
    "https://ai-user-dashboard.vercel.app",
    "https://aibotwizard.vercel.app",
    "https://chatbot.bayshorecommunication.com",
    "http://chatbot.bayshorecommunication.com",
    "http://localhost:8000",
    "http://localhost:8000",
    "*"  # Allow all origins as fallback
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin", "*")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
    response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    return response

# Move all other middleware after CORS
# Note: Custom JSON middleware removed due to missing MongoJSONEncoder

# Include available routers
available_features = []

if upload_available:
    app.include_router(upload_router, prefix="/api/upload", tags=["upload"])

if conversations_available:
    app.include_router(conversations_router, prefix="/api", tags=["Conversations"])
    available_features.append("Conversation Management")

if chatbot_available:
    try:
        app.include_router(chatbot_router, prefix="/api/chatbot", tags=["chatbot"])
        available_features.append("AI FAQ Bot with knowledge base")
        print("Successfully included chatbot router")
    except Exception as e:
        print(f"Error including chatbot router: {e}")
        print(traceback.format_exc())

if faq_available:
    app.include_router(faq_router, prefix="/api/faq", tags=["FAQ Management"])
    available_features.append("FAQ Management System")

if instant_reply_available:
    app.include_router(instant_reply_router, prefix="/api/instant-reply", tags=["Instant Reply"])
    available_features.append("Instant Reply Configuration")

if lead_available:
    app.include_router(lead_router, prefix="/lead", tags=["Lead Management"])
    available_features.append("Lead Capture Mode")

if appointment_available:
    app.include_router(appointment_router, prefix="/appointment", tags=["Appointment Booking"])
    available_features.append("Appointment & Booking Integration")

if appointment_availability_available:
    app.include_router(appointment_availability_router, prefix="/api/appointments", tags=["Appointment Availability"])
    available_features.append("Appointment Availability Configuration")

if sales_available:
    app.include_router(sales_router, prefix="/sales", tags=["Sales Assistant"])
    available_features.append("Sales Assistant Mode")

if organization_available:
    app.include_router(organization_router, prefix="/organization", tags=["Organization Management"])
    available_features.append("Multi-tenant organization support")

# Dashboard router is always included
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
available_features.append("Dashboard Analytics")

# Payment router is always included
app.include_router(payment_router, prefix="/payment", tags=["Payment Processing"])
available_features.append("Stripe Payment Processing")

# Admin router
if admin_available:
    app.include_router(admin_router, prefix="/admin", tags=["Admin Dashboard"])
    available_features.append("Admin Dashboard")

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(user_router, prefix="/user", tags=["User Profile"])

app.include_router(instant_reply.router, prefix="/api/instant-reply", tags=["instant-reply"])

# Add video routes separately
try:
    from routes.video_routes import router as video_router
    app.include_router(video_router, prefix="/api/video", tags=["Video Upload"])
    print("Successfully included video router")
except Exception as e:
    print(f"Error including video router: {e}")

# Add AI training routes
try:
    from routes.ai_training import router as ai_training_router
    app.include_router(ai_training_router, prefix="/api/ai-training", tags=["AI Training & Improvement"])
    print("Successfully included AI training router")
except Exception as e:
    print(f"Error including AI training router: {e}")

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

# Create the final app instance
if chatbot_available and 'socket_app' in locals():
    # If Socket.IO is available, use the wrapped app
    app = socket_app  # This ensures uvicorn uses the Socket.IO wrapped app
    print("Using Socket.IO wrapped application")
else:
    # Fallback to regular FastAPI app - app is already defined above
    print("Using regular FastAPI application")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
