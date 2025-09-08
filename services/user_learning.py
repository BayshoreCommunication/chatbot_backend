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
        """Store user interaction for learning purposes with enhanced context analysis"""
        try:
            # Analyze the interaction for learning insights
            user_question = interaction_data.get("user_question", "")
            ai_response = interaction_data.get("ai_response", "")
            
            # Extract intent and context
            intent_analysis = self._analyze_user_intent(user_question)
            response_quality = self._analyze_response_quality(user_question, ai_response)
            conversation_context = self._extract_conversation_context(interaction_data.get("user_data", {}))
            
            interaction = {
                "org_id": org_id,
                "session_id": session_id,
                "user_question": user_question,
                "ai_response": ai_response,
                "user_satisfaction": interaction_data.get("user_satisfaction"),  # Can be set later
                "response_time": interaction_data.get("response_time", 0),
                "mode": interaction_data.get("mode", "faq"),
                "intent_detected": intent_analysis.get("intent", ""),
                "intent_confidence": intent_analysis.get("confidence", 0.0),
                "case_type": intent_analysis.get("case_type", ""),
                "urgency_level": intent_analysis.get("urgency", "normal"),
                "knowledge_base_used": interaction_data.get("knowledge_base_used", False),
                "faq_matched": interaction_data.get("faq_matched", False),
                "response_quality_score": response_quality.get("score", 0.0),
                "response_effectiveness": response_quality.get("effectiveness", "unknown"),
                "follow_up_question": None,  # Will be updated if user asks follow-up
                "conversation_stage": interaction_data.get("conversation_stage", ""),
                "conversation_context": conversation_context,
                "timestamp": datetime.utcnow(),
                "user_data": interaction_data.get("user_data", {})
            }
            
            result = self.learning_collection.insert_one(interaction)
            print(f"[LEARNING] Stored enhanced interaction: {result.inserted_id}")
            
            # Update learning patterns
            self._update_learning_patterns(org_id, interaction)
            
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
                    model="gpt-4o",
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
    
    def _analyze_user_intent(self, user_question: str) -> Dict[str, Any]:
        """Analyze user intent and extract context from their question"""
        question_lower = user_question.lower()
        
        # Intent detection
        intent = "general_inquiry"
        confidence = 0.5
        case_type = ""
        urgency = "normal"
        
        # Case type detection
        if any(word in question_lower for word in ["accident", "crash", "collision", "car", "auto", "vehicle"]):
            case_type = "auto_accident"
            intent = "accident_inquiry"
            confidence = 0.8
        elif any(word in question_lower for word in ["slip", "fall", "premises", "property"]):
            case_type = "slip_fall"
            intent = "premises_liability"
            confidence = 0.8
        elif any(word in question_lower for word in ["medical", "malpractice", "doctor", "hospital", "surgery"]):
            case_type = "medical_malpractice"
            intent = "medical_inquiry"
            confidence = 0.8
        elif any(word in question_lower for word in ["work", "workers", "compensation", "job", "employment"]):
            case_type = "workers_comp"
            intent = "workers_comp_inquiry"
            confidence = 0.8
        
        # Urgency detection
        if any(word in question_lower for word in ["urgent", "emergency", "asap", "immediately", "right away"]):
            urgency = "high"
        elif any(word in question_lower for word in ["soon", "quickly", "fast", "priority"]):
            urgency = "medium"
        
        # Appointment intent
        if any(word in question_lower for word in ["appointment", "schedule", "meeting", "consultation", "book"]):
            intent = "appointment_request"
            confidence = 0.9
        
        return {
            "intent": intent,
            "confidence": confidence,
            "case_type": case_type,
            "urgency": urgency
        }
    
    def _analyze_response_quality(self, user_question: str, ai_response: str) -> Dict[str, Any]:
        """Analyze the quality and effectiveness of AI responses"""
        score = 0.5  # Default score
        effectiveness = "unknown"
        
        # Response length analysis
        if len(ai_response) > 100:
            score += 0.2
        if len(ai_response) > 300:
            score += 0.1
        
        # Check for helpful elements
        helpful_indicators = [
            "consultation", "free", "attorney", "lawyer", "help", "assist", 
            "information", "advice", "rights", "options", "case", "compensation"
        ]
        
        helpful_count = sum(1 for indicator in helpful_indicators if indicator in ai_response.lower())
        score += min(helpful_count * 0.05, 0.3)
        
        # Check for personalization
        if any(word in ai_response for word in ["your", "you", "personal", "specific"]):
            score += 0.1
        
        # Determine effectiveness
        if score > 0.8:
            effectiveness = "excellent"
        elif score > 0.6:
            effectiveness = "good"
        elif score > 0.4:
            effectiveness = "fair"
        else:
            effectiveness = "poor"
        
        return {
            "score": min(score, 1.0),
            "effectiveness": effectiveness
        }
    
    def _extract_conversation_context(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract conversation context for learning"""
        conversation_history = user_data.get("conversation_history", [])
        
        context = {
            "conversation_length": len(conversation_history),
            "has_name": bool(user_data.get("name")),
            "has_email": bool(user_data.get("email")),
            "user_engagement": "low"
        }
        
        # Calculate engagement level
        if context["conversation_length"] > 6:
            context["user_engagement"] = "high"
        elif context["conversation_length"] > 3:
            context["user_engagement"] = "medium"
        
        # Check for case-related keywords in conversation
        all_messages = " ".join([msg.get("content", "") for msg in conversation_history])
        case_keywords = ["accident", "injury", "legal", "case", "claim", "compensation"]
        context["case_related"] = any(keyword in all_messages.lower() for keyword in case_keywords)
        
        return context
    
    def _update_learning_patterns(self, org_id: str, interaction: Dict[str, Any]):
        """Update learning patterns based on interaction data"""
        try:
            # Store patterns for future improvement
            pattern_data = {
                "org_id": org_id,
                "intent": interaction.get("intent_detected"),
                "case_type": interaction.get("case_type"),
                "response_quality": interaction.get("response_quality_score"),
                "timestamp": datetime.utcnow()
            }
            
            # Update or create pattern record
            self.learning_collection.update_one(
                {
                    "org_id": org_id,
                    "intent": interaction.get("intent_detected"),
                    "case_type": interaction.get("case_type")
                },
                {
                    "$set": pattern_data,
                    "$inc": {"occurrence_count": 1}
                },
                upsert=True
            )
            
        except Exception as e:
            print(f"Error updating learning patterns: {str(e)}")
    
    def get_smart_response_suggestions(self, org_id: str, user_question: str) -> Dict[str, Any]:
        """Get smart response suggestions based on learned patterns"""
        try:
            # Analyze the current question
            intent_analysis = self._analyze_user_intent(user_question)
            
            # Find similar successful interactions
            similar_interactions = self.learning_collection.find({
                "org_id": org_id,
                "intent_detected": intent_analysis.get("intent"),
                "response_quality_score": {"$gte": 0.7}  # Only successful responses
            }).limit(5)
            
            suggestions = {
                "intent": intent_analysis.get("intent"),
                "case_type": intent_analysis.get("case_type"),
                "urgency": intent_analysis.get("urgency"),
                "successful_patterns": [],
                "recommended_approach": "standard"
            }
            
            for interaction in similar_interactions:
                suggestions["successful_patterns"].append({
                    "response": interaction.get("ai_response", ""),
                    "quality_score": interaction.get("response_quality_score", 0),
                    "effectiveness": interaction.get("response_effectiveness", "unknown")
                })
            
            # Determine recommended approach
            if intent_analysis.get("urgency") == "high":
                suggestions["recommended_approach"] = "urgent"
            elif intent_analysis.get("case_type"):
                suggestions["recommended_approach"] = "case_specific"
            
            return suggestions
            
        except Exception as e:
            print(f"Error getting smart response suggestions: {str(e)}")
            return {}

# Global instance
user_learning_service = UserLearningService()
