import openai
import json
import re

def analyze_query(query, user_info, mode, needs_info, has_vector_data, conversation_summary):
    """Use AI to analyze a query and determine the best response approach"""
    available_modes = ["faq", "appointment", "sales", "lead_capture"]
    
    # PRE-ANALYSIS: Check for specific appointment patterns first
    appointment_patterns = [
        r'slot_\d{4}-\d{2}-\d{2}_\d+_\d+',  # Direct slot ID
        r'confirm.*slot',  # Confirm + slot
        r'book.*slot',     # Book + slot
        r'confirm.*\d+:\d+',  # Confirm + time
        r'confirm.*this.*one',  # Confirm this one
        r'i want.*slot',   # I want slot
        r'take.*slot',     # Take slot
        r'pick.*slot',     # Pick slot
        r'choose.*slot',   # Choose slot
        r'book.*appointment',  # Book appointment
        r'schedule.*appointment',  # Schedule appointment
        r'confirm.*appointment',  # Confirm appointment
        r'book.*\d+:\d+.*[ap]m',  # Book + time with AM/PM
        r'confirm.*\d+:\d+.*[ap]m',  # Confirm + time with AM/PM
    ]
    
    is_appointment_query = any(re.search(pattern, query.lower()) for pattern in appointment_patterns)
    has_slot_id = bool(re.search(r'slot_\d{4}-\d{2}-\d{2}_\d+_\d+', query))
    
    analysis_prompt = f"""
    You are an AI assistant analyzing a user query to determine the best response approach.
    
    USER QUERY: "{query}"
    
    USER INFORMATION:
    - Name: {user_info['name']}
    - Email: {user_info['email']}
    - Has booked appointment: {user_info['has_appointment']}
    - Appointment details: {user_info['appointment_details']}
    
    CONTEXT:
    - Current mode: {mode}
    - Needs personal info: {needs_info}
    - Has knowledge base: {has_vector_data}
    
    CONVERSATION HISTORY:
    {conversation_summary}
    
    PRE-ANALYSIS DETECTION:
    - Contains appointment patterns: {is_appointment_query}
    - Contains slot ID: {has_slot_id}
    
    CRITICAL APPOINTMENT DETECTION RULES:
    1. If query contains a slot ID (format: slot_YYYY-MM-DD_HH_MM), this is ALWAYS an appointment booking action
    2. If query has "confirm" + slot/time, this is appointment booking
    3. If query has "book/schedule/pick/take/choose" + appointment/slot/time, this is appointment booking
    4. Appointment confirmation queries should have appointment_action="book" even if using words like "confirm"
    5. Time selection with previous appointment context is also appointment booking
    
    Analyze the following aspects and respond in JSON format:
    1. What is the user's primary intent?
    2. Should we collect user information before proceeding? (Name/Email)
    3. What mode is most appropriate? (faq/appointment/sales/lead_capture)
    4. Does this query need knowledge base lookup?
    5. If appointment related, is user trying to book, reschedule, or cancel?
    6. Any special handling needed? (like identity questions)
    
    MODE DESCRIPTIONS:
    - faq: General knowledge questions and information retrieval
    - appointment: Booking, managing, or inquiring about appointments
    - sales: Inquiries about products, services, or pricing
    - lead_capture: When the user is indicating interest in becoming a client
    
    MODE SELECTION RULES:
    - If user mentions scheduling, booking, availability, or has slot ID, use appointment mode
    - If user asks about products, pricing, or deals, use sales mode
    - If user mentions becoming a client or asks how to start, use lead_capture mode
    - Default to faq mode for general information questions
    - If currently in a specific mode (like appointment) but has completed the process, switch back to faq
    
    APPOINTMENT ACTION DETECTION:
    - "book": When user wants to book/confirm/schedule/pick/take/choose a slot or time
    - "reschedule": When user wants to change existing appointment
    - "cancel": When user wants to cancel existing appointment
    - "info": When user asks about existing appointment details
    - "none": When not appointment related
    
    EXAMPLES:
    - "confirm this one : slot_2025-06-24_13_59" → appointment_action="book"
    - "I want to book the 3pm slot" → appointment_action="book"
    - "book appointment for Monday" → appointment_action="book"
    - "confirm my appointment" → appointment_action="info" (if has existing) or "book" (if confirming new)
    - "reschedule my appointment" → appointment_action="reschedule"
    - "cancel my appointment" → appointment_action="cancel"
    
    CRITICAL INSTRUCTIONS:
    - Identity questions (like "who are you?") should be marked for special_handling="identity"
    - All queries about identity, background, experience, etc. should have needs_knowledge_lookup=true
    - ALWAYS prioritize collecting user information if it's missing
    - If pre-analysis detected appointment patterns, strongly favor appointment mode
    
    RESPOND WITH JSON ONLY in the following format:
    {{
        "intent": "primary user intent",
        "collect_info": true/false,
        "info_to_collect": "name/email/none",
        "appropriate_mode": "one of {', '.join(available_modes)}",
        "needs_knowledge_lookup": true/false,
        "appointment_action": "book/reschedule/cancel/info/none",
        "special_handling": "identity/none/other",
        "mode_confidence": "high/medium/low",
        "reasoning": "brief explanation of mode selection"
    }}
    """
    
    # Call OpenAI for central analysis
    try:
        analysis_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": analysis_prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        # Parse analysis
        analysis = json.loads(analysis_response.choices[0].message.content)
        
        # OVERRIDE: If we detected appointment patterns, force appointment mode
        if is_appointment_query or has_slot_id:
            analysis["appropriate_mode"] = "appointment"
            if has_slot_id or any(word in query.lower() for word in ["confirm", "book", "schedule", "pick", "take", "choose"]):
                analysis["appointment_action"] = "book"
                analysis["mode_confidence"] = "high"
                analysis["reasoning"] = "Detected slot ID or appointment confirmation pattern"
        
        return analysis
    except Exception as e:
        # Enhanced fallback analysis for appointment queries
        fallback_analysis = {
            "intent": "general question",
            "collect_info": needs_info,
            "info_to_collect": "name" if "name" not in user_info or user_info["name"] == "Unknown" else "email" if "email" not in user_info or user_info["email"] == "Unknown" else "none",
            "appropriate_mode": mode,
            "needs_knowledge_lookup": True,
            "appointment_action": "none",
            "special_handling": "none",
            "mode_confidence": "low",
            "reasoning": "Error in analysis, falling back to current mode"
        }
        
        # Override for appointment patterns even in error case
        if is_appointment_query or has_slot_id:
            fallback_analysis["appropriate_mode"] = "appointment"
            fallback_analysis["appointment_action"] = "book"
            fallback_analysis["reasoning"] = "Fallback: detected appointment pattern"
        
        return fallback_analysis

def generate_response(query, user_info, conversation_summary, retrieved_context, personal_information, analysis, language, organization=None):
    """Generate the final AI response based on context and analysis.
    The optional organization param can tailor tone slightly without changing core logic.
    """
    # Check if query is about identity/experience/background
    identity_keywords = ["who are you", "what are you", "your name", "about yourself", "tell me about you",
                         "your experience", "your background", "your education", "your skills", 
                         "your work", "your expertise", "about your experience", "qualification", 
                         "tell me about your work", "your profile", "about your background"]
    
    is_identity_query = any(keyword in query.lower() for keyword in identity_keywords)
    
    # Build a prompt that includes all relevant context
    vertical_hint = "Professional assistant for law firms, real estate, clinics, agencies, and consultants"
    org_name = organization.get("name") if isinstance(organization, dict) else None
    branding = f"Organization: {org_name}" if org_name else ""

    final_prompt = f"""
    Act as a concise, professional {vertical_hint}. {branding}
    - Answer clearly first, then optionally ask ONE short clarifying question if needed.
    - Use retrieved knowledge faithfully; avoid speculation. If unsure, say so briefly and suggest next step.
    - Keep to 2-5 sentences. Use plain language. Avoid greetings and fluff.
    - If the user shows intent to engage (hire/book/contact), smoothly guide them and note we can follow up by email/phone if provided.
    - Never fabricate identities or credentials. Follow ABI/org behavior if provided.

    USER QUERY: "{query}"

    CONVERSATION HISTORY (last 6 messages):
    {conversation_summary}

    {"RETRIEVED INFORMATION:" if retrieved_context else ""}
    {retrieved_context}

    {"PERSONAL INFORMATION FOUND:" if personal_information else ""}
    {json.dumps(personal_information) if personal_information else ""}

    USER INTENT: {analysis["intent"]}
    LANGUAGE: {language}
    """
    
    # Add special instruction for identity queries
    if is_identity_query:
        final_prompt += """
        CRITICAL IDENTITY BEHAVIOR ENFORCEMENT:

            1. Check if AI Behavior Instructions (ABI) are present and define a specific identity (e.g., "You are Alex, a marketing agent").
                - ✅ If YES: You must strictly assume ONLY that identity and act as that role (e.g., Alex).
                    - Use "I" statements only in context of that ABI-defined identity.
                    - Completely IGNORE any retrieved personal profiles (such as lawyers, professionals, etc.).
                    - DO NOT reference retrieved names (e.g., "Rayhan Al Mim") under any circumstance.
                - ❌ If NO ABI identity is defined: 
                    - DO NOT assume or fabricate any personal identity.
                    - DO NOT say "I am [retrieved person's name]" even if retrieved.
                    - Instead, respond neutrally or in a helpful third-person perspective.

            2. You are NEVER allowed to mix ABI-defined identity and retrieved knowledge base identity. ABI takes full priority.

            3. Examples:
                - ✅ ABI: "You are Alex, a marketing agent" → Response: "I am Alex, a marketing agent..."
                - ❌ ABI not defined, but retrieval: "Rayhan Al Mim, lawyer..." → Response: "I am Rayhan Al Mim..." ← NOT ALLOWED

            4. You may reference general retrieved data (e.g., "the company has served 70+ clients") but never as first-person unless ABI identity fits.

            This is essential to protect user trust, brand integrity, and legal boundaries.
            """
    
    final_prompt += """
                GENERAL CONVERSATION GUIDELINES:
                - Start with the core answer; skip greetings.
                - Use user's name only when clarifying next steps.
                - Prefer bullet-like structure in plain sentences when listing options.
                - If information is missing, ask one specific follow-up.
                - If out-of-domain or no matching knowledge: say so briefly, then offer alternatives (browse site, contact, human handoff).

                Summary: FOLLOW ABI > IGNORE retrieved identity if ABI exists > No impersonation unless ABI says so.
                """
    
    try:
        # Call OpenAI for final response generation
        # If little to no context was retrieved but knowledge lookup was needed, steer to graceful OOD handling
        context_is_sparse = not retrieved_context or len(retrieved_context.strip()) < 100
        if context_is_sparse and analysis.get("needs_knowledge_lookup", False):
            final_prompt += """
            OUT-OF-DOMAIN OR LOW-CONTEXT HANDLING:
            - Acknowledge limited info in one short sentence.
            - Ask one targeted question to narrow the request OR offer to connect with a human.
            - If leadCapture is relevant, invite the user to share email/phone for a quick follow-up.
            - Keep the total response within 2-5 sentences.
            """

        response_completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.6
        )
        
        final_response = response_completion.choices[0].message.content.strip()
        
        # Remove any leading "Hello [Name]," pattern
        final_response = remove_greeting(final_response, user_info['name'])
        
        return final_response
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        if is_identity_query and retrieved_context:
            return "I am a legal professional with expertise in civil, corporate, and constitutional matters. How can I assist you today?"
        return "How can I assist you today?"

def remove_greeting(response, user_name):
    """Remove greeting patterns from the beginning of responses"""
    import re
    
    # Common greeting patterns
    greeting_patterns = [
        rf"^Hello,?\s*{user_name}[,.]?\s*",
        rf"^Hi,?\s*{user_name}[,.]?\s*",
        rf"^Hey,?\s*{user_name}[,.]?\s*",
        r"^Hello,?\s*",
        r"^Hi,?\s*",
        r"^Hey,?\s*",
        r"^Greetings,?\s*",
        r"^Good morning,?\s*",
        r"^Good afternoon,?\s*",
        r"^Good evening,?\s*",
    ]
    
    cleaned_response = response
    for pattern in greeting_patterns:
        cleaned_response = re.sub(pattern, "", cleaned_response, flags=re.IGNORECASE)
    
    # Capitalize the first letter if needed
    if cleaned_response and cleaned_response[0].islower():
        cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]
        
    return cleaned_response

def verify_identity(query, response, user_info, is_experience_query=False):
    """This function has been deprecated as we now want the AI to assume the identity from the documents"""
    return response 