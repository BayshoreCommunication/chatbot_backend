#!/usr/bin/env python3
"""
Hardcoded FAQ responses for Carter Injury Law presentation
This provides exact responses for the specific Q&A pairs requested
"""

# Hardcoded Q&A pairs for the presentation
HARDCODED_FAQS = {
    # 1. Case Type & Services
    "do you handle personal injury cases": {
        "answer": "Yes, we handle personal injury cases. Could you tell me a little more about what happened so I can better understand your situation?",
        "category": "Case Types & Services"
    },
    "do you take car accident cases": {
        "answer": "Absolutely, we work with clients involved in car accidents. Were you the driver, passenger, or pedestrian?",
        "category": "Case Types & Services"
    },
    "do you handle family law cases like divorce or custody": {
        "answer": "Yes, we handle family law matters, including divorce and custody. Would you like me to connect you with our attorney for a consultation?",
        "category": "Case Types & Services"
    },
    
    # 2. Fees & Payment
    "how much do you charge": {
        "answer": "Many of our cases are handled on a contingency fee basis, meaning you don't pay unless we win. For other case types, we can explain fees in your consultation. Would you like to schedule one?",
        "category": "Fees & Payment"
    },
    "do you offer free consultations": {
        "answer": "Yes, we offer free initial consultations. When would you like to schedule yours?",
        "category": "Fees & Payment"
    },
    
    # 3. Case Process & Timeline
    "how long will my case take": {
        "answer": "The timeline depends on the type of case and details involved. Some cases settle quickly, while others may take longer. An attorney can give you a better estimate after reviewing your case.",
        "category": "Case Process & Timeline"
    },
    "what information do i need to start": {
        "answer": "Typically, details like the date of the incident, any documents, and witness information are helpful. Don't worry—we'll guide you through everything during your consultation.",
        "category": "Case Process & Timeline"
    },
    
    # 4. Communication & Availability
    "how do i contact my lawyer": {
        "answer": "You can reach us by phone, email, or schedule an appointment. After your consultation, we'll make sure you have direct contact details for your attorney.",
        "category": "Communication & Availability"
    },
    "how quickly do you respond": {
        "answer": "We aim to respond within 24 hours or sooner. Urgent matters are prioritized immediately.",
        "category": "Communication & Availability"
    },
    
    # 5. Location & Jurisdiction
    "do you only work in": {
        "answer": "We are licensed in [State Name], but we may assist with referrals if your case is in another state. Can you tell me where your case is based?",
        "category": "Location & Jurisdiction"
    },
    "can you represent me if i live out of state": {
        "answer": "In some cases, yes. Please share where you're located, and we'll confirm if we can help or connect you with a trusted partner.",
        "category": "Location & Jurisdiction"
    },
    
    # 6. Next Steps for Clients
    "what should i do right now": {
        "answer": "The best next step is to schedule a free consultation. We'll review your case and explain your options. Would you like me to help book a time?",
        "category": "Next Steps for Clients"
    },
    "can i bring documents or photos": {
        "answer": "Yes, please do. Documents, photos, and any evidence you have can be very helpful for your case review.",
        "category": "Next Steps for Clients"
    }
}

def find_hardcoded_response(user_question):
    """
    Find a hardcoded response for the user's question
    Returns the response if found, None otherwise
    """
    # Convert to lowercase for matching
    question_lower = user_question.lower().strip()
    
    # Try exact matches first
    if question_lower in HARDCODED_FAQS:
        return HARDCODED_FAQS[question_lower]
    
    # Try partial matches
    for key, response in HARDCODED_FAQS.items():
        if key in question_lower or question_lower in key:
            return response
    
    # Try keyword matching
    keywords = {
        "personal injury": "do you handle personal injury cases",
        "car accident": "do you take car accident cases", 
        "family law": "do you handle family law cases like divorce or custody",
        "divorce": "do you handle family law cases like divorce or custody",
        "custody": "do you handle family law cases like divorce or custody",
        "charge": "how much do you charge",
        "cost": "how much do you charge",
        "fee": "how much do you charge",
        "free consultation": "do you offer free consultations",
        "consultation": "do you offer free consultations",
        "how long": "how long will my case take",
        "timeline": "how long will my case take",
        "duration": "how long will my case take",
        "information": "what information do i need to start",
        "documents": "what information do i need to start",
        "contact": "how do i contact my lawyer",
        "lawyer": "how do i contact my lawyer",
        "attorney": "how do i contact my lawyer",
        "respond": "how quickly do you respond",
        "response time": "how quickly do you respond",
        "state": "do you only work in",
        "jurisdiction": "do you only work in",
        "out of state": "can you represent me if i live out of state",
        "next step": "what should i do right now",
        "what now": "what should i do right now",
        "bring": "can i bring documents or photos",
        "photos": "can i bring documents or photos",
        "evidence": "can i bring documents or photos"
    }
    
    for keyword, faq_key in keywords.items():
        if keyword in question_lower:
            return HARDCODED_FAQS[faq_key]
    
    return None

def get_hardcoded_response(user_question):
    """
    Get a hardcoded response for the user's question
    Returns a formatted response object
    """
    response_data = find_hardcoded_response(user_question)
    
    if response_data:
        return {
            "answer": response_data["answer"],
            "category": response_data["category"],
            "source": "hardcoded_faq",
            "confidence": 1.0
        }
    
    return None
