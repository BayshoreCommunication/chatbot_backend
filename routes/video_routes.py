from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from pathlib import Path
import uuid
import shutil
import os
from pydantic import BaseModel
from typing import Optional

# Import the dependency function
import sys
sys.path.append('..')
from services.database import get_organization_by_api_key, db

router = APIRouter()

# Dependency function for getting organization
from fastapi import Header

async def get_organization_from_api_key_header(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    from services.database import get_organization_by_api_key
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

@router.post("/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    organization=Depends(get_organization_from_api_key_header)
):
    """Upload a video for the chat widget"""
    try:
        # Validate file type
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="Only video files are allowed")
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads/videos")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = upload_dir / unique_filename
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Update organization settings with video info
        video_url = f"/api/video/video/{unique_filename}"
        
        db.organizations.update_one(
            {"_id": organization["_id"]},
            {
                "$set": {
                    "chat_widget_settings.video_url": video_url,
                    "chat_widget_settings.video_filename": unique_filename,
                    "chat_widget_settings.video_autoplay": True,
                    "chat_widget_settings.video_duration": 10
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Video uploaded successfully",
            "video_url": video_url,
            "filename": unique_filename
        }
        
    except Exception as e:
        print(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/video/{filename}")
async def get_video(filename: str):
    """Serve uploaded video files"""
    try:
        file_path = Path("uploads/videos") / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")
        
        return FileResponse(file_path, media_type="video/mp4")
        
    except Exception as e:
        print(f"Error serving video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/video")
async def delete_video(
    organization=Depends(get_organization_from_api_key_header)
):
    """Delete the current video"""
    try:
        # Get current video filename
        org = db.organizations.find_one({"_id": organization["_id"]})
        if org and "chat_widget_settings" in org:
            video_filename = org["chat_widget_settings"].get("video_filename")
            
            if video_filename:
                # Delete local file
                file_path = Path("uploads/videos") / video_filename
                if file_path.exists():
                    file_path.unlink()
                    print(f"Deleted local video: {file_path}")
                
                # Update organization settings
                db.organizations.update_one(
                    {"_id": organization["_id"]},
                    {
                        "$unset": {
                            "chat_widget_settings.video_url": "",
                            "chat_widget_settings.video_filename": "",
                            "chat_widget_settings.video_autoplay": "",
                            "chat_widget_settings.video_duration": ""
                        }
                    }
                )
        
        return {
            "status": "success",
            "message": "Video deleted successfully"
        }
        
    except Exception as e:
        print(f"Error deleting video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/video-settings")
async def update_video_settings(
    request: Request,
    organization=Depends(get_organization_from_api_key_header)
):
    """Update video settings"""
    try:
        data = await request.json()
        autoplay = data.get("autoplay", True)
        duration = data.get("duration", 10)
        
        db.organizations.update_one(
            {"_id": organization["_id"]},
            {
                "$set": {
                    "chat_widget_settings.video_autoplay": autoplay,
                    "chat_widget_settings.video_duration": duration
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Video settings updated successfully",
            "autoplay": autoplay,
            "duration": duration
        }
        
    except Exception as e:
        print(f"Error updating video settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
