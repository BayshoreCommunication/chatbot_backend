#!/usr/bin/env python3
"""
Natural Conversation Flow Controller
Manages when and how to collect user information during conversations
"""

def calculate_engagement_score(conversation_history, user_query):
    """Calculate user engagement based on conversation patterns"""
    if not conversation_history:
        return 0.0
    
    score = 0
    
    # Points for conversation length
    conversation_count = len(conversation_history)
    score += min(conversation_count * 0.1, 0.4)  # Max 0.4 for length
    
    # Points for question complexity
    if len(user_query.split()) > 5:
        score += 0.2
    
    # Points for showing interest keywords
    interest_keywords = [
        "consultation", "appointment", "help", "case", "injured", 
        "accident", "legal", "lawyer", "attorney", "sue", "claim"
    ]
    
    if any(keyword in user_query.lower() for keyword in interest_keywords):
        score += 0.3
    
    # Points for asking follow-up questions
    recent_user_messages = [msg for msg in conversation_history[-6:] if msg.get('role') == 'user']
    if len(recent_user_messages) >= 2:
        score += 0.2
    
    return min(score, 1.0)  # Cap at 1.0

def should_collect_information(conversation_history, user_query, current_mode):
    """Determine if we should collect user information at this point"""
    conversation_count = len(conversation_history)
    
    # Never collect in first 4 exchanges (8 messages total)
    if conversation_count < 8:
        return False
    
    # Always collect if user is trying to book appointment
    if current_mode == "appointment":
        return True
    
    # Collect if user shows high engagement
    engagement = calculate_engagement_score(conversation_history, user_query)
    if engagement > 0.6:
        return True
    
    # Collect if conversation is getting long (user is invested)
    if conversation_count > 12:  # 6+ exchanges
        return True
    
    return False

def get_natural_collection_prompt(user_context, info_type="name"):
    """Generate natural prompts for information collection"""
    conversation_count = len(user_context.get("conversation_history", []))
    
    if info_type == "name":
        if conversation_count > 10:
            return "I'd love to personalize our conversation better. What's your first name?"
        else:
            return "By the way, what should I call you?"
    
    elif info_type == "email":
        if user_context.get("name"):
            return f"Thanks, {user_context['name']}! If you'd like me to send you some helpful information, what's your email address?"
        else:
            return "If you'd like me to send you some helpful resources, what's your email address?"
    
    return "Could you share your contact information so I can better assist you?"

def clear_conversation_cache(session_id, org_id):
    """Clear any cached conversation data"""
    try:
        from services.cache import cache
        
        # Clear various cache keys that might be storing conversation state
        cache_keys = [
            f"conversation:{org_id}:{session_id}",
            f"user_data:{org_id}:{session_id}",
            f"session:{org_id}:{session_id}",
            f"visitor:{org_id}:{session_id}"
        ]
        
        for key in cache_keys:
            try:
                cache.delete(key)
                print(f"[CACHE] Cleared cache key: {key}")
            except Exception as e:
                print(f"[CACHE] Error clearing key {key}: {str(e)}")
        
        return True
    except Exception as e:
        print(f"[CACHE] Error in clear_conversation_cache: {str(e)}")
        return False

def reset_user_session(org_id, session_id):
    """Reset user session data to start fresh"""
    try:
        from services.database import db
        
        # Clear visitor data
        db.visitors.update_one(
            {"organization_id": org_id, "session_id": session_id},
            {"$unset": {"profile_data": "", "metadata.user_data": ""}}
        )
        
        # Clear user profiles
        db.user_profiles.delete_many({
            "organization_id": org_id, 
            "session_id": session_id
        })
        
        print(f"[SESSION] Reset session data for {org_id}:{session_id}")
        return True
    except Exception as e:
        print(f"[SESSION] Error resetting session: {str(e)}")
        return False
