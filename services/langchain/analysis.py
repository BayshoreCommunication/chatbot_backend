import openai
import json

def analyze_query(query, user_info, mode, needs_info, has_vector_data, conversation_summary):
    """Use AI to analyze a query and determine the best response approach"""
    available_modes = ["faq", "appointment", "sales", "lead_capture"]
    
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
    - If user mentions scheduling, booking, or availability, use appointment mode
    - If user asks about products, pricing, or deals, use sales mode
    - If user mentions becoming a client or asks how to start, use lead_capture mode
    - Default to faq mode for general information questions
    - If currently in a specific mode (like appointment) but has completed the process, switch back to faq
    
    CRITICAL INSTRUCTIONS:
    - Identity questions (like "who are you?") should be marked for special_handling="identity"
    - All queries about identity, background, experience, etc. should have needs_knowledge_lookup=true
    - ALWAYS prioritize collecting user information if it's missing
    
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
            model="gpt-4.1",
            messages=[{"role": "user", "content": analysis_prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        # Parse analysis
        analysis = json.loads(analysis_response.choices[0].message.content)
        print(f"AI Analysis: {analysis}")
        return analysis
    except Exception as e:
        print(f"Error in AI query analysis: {str(e)}")
        # Return default analysis as fallback
        return {
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

def generate_response(query, user_info, conversation_summary, retrieved_context, personal_information, analysis, language):
    """Generate the final AI response based on context and analysis"""
    # Check if query is about identity/experience/background
    identity_keywords = ["who are you", "what are you", "your name", "about yourself", "tell me about you",
                         "your experience", "your background", "your education", "your skills", 
                         "your work", "your expertise", "about your experience", "qualification", 
                         "tell me about your work", "your profile", "about your background"]
    
    is_identity_query = any(keyword in query.lower() for keyword in identity_keywords)
    
    # Build a prompt that includes all relevant context
    final_prompt = f"""
    You are responding to a user's query based on information in your knowledge base.
    
    USER QUERY: "{query}"
    
    USER INFORMATION:
    - Name: {user_info['name']}
    - Email: {user_info['email']}
    - Has booked appointment: {user_info['has_appointment']}
    {f"- Appointment details: {user_info['appointment_details']}" if user_info['has_appointment'] else ""}
    
    CONVERSATION HISTORY:
    {conversation_summary}
    
    {"RETRIEVED INFORMATION:" if retrieved_context else ""}
    {retrieved_context}
    
    {"PERSONAL INFORMATION FOUND:" if personal_information else ""}
    {json.dumps(personal_information) if personal_information else ""}
    
    CURRENT MODE: {analysis["appropriate_mode"]}
    USER INTENT: {analysis["intent"]}
    """
    
    # Add special instruction for identity queries
    if is_identity_query:
        final_prompt += """
    CRITICAL IDENTITY INSTRUCTIONS:
    Based on the retrieved information about (likely) a lawyer named Rayhan Al Mim or other professional:
    - ASSUME this identity completely in your response
    - Speak in first person as if you ARE this person
    - Use "I" statements when referring to the person's experience, background, etc.
    - Incorporate details from the retrieved information naturally
    - Do NOT say "Based on the information" or reveal you are an AI
    - If asked directly "Are you an AI" or similar, you can acknowledge being an AI assistant that represents the person
    - For example, if the retrieved information shows a lawyer named Rayhan, respond as "I am Rayhan Al Mim, a lawyer specializing in..."
    """
    
    final_prompt += """
    IMPORTANT GUIDELINES:
    1. If this is an identity query (who are you, background, experience, etc.) and you have retrieved information about a person,
       REPRESENT YOURSELF AS THAT PERSON in your response
    2. Keep responses concise and to the point
    3. For appointments, be specific about dates and times
    4. Always verify user's intentions before finalizing appointments
    
    Provide a helpful, informative, and conversational response that directly addresses the user's query.
    If knowledge base information is available, incorporate it naturally into your response.
    If no relevant information is available from the knowledge base, provide a general helpful response.
    Keep your response concise but informative.
    """
    
    try:
        # Call OpenAI for final response generation
        response_completion = openai.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.7
        )
        
        final_response = response_completion.choices[0].message.content.strip()
        
        return final_response
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        if is_identity_query and retrieved_context:
            return "I am Rayhan Al Mim, a legal professional with expertise in civil, corporate, and constitutional matters. How can I assist you today?"
        return "I'm here to help with your questions and appointment scheduling. How can I assist you today?"

def verify_identity(query, response, user_info, is_experience_query=False):
    """This function has been deprecated as we now want the AI to assume the identity from the documents"""
    return response 