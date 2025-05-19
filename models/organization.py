from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

class Organization(BaseModel):
    """Organization model for SaaS multi-tenancy"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    api_key: str
    subscription_tier: str = "free"  # free, standard, premium
    subscription_status: str = "active"  # active, cancelled, suspended
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    pinecone_namespace: str  # Namespace in vector DB for organization's data
    settings: dict = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corporation",
                "api_key": "org_sk_1234567890abcdef",
                "subscription_tier": "standard",
                "subscription_status": "active"
            }
        }

class OrganizationCreate(BaseModel):
    """Schema for creating a new organization"""
    name: str
    subscription_tier: str = "free"

class OrganizationUpdate(BaseModel):
    """Schema for updating an organization"""
    name: Optional[str] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    settings: Optional[dict] = None

class User(BaseModel):
    """User model for organization members"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    name: str
    email: str
    role: str = "member"  # admin, member
    created_at: datetime = Field(default_factory=datetime.now) 