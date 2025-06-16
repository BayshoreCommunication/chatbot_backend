from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class Conversation(BaseModel):
    id: Optional[str] = None
    organization_id: str
    visitor_id: str
    session_id: str
    role: str
    content: str
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True 