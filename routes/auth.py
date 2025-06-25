from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse, RedirectResponse
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
    verify_password,
    serialize_user
)
import logging
from bson.objectid import ObjectId
import urllib.parse
import requests
import json

# Get logger instead of configuring it
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

router = APIRouter()

# Security configurations from environment variables
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "580986048415-qpgtv2kvij47ae4if8ep47jjq8o2qtmj.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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
        logger.debug(f"Login attempt for email: {user.email}")
        
        # Get user from database
        db_user = get_user_by_email(user.email)
        logger.debug(f"Database user found: {bool(db_user)}")
        
        if not db_user:
            logger.warning(f"Login failed: Email not registered - {user.email}")
            raise HTTPException(status_code=400, detail="Email not registered")
        
        # Verify password
        is_valid = verify_password(user.password, db_user["hashed_password"])
        logger.debug(f"Password verification result: {is_valid}")
        
        if not is_valid:
            logger.warning(f"Login failed: Incorrect password for {user.email}")
            raise HTTPException(status_code=400, detail="Incorrect password")
        
        # Remove sensitive data and ensure all fields are JSON serializable
        user_data = {}
        for k, v in db_user.items():
            if k != "hashed_password":
                if isinstance(v, ObjectId):
                    user_data[k] = str(v)
                elif isinstance(v, datetime):
                    user_data[k] = v.isoformat()
                else:
                    user_data[k] = v
        
        logger.debug("User data prepared for response")
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        logger.debug("Access token created successfully")
        
        response_data = {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }
        logger.info(f"Login successful for user: {user.email}")
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )
    except HTTPException as e:
        logger.error(f"HTTP Exception during login: {str(e)}")
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"},
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

@router.get("/google/login")
async def google_oauth_login(request: Request, state: str = None, redirect_uri: str = None):
    """Initiate Google OAuth flow for mobile app"""
    try:
        # Store state and redirect_uri in session or cache (simplified for demo)
        google_auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri=https://6625-103-112-54-213.ngrok-free.app/auth/google/callback&"
            f"scope=openid email profile&"
            f"response_type=code&"
            f"state={state}|{urllib.parse.quote(redirect_uri or '')}"
        )
        
        logger.info(f"Redirecting to Google OAuth: {google_auth_url}")
        return RedirectResponse(url=google_auth_url)
        
    except Exception as e:
        logger.error(f"Error initiating Google OAuth: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate Google OAuth")

@router.get("/google/callback")
async def google_oauth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handle Google OAuth callback and redirect back to mobile app"""
    try:
        if error:
            logger.error(f"Google OAuth error: {error}")
            # Redirect back to mobile app with error
            return RedirectResponse(url="exp://192.168.68.111:8081/--/auth/callback?error=oauth_error")
        
        if not code:
            logger.error("No authorization code received from Google")
            return RedirectResponse(url="exp://192.168.68.111:8081/--/auth/callback?error=no_code")
        
        # Parse state to get original redirect URI
        original_state, mobile_redirect_uri = state.split('|', 1) if state and '|' in state else (state, '')
        mobile_redirect_uri = urllib.parse.unquote(mobile_redirect_uri) if mobile_redirect_uri else "exp://192.168.68.111:8081/--/auth/callback"
        
        # Exchange code for access token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": "https://6625-103-112-54-213.ngrok-free.app/auth/google/callback"
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        token_info = token_response.json()
        
        # Get user info from Google
        user_info_url = f"https://www.googleapis.com/oauth2/v1/userinfo?access_token={token_info['access_token']}"
        user_response = requests.get(user_info_url)
        user_response.raise_for_status()
        user_info = user_response.json()
        
        logger.info(f"Google user info received: {user_info.get('email')}")
        
        # Check if user exists by Google ID
        db_user = get_user_by_google_id(user_info['id'])
        
        if db_user:
            # User exists, update last login
            user_data = db_user
        else:
            # Check if email already exists
            email_user = get_user_by_email(user_info['email'])
            if email_user:
                # Link Google account to existing user
                # Update existing user with Google ID
                user_data = email_user
                # Here you would update the user record with google_id
            else:
                # Create new user
                user_data = create_user({
                    "email": user_info['email'],
                    "name": user_info.get('name', user_info['email']),
                    "google_id": user_info['id'],
                })
        
        # Create access token for the app
        access_token = create_access_token(
            data={"sub": user_info['email']},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        # Prepare user data for mobile app (remove sensitive info)
        safe_user_data = {}
        for k, v in user_data.items():
            if k != "hashed_password":
                if isinstance(v, ObjectId):
                    safe_user_data[k] = str(v)
                elif isinstance(v, datetime):
                    safe_user_data[k] = v.isoformat()
                else:
                    safe_user_data[k] = v
        
        # Redirect back to mobile app with auth data
        user_data_encoded = urllib.parse.quote(json.dumps(safe_user_data))
        success_url = f"{mobile_redirect_uri}?token={access_token}&user={user_data_encoded}&success=true"
        
        logger.info(f"Redirecting back to mobile app: {mobile_redirect_uri}")
        return RedirectResponse(url=success_url)
        
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {str(e)}")
        error_url = f"exp://192.168.68.111:8081/--/auth/callback?error=callback_error&message={urllib.parse.quote(str(e))}"
        return RedirectResponse(url=error_url)

@router.post("/admin/google")
async def admin_google_auth(user: UserGoogle):
    """Google OAuth for admin users"""
    try:
        # Check if user exists by Google ID
        db_user = get_user_by_google_id(user.google_id)
        
        if db_user:
            # User exists, check if they're admin
            if not db_user.get("is_admin") or db_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
            user_data = db_user
        else:
            # Check if email already exists
            email_user = get_user_by_email(user.email)
            if email_user:
                # Link Google account to existing user if they're admin
                if not email_user.get("is_admin") or email_user.get("role") != "admin":
                    raise HTTPException(status_code=403, detail="Admin access required")
                user_data = email_user
            else:
                # Don't create new admin users through Google auth
                raise HTTPException(status_code=403, detail="Admin access required")
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": serialize_user(user_data)
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Admin Google auth error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@router.post("/admin/login")
async def admin_login(user: UserLogin):
    """Admin login with email and password"""
    try:
        logger.debug(f"Admin login attempt for email: {user.email}")
        
        # Get user from database
        db_user = get_user_by_email(user.email)
        logger.debug(f"Database user found: {bool(db_user)}")
        
        if not db_user:
            logger.warning(f"Admin login failed: Email not registered - {user.email}")
            raise HTTPException(status_code=400, detail="Email not registered")
        
        # Check if user is admin
        if not db_user.get("is_admin") or db_user.get("role") != "admin":
            logger.warning(f"Admin login failed: User is not admin - {user.email}")
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Verify password
        is_valid = verify_password(user.password, db_user["hashed_password"])
        logger.debug(f"Password verification result: {is_valid}")
        
        if not is_valid:
            logger.warning(f"Admin login failed: Incorrect password for {user.email}")
            raise HTTPException(status_code=400, detail="Incorrect password")
        
        # Remove sensitive data and ensure all fields are JSON serializable
        user_data = serialize_user(db_user)
        logger.debug("Admin user data prepared for response")
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        logger.debug("Access token created successfully")
        
        response_data = {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }
        logger.info(f"Admin login successful for user: {user.email}")
        
        return JSONResponse(
            content=response_data,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )
    except HTTPException as e:
        logger.error(f"HTTP Exception during admin login: {str(e)}")
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error during admin login: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        ) 