"""
Unknown Questions Database Service
=================================
Service for managing unknown questions and responses in MongoDB
"""

from pymongo import MongoClient
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from bson import ObjectId
import re
import os

from models.unknown_questions import (
    UnknownQuestion, 
    UnknownQuestionStats, 
    UnknownQuestionUpdate,
    UnknownQuestionFilters
)
from services.database import db

# Get the unknown_questions collection
unknown_questions_collection = db.unknown_questions

class UnknownQuestionsService:
    """Service for managing unknown questions"""
    
    @staticmethod
    def normalize_question(question: str) -> str:
        """Normalize question for better matching"""
        # Convert to lowercase
        normalized = question.lower().strip()
        
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'do', 'does', 'did', 'can', 'could', 'should', 'would', 'will'}
        words = normalized.split()
        filtered_words = [word for word in words if word not in stop_words]
        
        # Remove punctuation and join
        normalized = ' '.join(filtered_words)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        return normalized
    
    @staticmethod
    def categorize_question(question: str, ai_response: str) -> str:
        """Automatically categorize the question"""
        question_lower = question.lower()
        response_lower = ai_response.lower()
        
        # Legal keywords
        legal_keywords = ['law', 'legal', 'injury', 'accident', 'case', 'lawsuit', 'attorney', 'lawyer', 'court', 'settlement', 'compensation', 'damages', 'liability', 'negligence']
        if any(keyword in question_lower for keyword in legal_keywords):
            return 'legal'
        
        # Appointment keywords  
        appointment_keywords = ['appointment', 'schedule', 'book', 'meeting', 'consultation', 'available', 'time', 'date']
        if any(keyword in question_lower for keyword in appointment_keywords):
            return 'appointment'
        
        # Contact/info keywords
        contact_keywords = ['contact', 'phone', 'email', 'address', 'location', 'office', 'hours']
        if any(keyword in question_lower for keyword in contact_keywords):
            return 'contact'
        
        # Pricing keywords
        pricing_keywords = ['cost', 'price', 'fee', 'charge', 'payment', 'expensive', 'affordable']
        if any(keyword in question_lower for keyword in pricing_keywords):
            return 'pricing'
        
        return 'general'
    
    @staticmethod
    def check_if_question_exists(organization_id: str, question_normalized: str) -> Optional[Dict]:
        """Check if similar question already exists"""
        try:
            # Look for exact match first
            existing = unknown_questions_collection.find_one({
                "organization_id": organization_id,
                "question_normalized": question_normalized
            })
            
            if existing:
                return existing
            
            # Look for similar questions (basic text matching)
            similar_questions = unknown_questions_collection.find({
                "organization_id": organization_id,
                "question_normalized": {"$regex": re.escape(question_normalized[:20]), "$options": "i"}
            }).limit(5)
            
            for similar in similar_questions:
                # Simple similarity check
                similarity = len(set(question_normalized.split()) & set(similar['question_normalized'].split())) / len(set(question_normalized.split()) | set(similar['question_normalized'].split()))
                if similarity > 0.7:  # 70% similarity threshold
                    return similar
            
            return None
        except Exception as e:
            print(f"Error checking existing question: {str(e)}")
            return None
    
    @staticmethod
    def save_unknown_question(
        organization_id: str,
        session_id: str,
        question: str,
        ai_response: str,
        knowledge_base_results: List[Dict] = None,
        similarity_scores: List[float] = None,
        user_context: Dict = None,
        conversation_context: List[Dict] = None,
        visitor_id: str = None
    ) -> str:
        """Save an unknown question to the database"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            question_normalized = UnknownQuestionsService.normalize_question(question)
            logger.info(f"[UNKNOWN Q SERVICE] Processing question | org={organization_id[:8]}... | session={session_id[:8]}...")
            
            # Check if question already exists
            existing = UnknownQuestionsService.check_if_question_exists(organization_id, question_normalized)
            
            if existing:
                # Update frequency and last asked time
                new_frequency = existing.get("frequency_count", 1) + 1
                unknown_questions_collection.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$inc": {"frequency_count": 1},
                        "$set": {
                            "last_asked_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                logger.info(f"[UNKNOWN Q SERVICE] ✓ Updated existing | id={str(existing['_id'])} | frequency={new_frequency}")
                logger.info(f"  └─ This question has been asked {new_frequency} times")
                return str(existing["_id"])
            
            # Create new unknown question
            max_similarity = max(similarity_scores) if similarity_scores else 0.0
            question_category = UnknownQuestionsService.categorize_question(question, ai_response)
            
            # Determine if AI response seems good based on length and content
            response_quality = "good" if len(ai_response) > 50 and "I don't know" not in ai_response.lower() else "poor"
            is_answered_well = response_quality == "good" and max_similarity < 0.5  # Low similarity means not found in training
            
            unknown_question = {
                "organization_id": organization_id,
                "session_id": session_id,
                "visitor_id": visitor_id,
                "question": question,
                "question_normalized": question_normalized,
                "ai_response": ai_response,
                "response_quality": response_quality,
                "user_context": user_context or {},
                "conversation_context": conversation_context or [],
                "knowledge_base_results": knowledge_base_results or [],
                "similarity_scores": similarity_scores or [],
                "max_similarity": max_similarity,
                "question_category": question_category,
                "is_answered_well": is_answered_well,
                "needs_human_review": not is_answered_well,  # Needs review if poorly answered
                "status": "new",
                "reviewed_by": None,
                "reviewed_at": None,
                "improved_answer": None,
                "added_to_training": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "frequency_count": 1,
                "last_asked_at": datetime.utcnow()
            }
            
            result = unknown_questions_collection.insert_one(unknown_question)
            question_id = str(result.inserted_id)
            
            # Log detailed information about what was saved
            logger.info(f"[UNKNOWN Q SERVICE] ✓ New question saved | id={question_id[:12]}...")
            logger.info(f"  └─ category={question_category} | quality={response_quality} | similarity={max_similarity:.3f}")
            logger.info(f"  └─ needs_review={not is_answered_well} | kb_results={len(knowledge_base_results or [])}")
            
            # Log vectorstore info if available
            if user_context:
                vectorstore_id = user_context.get("vectorstore_id", "not_set")
                user_id = user_context.get("user_id", "unknown")
                logger.info(f"  └─ vectorstore_id={vectorstore_id[:12] if vectorstore_id != 'not_set' else 'not_set'}... | user_id={user_id[:8] if user_id != 'unknown' else 'unknown'}...")
            
            return question_id
            
        except Exception as e:
            logger.error(f"[UNKNOWN Q SERVICE ERROR] Failed to save: {str(e)}")
            import traceback
            logger.error(f"  └─ {traceback.format_exc()}")
            return None
    
    @staticmethod
    def get_unknown_questions(filters: UnknownQuestionFilters, page: int = 1, limit: int = 20) -> Dict:
        """Get unknown questions with filters and pagination"""
        
        try:
            # Build query
            query = {"organization_id": filters.organization_id}
            
            if filters.status:
                query["status"] = filters.status
            
            if filters.question_category:
                query["question_category"] = filters.question_category
            
            if filters.needs_human_review is not None:
                query["needs_human_review"] = filters.needs_human_review
            
            if filters.is_answered_well is not None:
                query["is_answered_well"] = filters.is_answered_well
            
            if filters.date_from or filters.date_to:
                date_query = {}
                if filters.date_from:
                    date_query["$gte"] = filters.date_from
                if filters.date_to:
                    date_query["$lte"] = filters.date_to
                query["created_at"] = date_query
            
            if filters.min_frequency:
                query["frequency_count"] = {"$gte": filters.min_frequency}
            
            if filters.search_query:
                query["$or"] = [
                    {"question": {"$regex": filters.search_query, "$options": "i"}},
                    {"ai_response": {"$regex": filters.search_query, "$options": "i"}}
                ]
            
            # Get total count
            total_count = unknown_questions_collection.count_documents(query)
            
            # Get paginated results
            skip = (page - 1) * limit
            questions = list(unknown_questions_collection.find(query)
                           .sort("created_at", -1)
                           .skip(skip)
                           .limit(limit))
            
            # Convert ObjectIds to strings
            for question in questions:
                question["_id"] = str(question["_id"])
            
            return {
                "questions": questions,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": (total_count + limit - 1) // limit
            }
            
        except Exception as e:
            print(f"Error getting unknown questions: {str(e)}")
            return {"questions": [], "total_count": 0, "page": 1, "limit": limit, "total_pages": 0}
    
    @staticmethod
    def update_unknown_question(question_id: str, update_data: UnknownQuestionUpdate) -> bool:
        """Update an unknown question"""
        
        try:
            update_dict = {}
            
            # Add non-None fields to update
            if update_data.response_quality is not None:
                update_dict["response_quality"] = update_data.response_quality
            
            if update_data.is_answered_well is not None:
                update_dict["is_answered_well"] = update_data.is_answered_well
            
            if update_data.improved_answer is not None:
                update_dict["improved_answer"] = update_data.improved_answer
            
            if update_data.status is not None:
                update_dict["status"] = update_data.status
            
            if update_data.reviewed_by is not None:
                update_dict["reviewed_by"] = update_data.reviewed_by
                update_dict["reviewed_at"] = datetime.utcnow()
            
            if update_data.question_category is not None:
                update_dict["question_category"] = update_data.question_category
            
            if update_data.needs_human_review is not None:
                update_dict["needs_human_review"] = update_data.needs_human_review
            
            update_dict["updated_at"] = datetime.utcnow()
            
            result = unknown_questions_collection.update_one(
                {"_id": ObjectId(question_id)},
                {"$set": update_dict}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error updating unknown question: {str(e)}")
            return False
    
    @staticmethod
    def get_unknown_question_stats(organization_id: str, days: int = 30) -> UnknownQuestionStats:
        """Get statistics for unknown questions"""
        
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Build aggregation pipeline
            pipeline = [
                {
                    "$match": {
                        "organization_id": organization_id,
                        "created_at": {"$gte": start_date, "$lte": end_date}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_unknown_questions": {"$sum": 1},
                        "new_questions": {
                            "$sum": {"$cond": [{"$eq": ["$status", "new"]}, 1, 0]}
                        },
                        "reviewed_questions": {
                            "$sum": {"$cond": [{"$eq": ["$status", "reviewed"]}, 1, 0]}
                        },
                        "added_to_training": {
                            "$sum": {"$cond": ["$added_to_training", 1, 0]}
                        },
                        "ignored_questions": {
                            "$sum": {"$cond": [{"$eq": ["$status", "ignored"]}, 1, 0]}
                        },
                        "good_ai_responses": {
                            "$sum": {"$cond": [{"$eq": ["$response_quality", "good"]}, 1, 0]}
                        },
                        "poor_ai_responses": {
                            "$sum": {"$cond": [{"$eq": ["$response_quality", "poor"]}, 1, 0]}
                        },
                        "needs_improvement": {
                            "$sum": {"$cond": ["$needs_human_review", 1, 0]}
                        },
                        "legal_questions": {
                            "$sum": {"$cond": [{"$eq": ["$question_category", "legal"]}, 1, 0]}
                        },
                        "appointment_questions": {
                            "$sum": {"$cond": [{"$eq": ["$question_category", "appointment"]}, 1, 0]}
                        },
                        "general_questions": {
                            "$sum": {"$cond": [{"$eq": ["$question_category", "general"]}, 1, 0]}
                        }
                    }
                }
            ]
            
            result = list(unknown_questions_collection.aggregate(pipeline))
            
            if result:
                stats_data = result[0]
                stats_data.pop("_id", None)  # Remove the _id field
                stats_data["organization_id"] = organization_id
                stats_data["period_start"] = start_date
                stats_data["period_end"] = end_date
                stats_data["other_questions"] = stats_data["total_unknown_questions"] - (
                    stats_data["legal_questions"] + 
                    stats_data["appointment_questions"] + 
                    stats_data["general_questions"]
                )
            else:
                stats_data = {
                    "organization_id": organization_id,
                    "total_unknown_questions": 0,
                    "new_questions": 0,
                    "reviewed_questions": 0,
                    "added_to_training": 0,
                    "ignored_questions": 0,
                    "good_ai_responses": 0,
                    "poor_ai_responses": 0,
                    "needs_improvement": 0,
                    "legal_questions": 0,
                    "appointment_questions": 0,
                    "general_questions": 0,
                    "other_questions": 0,
                    "period_start": start_date,
                    "period_end": end_date
                }
            
            return UnknownQuestionStats(**stats_data)
            
        except Exception as e:
            print(f"Error getting unknown question stats: {str(e)}")
            return UnknownQuestionStats(
                organization_id=organization_id,
                period_start=datetime.utcnow() - timedelta(days=days),
                period_end=datetime.utcnow()
            )
    
    @staticmethod
    def delete_unknown_question(question_id: str) -> bool:
        """Delete an unknown question"""
        
        try:
            result = unknown_questions_collection.delete_one({"_id": ObjectId(question_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            print(f"Error deleting unknown question: {str(e)}")
            return False

# Create indexes for better performance
def create_indexes():
    """Create database indexes for unknown questions"""
    try:
        # Compound index for organization and status queries
        unknown_questions_collection.create_index([
            ("organization_id", 1),
            ("status", 1),
            ("created_at", -1)
        ])
        
        # Index for question normalization and similarity matching
        unknown_questions_collection.create_index([
            ("organization_id", 1),
            ("question_normalized", 1)
        ])
        
        # Index for category and quality filtering
        unknown_questions_collection.create_index([
            ("organization_id", 1),
            ("question_category", 1),
            ("response_quality", 1)
        ])
        
        # Text index for search
        unknown_questions_collection.create_index([
            ("question", "text"),
            ("ai_response", "text")
        ])
        
        print("✅ Created indexes for unknown_questions collection")
        
    except Exception as e:
        print(f"Error creating indexes: {str(e)}")

# Create indexes when module is imported
create_indexes()
