#!/usr/bin/env python3
"""
User Learning System
Stores and analyzes user chat data to improve AI responses
"""

from datetime import datetime
from typing import Dict, Any, List
from services.database import db
import openai
import os

class UserLearningService:
    """Service to learn from user interactions and improve AI responses"""
    
    def __init__(self):
        self.learning_collection = db.user_learning
        self.response_analytics = db.response_analytics
        
    def store_interaction(self, org_id: str, session_id: str, interaction_data: Dict[str, Any]):
        """Store user interaction for learning purposes"""
        try:
            interaction = {
                "org_id": org_id,
                "session_id": session_id,
                "user_question": interaction_data.get("user_question", ""),
                "ai_response": interaction_data.get("ai_response", ""),
                "user_satisfaction": interaction_data.get("user_satisfaction"),  # Can be set later
                "response_time": interaction_data.get("response_time", 0),
                "mode": interaction_data.get("mode", "faq"),
                "intent_detected": interaction_data.get("intent_detected", ""),
                "knowledge_base_used": interaction_data.get("knowledge_base_used", False),
                "faq_matched": interaction_data.get("faq_matched", False),
                "follow_up_question": None,  # Will be updated if user asks follow-up
                "conversation_stage": interaction_data.get("conversation_stage", ""),
                "timestamp": datetime.utcnow(),
                "user_data": interaction_data.get("user_data", {})
            }
            
            result = self.learning_collection.insert_one(interaction)
            print(f"[LEARNING] Stored interaction: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"Error storing interaction for learning: {str(e)}")
            return None
    
    def mark_follow_up(self, org_id: str, session_id: str, follow_up_question: str):
        """Mark the last interaction as having a follow-up question"""
        try:
            # Find the most recent interaction for this session
            last_interaction = self.learning_collection.find_one(
                {"org_id": org_id, "session_id": session_id},
                sort=[("timestamp", -1)]
            )
            
            if last_interaction:
                self.learning_collection.update_one(
                    {"_id": last_interaction["_id"]},
                    {"$set": {"follow_up_question": follow_up_question}}
                )
                print(f"[LEARNING] Marked follow-up for interaction: {last_interaction['_id']}")
                
        except Exception as e:
            print(f"Error marking follow-up: {str(e)}")
    
    def analyze_common_questions(self, org_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Analyze common questions to improve responses"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            pipeline = [
                {"$match": {
                    "org_id": org_id,
                    "timestamp": {"$gte": cutoff_date}
                }},
                {"$group": {
                    "_id": "$user_question",
                    "count": {"$sum": 1},
                    "avg_response_time": {"$avg": "$response_time"},
                    "has_follow_ups": {"$sum": {"$cond": [{"$ne": ["$follow_up_question", None]}, 1, 0]}},
                    "sample_response": {"$first": "$ai_response"}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 20}
            ]
            
            common_questions = list(self.learning_collection.aggregate(pipeline))
            return common_questions
            
        except Exception as e:
            print(f"Error analyzing common questions: {str(e)}")
            return []
    
    def get_response_improvement_suggestions(self, org_id: str) -> Dict[str, Any]:
        """Get suggestions for improving AI responses based on user interactions"""
        try:
            common_questions = self.analyze_common_questions(org_id)
            
            # Analyze patterns
            suggestions = {
                "frequent_questions": [],
                "questions_with_follow_ups": [],
                "slow_responses": [],
                "suggested_faqs": [],
                "training_recommendations": []
            }
            
            for q in common_questions:
                if q["count"] >= 5:  # Asked 5+ times
                    suggestions["frequent_questions"].append({
                        "question": q["_id"],
                        "frequency": q["count"],
                        "suggestion": "Consider adding this as an FAQ or improving the response"
                    })
                
                if q["has_follow_ups"] > q["count"] * 0.3:  # 30%+ follow-up rate
                    suggestions["questions_with_follow_ups"].append({
                        "question": q["_id"],
                        "follow_up_rate": round(q["has_follow_ups"] / q["count"] * 100, 1),
                        "suggestion": "Response may be incomplete - consider expanding the answer"
                    })
                
                if q["avg_response_time"] > 3000:  # Slow responses
                    suggestions["slow_responses"].append({
                        "question": q["_id"],
                        "avg_time": round(q["avg_response_time"], 0),
                        "suggestion": "Consider optimizing response generation for this question type"
                    })
            
            # Generate FAQ suggestions
            for q in common_questions[:5]:  # Top 5 questions
                suggestions["suggested_faqs"].append({
                    "question": q["_id"],
                    "answer": q["sample_response"],
                    "frequency": q["count"]
                })
            
            return suggestions
            
        except Exception as e:
            print(f"Error getting improvement suggestions: {str(e)}")
            return {}
    
    def improve_response_with_learning(self, question: str, org_id: str, current_response: str) -> str:
        """Improve response based on learned patterns"""
        try:
            # Find similar questions that had good outcomes (no follow-ups)
            similar_interactions = self.learning_collection.find({
                "org_id": org_id,
                "follow_up_question": None,  # No follow-up means good response
                "$text": {"$search": question}
            }).limit(3)
            
            successful_responses = []
            for interaction in similar_interactions:
                successful_responses.append(interaction["ai_response"])
            
            if successful_responses:
                # Use AI to improve current response based on successful past responses
                improvement_prompt = f"""
                Improve this response based on successful similar responses:
                
                Current Response: {current_response}
                
                Successful Similar Responses:
                {chr(10).join([f"- {resp}" for resp in successful_responses])}
                
                Create an improved response that combines the best elements:
                """
                
                improved_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": improvement_prompt}],
                    temperature=0.3,
                    max_tokens=300
                )
                
                return improved_response.choices[0].message.content.strip()
            
            return current_response
            
        except Exception as e:
            print(f"Error improving response with learning: {str(e)}")
            return current_response
    
    def get_learning_analytics(self, org_id: str) -> Dict[str, Any]:
        """Get analytics about user learning data"""
        try:
            total_interactions = self.learning_collection.count_documents({"org_id": org_id})
            
            # Get interactions from last 7 days
            from datetime import timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_interactions = self.learning_collection.count_documents({
                "org_id": org_id,
                "timestamp": {"$gte": week_ago}
            })
            
            # Calculate follow-up rate
            follow_ups = self.learning_collection.count_documents({
                "org_id": org_id,
                "follow_up_question": {"$ne": None}
            })
            
            follow_up_rate = (follow_ups / total_interactions * 100) if total_interactions > 0 else 0
            
            # Get average response time
            avg_time_pipeline = [
                {"$match": {"org_id": org_id}},
                {"$group": {"_id": None, "avg_time": {"$avg": "$response_time"}}}
            ]
            
            avg_time_result = list(self.learning_collection.aggregate(avg_time_pipeline))
            avg_response_time = avg_time_result[0]["avg_time"] if avg_time_result else 0
            
            return {
                "total_interactions": total_interactions,
                "recent_interactions": recent_interactions,
                "follow_up_rate": round(follow_up_rate, 1),
                "avg_response_time": round(avg_response_time, 0),
                "learning_score": max(0, 100 - follow_up_rate)  # Lower follow-up rate = better learning
            }
            
        except Exception as e:
            print(f"Error getting learning analytics: {str(e)}")
            return {}

# Global instance
user_learning_service = UserLearningService()
