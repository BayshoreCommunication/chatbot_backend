"""
Off-Topic Question Detection and Handling
Detects when users ask questions unrelated to the organization's knowledge base
and provides professional, helpful redirects.

All prompts are now in prompts.py for centralized management.
"""

from typing import List, Optional, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .llm import llm
from .prompts import OFF_TOPIC_DETECTION_PROMPT, OFF_TOPIC_REDIRECT_PROMPT


def is_greeting(text: str) -> bool:
    """Check if the text is a simple greeting"""
    greetings = [
        'hi', 'hello', 'hey', 'greetings', 'good morning',
        'good afternoon', 'good evening', 'hola', 'howdy'
    ]
    text_lower = text.lower().strip()

    # Check if it's a short greeting
    if len(text_lower.split()) <= 3:
        for greeting in greetings:
            if greeting in text_lower:
                return True
    return False


def is_likely_off_topic(question: str, context: str) -> bool:
    """
    NO HARDCODED PATTERNS - LLM decides everything intelligently.

    This function just does basic filtering for greetings.
    All off-topic detection is done by LLM based on organization context.

    Args:
        question: User's question
        context: Knowledge base context

    Returns:
        False - always let LLM decide
    """
    # Don't flag greetings as off-topic
    if is_greeting(question):
        return False

    # NO HARDCODED PATTERNS
    # LLM will intelligently decide what's off-topic based on:
    # - Organization's business context
    # - Conversation history
    # - Question relevance
    return False


def detect_off_topic(
    question: str,
    context: str,
    company_name: str,
    chat_history: List[BaseMessage]
) -> Tuple[bool, float]:
    """
    Detect if a question is off-topic using LLM.

    Args:
        question: User's question
        context: Knowledge base context
        company_name: Organization name
        chat_history: Conversation history

    Returns:
        Tuple of (is_off_topic: bool, confidence: float)
    """
    # Quick pre-filter (but if context is empty, always check with LLM)
    if context and len(context.strip()) > 50:
        # We have good context, use pre-filter
        if not is_likely_off_topic(question, context):
            return False, 0.0
    # If no context or poor context, always run LLM check

    print(f"[OFF-TOPIC] Checking if off-topic: {question}")

    try:
        # Format chat history
        history_text = ""
        if chat_history:
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
            ("human", OFF_TOPIC_DETECTION_PROMPT)
        ])

        # Create chain
        chain = prompt | llm | StrOutputParser()

        # Detect
        result = chain.invoke({
            "question": question,
            "context": context[:1000],  # Limit context length
            "company_name": company_name,
            "chat_history": history_text
        })

        result = result.strip().upper()

        is_off_topic = "OFF_TOPIC" in result or "OFF-TOPIC" in result
        confidence = 0.9 if is_off_topic else 0.1

        print(f"[OFF-TOPIC] Detection result: {result} (off_topic={is_off_topic})")

        return is_off_topic, confidence

    except Exception as e:
        print(f"[OFF-TOPIC] Error in detection: {str(e)}")
        # Fallback to rule-based
        return is_likely_off_topic(question, context), 0.5


def generate_redirect_response(
    question: str,
    context: str,
    company_name: str,
    chat_history: List[BaseMessage]
) -> str:
    """
    Generate a smart redirect response for off-topic questions.

    Args:
        question: User's off-topic question
        context: Knowledge base context (to suggest relevant topics)
        company_name: Organization name
        chat_history: Conversation history

    Returns:
        Friendly redirect message
    """
    print(f"[OFF-TOPIC] Generating redirect for: {question}")

    try:
        # Format chat history
        history_text = "\n".join([
            f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content}"
            for msg in chat_history[-4:]  # Last 4 messages for context
        ]) if chat_history else "No previous conversation"

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("human", OFF_TOPIC_REDIRECT_PROMPT)
        ])

        # Create chain
        chain = prompt | llm | StrOutputParser()

        # Generate redirect
        redirect = chain.invoke({
            "question": question,
            "company_name": company_name,
            "context": context[:1000] if context else "Personal injury law, car accidents, workers' compensation",  # Fallback context
            "chat_history": history_text
        })

        redirect = redirect.strip()

        print(f"[OFF-TOPIC] Generated redirect ({len(redirect)} chars)")

        return redirect

    except Exception as e:
        print(f"[OFF-TOPIC] Error generating redirect: {str(e)}")

        # Fallback generic redirect
        return f"""I appreciate your question, but I'm specifically designed to help with {company_name}-related topics.

I'd be happy to help you with questions about our products, services, pricing, or support. What would you like to know?"""


def should_check_off_topic(question: str, kb_context: str, sources: List[dict]) -> bool:
    """
    Determine if we should ask LLM to check for off-topic.

    LLM DECIDES EVERYTHING - no hardcoded patterns.
    Check with LLM when KB has poor results.

    Args:
        question: User's question
        kb_context: Retrieved knowledge base context
        sources: Retrieved sources

    Returns:
        True if we should ask LLM to check off-topic
    """
    # Don't check for greetings
    if is_greeting(question):
        return False

    # Don't check very short conversational responses (they're contextual)
    # Things like "Yes", "No", "Car" are part of ongoing conversation
    question_words = question.strip().split()
    if len(question_words) <= 2:
        # Very short responses are contextual, let LLM handle in answer node
        return False

    # If KB has poor results, ask LLM to check if it's off-topic
    # LLM will intelligently decide based on organization context
    if not kb_context or len(kb_context.strip()) < 50:
        # Poor KB results - let LLM decide if it's off-topic
        return True

    # Check if sources have very low relevance scores
    if sources:
        avg_score = sum(s.get('score', 0) for s in sources) / len(sources)
        if avg_score < 0.25:  # Very low relevance
            # Let LLM check if it's off-topic
            return True

    # Good KB results - skip off-topic check, go straight to answer
    return False
