"""
Intent Detection Module
Intelligently detects user's intent using LLM-based classification.
Helps the chatbot understand what the user wants and respond appropriately.
"""

from typing import List, Tuple, Optional
from enum import Enum
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .llm import llm


class UserIntent(str, Enum):
    """User intent categories"""
    GREETING = "greeting"  # Hi, hello, hey
    QUESTION = "question"  # Asking for information
    CALLBACK_REQUEST = "callback_request"  # Wants someone to call them
    PROVIDING_INFO = "providing_info"  # Sharing their info (name, phone, details)
    CONFIRMATION = "confirmation"  # Yes/no/confirming something
    COMPLAINT = "complaint"  # Expressing frustration/complaint
    FAREWELL = "farewell"  # Goodbye, bye, etc.
    OTHER = "other"  # Anything else


INTENT_DETECTION_PROMPT = """You are an intent classifier for a legal chatbot assistant.

Analyze the user's message and determine their primary intent from these categories:

**greeting** - User is saying hi, hello, or starting conversation
Examples: "Hi", "Hello", "Hey there", "Good morning"

**question** - User is asking for information or has a question
Examples: "What are your hours?", "Do you handle car accidents?", "How much does it cost?"

**callback_request** - User wants someone to call them or contact them
Examples: "Call me", "Can someone reach out?", "I want to talk to an attorney", "Schedule a consultation"

**providing_info** - User is providing their information (name, phone, details about their case)
Examples: "My name is John", "555-1234", "I was in an accident yesterday", "My back hurts"

**confirmation** - User is confirming or denying something (yes/no)
Examples: "Yes", "No", "That's correct", "Yep", "Nope"

**complaint** - User is expressing frustration or complaining
Examples: "This isn't helping", "I've been waiting forever", "You're not understanding me"

**farewell** - User is ending the conversation
Examples: "Bye", "Goodbye", "Thanks, that's all", "See you later"

**other** - Anything that doesn't fit above categories

CONVERSATION HISTORY (for context):
{chat_history}

USER'S CURRENT MESSAGE:
{message}

Respond with ONLY ONE WORD - the intent category:
greeting, question, callback_request, providing_info, confirmation, complaint, farewell, or other

INTENT:"""


def detect_intent(message: str, chat_history: List[BaseMessage] = None) -> Tuple[UserIntent, float]:
    """
    Detect user's intent using LLM classification.

    Args:
        message: User's message
        chat_history: Previous conversation messages for context

    Returns:
        Tuple of (UserIntent, confidence_score)
    """
    # Quick rule-based checks for common patterns (faster)
    message_lower = message.lower().strip()

    # Very short greetings
    if message_lower in ['hi', 'hello', 'hey', 'hiya', 'howdy']:
        return UserIntent.GREETING, 0.95

    # Very short farewells
    if message_lower in ['bye', 'goodbye', 'bye bye', 'see you', 'later']:
        return UserIntent.FAREWELL, 0.95

    # Very short confirmations
    if message_lower in ['yes', 'no', 'yep', 'nope', 'yeah', 'nah', 'ok', 'okay']:
        return UserIntent.CONFIRMATION, 0.90

    # Callback request keywords
    callback_keywords = ['call me', 'contact me', 'reach out', 'schedule', 'consultation', 'talk to someone']
    if any(keyword in message_lower for keyword in callback_keywords):
        return UserIntent.CALLBACK_REQUEST, 0.85

    # Use LLM for more complex cases
    try:
        # Format chat history
        history_text = ""
        if chat_history and len(chat_history) > 0:
            recent = chat_history[-4:]  # Last 2 turns
            history_parts = []
            for msg in recent:
                if isinstance(msg, HumanMessage):
                    history_parts.append(f"User: {msg.content}")
                elif isinstance(msg, AIMessage):
                    history_parts.append(f"Assistant: {msg.content}")
            history_text = "\n".join(history_parts)
        else:
            history_text = "No previous conversation"

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("human", INTENT_DETECTION_PROMPT)
        ])

        # Create chain
        chain = prompt | llm | StrOutputParser()

        # Detect intent
        result = chain.invoke({
            "message": message,
            "chat_history": history_text
        })

        result = result.strip().lower()

        # Map result to UserIntent
        intent_map = {
            'greeting': UserIntent.GREETING,
            'question': UserIntent.QUESTION,
            'callback_request': UserIntent.CALLBACK_REQUEST,
            'providing_info': UserIntent.PROVIDING_INFO,
            'confirmation': UserIntent.CONFIRMATION,
            'complaint': UserIntent.COMPLAINT,
            'farewell': UserIntent.FAREWELL,
            'other': UserIntent.OTHER
        }

        detected_intent = intent_map.get(result, UserIntent.OTHER)
        confidence = 0.8  # LLM-based detection confidence

        print(f"[INTENT DETECTOR] Message: '{message[:50]}...' -> Intent: {detected_intent} (confidence: {confidence})")

        return detected_intent, confidence

    except Exception as e:
        print(f"[INTENT DETECTOR] Error detecting intent: {str(e)}")
        # Fallback to OTHER
        return UserIntent.OTHER, 0.5


def get_intent_specific_guidance(intent: UserIntent) -> str:
    """
    Get specific guidance for the LLM based on detected intent.

    Args:
        intent: Detected user intent

    Returns:
        Guidance string to add to system prompt
    """
    guidance = {
        UserIntent.GREETING: "User is greeting you. Respond warmly and ask what brings them here.",
        UserIntent.QUESTION: "User has a question. Provide clear, helpful information from your knowledge base.",
        UserIntent.CALLBACK_REQUEST: "User wants a callback. Start collecting their name and phone number.",
        UserIntent.PROVIDING_INFO: "User is sharing information. Acknowledge what they shared and ask relevant follow-up.",
        UserIntent.CONFIRMATION: "User is confirming something. Proceed based on their confirmation (yes/no).",
        UserIntent.COMPLAINT: "User is frustrated. Show empathy and try to help resolve their concern.",
        UserIntent.FAREWELL: "User is ending conversation. Thank them and offer to help again in the future.",
        UserIntent.OTHER: "Respond naturally based on the context."
    }
    return guidance.get(intent, "")


def should_collect_contact_info(intent: UserIntent) -> bool:
    """
    Determine if we should collect contact info based on intent.

    Args:
        intent: Detected user intent

    Returns:
        True if should collect contact info
    """
    return intent == UserIntent.CALLBACK_REQUEST


def is_conversation_ending(intent: UserIntent) -> bool:
    """
    Check if conversation is ending based on intent.

    Args:
        intent: Detected user intent

    Returns:
        True if conversation is ending
    """
    return intent == UserIntent.FAREWELL


# Example usage and testing
if __name__ == "__main__":
    print("Testing Intent Detection:")
    print("=" * 60)

    test_cases = [
        ("Hi", UserIntent.GREETING),
        ("Hello there", UserIntent.GREETING),
        ("What are your hours?", UserIntent.QUESTION),
        ("Do you handle car accidents?", UserIntent.QUESTION),
        ("Can someone call me?", UserIntent.CALLBACK_REQUEST),
        ("I want to talk to an attorney", UserIntent.CALLBACK_REQUEST),
        ("My name is John Smith", UserIntent.PROVIDING_INFO),
        ("555-123-4567", UserIntent.PROVIDING_INFO),
        ("Yes", UserIntent.CONFIRMATION),
        ("No thanks", UserIntent.CONFIRMATION),
        ("This isn't helping", UserIntent.COMPLAINT),
        ("Goodbye", UserIntent.FAREWELL),
        ("Thanks bye", UserIntent.FAREWELL),
    ]

    for message, expected_intent in test_cases:
        detected_intent, confidence = detect_intent(message)
        status = "✓" if detected_intent == expected_intent else "✗"
        print(f"{status} '{message}'")
        print(f"   Expected: {expected_intent}, Got: {detected_intent} (confidence: {confidence:.2f})")
        print(f"   Guidance: {get_intent_specific_guidance(detected_intent)}")
        print()
