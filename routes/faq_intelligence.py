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


@router.get("/latest")
async def get_latest_analysis(
    organization=Depends(get_organization_from_api_key)
):
    """
    📊 Get Latest Analysis Report
    
    Returns the most recent analysis report for the organization.
    If no analysis exists, runs quick-check to show immediate stats.
    
    This endpoint loads on page mount to show last analysis data.
    """
    try:
        org_id = organization["id"]
        
        # Get latest report
        latest_report = analysis_reports.find_one(
            {"organization_id": org_id},
            sort=[("timestamp", -1)]
        )
        
        if latest_report:
            # Convert ObjectId to string for JSON serialization
            latest_report["_id"] = str(latest_report["_id"])
            
            return {
                "status": "success",
                **latest_report
            }
        
        # No analysis yet - run quick check to show immediate stats
        print(f"⚡ No analysis found for org {org_id}, running quick check...")
        
        # Get user data
        user_id = organization.get("user_id")
        user_data = {}
        if user_id:
            user = db.users.find_one({"_id": ObjectId(user_id)} if len(str(user_id)) == 24 else {"id": user_id})
            if user:
                user_data = user
        
        # Quick checks
        missing_fields = []
        alerts = []
        
        # Check profile
        if not user_data.get("organization_name"):
            missing_fields.append("organization_name")
            alerts.append({
                "type": "critical",
                "category": "profile",
                "message": "Organization name is missing",
                "action": "Add your organization name in settings"
            })
        
        if not user_data.get("website"):
            missing_fields.append("website")
            alerts.append({
                "type": "warning",
                "category": "profile",
                "message": "Website URL is missing",
                "action": "Add your website URL to enable content analysis"
            })
        
        if not user_data.get("company_organization_type"):
            missing_fields.append("company_organization_type")
            alerts.append({
                "type": "warning",
                "category": "profile",
                "message": "Company type is missing",
                "action": "Specify your company/organization type for better AI suggestions"
            })
        
        # Check FAQs
        faq_count = db.faqs.count_documents({
            "org_id": org_id,
            "is_active": True
        })
        
        if faq_count == 0:
            alerts.append({
                "type": "critical",
                "category": "faqs",
                "message": "No FAQs found",
                "action": "Add at least 5-10 FAQs to your knowledge base"
            })
        elif faq_count < 5:
            alerts.append({
                "type": "warning",
                "category": "faqs",
                "message": f"Only {faq_count} FAQ(s) found",
                "action": "Add more FAQs for comprehensive coverage"
            })
        
        # Check documents
        all_uploads = list(db.upload_history.find({
            "org_id": org_id,
            "status": "Used"
        }))
        
        doc_count = sum(1 for upload in all_uploads if upload.get("type") in ["pdf", "csv", "text"])
        
        if doc_count == 0:
            alerts.append({
                "type": "warning",
                "category": "documents",
                "message": "No training documents found",
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
        
        # Check if website is available (from user profile OR uploaded URLs)
        # Collect ALL URL uploads (type="url")
        url_uploads = [upload for upload in all_uploads if upload.get("type") == "url"]
        url_count = len(url_uploads)
        
        has_website = bool(user_data.get("website"))
        website_url = user_data.get("website")
        trained_urls = []
        
        # Add profile website if exists
        if has_website:
            trained_urls.append(website_url)
        
        # Add all uploaded URLs
        for url_upload in url_uploads:
            url = url_upload.get("url")
            if url and url not in trained_urls:
                trained_urls.append(url)
        
        # Update has_website based on either profile or uploads
        if not has_website and url_count > 0:
            has_website = True
        
        if has_website:
            score += 10
        
        # Conversation check
        conv_count = db.conversations.count_documents({
            "organization_id": org_id
        })
        if conv_count > 10:
            score += 15
        
        # Return quick check result
        return {
            "status": "success",
            "message": "Quick check complete. Click 'Run Analysis' for AI-powered suggestions.",
            "analysis_type": "quick",
            "readiness_score": min(100, score),
            "timestamp": datetime.utcnow().isoformat(),
            "alerts": alerts,
            "suggestions": [{
                "type": "info",
                "message": "Run full analysis to get AI-powered FAQ suggestions",
                "action": "Click 'Run Analysis' button above"
            }],
            "stats": {
                "faq_count": faq_count,
                "document_count": doc_count,
                "website_url": website_url if has_website else None,
                "trained_urls": trained_urls,
                "url_count": len(trained_urls),
                "has_website": has_website,
                "conversation_count": conv_count,
                "profile_complete": len(missing_fields) == 0,
                "missing_fields": missing_fields
            },
            "analysis": {
                "profile": {
                    "complete": len(missing_fields) == 0,
                    "missing_critical_fields": missing_fields
                },
                "faqs": {
                    "count": faq_count,
                    "status": "good" if faq_count >= 10 else "needs_improvement"
                },
                "documents": {
                    "count": doc_count,
                    "status": "good" if doc_count > 0 else "missing"
                },
                "website": {
                    "url": website_url if has_website else None,
                    "trained_urls": trained_urls,
                    "url_count": len(trained_urls),
                    "status": "configured" if has_website else "missing"
                },
                "conversations": {
                    "count": conv_count,
                    "status": "good" if conv_count > 10 else "needs_more"
                }
            }
        }
        
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] Error getting latest: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
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
        
        # 2. Get conversation history (last 100 for analysis, but count all)
        # Using organization_id field from conversations collection
        
        # Count total conversations
        total_conv_count = db.conversations.count_documents({
            "organization_id": org_id
        })
        
        # Get last 100 for AI analysis
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
        print(f"💬 Found {total_conv_count} total conversations (using last {len(conversation_data)} for analysis)")
        
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
        trained_urls = []
        
        # Add profile website if exists
        if website_url:
            trained_urls.append(website_url)
        
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
            
            # Website URL uploads (type="url") - collect all URLs
            elif upload_type == "url" and upload.get("url"):
                url = upload.get("url")
                if url not in trained_urls:
                    trained_urls.append(url)
                
                # If no website in user profile, use the first uploaded URL as website
                if not website_url:
                    website_url = url
                    print(f"🌐 Using uploaded URL as website: {website_url}")
        
        print(f"📄 Found {len(doc_data)} actual documents (PDFs, CSVs)")
        print(f"🌐 Website URL: {website_url}")
        print(f"🌐 Total trained URLs: {len(trained_urls)}")
        
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
                "website_url": website_url,
                "trained_urls": trained_urls,
                "url_count": len(trained_urls),
                "has_website": len(trained_urls) > 0,
                "conversation_count": total_conv_count,  # Use total count, not limited data
                "profile_complete": len(result['analysis'].get('profile', {}).get('missing_critical_fields', [])) == 0,
                "missing_fields": result['analysis'].get('profile', {}).get('missing_critical_fields', [])
            }
        }
        
        # Insert new report
        result_insert = analysis_reports.insert_one(report)
        
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
        
        # Convert ObjectId to string and convert datetime to ISO format for JSON serialization
        report_response = {
            **report,
            "_id": str(result_insert.inserted_id),
            "timestamp": report["timestamp"].isoformat() if isinstance(report["timestamp"], datetime) else report["timestamp"]
        }
        
        # Return the full report with stats and status
        return {
            "status": "success",
            **report_response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] Error: {str(e)}")
        import traceback
        traceback.print_exc()
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


@router.delete("/suggestion/{suggestion_index}")
async def remove_suggestion(
    suggestion_index: int,
    organization=Depends(get_organization_from_api_key)
):
    """
    🗑️ Remove a specific FAQ suggestion
    
    Removes a suggestion from the latest analysis report after it has been added to FAQs.
    This prevents showing the same suggestion again.
    
    Args:
        suggestion_index: The index of the suggestion to remove (0-based)
    """
    
    try:
        org_id = organization["id"]
        
        # Get the latest analysis report
        latest_report = analysis_reports.find_one(
            {"organization_id": org_id},
            sort=[("timestamp", -1)]
        )
        
        if not latest_report:
            raise HTTPException(status_code=404, detail="No analysis report found")
        
        # Get current suggestions
        suggestions = latest_report.get("suggestions", [])
        
        if suggestion_index < 0 or suggestion_index >= len(suggestions):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid suggestion index. Must be between 0 and {len(suggestions)-1}"
            )
        
        # Remove the suggestion at the specified index
        removed_suggestion = suggestions.pop(suggestion_index)
        
        # Update the report with the modified suggestions list
        analysis_reports.update_one(
            {"_id": latest_report["_id"]},
            {
                "$set": {
                    "suggestions": suggestions,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"✅ [FAQ-INTELLIGENCE] Removed suggestion at index {suggestion_index}: {removed_suggestion.get('question', 'Unknown')}")
        
        return {
            "status": "success",
            "message": "Suggestion removed successfully",
            "removed_suggestion": {
                "question": removed_suggestion.get("question", ""),
                "priority": removed_suggestion.get("priority", ""),
            },
            "remaining_suggestions": len(suggestions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [FAQ-INTELLIGENCE] Remove suggestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

