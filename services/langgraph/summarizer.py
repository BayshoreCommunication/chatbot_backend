"""
Conversation Summarization Module
Compresses long conversation history into concise summaries to maintain context
while staying within token limits.

All prompts are now in prompts.py for centralized management.
"""

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List, Dict
from .llm import llm
from .prompts import SUMMARIZATION_PROMPT, PROGRESSIVE_SUMMARIZATION_PROMPT


def format_messages_for_summary(messages: List[BaseMessage]) -> str:
    """
    Format messages into readable text for summarization.

    Args:
        messages: List of conversation messages

    Returns:
        Formatted conversation text
    """
    formatted = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            formatted.append(f"Assistant: {msg.content}")

    return "\n".join(formatted)


def should_summarize(messages: List[BaseMessage], threshold: int = 12) -> bool:
    """
    Determine if conversation should be summarized based on length.

    Args:
        messages: List of conversation messages
        threshold: Number of messages that triggers summarization (default: 12 = 6 turns)

    Returns:
        True if conversation should be summarized
    """
    return len(messages) >= threshold


def summarize_conversation(messages: List[BaseMessage]) -> str:
    """
    Create a concise summary of the conversation history.

    Args:
        messages: List of conversation messages

    Returns:
        Conversation summary
    """
    if not messages:
        return ""

    print(f"[SUMMARIZER] Summarizing {len(messages)} messages")

    try:
        # Format messages
        chat_text = format_messages_for_summary(messages)

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("human", SUMMARIZATION_PROMPT)
        ])

        # Create chain
        chain = prompt | llm | StrOutputParser()

        # Generate summary
        summary = chain.invoke({
            "chat_history": chat_text
        })

        summary = summary.strip()

        print(f"[SUMMARIZER] Generated summary ({len(summary)} chars)")
        return summary

    except Exception as e:
        print(f"[SUMMARIZER] Error summarizing conversation: {str(e)}")
        # Fallback: Simple truncation
        return format_messages_for_summary(messages[-6:])  # Last 3 turns


def progressive_summarize(existing_summary: str, new_messages: List[BaseMessage]) -> str:
    """
    Update existing summary with new conversation turns.
    More efficient than re-summarizing entire conversation.

    Args:
        existing_summary: Previous conversation summary
        new_messages: New messages since last summarization

    Returns:
        Updated summary
    """
    if not new_messages:
        return existing_summary

    print(f"[SUMMARIZER] Progressive summarization with {len(new_messages)} new messages")

    try:
        # Format new messages
        new_turns_text = format_messages_for_summary(new_messages)

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("human", PROGRESSIVE_SUMMARIZATION_PROMPT)
        ])

        # Create chain
        chain = prompt | llm | StrOutputParser()

        # Generate updated summary
        updated_summary = chain.invoke({
            "existing_summary": existing_summary,
            "new_turns": new_turns_text
        })

        updated_summary = updated_summary.strip()

        print(f"[SUMMARIZER] Updated summary ({len(updated_summary)} chars)")
        return updated_summary

    except Exception as e:
        print(f"[SUMMARIZER] Error in progressive summarization: {str(e)}")
        # Fallback: Append new messages to summary
        return f"{existing_summary}\n\nRecent updates:\n{format_messages_for_summary(new_messages[-4:])}"


def get_summarized_context(messages: List[BaseMessage], max_recent_turns: int = 3) -> Dict[str, any]:
    """
    Get conversation context with automatic summarization for long conversations.
    Returns both summary of old messages and recent messages in full.

    Args:
        messages: Full conversation history
        max_recent_turns: Number of recent turns to keep in full (default: 3 = 6 messages)

    Returns:
        Dict with 'summary' (str), 'recent_messages' (List[BaseMessage]), and 'has_summary' (bool)
    """
    if not messages:
        return {
            "summary": "",
            "recent_messages": [],
            "has_summary": False
        }

    max_recent_messages = max_recent_turns * 2

    # If conversation is short, no summarization needed
    if len(messages) <= max_recent_messages:
        return {
            "summary": "",
            "recent_messages": messages,
            "has_summary": False
        }

    # Split into old (to summarize) and recent (keep in full)
    old_messages = messages[:-max_recent_messages]
    recent_messages = messages[-max_recent_messages:]

    # Summarize old messages
    summary = summarize_conversation(old_messages)

    print(f"[SUMMARIZER] Context: {len(old_messages)} messages summarized, {len(recent_messages)} kept in full")

    return {
        "summary": summary,
        "recent_messages": recent_messages,
        "has_summary": True
    }


def format_context_with_summary(summary: str, recent_messages: List[BaseMessage]) -> str:
    """
    Format conversation context combining summary and recent messages.

    Args:
        summary: Summary of older conversation
        recent_messages: Recent conversation messages

    Returns:
        Formatted context string
    """
    parts = []

    if summary:
        parts.append("=== Previous Conversation Summary ===")
        parts.append(summary)
        parts.append("")

    if recent_messages:
        parts.append("=== Recent Conversation ===")
        parts.append(format_messages_for_summary(recent_messages))

    return "\n".join(parts)
