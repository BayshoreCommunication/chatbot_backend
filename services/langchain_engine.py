"""
Legacy module that re-exports functionality from the new modular structure.
This file is kept for backward compatibility.
"""

from services.langchain.engine import ask_bot, add_document, escalate_to_human
from services.langchain.appointments import get_available_slots

# Re-export functions for backward compatibility
__all__ = ['ask_bot', 'add_document', 'escalate_to_human', 'get_available_slots']