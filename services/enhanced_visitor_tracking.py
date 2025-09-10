#!/usr/bin/env python3
"""
Enhanced Visitor Tracking System
Comprehensive tracking of visitor interactions, questions, and contact information
"""

import os
import sys
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from bson import ObjectId

# Add the parent directory to the path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import db, get_organization_by_api_key

class EnhancedVisitorTracker:
    def __init__(self):
        self.visitors_collection = db.visitors
        self.conversations_collection = db.conversations
        self.questions_collection = db.visitor_questions  # New collection for question tracking
        self.duplicate_detection_collection = db.duplicate_questions  # For duplicate detection
    
    def track_visitor_question(self, session_id: str, organization_id: str, question: str, 
                             answer: str, user_data: Dict[str, Any] = None) -> bool:
        """
        Track every visitor question with comprehensive metadata
        """
        try:
            # Create question hash for duplicate detection
            question_hash = hashlib.md5(question.lower().strip().encode()).hexdigest()
            
            # Prepare question document
            question_doc = {
                "session_id": session_id,
                "organization_id": organization_id,
                "question": question,
                "question_hash": question_hash,
                "answer": answer,
                "timestamp": datetime.utcnow(),
                "user_data": user_data or {},
                "question_length": len(question),
                "answer_length": len(answer),
                "language_detected": self._detect_language(question),
                "question_type": self._classify_question_type(question),
                "contains_contact_info": self._contains_contact_info(question),
                "urgency_level": self._assess_urgency(question),
                "topic_tags": self._extract_topic_tags(question)
            }
            
            # Insert question record
            result = self.questions_collection.insert_one(question_doc)
            
            # Update visitor record with latest question
            self._update_visitor_with_question(session_id, organization_id, question_doc)
            
            # Update duplicate detection cache
            self._update_duplicate_detection(question_hash, organization_id, question, answer)
            
            return True
            
        except Exception as e:
            print(f"Error tracking visitor question: {str(e)}")
            return False
    
    def update_visitor_contact_info(self, session_id: str, organization_id: str, 
                                   name: str = None, email: str = None, 
                                   phone: str = None, additional_data: Dict = None) -> bool:
        """
        Update visitor contact information with comprehensive tracking
        """
        try:
            update_data = {
                "last_updated": datetime.utcnow(),
                "contact_info_collected": True
            }
            
            if name:
                update_data["name"] = name
                update_data["name_collected_at"] = datetime.utcnow()
            
            if email:
                update_data["email"] = email
                update_data["email_collected_at"] = datetime.utcnow()
                update_data["email_valid"] = self._validate_email(email)
            
            if phone:
                update_data["phone"] = phone
                update_data["phone_collected_at"] = datetime.utcnow()
            
            if additional_data:
                update_data.update(additional_data)
            
            # Update visitor record
            result = self.visitors_collection.update_one(
                {"session_id": session_id, "organization_id": organization_id},
                {"$set": update_data},
                upsert=True
            )
            
            # Also update all question records for this visitor
            self.questions_collection.update_many(
                {"session_id": session_id, "organization_id": organization_id},
                {"$set": {
                    "visitor_name": name,
                    "visitor_email": email,
                    "visitor_phone": phone,
                    "contact_updated_at": datetime.utcnow()
                }}
            )
            
            return True
            
        except Exception as e:
            print(f"Error updating visitor contact info: {str(e)}")
            return False
    
    def check_duplicate_question(self, question: str, organization_id: str, 
                               similarity_threshold: float = 0.85) -> Optional[Dict]:
        """
        Check if this question has been asked before (duplicate detection)
        """
        try:
            question_hash = hashlib.md5(question.lower().strip().encode()).hexdigest()
            
            # First check for exact hash match
            exact_match = self.duplicate_detection_collection.find_one({
                "question_hash": question_hash,
                "organization_id": organization_id
            })
            
            if exact_match:
                return {
                    "is_duplicate": True,
                    "match_type": "exact",
                    "original_question": exact_match["question"],
                    "cached_answer": exact_match["answer"],
                    "first_asked": exact_match["first_asked"],
                    "times_asked": exact_match["times_asked"]
                }
            
            # Check for similar questions using basic text similarity
            similar_questions = self._find_similar_questions(question, organization_id, similarity_threshold)
            
            if similar_questions:
                return {
                    "is_duplicate": True,
                    "match_type": "similar",
                    "similar_questions": similar_questions
                }
            
            return {"is_duplicate": False}
            
        except Exception as e:
            print(f"Error checking duplicate question: {str(e)}")
            return {"is_duplicate": False}
    
    def get_visitor_history(self, session_id: str, organization_id: str) -> Dict:
        """
        Get comprehensive visitor history including all questions and interactions
        """
        try:
            # Get visitor record
            visitor = self.visitors_collection.find_one({
                "session_id": session_id,
                "organization_id": organization_id
            })
            
            # Get all questions asked by this visitor
            questions = list(self.questions_collection.find({
                "session_id": session_id,
                "organization_id": organization_id
            }).sort("timestamp", 1))
            
            # Get conversation history
            conversations = list(self.conversations_collection.find({
                "session_id": session_id,
                "organization_id": organization_id
            }).sort("timestamp", 1))
            
            return {
                "visitor_info": visitor,
                "questions": questions,
                "conversations": conversations,
                "total_questions": len(questions),
                "total_conversations": len(conversations),
                "first_interaction": questions[0]["timestamp"] if questions else None,
                "last_interaction": questions[-1]["timestamp"] if questions else None,
                "session_duration": self._calculate_session_duration(questions),
                "engagement_score": self._calculate_engagement_score(questions, conversations)
            }
            
        except Exception as e:
            print(f"Error getting visitor history: {str(e)}")
            return {}
    
    def get_organization_analytics(self, organization_id: str, days: int = 30) -> Dict:
        """
        Get comprehensive analytics for an organization
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Total questions in period
            total_questions = self.questions_collection.count_documents({
                "organization_id": organization_id,
                "timestamp": {"$gte": since_date}
            })
            
            # Unique visitors
            unique_visitors = len(self.questions_collection.distinct("session_id", {
                "organization_id": organization_id,
                "timestamp": {"$gte": since_date}
            }))
            
            # Contact information collection rate
            visitors_with_contact = self.visitors_collection.count_documents({
                "organization_id": organization_id,
                "contact_info_collected": True,
                "last_updated": {"$gte": since_date}
            })
            
            # Most common question types
            question_types = list(self.questions_collection.aggregate([
                {"$match": {"organization_id": organization_id, "timestamp": {"$gte": since_date}}},
                {"$group": {"_id": "$question_type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]))
            
            # Most common topics
            topic_tags = list(self.questions_collection.aggregate([
                {"$match": {"organization_id": organization_id, "timestamp": {"$gte": since_date}}},
                {"$unwind": "$topic_tags"},
                {"$group": {"_id": "$topic_tags", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 15}
            ]))
            
            # Duplicate question rate
            duplicate_questions = self.duplicate_detection_collection.count_documents({
                "organization_id": organization_id,
                "times_asked": {"$gt": 1}
            })
            
            return {
                "period_days": days,
                "total_questions": total_questions,
                "unique_visitors": unique_visitors,
                "contact_collection_rate": (visitors_with_contact / unique_visitors * 100) if unique_visitors > 0 else 0,
                "avg_questions_per_visitor": total_questions / unique_visitors if unique_visitors > 0 else 0,
                "question_types": question_types,
                "popular_topics": topic_tags,
                "duplicate_questions": duplicate_questions,
                "duplicate_rate": (duplicate_questions / total_questions * 100) if total_questions > 0 else 0
            }
            
        except Exception as e:
            print(f"Error getting organization analytics: {str(e)}")
            return {}
    
    def _detect_language(self, text: str) -> str:
        """Detect the language of the text"""
        # Simple language detection - can be enhanced with proper library
        english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        spanish_words = ['el', 'la', 'y', 'o', 'pero', 'en', 'de', 'con', 'por', 'para', 'que', 'es']
        
        text_lower = text.lower()
        english_count = sum(1 for word in english_words if word in text_lower)
        spanish_count = sum(1 for word in spanish_words if word in text_lower)
        
        if spanish_count > english_count:
            return "spanish"
        return "english"
    
    def _classify_question_type(self, question: str) -> str:
        """Classify the type of question"""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['accident', 'injured', 'hurt', 'crash', 'collision']):
            return "accident_inquiry"
        elif any(word in question_lower for word in ['appointment', 'schedule', 'meet', 'consultation']):
            return "appointment_request"
        elif any(word in question_lower for word in ['cost', 'fee', 'charge', 'price', 'money']):
            return "pricing_inquiry"
        elif any(word in question_lower for word in ['how', 'what', 'when', 'where', 'why']):
            return "information_request"
        elif any(word in question_lower for word in ['hello', 'hi', 'hey', 'good morning']):
            return "greeting"
        else:
            return "general_inquiry"
    
    def _contains_contact_info(self, text: str) -> bool:
        """Check if text contains contact information"""
        import re
        
        # Check for email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, text):
            return True
        
        # Check for phone pattern
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        if re.search(phone_pattern, text):
            return True
        
        # Check for name patterns
        name_patterns = ['my name is', 'i am', 'i\'m', 'call me']
        if any(pattern in text.lower() for pattern in name_patterns):
            return True
        
        return False
    
    def _assess_urgency(self, question: str) -> str:
        """Assess the urgency level of the question"""
        question_lower = question.lower()
        
        urgent_keywords = ['emergency', 'urgent', 'asap', 'immediately', 'right now', 'help me']
        high_keywords = ['serious', 'severe', 'hospital', 'ambulance', 'surgery']
        medium_keywords = ['accident', 'injured', 'hurt', 'pain']
        
        if any(word in question_lower for word in urgent_keywords):
            return "urgent"
        elif any(word in question_lower for word in high_keywords):
            return "high"
        elif any(word in question_lower for word in medium_keywords):
            return "medium"
        else:
            return "low"
    
    def _extract_topic_tags(self, question: str) -> List[str]:
        """Extract topic tags from the question"""
        question_lower = question.lower()
        tags = []
        
        topic_keywords = {
            'car_accident': ['car', 'auto', 'vehicle', 'driving', 'crash', 'collision'],
            'slip_fall': ['slip', 'fall', 'fell', 'tripped', 'floor', 'wet'],
            'medical_malpractice': ['doctor', 'hospital', 'medical', 'surgery', 'medication', 'diagnosis'],
            'workers_comp': ['work', 'job', 'workplace', 'workers', 'compensation', 'injured at work'],
            'appointment': ['appointment', 'schedule', 'meet', 'consultation', 'available'],
            'pricing': ['cost', 'fee', 'charge', 'price', 'money', 'expensive'],
            'legal_advice': ['legal', 'law', 'attorney', 'lawyer', 'advice', 'help'],
            'insurance': ['insurance', 'claim', 'adjuster', 'coverage', 'policy']
        }
        
        for tag, keywords in topic_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                tags.append(tag)
        
        return tags
    
    def _update_visitor_with_question(self, session_id: str, organization_id: str, question_doc: Dict):
        """Update visitor record with latest question information"""
        try:
            self.visitors_collection.update_one(
                {"session_id": session_id, "organization_id": organization_id},
                {
                    "$set": {
                        "last_question": question_doc["question"],
                        "last_question_type": question_doc["question_type"],
                        "last_interaction": question_doc["timestamp"],
                        "total_questions": {"$inc": 1}
                    },
                    "$push": {
                        "recent_topics": {"$each": question_doc["topic_tags"], "$slice": -10}
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"Error updating visitor with question: {str(e)}")
    
    def _update_duplicate_detection(self, question_hash: str, organization_id: str, 
                                   question: str, answer: str):
        """Update duplicate detection cache"""
        try:
            self.duplicate_detection_collection.update_one(
                {"question_hash": question_hash, "organization_id": organization_id},
                {
                    "$set": {
                        "question": question,
                        "answer": answer,
                        "last_asked": datetime.utcnow()
                    },
                    "$inc": {"times_asked": 1},
                    "$setOnInsert": {"first_asked": datetime.utcnow()}
                },
                upsert=True
            )
        except Exception as e:
            print(f"Error updating duplicate detection: {str(e)}")
    
    def _find_similar_questions(self, question: str, organization_id: str, 
                               threshold: float) -> List[Dict]:
        """Find similar questions using basic text similarity"""
        # This is a simplified version - in production, you'd use more sophisticated NLP
        try:
            question_words = set(question.lower().split())
            similar_questions = []
            
            # Get recent questions from the same organization
            recent_questions = self.duplicate_detection_collection.find({
                "organization_id": organization_id,
                "times_asked": {"$gte": 2}  # Only check questions asked multiple times
            }).limit(100)
            
            for q_doc in recent_questions:
                stored_words = set(q_doc["question"].lower().split())
                
                # Calculate Jaccard similarity
                intersection = len(question_words.intersection(stored_words))
                union = len(question_words.union(stored_words))
                
                if union > 0:
                    similarity = intersection / union
                    
                    if similarity >= threshold:
                        similar_questions.append({
                            "question": q_doc["question"],
                            "answer": q_doc["answer"],
                            "similarity": similarity,
                            "times_asked": q_doc["times_asked"]
                        })
            
            return sorted(similar_questions, key=lambda x: x["similarity"], reverse=True)[:3]
            
        except Exception as e:
            print(f"Error finding similar questions: {str(e)}")
            return []
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        import re
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _calculate_session_duration(self, questions: List[Dict]) -> Optional[int]:
        """Calculate session duration in minutes"""
        if len(questions) < 2:
            return None
        
        first_time = questions[0]["timestamp"]
        last_time = questions[-1]["timestamp"]
        
        duration = (last_time - first_time).total_seconds() / 60
        return int(duration)
    
    def _calculate_engagement_score(self, questions: List[Dict], 
                                   conversations: List[Dict]) -> float:
        """Calculate visitor engagement score (0-1)"""
        try:
            score = 0.0
            
            # Points for number of questions
            score += min(len(questions) * 0.1, 0.4)
            
            # Points for question complexity
            avg_question_length = sum(len(q["question"]) for q in questions) / len(questions) if questions else 0
            if avg_question_length > 50:
                score += 0.2
            
            # Points for contact info sharing
            if any("contact_info_collected" in q.get("user_data", {}) for q in questions):
                score += 0.3
            
            # Points for session duration
            duration = self._calculate_session_duration(questions)
            if duration and duration > 10:  # More than 10 minutes
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            print(f"Error calculating engagement score: {str(e)}")
            return 0.0

# Global instance
visitor_tracker = EnhancedVisitorTracker()

def track_visitor_question(session_id: str, organization_id: str, question: str, 
                          answer: str, user_data: Dict[str, Any] = None) -> bool:
    """Convenience function to track visitor questions"""
    return visitor_tracker.track_visitor_question(session_id, organization_id, question, answer, user_data)

def update_visitor_contact_info(session_id: str, organization_id: str, 
                               name: str = None, email: str = None, 
                               phone: str = None, additional_data: Dict = None) -> bool:
    """Convenience function to update visitor contact info"""
    return visitor_tracker.update_visitor_contact_info(session_id, organization_id, name, email, phone, additional_data)

def check_duplicate_question(question: str, organization_id: str) -> Optional[Dict]:
    """Convenience function to check for duplicate questions"""
    return visitor_tracker.check_duplicate_question(question, organization_id)

