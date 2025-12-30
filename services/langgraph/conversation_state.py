"""
Conversation State Tracking Module
Tracks the stage of conversation and collected information.
Helps the LLM understand context and make smarter decisions.
"""

from typing import Dict, Optional, List, Any
from enum import Enum
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from .entity_extractor import extract_contact_info, get_missing_contact_fields


class ConversationStage(str, Enum):
    """Conversation stages for tracking progress"""
    GREETING = "greeting"  # Initial greeting
    DISCOVERY = "discovery"  # Learning about user's problem/need
    GATHERING_INFO = "gathering_info"  # Collecting case details
    COLLECTING_CONTACT = "collecting_contact"  # Getting name/phone for callback
    CONFIRMING_CONTACT = "confirming_contact"  # Confirming collected contact info
    OFFERING_HELP = "offering_help"  # Proposing solutions/next steps
    CLOSING = "closing"  # Conversation ending


class ConversationState:
    """
    Tracks conversation state including stage, collected information, and context.
    """

    def __init__(self):
        self.stage: ConversationStage = ConversationStage.GREETING
        self.contact_info: Dict[str, Optional[str]] = {
            "name": None,
            "phone": None,
            "email": None
        }
        self.case_info: Dict[str, Any] = {}  # Store case-specific details
        self.needs_callback: bool = False
        self.callback_confirmed: bool = False

    def update_from_message(self, user_message: str, chat_history: List[BaseMessage] = None):
        """
        Update conversation state based on user's message.

        Args:
            user_message: Latest message from user
            chat_history: Full conversation history for context
        """
        # Extract contact information
        extracted = extract_contact_info(user_message, chat_history)

        # Update contact info if new data found
        if extracted['name'] and not self.contact_info['name']:
            self.contact_info['name'] = extracted['name']
        if extracted['phone'] and not self.contact_info['phone']:
            self.contact_info['phone'] = extracted['phone']
        if extracted['email'] and not self.contact_info['email']:
            self.contact_info['email'] = extracted['email']

        # Check for callback request
        callback_keywords = [
            'call me', 'contact me', 'reach out', 'get back to me',
            'schedule', 'appointment', 'consultation', 'speak with',
            'talk to someone', 'attorney call', 'lawyer call'
        ]
        if any(keyword in user_message.lower() for keyword in callback_keywords):
            self.needs_callback = True

        # Update stage based on context
        self._update_stage(user_message, chat_history)

    def _update_stage(self, user_message: str, chat_history: List[BaseMessage] = None):
        """
        Update conversation stage based on current state and message.

        Args:
            user_message: Latest user message
            chat_history: Full conversation history
        """
        message_lower = user_message.lower()

        # If callback requested and we're collecting contact info
        if self.needs_callback:
            missing = get_missing_contact_fields(self.contact_info)

            if not missing:
                # All contact info collected
                if not self.callback_confirmed:
                    self.stage = ConversationStage.CONFIRMING_CONTACT
                else:
                    self.stage = ConversationStage.CLOSING
            else:
                # Still collecting contact info
                self.stage = ConversationStage.COLLECTING_CONTACT
            return

        # Check conversation history length
        history_length = len(chat_history) if chat_history else 0

        # First message - greeting
        if history_length == 0:
            self.stage = ConversationStage.GREETING
            return

        # User mentioned a problem/issue
        problem_keywords = [
            'accident', 'injury', 'hurt', 'crash', 'fall', 'slip',
            'workers comp', 'workplace', 'medical', 'malpractice',
            'help', 'problem', 'issue', 'happened'
        ]
        if any(keyword in message_lower for keyword in problem_keywords):
            if self.stage == ConversationStage.GREETING:
                self.stage = ConversationStage.DISCOVERY
            elif self.stage == ConversationStage.DISCOVERY:
                self.stage = ConversationStage.GATHERING_INFO
            return

        # Offering help phase
        if history_length >= 4:
            self.stage = ConversationStage.OFFERING_HELP

    def get_stage_prompt_hint(self) -> str:
        """
        Get a hint for the LLM about current conversation stage.

        Returns:
            String hint to add to system prompt
        """
        hints = {
            ConversationStage.GREETING: "User just started conversation. Be welcoming and ask what brings them here.",
            ConversationStage.DISCOVERY: "User mentioned a problem. Show empathy and ask what happened.",
            ConversationStage.GATHERING_INFO: "Gathering case details. Ask about injuries, timeline, documentation.",
            ConversationStage.COLLECTING_CONTACT: f"Collecting contact info for callback. Missing: {', '.join(get_missing_contact_fields(self.contact_info))}",
            ConversationStage.CONFIRMING_CONTACT: "Confirm collected contact info with user before proceeding.",
            ConversationStage.OFFERING_HELP: "User shared details. Offer next steps (consultation, attorney call, etc.)",
            ConversationStage.CLOSING: "Conversation wrapping up. Confirm next steps and thank them."
        }
        return hints.get(self.stage, "")

    def is_collecting_contact_info(self) -> bool:
        """Check if currently in contact collection phase"""
        return self.stage in [ConversationStage.COLLECTING_CONTACT, ConversationStage.CONFIRMING_CONTACT]

    def get_next_question_suggestion(self) -> Optional[str]:
        """
        Suggest what to ask next based on current state.

        Returns:
            Suggested question or None
        """
        # If collecting contact info, suggest what to ask for
        if self.stage == ConversationStage.COLLECTING_CONTACT:
            missing = get_missing_contact_fields(self.contact_info)
            if 'name' in missing:
                return "Ask for their name"
            elif 'phone' in missing:
                return "Ask for their phone number"

        # If confirming contact info
        if self.stage == ConversationStage.CONFIRMING_CONTACT:
            return f"Confirm: {self.contact_info['name']} at {self.contact_info['phone']}"

        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary for serialization.

        Returns:
            Dictionary representation of state
        """
        return {
            "stage": self.stage.value,
            "contact_info": self.contact_info,
            "case_info": self.case_info,
            "needs_callback": self.needs_callback,
            "callback_confirmed": self.callback_confirmed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationState':
        """
        Create ConversationState from dictionary.

        Args:
            data: Dictionary with state data

        Returns:
            ConversationState instance
        """
        state = cls()
        state.stage = ConversationStage(data.get("stage", "greeting"))
        state.contact_info = data.get("contact_info", {"name": None, "phone": None, "email": None})
        state.case_info = data.get("case_info", {})
        state.needs_callback = data.get("needs_callback", False)
        state.callback_confirmed = data.get("callback_confirmed", False)
        return state


def analyze_conversation_state(chat_history: List[BaseMessage], latest_message: str) -> ConversationState:
    """
    Analyze conversation history and current message to determine state.

    Args:
        chat_history: Full conversation history
        latest_message: Latest user message

    Returns:
        ConversationState object with current state
    """
    state = ConversationState()

    # Process all messages to build state
    for msg in chat_history:
        if isinstance(msg, HumanMessage):
            state.update_from_message(msg.content, chat_history)

    # Process latest message
    state.update_from_message(latest_message, chat_history)

    return state


# Example usage
if __name__ == "__main__":
    print("Testing Conversation State Tracking:")
    print("=" * 60)

    # Test case 1: Greeting
    state = ConversationState()
    state.update_from_message("Hi", [])
    print(f"\nMessage: 'Hi'")
    print(f"Stage: {state.stage}")
    print(f"Hint: {state.get_stage_prompt_hint()}")

    # Test case 2: Problem mentioned
    from langchain_core.messages import HumanMessage, AIMessage
    history = [
        HumanMessage(content="Hi"),
        AIMessage(content="Hello! What brings you here today?")
    ]
    state.update_from_message("I was in a car accident", history)
    print(f"\nMessage: 'I was in a car accident'")
    print(f"Stage: {state.stage}")
    print(f"Hint: {state.get_stage_prompt_hint()}")

    # Test case 3: Callback request
    history.append(HumanMessage(content="I was in a car accident"))
    history.append(AIMessage(content="I'm sorry to hear that. What happened?"))
    state.update_from_message("Can you have someone call me?", history)
    print(f"\nMessage: 'Can you have someone call me?'")
    print(f"Stage: {state.stage}")
    print(f"Needs callback: {state.needs_callback}")
    print(f"Hint: {state.get_stage_prompt_hint()}")

    # Test case 4: Providing name
    state.update_from_message("My name is John Smith", history)
    print(f"\nMessage: 'My name is John Smith'")
    print(f"Stage: {state.stage}")
    print(f"Contact info: {state.contact_info}")
    print(f"Next suggestion: {state.get_next_question_suggestion()}")

    # Test case 5: Providing phone
    state.update_from_message("555-123-4567", history)
    print(f"\nMessage: '555-123-4567'")
    print(f"Stage: {state.stage}")
    print(f"Contact info: {state.contact_info}")
    print(f"Next suggestion: {state.get_next_question_suggestion()}")
