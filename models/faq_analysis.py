from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class FAQAnalysisReport(BaseModel):
    """Model for storing FAQ Intelligence analysis reports"""
    id: Optional[str] = None
    organization_id: str
    analysis_type: str  # "full" or "quick"
    readiness_score: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Analysis results
    alerts: List[Dict[str, Any]] = []
    suggestions: List[Dict[str, Any]] = []
    analysis: Dict[str, Any] = {}
    
    # Stats for comparison
    stats: Dict[str, Any] = {
        "faq_count": 0,
        "document_count": 0,
        "conversation_count": 0,
        "profile_complete": False,
        "missing_fields": []
    }
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AnalysisHistory(BaseModel):
    """Model for analysis history with progress tracking"""
    organization_id: str
    reports: List[FAQAnalysisReport]
    latest_score: int
    score_trend: str  # "improving", "declining", "stable"
    last_analysis_date: datetime
    total_analyses: int
    
    class Config:
        from_attributes = True
