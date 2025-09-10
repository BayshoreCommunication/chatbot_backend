import openai
import json
import re
import os

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
            model="gpt-4o",
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

def generate_response(query, user_info, conversation_summary, retrieved_context, personal_information, analysis, language):
    """Generate the final AI response based on context and analysis"""
    # Check if query is about identity/experience/background
    identity_keywords = ["who are you", "what are you", "your name", "about yourself", "tell me about you",
                         "your experience", "your background", "your education", "your skills", 
                         "your work", "your expertise", "about your experience", "qualification", 
                         "tell me about your work", "your profile", "about your background"]
    
    is_identity_query = any(keyword in query.lower() for keyword in identity_keywords)
    
    # Detect if this is an injury/accident-related query for empathy
    injury_keywords = ["accident", "injured", "hurt", "pain", "hospital", "medical", "crash", "collision", "slip", "fall"]
    is_injury_query = any(keyword in query.lower() for keyword in injury_keywords)
    
    # Build a comprehensive, natural prompt
    final_prompt = f"""
    You are a professional, compassionate personal injury lawyer assistant for Carter Injury Law in Tampa, Florida. 
    You speak naturally and professionally, providing helpful legal guidance to people in difficult situations.

    CONTEXT INFORMATION:
    - User's Query: "{query}"
    - User's Name: {user_info.get('name', 'Not provided')}
    - User's Intent: {analysis.get("intent", "General inquiry")}
    - Language Preference: {language}
    
    CONVERSATION HISTORY (Recent context):
    {conversation_summary if conversation_summary else "This is the beginning of our conversation."}
    
    KNOWLEDGE BASE INFORMATION:
    {retrieved_context if retrieved_context else "No specific knowledge base information retrieved for this query."}
    
    FIRM DETAILS FOUND:
    {json.dumps(personal_information) if personal_information else "Using general firm knowledge."}
    
    PROFESSIONAL LAWYER PERSONA GUIDELINES:
    
    1. PROFESSIONAL COMMUNICATION:
       - Maintain a polite, professional tone at all times
       - Be informative and helpful without being overly casual
       - Show empathy for injury situations with appropriate concern
       - Use clear, understandable language for legal concepts
    
    2. INJURY CASE EMPATHY:
       {"- Acknowledge their difficult situation professionally" if is_injury_query else ""}
       {"- Express appropriate concern: 'I understand this situation must be challenging'" if is_injury_query else ""}
       {"- Focus on how the firm can help with their legal needs" if is_injury_query else ""}
    
    3. FIRM EXPERTISE TO HIGHLIGHT:
       - Carter Injury Law: Premier personal injury firm in Tampa
       - Attorneys David J. Carter and Robert Johnson
       - 30-day no-fee satisfaction guarantee
       - Free consultations with no obligation
       - Extensive experience in personal injury law
       - Proven track record helping accident victims
    
    4. PROFESSIONAL INFORMATION DELIVERY:
       - Explain legal concepts clearly and accurately
       - Provide actionable guidance when appropriate
       - Reference relevant legal procedures and rights
       - Build confidence through demonstrated expertise
       - Offer next steps like free consultations
    
    5. TRUST AND CREDIBILITY:
       - Reference firm achievements and experience naturally
       - Mention the no-fee-unless-we-win approach
       - Highlight free consultation value proposition
       - Share relevant legal insights professionally
    
    6. LEGAL DISCLAIMERS (include naturally):
       - "Every case has unique circumstances"
       - "For specific legal advice, I recommend consulting with our attorneys"
       - "A free consultation can help determine your best options"
    
    CRITICAL INSTRUCTIONS:
    - Act as a knowledgeable legal professional
    - Use retrieved information to provide accurate responses
    - Be helpful and informative first, promotional second
    - Maintain professional boundaries while being approachable
    - For injury cases, show appropriate professional concern
    - Make legal information accessible but accurate
    - Offer concrete next steps when appropriate
    
    Generate a professional, helpful lawyer assistant response:"""
    
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
                - Start your answer with relevant value, skip greetings.
                - Use user's name only contextually, not as opening (e.g., "Alvi, your request...").
                - Keep it short, informative, and aligned with ABI instructions.
                - For appointments, confirm details.
                - Do not hallucinate identities or credentials under any condition.

                Summary: FOLLOW ABI > IGNORE retrieved identity if ABI exists > No impersonation unless ABI says so.
                """
    
    try:
        # Call OpenAI for final response generation
        response_completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.7
        )
        
        final_response = response_completion.choices[0].message.content.strip()
        
        # Remove any leading "Hello [Name]," pattern
        final_response = remove_greeting(final_response, user_info['name'])
        
        return final_response
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        print(f"OpenAI API Key present: {bool(os.getenv('OPENAI_API_KEY'))}")
        
        # Try a simpler OpenAI call as fallback
        try:
            simple_prompt = f"""Answer this question professionally and helpfully: {query}
            
            Context: You are a legal assistant for Carter Injury Law, specializing in personal injury cases.
            
            Question: {query}
            
            Provide a direct, helpful answer:"""
            
            fallback_response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": simple_prompt}],
                temperature=0.7,
                max_tokens=200
            )
            
            return fallback_response.choices[0].message.content.strip()
            
        except Exception as fallback_error:
            print(f"Fallback response generation failed: {str(fallback_error)}")
            
            # Manual intelligent response based on query content
            query_lower = query.lower()
            
            if "cases" in query_lower and ("outside" in query_lower or "tampa" in query_lower):
                return "Yes, Carter Injury Law handles personal injury cases throughout Florida, not just in Tampa. We serve clients in surrounding areas and can travel to meet with you. Our experienced attorneys David J. Carter and Robert Johnson are licensed to practice throughout the state. Would you like to schedule a free consultation to discuss your case?"
            elif "help" in query_lower or "assist" in query_lower:
                return "I'm here to help you with any questions about personal injury law, our services, or to schedule a consultation. Carter Injury Law offers free initial consultations and we work on a no-fee-unless-we-win basis. What specific questions do you have?"
            elif "accident" in query_lower:
                return "I'm sorry to hear about your accident. Carter Injury Law specializes in all types of personal injury cases including auto accidents, slip and falls, and more. We offer free consultations and work on a contingency fee basis. Would you like to discuss your case with one of our experienced attorneys?"
            else:
                return f"Thank you for your question about {query}. As a legal assistant for Carter Injury Law, I'm here to help with personal injury matters. Could you provide more details about your situation so I can better assist you?"

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