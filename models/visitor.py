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
    # Agent takeover fields
    is_agent_mode: bool = Field(default=False)
    agent_takeover_at: Optional[datetime] = None
    agent_id: Optional[str] = None  # ID of the agent who took over
    
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
                },
                "is_agent_mode": False,
                "agent_takeover_at": None,
                "agent_id": None
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