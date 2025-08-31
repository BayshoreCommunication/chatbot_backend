#!/usr/bin/env python3
"""
Database model for accident intake data
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class AccidentIntakeModel(BaseModel):
    """Model for accident intake data"""
    
    # Basic incident information
    incident_date: Optional[str] = Field(None, description="Date of the accident (YYYY-MM-DD)")
    incident_time: Optional[str] = Field(None, description="Time of the accident (HH:MM)")
    location: Optional[str] = Field(None, description="Location of the accident")
    crash_type: Optional[str] = Field(None, description="Type of crash (rear-end, side impact, etc.)")
    vehicles_involved: Optional[int] = Field(None, description="Number of vehicles involved")
    
    # Injuries and medical care
    injuries: List[str] = Field(default_factory=list, description="List of injuries sustained")
    medical_care_to_date: Optional[str] = Field(None, description="Medical care received so far")
    
    # Police and evidence
    police_present: Optional[bool] = Field(None, description="Whether police were present")
    police_report_number: Optional[str] = Field(None, description="Police report number if available")
    photos_evidence: Optional[bool] = Field(None, description="Whether photos were taken")
    witnesses: List[str] = Field(default_factory=list, description="List of witnesses")
    
    # Insurance information
    client_insurer: Optional[str] = Field(None, description="Client's insurance company")
    other_insurer: Optional[str] = Field(None, description="Other driver's insurance company")
    adjuster_contacted: Optional[bool] = Field(None, description="Whether adjuster has contacted")
    
    # Client contact information
    client_name: Optional[str] = Field(None, description="Client's full name")
    client_email: Optional[str] = Field(None, description="Client's email address")
    client_phone: Optional[str] = Field(None, description="Client's phone number")
    
    # Metadata
    organization_id: str = Field(..., description="Organization ID")
    session_id: str = Field(..., description="Session ID")
    created_at: datetime = Field(default_factory=datetime.now, description="When the intake was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="When the intake was last updated")
    intake_completed: bool = Field(False, description="Whether the intake process is complete")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

def save_accident_intake(org_id: str, session_id: str, intake_data: dict) -> bool:
    """Save accident intake data to database"""
    try:
        from services.database import db
        
        # Create the intake document
        intake_doc = {
            "organization_id": org_id,
            "session_id": session_id,
            "incident_date": intake_data.get("incident_date"),
            "incident_time": intake_data.get("incident_time"),
            "location": intake_data.get("location"),
            "crash_type": intake_data.get("crash_type"),
            "vehicles_involved": intake_data.get("vehicles_involved"),
            "injuries": intake_data.get("injuries", []),
            "medical_care_to_date": intake_data.get("medical_care_to_date"),
            "police_present": intake_data.get("police_present"),
            "police_report_number": intake_data.get("police_report_number"),
            "photos_evidence": intake_data.get("photos_evidence"),
            "witnesses": intake_data.get("witnesses", []),
            "client_insurer": intake_data.get("client_insurer"),
            "other_insurer": intake_data.get("other_insurer"),
            "adjuster_contacted": intake_data.get("adjuster_contacted"),
            "client_name": intake_data.get("client_name"),
            "client_email": intake_data.get("client_email"),
            "client_phone": intake_data.get("client_phone"),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "intake_completed": True
        }
        
        # Upsert the document (update if exists, insert if not)
        result = db.accident_intakes.update_one(
            {"organization_id": org_id, "session_id": session_id},
            {"$set": intake_doc},
            upsert=True
        )
        
        print(f"[DATABASE] Accident intake saved for {org_id}:{session_id}")
        return True
        
    except Exception as e:
        print(f"[DATABASE] Error saving accident intake: {str(e)}")
        return False

def get_accident_intake(org_id: str, session_id: str) -> Optional[dict]:
    """Get accident intake data from database"""
    try:
        from services.database import db
        
        intake_doc = db.accident_intakes.find_one({
            "organization_id": org_id,
            "session_id": session_id
        })
        
        if intake_doc:
            # Convert ObjectId to string for JSON serialization
            intake_doc["_id"] = str(intake_doc["_id"])
            return intake_doc
        
        return None
        
    except Exception as e:
        print(f"[DATABASE] Error getting accident intake: {str(e)}")
        return None

def get_all_accident_intakes(org_id: str) -> List[dict]:
    """Get all accident intakes for an organization"""
    try:
        from services.database import db
        
        intakes = list(db.accident_intakes.find({
            "organization_id": org_id
        }).sort("created_at", -1))
        
        # Convert ObjectIds to strings
        for intake in intakes:
            intake["_id"] = str(intake["_id"])
        
        return intakes
        
    except Exception as e:
        print(f"[DATABASE] Error getting accident intakes: {str(e)}")
        return []

def get_accident_intake_stats(org_id: str) -> dict:
    """Get statistics for accident intakes"""
    try:
        from services.database import db
        
        pipeline = [
            {"$match": {"organization_id": org_id}},
            {"$group": {
                "_id": None,
                "total_intakes": {"$sum": 1},
                "completed_intakes": {"$sum": {"$cond": ["$intake_completed", 1, 0]}},
                "with_contact_info": {"$sum": {"$cond": [
                    {"$or": [
                        {"$ne": ["$client_name", None]},
                        {"$ne": ["$client_email", None]},
                        {"$ne": ["$client_phone", None]}
                    ]}, 1, 0]}},
                "with_insurance": {"$sum": {"$cond": [
                    {"$or": [
                        {"$ne": ["$client_insurer", None]},
                        {"$ne": ["$other_insurer", None]}
                    ]}, 1, 0]}}
            }}
        ]
        
        result = list(db.accident_intakes.aggregate(pipeline))
        
        if result:
            stats = result[0]
            return {
                "total_intakes": stats["total_intakes"],
                "completed_intakes": stats["completed_intakes"],
                "with_contact_info": stats["with_contact_info"],
                "with_insurance": stats["with_insurance"]
            }
        
        return {
            "total_intakes": 0,
            "completed_intakes": 0,
            "with_contact_info": 0,
            "with_insurance": 0
        }
        
    except Exception as e:
        print(f"[DATABASE] Error getting accident intake stats: {str(e)}")
        return {
            "total_intakes": 0,
            "completed_intakes": 0,
            "with_contact_info": 0,
            "with_insurance": 0
        }
