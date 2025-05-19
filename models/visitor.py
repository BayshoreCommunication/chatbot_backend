from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class Visitor(BaseModel):
    """Visitor model for tracking chatbot users across organizations"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    session_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "org_123456",
                "session_id": "sess_abcdef",
                "name": "John Doe",
                "email": "john@example.com",
                "metadata": {
                    "browser": "Chrome",
                    "referrer": "google.com"
                }
            }
        }

class ConversationMessage(BaseModel):
    """Model for storing conversation messages"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    visitor_id: str
    organization_id: str
    session_id: str
    role: str  # user or assistant
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "visitor_id": "vis_123456",
                "organization_id": "org_123456",
                "session_id": "sess_abcdef",
                "role": "user",
                "content": "How can I schedule an appointment?",
                "metadata": {
                    "mode": "faq",
                    "intent": "appointment_scheduling"
                }
            }
        } 