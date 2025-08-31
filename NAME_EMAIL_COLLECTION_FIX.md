# Name and Email Collection Fix

## Issue Description

The chatbot was experiencing a critical bug where email addresses were being incorrectly treated as names, leading to:

1. **Repetitive prompts**: After a user provided their email, the chatbot would ask for the email again
2. **Incorrect greetings**: The chatbot would greet users using their email address instead of their name
3. **Poor user experience**: Users were confused by the bot's inability to properly collect and store their information

### Example of the Issue

**User Conversation:**

```
Bot: "I'd love to personalize our conversation better. What's your first name?"
User: "Sahak"
Bot: "Please provide a valid email address so I can better assist you."
User: "arsahak@gmail.com"
Bot: "Nice to meet you, arsahak@gmail.com! Could you please share your email address..."
```

**Problem:** The email address `arsahak@gmail.com` was being treated as the user's name, causing the bot to ask for the email again.

## Root Cause Analysis

The issue was in the name extraction logic in two places:

1. **`services/langchain/user_management.py`**: The `handle_name_collection` function had a fallback mechanism that treated any short text (≤3 words) that didn't end with "?" as a name, without checking if it was an email address.

2. **`services/conversation_flow.py`**: The `extract_name_from_text` function didn't have proper email detection before attempting name extraction.

## Solution Implemented

### 1. Enhanced Email Detection in Name Extraction

**File:** `services/conversation_flow.py`

Added email pattern detection at the beginning of the `extract_name_from_text` function:

```python
def extract_name_from_text(text: str) -> Tuple[Optional[str], bool]:
    text = text.strip()

    # Check if the text contains an email address - if so, it's not a name
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if re.search(email_pattern, text):
        return None, False

    # ... rest of the function
```

### 2. Improved Fallback Logic in User Management

**File:** `services/langchain/user_management.py`

Enhanced the fallback logic in `handle_name_collection` to exclude email addresses:

```python
# Only treat as name if we're confident it's not a refusal and not an email
if (not query.endswith("?") and len(query.split()) <= 3 and
    not any(keyword in query.lower() for keyword in skip_keywords) and
    not any(pattern in query.lower() for pattern in refusal_patterns) and
    "@" not in query and "." not in query):  # Don't treat emails as names
    name = query.strip()
else:
    name = None
```

### 3. Added Fallback Name Extraction

**File:** `services/conversation_flow.py`

Added a robust fallback function for when OpenAI API is unavailable:

```python
def extract_name_with_regex_fallback(text: str) -> Optional[str]:
    """Fallback name extraction using regex patterns"""
    text = text.strip()

    # Simple name patterns
    name_patterns = [
        r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)$',  # Capitalized words
        r'^([a-z]+(?:\s[a-z]+)*)$',  # All lowercase words
    ]

    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            # Basic validation - should be 2-50 characters and not contain special chars
            if 2 <= len(name) <= 50 and re.match(r'^[A-Za-z\s]+$', name):
                return name

    return None
```

### 4. Fixed Syntax Error in Chatbot Routes

**File:** `routes/chatbot.py`

Fixed a syntax error where the `except` block was misplaced, causing the fallback logic to be unreachable.

## New API Endpoints for Leads Management

### Updated Lead Management API

**File:** `routes/lead.py`

Enhanced the existing lead router to provide real database integration for leads management:

#### Available Endpoints:

1. **GET /lead/leads** - Get all leads for an organization

   - Returns all valid leads (name and email) from user profiles
   - Filters out anonymous users and invalid data
   - Requires `X-API-Key` header

2. **GET /lead/leads/{session_id}** - Get a specific lead by session ID

   - Returns lead information for a specific conversation session
   - Requires `X-API-Key` header

3. **GET /lead/leads/stats** - Get leads statistics
   - Returns statistics about leads collection
   - Includes total profiles, valid leads, leads with email, leads with name
   - Requires `X-API-Key` header

#### Example Usage:

```bash
# Get all leads
curl -X GET "http://localhost:8000/lead/leads" \
  -H "X-API-Key: your_organization_api_key"

# Response format:
{
  "leads": [
    {
      "name": "Sahak",
      "email": "arsahak@gmail.com",
      "session_id": "session_123",
      "created_at": "2024-01-01T12:00:00",
      "organization_id": "org_123"
    }
  ],
  "total_count": 1
}
```

## Testing

### Test Scripts Created:

1. **`test_name_email_issue.py`** - Reproduces the original issue
2. **`test_name_email_fix.py`** - Tests the fix implementation
3. **`test_complete_fix.py`** - Comprehensive test of the complete solution

### Test Results:

✅ **Email addresses are correctly NOT extracted as names**
✅ **Name extraction still works correctly**
✅ **Email extraction works correctly**
✅ **Refusal detection works correctly**
✅ **The user's conversation flow now works as expected**

## Impact

### Before the Fix:

- Users experienced confusing conversations
- Email addresses were treated as names
- Repetitive prompts for the same information
- Poor user experience

### After the Fix:

- Clean, logical conversation flow
- Proper name and email collection
- No more repetitive prompts
- Improved user experience
- New API endpoints for leads management

## Files Modified

1. `services/conversation_flow.py` - Enhanced name extraction logic
2. `services/langchain/user_management.py` - Improved fallback logic
3. `routes/chatbot.py` - Fixed syntax error
4. `routes/lead.py` - Enhanced leads API
5. `test_name_email_issue.py` - Test script (new)
6. `test_name_email_fix.py` - Test script (new)
7. `test_complete_fix.py` - Comprehensive test (new)

## Future Improvements

1. **Enhanced Name Validation**: Add more sophisticated name validation patterns
2. **Email Validation**: Add more robust email validation
3. **Lead Export**: Add CSV/Excel export functionality for leads
4. **Lead Analytics**: Add more detailed analytics and reporting
5. **CRM Integration**: Integrate with popular CRM systems

## Conclusion

The fix successfully resolves the name and email collection issue while maintaining backward compatibility and adding new functionality for leads management. The solution is robust, well-tested, and provides a foundation for future enhancements.
