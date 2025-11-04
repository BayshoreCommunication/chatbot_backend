"""
FAQ Intelligence API Route
Real-time analysis with history tracking
Analyzes organization setup and stores last 5 reports
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional, List
from services.faq_intelligence import FAQIntelligenceService
from services.database import get_organization_by_api_key, db
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Collection for storing analysis reports
analysis_reports = db.faq_analysis_reports


async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization


@router.get("/analyze")
async def analyze_faq_readiness(
    organization=Depends(get_organization_from_api_key)
):
    """
    🔍 Real-time FAQ Intelligence Analysis
    
    Checks:
    1. ✅ Organization profile completeness (name, website, company type)
    2. ✅ FAQ availability and quality
    3. ✅ Website content for training
    4. ✅ Uploaded documents (PDFs)
    5. ✅ Conversation history patterns
    
    Returns:
    - Alerts for missing critical information
    - Suggestions for missing FAQs
    - Readiness score (0-100)
    - Actionable recommendations
    
    NO DATA IS STORED - Analysis runs in real-time only when requested
    """
    
    try:
        print(f"\n{'='*60}")
        print(f"🔍 [FAQ-INTELLIGENCE] Starting real-time analysis")
        print(f"Organization: {organization.get('organization_name', 'Unknown')}")
        print(f"{'='*60}\n")
        
        # Get OpenAI API key
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise HTTPException(
                status_code=500,
                detail="OpenAI API key not configured. Please add OPENAI_API_KEY to your .env file"
            )
        
        # Initialize service
        intelligence = FAQIntelligenceService(openai_key)
        
        # Collect organization data (using organization["id"] to match FAQ routes)
        org_id = organization["id"]  # Same field as FAQ list API uses
        
        # Get user data to fetch organization_name, website, company_organization_type
        # These fields are stored in the users collection, not organizations collection
        user_id = organization.get("user_id")
        user_data = {}
        if user_id:
            user = db.users.find_one({"_id": ObjectId(user_id)} if len(str(user_id)) == 24 else {"id": user_id})
            if user:
                user_data = {
                    "organization_name": user.get("organization_name"),
                    "website": user.get("website"),
                    "company_organization_type": user.get("company_organization_type")
                }
        
        print(f"📊 User data: {user_data}")
        
        # 1. Get existing FAQs using same query structure as FAQ list API
        # Query matches: {"org_id": org_id, "is_active": True}
        faqs = list(db.faqs.find({
            "org_id": org_id,
            "is_active": True
        }))
        
        # Transform FAQs to match FAQ list API response format
        existing_faqs = []
        for faq in faqs:
            # FAQ structure: question, response (not answer)
            existing_faqs.append({
                "question": faq.get("question", ""),
                "answer": faq.get("response", "")  # response field from FAQ, mapped to answer for analysis
            })
        print(f"📋 Found {len(existing_faqs)} active FAQs")
        
        # 2. Get conversation history (last 100)
        # Using organization_id field from conversations collection
        conversations = list(db.conversations.find({
            "organization_id": org_id
        }).sort("created_at", -1).limit(100))
        
        conversation_data = [
            {
                "role": conv.get("role", "user"),
                "content": conv.get("content", "")
            }
            for conv in conversations
        ]
        print(f"💬 Found {len(conversation_data)} conversations")
        
        # 3. Get uploaded documents from upload_history collection
        # Separate website URLs from actual documents (PDFs, CSV, etc.)
        all_uploads = list(db.upload_history.find({
            "org_id": org_id,
            "status": "Used"  # Only successful uploads
        }))
        
        # Separate documents by type:
        # - type="url" → Website training (use for website analysis)
        # - type="pdf", "csv", etc. → Documents (use for document analysis)
        doc_data = []
        website_url = user_data.get("website")  # Primary website from user profile
        
        for upload in all_uploads:
            upload_type = upload.get("type", "")
            
            # Documents (PDFs, CSV, etc.) - NOT URLs
            if upload_type in ["pdf", "csv", "text"] and upload_type != "url":
                doc_info = {}
                
                # For file uploads
                if upload.get("file_name"):
                    doc_info["file_path"] = upload.get("file_name")
                    doc_info["filename"] = upload.get("file_name")
                    doc_info["type"] = upload_type
                
                # For text content
                elif upload_type == "text":
                    doc_info["type"] = "text"
                    doc_info["filename"] = "text_content"
                
                if doc_info:
                    doc_data.append(doc_info)
            
            # Website URL uploads (type="url") - use for website analysis
            elif upload_type == "url" and upload.get("url"):
                # If no website in user profile, use the first uploaded URL as website
                if not website_url:
                    website_url = upload.get("url")
                    print(f"🌐 Using uploaded URL as website: {website_url}")
        
        print(f"📄 Found {len(doc_data)} actual documents (PDFs, CSVs)")
        print(f"🌐 Website URL: {website_url}")
        
        # 4. Prepare organization data (using exact field names from user model)
        # These fields come from the users collection, not organizations collection
        # Use detected website_url (from profile OR first uploaded URL)
        org_data = {
            "organization_name": user_data.get("organization_name"),  # From users collection
            "website": website_url,  # From user profile OR first uploaded URL
            "company_organization_type": user_data.get("company_organization_type")  # From users collection
        }
        
        print(f"📋 Organization data for analysis: {org_data}")
        
        # Run real-time analysis
        result = await intelligence.analyze_organization(
            organization=org_data,
            existing_faqs=existing_faqs,
            conversation_history=conversation_data,
            uploaded_documents=doc_data
        )
        
        print(f"\n{'='*60}")
        print(f"✅ [FAQ-INTELLIGENCE] Analysis complete")
        print(f"Readiness Score: {result['readiness_score']}/100")
        print(f"Alerts: {len(result['alerts'])}")
        print(f"Suggestions: {len(result['suggestions'])}")
        print(f"{'='*60}\n")
        
        # Save report to database (keep last 5)
        report = {
            "organization_id": org_id,
            "analysis_type": "full",
            "readiness_score": result['readiness_score'],
            "timestamp": datetime.utcnow(),
            "alerts": result['alerts'],
            "suggestions": result['suggestions'],
            "analysis": result['analysis'],
            "stats": {
                "faq_count": len(existing_faqs),
                "document_count": len(doc_data),
                "conversation_count": len(conversation_data),
                "profile_complete": len(result['analysis'].get('profile', {}).get('missing_critical_fields', [])) == 0,
                "missing_fields": result['analysis'].get('profile', {}).get('missing_critical_fields', [])
            }
        }
        
        # Insert new report
        analysis_reports.insert_one(report)
        
        # Keep only last 5 reports per organization
        all_reports = list(analysis_reports.find({
            "organization_id": org_id
        }).sort("timestamp", -1))
        
        if len(all_reports) > 5:
            # Delete older reports
            reports_to_delete = all_reports[5:]
            for old_report in reports_to_delete:
                analysis_reports.delete_one({"_id": old_report["_id"]})
        
        print(f"💾 Report saved. Total reports for org: {min(len(all_reports), 5)}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick-check")
async def quick_readiness_check(
    organization=Depends(get_organization_from_api_key)
):
    """
    ⚡ Quick readiness check (no AI analysis)
    
    Fast check for:
    - Organization profile completeness
    - FAQ count
    - Document count
    
    Use this for dashboard widgets or frequent checks
    """
    
    try:
        org_id = organization["id"]  # Same field as FAQ list API uses
        
        # Get user data (organization_name, website, company_organization_type are in users collection)
        user_id = organization.get("user_id")
        user_data = {}
        if user_id:
            user = db.users.find_one({"_id": ObjectId(user_id)} if len(str(user_id)) == 24 else {"id": user_id})
            if user:
                user_data = user
        
        # Quick checks
        missing_fields = []
        alerts = []
        
        # Check profile (using exact field names from user model - stored in users collection)
        if not user_data.get("organization_name"):
            missing_fields.append("organization_name")
            alerts.append({
                "type": "critical",
                "message": "⚠️ Organization name is missing",
                "action": "Add your organization name in settings"
            })
        
        if not user_data.get("website"):
            missing_fields.append("website")
            alerts.append({
                "type": "warning",
                "message": "⚠️ Website URL is missing",
                "action": "Add your website URL to enable content analysis"
            })
        
        if not user_data.get("company_organization_type"):
            missing_fields.append("company_organization_type")
            alerts.append({
                "type": "warning",
                "message": "⚠️ Company type is missing",
                "action": "Specify your company/organization type for better AI suggestions"
            })
        
        # Check FAQs using same query as FAQ list API
        faq_count = db.faqs.count_documents({
            "org_id": org_id,
            "is_active": True
        })
        
        if faq_count == 0:
            alerts.append({
                "type": "critical",
                "message": "❌ No FAQs found",
                "action": "Add at least 5-10 FAQs to your knowledge base"
            })
        elif faq_count < 5:
            alerts.append({
                "type": "warning",
                "message": f"⚠️ Only {faq_count} FAQ(s) found",
                "action": "Add more FAQs for comprehensive coverage"
            })
        
        # Check documents from upload_history (PDFs, CSVs - NOT URLs)
        # URLs (type="url") are for website training, not documents
        all_uploads = list(db.upload_history.find({
            "org_id": org_id,
            "status": "Used"
        }))
        
        # Count only actual documents (PDFs, CSV, text) - NOT URLs
        doc_count = sum(1 for upload in all_uploads if upload.get("type") in ["pdf", "csv", "text"])
        
        # Check if website is available (from user profile OR uploaded URLs)
        has_website = bool(user_data.get("website"))
        if not has_website:
            # Check if any URL was uploaded (type="url")
            has_website = any(upload.get("type") == "url" for upload in all_uploads)
        
        if doc_count == 0:
            alerts.append({
                "type": "warning",
                "message": "⚠️ No training documents found",
                "action": "Upload PDF documents to improve AI responses"
            })
        
        # Calculate quick score
        score = 0
        if not missing_fields:
            score += 30
        elif len(missing_fields) == 1:
            score += 20
        elif len(missing_fields) == 2:
            score += 10
        
        if faq_count >= 10:
            score += 40
        elif faq_count >= 5:
            score += 30
        elif faq_count > 0:
            score += 20
        
        if doc_count > 0:
            score += 15
        
        # Conversation check
        conv_count = db.conversations.count_documents({
            "organization_id": org_id
        })
        if conv_count > 10:
            score += 15
        
        # Prepare result
        result = {
            "status": "success",
            "readiness_score": min(100, score),
            "alerts": alerts,
            "stats": {
                "profile_complete": len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "faq_count": faq_count,
                "document_count": doc_count,
                "conversation_count": conv_count
            },
            "recommendation": "Run full analysis for detailed suggestions" if score < 70 else "Your setup looks good!"
        }
        
        # Save quick check report (keep last 5)
        report = {
            "organization_id": org_id,
            "analysis_type": "quick",
            "readiness_score": min(100, score),
            "timestamp": datetime.utcnow(),
            "alerts": alerts,
            "suggestions": [],
            "analysis": {},
            "stats": {
                "faq_count": faq_count,
                "document_count": doc_count,
                "conversation_count": conv_count,
                "profile_complete": len(missing_fields) == 0,
                "missing_fields": missing_fields
            }
        }
        
        # Insert new report
        analysis_reports.insert_one(report)
        
        # Keep only last 5 reports per organization
        all_reports = list(analysis_reports.find({
            "organization_id": org_id
        }).sort("timestamp", -1))
        
        if len(all_reports) > 5:
            reports_to_delete = all_reports[5:]
            for old_report in reports_to_delete:
                analysis_reports.delete_one({"_id": old_report["_id"]})
        
        return result
        
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] Quick check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company-types")
async def get_company_types():
    """Get list of supported company/organization types"""
    
    return {
        "status": "success",
        "company_types": [
            # Law Firms
            "Law Firm",
            "Personal Injury Law Firm",
            "Criminal Defense Law Firm",
            "Family Law Firm",
            "Corporate Law Firm",
            "Immigration Law Firm",
            "Estate Planning Law Firm",
            "Bankruptcy Law Firm",
            
            # Real Estate
            "Real Estate Agency",
            "Real Estate Brokerage",
            "Property Management Agency",
            "Commercial Real Estate",
            "Residential Real Estate",
            
            # Medical & Health Clinics
            "Medical Clinic",
            "Dental Clinic",
            "Veterinary Clinic",
            "Urgent Care Clinic",
            "Mental Health Clinic",
            "Physical Therapy Clinic",
            "Chiropractic Clinic",
            "Dermatology Clinic",
            "Pediatric Clinic",
            "Eye Care Clinic",
            
            # Agencies
            "Marketing Agency",
            "Digital Marketing Agency",
            "Advertising Agency",
            "PR Agency",
            "Recruitment Agency",
            "Staffing Agency",
            "Travel Agency",
            "Insurance Agency",
            "Creative Agency",
            "SEO Agency",
            "Social Media Agency",
            
            # Consultants & Consulting Firms
            "Business Consulting Firm",
            "Management Consulting Firm",
            "IT Consulting Firm",
            "Financial Consulting Firm",
            "HR Consulting Firm",
            "Strategy Consulting Firm",
            "Marketing Consultant",
            "Legal Consultant",
            "Healthcare Consultant",
            "Technology Consultant",
            "Independent Consultant"
        ]
    }


@router.get("/history")
async def get_analysis_history(
    organization=Depends(get_organization_from_api_key)
):
    """
    📊 Get analysis history (last 5 reports)
    
    Returns:
    - List of previous analysis reports
    - Progress tracking (score trend)
    - Comparison data
    """
    
    try:
        org_id = organization["id"]
        
        # Get last 5 reports
        reports = list(analysis_reports.find({
            "organization_id": org_id
        }).sort("timestamp", -1).limit(5))
        
        if not reports:
            return {
                "status": "success",
                "message": "No analysis history found",
                "reports": [],
                "progress": {
                    "latest_score": 0,
                    "score_trend": "no_data",
                    "total_analyses": 0
                }
            }
        
        # Convert ObjectId to string
        for report in reports:
            report["_id"] = str(report["_id"])
            report["timestamp"] = report["timestamp"].isoformat()
        
        # Calculate progress
        latest_score = reports[0]["readiness_score"]
        
        # Determine trend (compare last 2 reports)
        score_trend = "stable"
        if len(reports) >= 2:
            previous_score = reports[1]["readiness_score"]
            if latest_score > previous_score + 5:
                score_trend = "improving"
            elif latest_score < previous_score - 5:
                score_trend = "declining"
        
        # Get total count
        total_count = analysis_reports.count_documents({
            "organization_id": org_id
        })
        
        return {
            "status": "success",
            "reports": reports,
            "progress": {
                "latest_score": latest_score,
                "score_trend": score_trend,
                "total_analyses": total_count,
                "last_analysis_date": reports[0]["timestamp"]
            }
        }
        
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] History error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress")
async def get_progress_tracking(
    organization=Depends(get_organization_from_api_key)
):
    """
    📈 Get progress tracking with score comparison
    
    Returns:
    - Score over time
    - Improvement metrics
    - Recommendations based on trend
    """
    
    try:
        org_id = organization["id"]
        
        # Get all reports for this organization
        all_reports = list(analysis_reports.find({
            "organization_id": org_id
        }).sort("timestamp", 1))  # Ascending order for timeline
        
        if not all_reports:
            return {
                "status": "success",
                "message": "No analysis data available",
                "timeline": [],
                "metrics": {}
            }
        
        # Build timeline
        timeline = []
        for report in all_reports:
            timeline.append({
                "date": report["timestamp"].isoformat(),
                "score": report["readiness_score"],
                "type": report["analysis_type"],
                "faq_count": report["stats"].get("faq_count", 0),
                "alert_count": len(report.get("alerts", []))
            })
        
        # Calculate metrics
        first_score = all_reports[0]["readiness_score"]
        latest_score = all_reports[-1]["readiness_score"]
        improvement = latest_score - first_score
        
        avg_score = sum(r["readiness_score"] for r in all_reports) / len(all_reports)
        
        # Generate recommendations
        recommendations = []
        if improvement < 0:
            recommendations.append("Your score has declined. Review recent changes.")
        elif improvement == 0:
            recommendations.append("Your score is stable. Consider running full analysis for new suggestions.")
        else:
            recommendations.append(f"Great progress! Your score improved by {improvement} points.")
        
        if latest_score < 50:
            recommendations.append("Critical: Complete your organization profile and add FAQs.")
        elif latest_score < 70:
            recommendations.append("Add more FAQs and training documents for better AI performance.")
        elif latest_score < 90:
            recommendations.append("Almost there! Review AI suggestions to reach excellence.")
        else:
            recommendations.append("Excellent setup! Maintain this quality.")
        
        return {
            "status": "success",
            "timeline": timeline,
            "metrics": {
                "first_score": first_score,
                "latest_score": latest_score,
                "improvement": improvement,
                "average_score": round(avg_score, 1),
                "total_analyses": len(all_reports),
                "trend": "improving" if improvement > 5 else "declining" if improvement < -5 else "stable"
            },
            "recommendations": recommendations
        }
        
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] Progress error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history")
async def clear_analysis_history(
    organization=Depends(get_organization_from_api_key)
):
    """
    🗑️ Clear analysis history
    
    Deletes all stored analysis reports for the organization
    """
    
    try:
        org_id = organization["id"]
        
        result = analysis_reports.delete_many({
            "organization_id": org_id
        })
        
        return {
            "status": "success",
            "message": f"Deleted {result.deleted_count} analysis reports",
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] Delete history error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
