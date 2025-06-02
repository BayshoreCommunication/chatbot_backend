from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional
import jwt
import os
from dotenv import load_dotenv
from models.user import UserCreate, UserLogin, UserGoogle, User
from services.auth import (
    create_user,
    get_user_by_email,
    get_user_by_google_id,
    verify_password
)

# Load environment variables
load_dotenv()

router = APIRouter()

# Security configurations from environment variables
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Add CORS middleware specifically for auth routes
router.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register")
async def register(user: UserCreate):
    # Check if user already exists
    if get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user_data = create_user({
        "email": user.email,
        "password": user.password,
        "name": user.name,
    })
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

@router.options("/login")
async def options_login():
    """Handle OPTIONS request for login endpoint"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@router.post("/login")
async def login(request: Request, user: UserLogin):
    try:
        # Get user from database
        db_user = get_user_by_email(user.email)
        if not db_user:
            raise HTTPException(status_code=400, detail="Email not registered")
        
        # Verify password
        if not verify_password(user.password, db_user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Incorrect password")
        
        # Remove sensitive data
        user_data = {k: v for k, v in db_user.items() if k != "hashed_password"}
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return JSONResponse(
            content={
                "access_token": access_token,
                "token_type": "bearer",
                "user": user_data
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )

@router.post("/google")
async def google_auth(user: UserGoogle):
    # Check if user exists by Google ID
    db_user = get_user_by_google_id(user.google_id)
    
    if db_user:
        # User exists, update last login
        user_data = db_user
    else:
        # Check if email already exists
        email_user = get_user_by_email(user.email)
        if email_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered with different method"
            )
        
        # Create new user
        user_data = create_user({
            "email": user.email,
            "name": user.name,
            "google_id": user.google_id,
        })
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    } 