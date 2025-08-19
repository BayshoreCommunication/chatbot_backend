#!/usr/bin/env python3
"""
Async Training Routes
Handles long-running training operations asynchronously
"""

import asyncio
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from typing import Optional, Dict, Any
from datetime import datetime
from services.database import db
from services.auth import get_organization_from_api_key
from services.langchain.engine import add_document
import uuid

router = APIRouter()

# In-memory storage for training status (in production, use Redis or database)
training_status = {}

async def process_training_async(training_id: str, url: str, platform: str, max_pages: int, api_key: str):
    """Process training asynchronously in the background"""
    try:
        # Update status to processing
        training_status[training_id] = {
            "status": "processing",
            "progress": 0,
            "message": f"Starting training from {platform}: {url}",
            "started_at": datetime.utcnow().isoformat()
        }
        
        # Build URL with parameters
        scrape_url = f"{url}?scrape_website=true&max_pages={max_pages}&platform={platform}"
        
        # Update progress
        training_status[training_id]["progress"] = 25
        training_status[training_id]["message"] = "Downloading content..."
        
        # Process the document
        result = add_document(url=scrape_url, api_key=api_key)
        
        # Update progress
        training_status[training_id]["progress"] = 75
        training_status[training_id]["message"] = "Processing content..."
        
        # Final result
        if result.get("status") == "success":
            training_status[training_id] = {
                "status": "completed",
                "progress": 100,
                "message": f"Successfully trained from {platform}",
                "result": result,
                "completed_at": datetime.utcnow().isoformat()
            }
        else:
            training_status[training_id] = {
                "status": "failed",
                "progress": 0,
                "message": f"Training failed: {result.get('message', 'Unknown error')}",
                "error": result.get("message", "Unknown error"),
                "completed_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        training_status[training_id] = {
            "status": "failed",
            "progress": 0,
            "message": f"Training failed: {str(e)}",
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat()
        }

@router.post("/start-async-training")
async def start_async_training(
    request: Request,
    background_tasks: BackgroundTasks,
    organization=Depends(get_organization_from_api_key)
):
    """Start training asynchronously and return immediately with training ID"""
    try:
        data = await request.json()
        url = data.get("url")
        platform = data.get("platform", "website")
        max_pages = data.get("max_pages", 5)
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        # Generate unique training ID
        training_id = str(uuid.uuid4())
        
        # Initialize status
        training_status[training_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Training queued",
            "url": url,
            "platform": platform,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Start background task
        background_tasks.add_task(
            process_training_async,
            training_id,
            url,
            platform,
            max_pages,
            organization["api_key"]
        )
        
        return {
            "status": "success",
            "training_id": training_id,
            "message": "Training started in background"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/training-status/{training_id}")
async def get_training_status(
    training_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Get the status of an async training operation"""
    if training_id not in training_status:
        raise HTTPException(status_code=404, detail="Training ID not found")
    
    return {
        "status": "success",
        "training": training_status[training_id]
    }

@router.delete("/training-status/{training_id}")
async def clear_training_status(
    training_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Clear training status after completion"""
    if training_id in training_status:
        del training_status[training_id]
    
    return {"status": "success", "message": "Training status cleared"}
