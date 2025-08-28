#!/usr/bin/env python3
"""
AI Training and Improvement Routes
"""
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from services.database import get_organization_by_api_key, db
from services.ai_improvement import AIImprovementService, get_improvement_recommendations
from services.langchain.engine import add_document
from datetime import datetime
import json

router = APIRouter()

# Dependency for API key  validation
from fastapi import Header

async def get_organization_from_api_key_header(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get organization from API key in header"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

class AIBehaviorUpdate(BaseModel):
    ai_behavior: str
    personality_traits: Optional[List[str]] = []
    tone: Optional[str] = "professional"
    expertise_areas: Optional[List[str]] = []

class TrainingDataUpload(BaseModel):
    training_type: str  # "faq", "services", "policies", "scripts"
    content: str
    title: Optional[str] = None
    category: Optional[str] = None

class ResponseTemplate(BaseModel):
    template_name: str
    scenario: str
    response_template: str
    variables: Optional[List[str]] = []

@router.get("/improvement-analysis")
async def get_improvement_analysis(
    organization=Depends(get_organization_from_api_key_header)
):
    """Analyze current AI performance and provide improvement recommendations"""
    try:
        api_key = organization["api_key"]
        
        # Get current settings
        current_settings = organization.get("chat_widget_settings", {})
        ai_behavior = current_settings.get("ai_behavior", "")
        
        # Analyze current state
        analysis = {
            "current_state": {
                "has_ai_behavior": bool(ai_behavior),
                "ai_behavior_length": len(ai_behavior) if ai_behavior else 0,
                "has_custom_prompts": bool(organization.get("custom_prompts")),
                "knowledge_base_size": organization.get("knowledge_base_size", 0),
                "training_data_types": list(organization.get("training_data", {}).keys())
            },
            "recommendations": get_improvement_recommendations(api_key),
            "quick_wins": [
                {
                    "action": "Define AI Personality",
                    "description": "Give your AI a clear personality and tone",
                    "impact": "High",
                    "effort": "Low"
                },
                {
                    "action": "Upload Service Information", 
                    "description": "Add detailed information about your services",
                    "impact": "High",
                    "effort": "Medium"
                },
                {
                    "action": "Create Response Templates",
                    "description": "Set up templates for common scenarios",
                    "impact": "Medium",
                    "effort": "Low"
                }
            ],
            "industry_templates": {
                "law_firm": "Legal practice template with proper disclaimers",
                "medical_practice": "Healthcare template with HIPAA compliance",
                "restaurant": "Hospitality template for reservations and menu",
                "retail": "Sales-focused template for product inquiries",
                "consulting": "Professional services template"
            }
        }
        
        return {"status": "success", "analysis": analysis}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update-ai-behavior")
async def update_ai_behavior(
    ai_data: AIBehaviorUpdate,
    organization=Depends(get_organization_from_api_key_header)
):
    """Update AI behavior and personality"""
    try:
        api_key = organization["api_key"]
        
        # Build enhanced AI behavior prompt
        enhanced_behavior = f"""
{ai_data.ai_behavior}

PERSONALITY TRAITS: {', '.join(ai_data.personality_traits) if ai_data.personality_traits else 'Professional, helpful, knowledgeable'}

TONE: {ai_data.tone}

EXPERTISE AREAS: {', '.join(ai_data.expertise_areas) if ai_data.expertise_areas else 'General assistance'}

RESPONSE GUIDELINES:
- Always maintain the specified tone and personality
- Use your expertise to provide accurate information
- Be helpful and solution-oriented
- Ask follow-up questions when appropriate
- Offer to schedule appointments or consultations when relevant
"""
        
        # Save to database
        success = AIImprovementService.update_ai_behavior(api_key, enhanced_behavior)
        
        if success:
            return {
                "status": "success",
                "message": "AI behavior updated successfully",
                "ai_behavior_preview": enhanced_behavior[:200] + "..." if len(enhanced_behavior) > 200 else enhanced_behavior
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update AI behavior")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-training-data")
async def upload_training_data(
    training_data: TrainingDataUpload,
    organization=Depends(get_organization_from_api_key_header)
):
    """Upload custom training data to improve AI responses"""
    try:
        api_key = organization["api_key"]
        
        # Process and save training data
        data_to_save = {
            "title": training_data.title,
            "content": training_data.content,
            "category": training_data.category,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        # Save to organization's training data
        success = AIImprovementService.save_training_data(
            api_key, 
            training_data.training_type, 
            data_to_save
        )
        
        if success:
            # Also add to vector database for retrieval
            result = add_document(text=training_data.content, api_key=api_key)
            
            return {
                "status": "success",
                "message": f"Training data uploaded successfully for {training_data.training_type}",
                "vector_db_result": result
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save training data")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-document-for-training")
async def upload_document_for_training(
    file: UploadFile = File(...),
    training_type: str = Form(...),
    description: Optional[str] = Form(None),
    organization=Depends(get_organization_from_api_key_header)
):
    """Upload a document (PDF, TXT) to train the AI"""
    try:
        api_key = organization["api_key"]
        
        # Save file temporarily
        file_path = f"temp_training_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Add to vector database
        result = add_document(file_path=file_path, api_key=api_key)
        
        # Save metadata
        training_metadata = {
            "filename": file.filename,
            "training_type": training_type,
            "description": description,
            "file_size": len(content),
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        AIImprovementService.save_training_data(api_key, f"document_{training_type}", training_metadata)
        
        # Clean up temp file
        import os
        os.remove(file_path)
        
        return {
            "status": "success",
            "message": f"Document uploaded and processed for {training_type} training",
            "document_info": {
                "filename": file.filename,
                "size": len(content),
                "type": training_type
            },
            "processing_result": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/training-templates/{industry}")
async def get_training_templates(
    industry: str,
    organization=Depends(get_organization_from_api_key_header)
):
    """Get industry-specific training templates"""
    try:
        from services.ai_improvement import BUSINESS_TRAINING_TEMPLATES
        
        if industry not in BUSINESS_TRAINING_TEMPLATES:
            available = list(BUSINESS_TRAINING_TEMPLATES.keys())
            raise HTTPException(
                status_code=404, 
                detail=f"Industry template not found. Available: {available}"
            )
        
        template = BUSINESS_TRAINING_TEMPLATES[industry]
        
        # Customize template with organization name
        org_name = organization.get("name", "Your Business")
        customized_template = {
            "industry": industry,
            "identity": template["identity"].format(firm_name=org_name, practice_name=org_name, restaurant_name=org_name),
            "tone": template["tone"],
            "objectives": template["objectives"],
            "sample_prompts": AIImprovementService.CARTER_INJURY_LAW_PROMPTS if industry == "law_firm" else {}
        }
        
        return {
            "status": "success",
            "template": customized_template,
            "industry": industry
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/response-templates")
async def save_response_template(
    template: ResponseTemplate,
    organization=Depends(get_organization_from_api_key_header)
):
    """Save a custom response template"""
    try:
        api_key = organization["api_key"]
        
        # Get existing templates
        templates = organization.get("response_templates", {})
        
        # Add new template
        templates[template.template_name] = {
            "scenario": template.scenario,
            "response_template": template.response_template,
            "variables": template.variables,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Save to database
        db.organizations.update_one(
            {"_id": organization["_id"]},
            {
                "$set": {
                    "response_templates": templates,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "status": "success",
            "message": f"Response template '{template.template_name}' saved successfully",
            "template_count": len(templates)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/response-templates")
async def get_response_templates(
    organization=Depends(get_organization_from_api_key_header)
):
    """Get all saved response templates"""
    try:
        templates = organization.get("response_templates", {})
        
        return {
            "status": "success",
            "templates": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/training-status")
async def get_training_status(
    organization=Depends(get_organization_from_api_key_header)
):
    """Get current training status and progress"""
    try:
        current_settings = organization.get("chat_widget_settings", {})
        training_data = organization.get("training_data", {})
        response_templates = organization.get("response_templates", {})
        
        status = {
            "ai_behavior_configured": bool(current_settings.get("ai_behavior")),
            "training_data_types": list(training_data.keys()),
            "training_data_count": len(training_data),
            "response_templates_count": len(response_templates),
            "knowledge_base_size": organization.get("knowledge_base_size", 0),
            "last_updated": organization.get("updated_at", "Never").isoformat() if hasattr(organization.get("updated_at", "Never"), 'isoformat') else str(organization.get("updated_at", "Never")),
            "completeness_score": calculate_training_completeness(organization)
        }
        
        return {"status": "success", "training_status": status}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def calculate_training_completeness(organization: dict) -> int:
    """Calculate training completeness as a percentage"""
    score = 0
    
    # AI behavior configured (30 points)
    if organization.get("chat_widget_settings", {}).get("ai_behavior"):
        score += 30
    
    # Training data uploaded (25 points)
    if organization.get("training_data"):
        score += 25
    
    # Response templates created (20 points)
    if organization.get("response_templates"):
        score += 20
    
    # Knowledge base has content (15 points)
    if organization.get("knowledge_base_size", 0) > 0:
        score += 15
    
    # Custom prompts defined (10 points)
    if organization.get("custom_prompts"):
        score += 10
    
    return score
