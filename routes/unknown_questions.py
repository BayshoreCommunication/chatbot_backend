"""
Unknown Questions API Routes
===========================
API endpoints for managing unknown questions in the dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import List, Optional
from datetime import datetime, timedelta

from models.unknown_questions import (
    UnknownQuestion, 
    UnknownQuestionStats, 
    UnknownQuestionUpdate,
    UnknownQuestionFilters
)
from services.unknown_questions_service import UnknownQuestionsService
from services.database import get_organization_by_api_key

router = APIRouter(prefix="/api/unknown-questions", tags=["Unknown Questions"])

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

@router.get("/", response_model=dict)
async def get_unknown_questions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: new, reviewed, ignored, added_to_training"),
    category: Optional[str] = Query(None, description="Filter by category: legal, appointment, contact, pricing, general"),
    needs_review: Optional[bool] = Query(None, description="Filter by needs_human_review"),
    answered_well: Optional[bool] = Query(None, description="Filter by is_answered_well"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    min_frequency: Optional[int] = Query(None, ge=1, description="Minimum frequency count"),
    search: Optional[str] = Query(None, description="Search in questions and answers"),
    organization=Depends(get_organization_from_api_key)
):
    """Get unknown questions for the user's organization"""
    
    try:
        org_id = str(organization["_id"])
        
        # Build filters
        filters = UnknownQuestionFilters(
            organization_id=org_id,
            status=status,
            question_category=category,
            needs_human_review=needs_review,
            is_answered_well=answered_well,
            date_from=date_from,
            date_to=date_to,
            min_frequency=min_frequency,
            search_query=search
        )
        
        # Get questions
        result = UnknownQuestionsService.get_unknown_questions(filters, page, limit)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching unknown questions: {str(e)}")

@router.get("/stats", response_model=dict)
async def get_unknown_questions_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days for statistics"),
    organization=Depends(get_organization_from_api_key)
):
    """Get statistics for unknown questions"""
    
    try:
        org_id = str(organization["_id"])
        
        # Get stats
        stats = UnknownQuestionsService.get_unknown_question_stats(org_id, days)
        
        return {
            "success": True,
            "data": stats.dict()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching statistics: {str(e)}")

@router.put("/{question_id}", response_model=dict)
async def update_unknown_question(
    question_id: str,
    update_data: UnknownQuestionUpdate,
    organization=Depends(get_organization_from_api_key)
):
    """Update an unknown question"""
    
    try:
        # Add reviewer information
        update_data.reviewed_by = str(organization["_id"])
        
        # Update question
        success = UnknownQuestionsService.update_unknown_question(question_id, update_data)
        
        if not success:
            raise HTTPException(status_code=404, detail="Question not found or update failed")
        
        return {
            "success": True,
            "message": "Question updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating question: {str(e)}")

@router.delete("/{question_id}", response_model=dict)
async def delete_unknown_question(
    question_id: str,
    organization=Depends(get_organization_from_api_key)
):
    """Delete an unknown question"""
    
    try:
        success = UnknownQuestionsService.delete_unknown_question(question_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Question not found")
        
        return {
            "success": True,
            "message": "Question deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting question: {str(e)}")

@router.post("/{question_id}/add-to-training", response_model=dict)
async def add_question_to_training(
    question_id: str,
    improved_answer: Optional[str] = None,
    organization=Depends(get_organization_from_api_key)
):
    """Add an unknown question and its answer to the training data"""
    
    try:
        # Get the question first
        filters = UnknownQuestionFilters(organization_id="temp")  # Will be filtered by question_id
        questions_result = UnknownQuestionsService.get_unknown_questions(filters, 1, 1)
        
        if not questions_result["questions"]:
            raise HTTPException(status_code=404, detail="Question not found")
        
        question = questions_result["questions"][0]
        
        # Verify access to this organization's question
        if str(organization["_id"]) != question["organization_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Use improved answer if provided, otherwise use AI response
        answer_to_add = improved_answer if improved_answer else question["ai_response"]
        
        # Here you would integrate with your document upload system
        # For now, we'll just mark it as added to training
        
        # Update the question status
        update_data = UnknownQuestionUpdate(
            status="added_to_training",
            reviewed_by=str(organization["_id"]),
            improved_answer=improved_answer
        )
        
        success = UnknownQuestionsService.update_unknown_question(question_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update question status")
        
        # TODO: Integrate with document upload/training system
        # add_to_knowledge_base(question["question"], answer_to_add, organization["id"])
        
        return {
            "success": True,
            "message": "Question added to training data successfully",
            "data": {
                "question": question["question"],
                "answer": answer_to_add
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding to training: {str(e)}")

@router.get("/categories", response_model=dict)
async def get_question_categories(
    organization=Depends(get_organization_from_api_key)
):
    """Get available question categories"""
    
    categories = [
        {"value": "legal", "label": "Legal Questions", "description": "Questions about legal matters, cases, laws"},
        {"value": "appointment", "label": "Appointments", "description": "Scheduling, booking, consultation requests"},
        {"value": "contact", "label": "Contact Info", "description": "Phone, email, address, office hours"},
        {"value": "pricing", "label": "Pricing", "description": "Costs, fees, payment questions"},
        {"value": "general", "label": "General", "description": "Other general inquiries"}
    ]
    
    return {
        "success": True,
        "data": categories
    }

@router.get("/export", response_model=dict)
async def export_unknown_questions(
    format: str = Query("json", description="Export format: json, csv"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    organization=Depends(get_organization_from_api_key)
):
    """Export unknown questions for analysis"""
    
    try:
        org_id = str(organization["_id"])
        
        # Build filters
        filters = UnknownQuestionFilters(
            organization_id=org_id,
            status=status,
            question_category=category,
            date_from=date_from,
            date_to=date_to
        )
        
        # Get all questions (no pagination for export)
        result = UnknownQuestionsService.get_unknown_questions(filters, 1, 10000)
        
        if format.lower() == "csv":
            # TODO: Implement CSV export
            return {
                "success": False,
                "message": "CSV export not yet implemented"
            }
        
        return {
            "success": True,
            "data": result["questions"],
            "total_count": result["total_count"],
            "exported_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting questions: {str(e)}")

@router.post("/bulk-action", response_model=dict)
async def bulk_action_unknown_questions(
    question_ids: List[str],
    action: str = Query(..., description="Action: review, ignore, delete, add_to_training"),
    organization=Depends(get_organization_from_api_key)
):
    """Perform bulk actions on multiple unknown questions"""
    
    try:
        if not question_ids:
            raise HTTPException(status_code=400, detail="No question IDs provided")
        
        success_count = 0
        errors = []
        
        for question_id in question_ids:
            try:
                if action == "review":
                    update_data = UnknownQuestionUpdate(
                        status="reviewed",
                        reviewed_by=str(organization["_id"]),
                        needs_human_review=False
                    )
                    UnknownQuestionsService.update_unknown_question(question_id, update_data)
                    
                elif action == "ignore":
                    update_data = UnknownQuestionUpdate(
                        status="ignored",
                        reviewed_by=str(organization["_id"]),
                        needs_human_review=False
                    )
                    UnknownQuestionsService.update_unknown_question(question_id, update_data)
                    
                elif action == "delete":
                    UnknownQuestionsService.delete_unknown_question(question_id)
                    
                elif action == "add_to_training":
                    update_data = UnknownQuestionUpdate(
                        status="added_to_training",
                        reviewed_by=str(organization["_id"])
                    )
                    UnknownQuestionsService.update_unknown_question(question_id, update_data)
                    
                else:
                    errors.append(f"Invalid action: {action}")
                    continue
                
                success_count += 1
                
            except Exception as e:
                errors.append(f"Error processing {question_id}: {str(e)}")
        
        return {
            "success": True,
            "message": f"Processed {success_count} questions successfully",
            "data": {
                "success_count": success_count,
                "error_count": len(errors),
                "errors": errors[:10]  # Limit error messages
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing bulk action: {str(e)}")
