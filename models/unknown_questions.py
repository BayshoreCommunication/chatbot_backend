"""
Unknown Questions Model
======================
This model stores questions that the chatbot couldn't answer from training data,
along with the AI-generated responses, for each organization.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class UnknownQuestion(BaseModel):
    """Model for storing unknown questions and responses"""
    
    id: Optional[str] = Field(None, alias="_id")
    organization_id: str = Field(..., description="Organization ID this question belongs to")
    session_id: str = Field(..., description="Chat session ID")
    visitor_id: Optional[str] = Field(None, description="Visitor ID if available")
    
    # Question details
    question: str = Field(..., description="The user's original question")
    question_normalized: str = Field(..., description="Normalized version for matching")
    
    # Response details
    ai_response: str = Field(..., description="AI-generated response")
    response_quality: Optional[str] = Field("unknown", description="Quality rating: good, poor, unknown")
    
    # Context information
    user_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User information when question was asked")
    conversation_context: Optional[List[Dict]] = Field(default_factory=list, description="Previous conversation messages")
    
    # Search results
    knowledge_base_results: Optional[List[Dict]] = Field(default_factory=list, description="What was found in knowledge base")
    similarity_scores: Optional[List[float]] = Field(default_factory=list, description="Similarity scores from vector search")
    max_similarity: Optional[float] = Field(0.0, description="Highest similarity score found")
    
    # Classification
    question_category: Optional[str] = Field("general", description="Category of question: legal, appointment, general, etc.")
    is_answered_well: Optional[bool] = Field(None, description="Whether the AI response was satisfactory")
    needs_human_review: bool = Field(True, description="Whether this needs human review")
    
    # Status tracking
    status: str = Field("new", description="Status: new, reviewed, added_to_training, ignored")
    reviewed_by: Optional[str] = Field(None, description="Admin user who reviewed this")
    reviewed_at: Optional[datetime] = Field(None, description="When this was reviewed")
    
    # Improvement tracking
    improved_answer: Optional[str] = Field(None, description="Human-provided better answer")
    added_to_training: bool = Field(False, description="Whether this was added to training data")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Frequency tracking
    frequency_count: int = Field(1, description="How many times this question was asked")
    last_asked_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "organization_id": "org_123",
                "session_id": "session_456", 
                "question": "Do you handle dog bite cases in Florida?",
                "question_normalized": "handle dog bite cases florida",
                "ai_response": "Yes, we handle dog bite cases. Dog bite laws vary by state...",
                "response_quality": "good",
                "user_context": {
                    "name": "John Doe",
                    "location": "Florida"
                },
                "knowledge_base_results": [],
                "max_similarity": 0.3,
                "question_category": "legal",
                "is_answered_well": False,
                "needs_human_review": True,
                "status": "new",
                "frequency_count": 1
            }
        }

class UnknownQuestionStats(BaseModel):
    """Statistics for unknown questions by organization"""
    
    organization_id: str
    total_unknown_questions: int = 0
    new_questions: int = 0
    reviewed_questions: int = 0
    added_to_training: int = 0
    ignored_questions: int = 0
    
    # Quality breakdown
    good_ai_responses: int = 0
    poor_ai_responses: int = 0
    needs_improvement: int = 0
    
    # Category breakdown
    legal_questions: int = 0
    appointment_questions: int = 0
    general_questions: int = 0
    other_questions: int = 0
    
    # Time period
    period_start: datetime
    period_end: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UnknownQuestionUpdate(BaseModel):
    """Model for updating unknown questions"""
    
    response_quality: Optional[str] = None
    is_answered_well: Optional[bool] = None
    improved_answer: Optional[str] = None
    status: Optional[str] = None
    reviewed_by: Optional[str] = None
    question_category: Optional[str] = None
    needs_human_review: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "response_quality": "good",
                "is_answered_well": True,
                "status": "reviewed",
                "reviewed_by": "admin_user_123"
            }
        }

class UnknownQuestionFilters(BaseModel):
    """Filters for querying unknown questions"""
    
    organization_id: str
    status: Optional[str] = None
    question_category: Optional[str] = None
    needs_human_review: Optional[bool] = None
    is_answered_well: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_frequency: Optional[int] = None
    search_query: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
