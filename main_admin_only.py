# Configure logging first before importing other modules
import logging_config

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
from services.auth import seed_default_admin

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

# Create the FastAPI app
app = FastAPI(
    title="AI Chatbot SaaS Platform - Admin Only",
    description="Lightweight admin-only version for dashboard",
    version="1.0.0"
)

# Import only essential routers (no AI components)
try:
    from routes.organization import router as organization_router
    organization_available = True
except Exception as e:
    print(f"Warning: Organization router failed to import: {e}")
    organization_available = False

from routes.payment import router as payment_router

# Admin router
try:
    from routes.admin import router as admin_router
    admin_available = True
except Exception as e:
    print(f"Warning: Admin router failed to import: {e}")
    admin_available = False

try:
    from routes.conversations import router as conversations_router
    conversations_available = True
except Exception as e:
    print(f"Warning: Conversations router failed to import: {e}")
    conversations_available = False

# Load environment variables
load_dotenv()

# Mount uploads directory for static file serving
uploads_dir = Path("uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configure CORS
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
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
    return response

# JSON middleware
@app.middleware("http")
async def custom_json_middleware(request: Request, call_next):
    response = await call_next(request)
    if isinstance(response, JSONResponse):
        response.body = json.dumps(
            response.body.decode(),
            cls=MongoJSONEncoder
        ).encode()
    return response

# Include only essential routers
available_features = []

if conversations_available:
    app.include_router(conversations_router, prefix="/api", tags=["Conversations"])
    available_features.append("Conversation Management")

if organization_available:
    app.include_router(organization_router, prefix="/organization", tags=["Organization Management"])
    available_features.append("Multi-tenant organization support")

# Dashboard router
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
available_features.append("Dashboard Analytics")

# Payment router
app.include_router(payment_router, prefix="/payment", tags=["Payment Processing"])
available_features.append("Stripe Payment Processing")

# Admin router
if admin_available:
    app.include_router(admin_router, prefix="/admin", tags=["Admin Dashboard"])
    available_features.append("Admin Dashboard")

# Auth routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(user_router, prefix="/user", tags=["User Profile"])

@app.get("/")
def read_root():
    return {
        "message": "AI Chatbot SaaS Platform - Admin Dashboard Only",
        "documentation": "/docs",
        "features": available_features,
        "status": "Optimized for admin dashboard - AI features disabled for performance"
    }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    # Seed default admin user
    seed_default_admin()
    print("Admin-only server started successfully!")

# Export the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 