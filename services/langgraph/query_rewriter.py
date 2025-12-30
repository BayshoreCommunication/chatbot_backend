"""
Query Rewriting Module
Rewrites user queries to be standalone by incorporating conversation context.
This ensures vector search works correctly even with pronouns like "it", "that", "they".

All prompts are now in prompts.py for centralized management.
"""

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List
from .llm import llm
from .prompts import QUERY_REWRITE_PROMPT


def should_rewrite_query(question: str, chat_history: List[BaseMessage]) -> bool:
    """
    Determine if query needs rewriting based on pronouns and chat history.

    Args:
        question: Current user question
        chat_history: Previous conversation messages

    Returns:
        True if query should be rewritten
    """
    # If no history, no need to rewrite
    if not chat_history or len(chat_history) < 2:
        return False

    # Check for common pronouns that indicate context dependency
    pronouns = [
        'it', 'that', 'this', 'these', 'those', 'they', 'them', 'their',
        'he', 'she', 'his', 'her', 'its'
    ]

    question_lower = question.lower()

    # Check if question contains pronouns
    contains_pronouns = any(
        f' {pronoun} ' in f' {question_lower} ' or
        question_lower.startswith(f'{pronoun} ') or
        question_lower.endswith(f' {pronoun}')
        for pronoun in pronouns
    )

    # Check for context-dependent phrases
    context_phrases = [
        'what about',
        'how about',
        'tell me more',
        'more about',
        'also',
        'and',
        'what else',
        'anything else'
    ]

    contains_context_phrase = any(phrase in question_lower for phrase in context_phrases)

    return contains_pronouns or contains_context_phrase


def format_chat_history_for_rewrite(chat_history: List[BaseMessage], max_turns: int = 3) -> str:
    """
    Format recent chat history for query rewriting.

    Args:
        chat_history: List of conversation messages
        max_turns: Maximum number of conversation turns to include

    Returns:
        Formatted chat history string
    """
    if not chat_history:
        return "No previous conversation"

    formatted = []
    # Get last N messages (N = max_turns * 2)
    recent_messages = chat_history[-(max_turns * 2):]

    for msg in recent_messages:
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            formatted.append(f"Assistant: {msg.content}")

    return "\n".join(formatted)


def rewrite_query(question: str, chat_history: List[BaseMessage]) -> str:
    """
    Rewrite user query to be standalone using conversation context.

    Args:
        question: Current user question
        chat_history: Previous conversation messages

    Returns:
        Rewritten query (or original if no rewriting needed)
    """
    # Check if rewriting is needed
    if not should_rewrite_query(question, chat_history):
        print(f"[QUERY REWRITER] No rewriting needed for: {question}")
        return question

    print(f"[QUERY REWRITER] Rewriting query: {question}")

    try:
        # Format chat history
        history_text = format_chat_history_for_rewrite(chat_history, max_turns=3)

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("human", QUERY_REWRITE_PROMPT)
        ])

        # Create chain
        chain = prompt | llm | StrOutputParser()

        # Invoke rewriting
        rewritten = chain.invoke({
            "chat_history": history_text,
            "question": question
        })

        rewritten = rewritten.strip()

        print(f"[QUERY REWRITER] Original: {question}")
        print(f"[QUERY REWRITER] Rewritten: {rewritten}")

        return rewritten

    except Exception as e:
        print(f"[QUERY REWRITER] Error rewriting query: {str(e)}")
        # Fallback to original question
        return question


