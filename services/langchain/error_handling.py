import openai
import json

def handle_openai_rate_limit_error(error_message):
    """Handle OpenAI rate limit errors"""
    print(f"OpenAI Rate Limit Error: {error_message}")
    return {
        "status": "error", 
        "error_type": "openai_quota_exceeded",
        "message": "OpenAI API quota exceeded. Please check your billing details.",
        "detailed_error": error_message
    }

def handle_openai_api_error(error_message):
    """Handle general OpenAI API errors"""
    print(f"OpenAI API Error: {error_message}")
    return {
        "status": "error", 
        "error_type": "openai_api_error",
        "message": "There was an issue with the OpenAI API. Please try again later.",
        "detailed_error": error_message
    }

def handle_json_decode_error(error_message, language="en", user_data=None):
    """Handle JSON parsing errors"""
    print(f"JSON Decode Error: {error_message}")
    
    # Simple message about who the assistant is as fallback
    response = "I'm an AI assistant here to help with your questions and appointment scheduling. How can I assist you today?"
    
    return {
        "answer": response,
        "mode": "faq",
        "language": language,
        "user_data": user_data or {}
    }

def handle_general_error(error_message, language="en", user_data=None):
    """General error handling for any other exceptions"""
    print(f"General Error: {error_message}")
    
    try:
        # Simple message about who the assistant is as fallback
        response = "I'm an AI assistant here to help with your questions and appointment scheduling. How can I assist you today?"
        
        return {
            "answer": response,
            "mode": "faq",
            "language": language,
            "user_data": user_data or {}
        }
    except:
        # Ultimate fallback if everything fails
        return {
            "status": "error",
            "error_type": "general_error",
            "message": f"An error occurred: {error_message}"
        }

def create_error_handler(func):
    """Decorator for adding error handling to functions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError as e:
            return handle_openai_rate_limit_error(str(e))
        except openai.APIError as e:
            return handle_openai_api_error(str(e))
        except json.JSONDecodeError as e:
            language = kwargs.get("language", "en")
            user_data = kwargs.get("user_data", {})
            return handle_json_decode_error(str(e), language, user_data)
        except Exception as e:
            language = kwargs.get("language", "en")
            user_data = kwargs.get("user_data", {})
            return handle_general_error(str(e), language, user_data)
    return wrapper 