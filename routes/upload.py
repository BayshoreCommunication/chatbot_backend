from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import boto3
from botocore.config import Config
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter()

# DigitalOcean Spaces Configuration
SPACE_NAME = os.getenv('DO_SPACES_BUCKET', 'bayshore')
SPACE_REGION = os.getenv('DO_SPACES_REGION', 'nyc3')
SPACE_ENDPOINT = f"https://{SPACE_REGION}.digitaloceanspaces.com"
ACCESS_KEY = os.getenv('DO_SPACES_KEY')
SECRET_KEY = os.getenv('DO_SPACES_SECRET')
FOLDER_NAME = os.getenv('DO_FOLDER_NAME', 'ai_bot')

if not all([ACCESS_KEY, SECRET_KEY]):
    raise Exception("DigitalOcean Spaces credentials not found in environment variables")

# Initialize S3 client for DigitalOcean Spaces
s3_client = boto3.client('s3',
    endpoint_url=SPACE_ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(s3={'addressing_style': 'virtual'}),
    region_name=SPACE_REGION
)

@router.post("/upload-avatar")
async def upload_avatar(file: UploadFile = File(...)):
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Create a unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{FOLDER_NAME}/avatars/{uuid.uuid4()}{file_extension}"
        
        # Upload to DigitalOcean Spaces
        try:
            s3_client.upload_fileobj(
                file.file,
                SPACE_NAME,
                unique_filename,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': file.content_type
                }
            )
            
            # Generate the public URL
            file_url = f"https://{SPACE_NAME}.{SPACE_REGION}.digitaloceanspaces.com/{unique_filename}"
            
            return {
                "status": "success",
                "url": file_url
            }
            
        except Exception as e:
            print(f"Upload error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to upload file to storage")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Create a unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{FOLDER_NAME}/files/{uuid.uuid4()}{file_extension}"
        
        # Upload to DigitalOcean Spaces
        try:
            s3_client.upload_fileobj(
                file.file,
                SPACE_NAME,
                unique_filename,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': file.content_type
                }
            )
            
            # Generate the public URL
            file_url = f"https://{SPACE_NAME}.{SPACE_REGION}.digitaloceanspaces.com/{unique_filename}"
            
            return {
                "status": "success",
                "url": file_url,
                "filename": file.filename,
                "content_type": file.content_type
            }
            
        except Exception as e:
            print(f"Upload error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to upload file to storage")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 