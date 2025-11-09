from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: str
    organization_name: Optional[str] = None  # Made optional with default
    website: Optional[str] = None
    company_organization_type: Optional[str] = None
    has_paid_subscription: bool = False
    
    # Subscription tracking fields
    subscription_type: Optional[str] = "free"  # free, free_trial, professional, enterprise
    subscription_start_date: Optional[datetime] = None
    subscription_end_date: Optional[datetime] = None
    billing_cycle: Optional[str] = None  # monthly, yearly
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    free_trial_used: bool = False  # Track if user already used their free trial
    last_reminder_sent: Optional[datetime] = None  # Track when last expiry reminder was sent

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