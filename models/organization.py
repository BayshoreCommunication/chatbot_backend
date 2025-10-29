from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
import uuid
from bson import ObjectId
from pydantic_core import CoreSchema, core_schema

class PyObjectId(str):
    """Custom type for handling MongoDB ObjectId as string"""
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any
    ) -> CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str):
            return ObjectId(value)
        raise ValueError("Invalid ObjectId")

class Organization(BaseModel):
    """Organization model for SaaS multi-tenancy"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    api_key: str
    user_id: str  # Add user_id field
    subscription_tier: str = "free"  # free, standard, premium
    subscription_status: str = "active"  # active, cancelled, suspended
    stripe_subscription_id: str | None = Field(default=None)  # Explicit None default
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    pinecone_namespace: str  # Namespace in vector DB for organization's data
    chat_widget_settings: dict = Field(default_factory=lambda: {
        "name": "Bay AI",
        "selectedColor": "#4f46e5",  # Changed to hex color
        "leadCapture": True,
        "botBehavior": "2",
        "avatarUrl": None,
        "is_bot_connected": False,
        "ai_behavior": "You are a helpful and friendly AI assistant. You should be professional, concise, and focus on providing accurate information while maintaining a warm and engaging tone.",
        "intro_video": {
            "enabled": False,
            "video_url": None,
            "video_filename": None,
            "autoplay": True,
            "duration": 10,
            "show_on_first_visit": True
        }
    })
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corporation",
                "api_key": "org_sk_1234567890abcdef",
                "subscription_tier": "standard",
                "subscription_status": "active",
                "user_id": "user_123",
                "stripe_subscription_id": "sub_1234567890",
                "chat_widget_settings": {
                    "name": "Bay AI",
                    "selectedColor": "#4f46e5",  # Changed to hex color
                    "leadCapture": True,
                    "botBehavior": "2",
                    "avatarUrl": None,
                    "is_bot_connected": False,
                    "ai_behavior": "You are a helpful and friendly AI assistant. You should be professional, concise, and focus on providing accurate information while maintaining a warm and engaging tone.",
                    "intro_video": {
                        "enabled": False,
                        "video_url": None,
                        "video_filename": None,
                        "autoplay": True,
                        "duration": 10,
                        "show_on_first_visit": True
                    }
                }
            }
        }

class OrganizationCreate(BaseModel):
    """Schema for creating a new organization"""
    name: str
    subscription_tier: str = "free"
    user_id: str  # Add user_id field
    stripe_subscription_id: str | None = Field(default=None)  # Explicit None default

class OrganizationUpdate(BaseModel):
    """Schema for updating an organization"""
    name: Optional[str] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    stripe_subscription_id: str | None = Field(default=None)  # Explicit None default
    settings: Optional[dict] = None

class User(BaseModel):
    """User model for organization members"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str
    name: str
    email: str
    role: str = "member"  # admin, member
    created_at: datetime = Field(default_factory=datetime.now)

class Subscription(BaseModel):
    """Subscription model for tracking payment and subscription details"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "organization_id": "org_456",
                "stripe_subscription_id": "sub_789",
                "payment_amount": 79.00,
                "subscription_tier": "professional",
                "current_period_start": "2024-03-20T00:00:00Z",
                "current_period_end": "2024-04-20T00:00:00Z"
            }
        }
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    organization_id: str
    stripe_subscription_id: str
    payment_amount: float
    subscription_tier: str
    subscription_status: str = "active"
    current_period_start: datetime
    current_period_end: datetime
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now) 