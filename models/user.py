from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: str
    organization_name: str
    website: Optional[str] = None
    company_organization_type: Optional[str] = None
    has_paid_subscription: bool = False

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserGoogle(UserBase):
    google_id: str

class User(UserBase):
    id: str
    google_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True 