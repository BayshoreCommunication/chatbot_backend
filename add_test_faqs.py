#!/usr/bin/env python3
"""
Script to add test FAQs for Carter Injury Law chatbot
These are the specific Q&A pairs requested for testing natural responses
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.database import db
from services.pinecone.faq_vectors import upsert_faq_embedding
from bson import ObjectId
import uuid

def add_test_faqs():
    """Add the specific test FAQs for natural response testing"""
    
    # Test organization ID (you may need to update this)
    org_id = "test_org_123"  # Update this with your actual org ID
    
    # FAQ data with the specific Q&A pairs
    test_faqs = [
        # 1. Case Type & Services
        {
            "question": "Do you handle personal injury cases?",
            "answer": "Yes, we handle personal injury cases. Could you tell me a little more about what happened so I can better understand your situation?",
            "category": "Case Types & Services",
            "tags": ["personal injury", "case types", "services"]
        },
        {
            "question": "Do you take car accident cases?",
            "answer": "Absolutely, we work with clients involved in car accidents. Were you the driver, passenger, or pedestrian?",
            "category": "Case Types & Services", 
            "tags": ["car accident", "auto accident", "traffic accident"]
        },
        {
            "question": "Do you handle family law cases like divorce or custody?",
            "answer": "Yes, we handle family law matters, including divorce and custody. Would you like me to connect you with our attorney for a consultation?",
            "category": "Case Types & Services",
            "tags": ["family law", "divorce", "custody", "family matters"]
        },
        
        # 2. Fees & Payment
        {
            "question": "How much do you charge?",
            "answer": "Many of our cases are handled on a contingency fee basis, meaning you don't pay unless we win. For other case types, we can explain fees in your consultation. Would you like to schedule one?",
            "category": "Fees & Payment",
            "tags": ["fees", "cost", "payment", "contingency fee"]
        },
        {
            "question": "Do you offer free consultations?",
            "answer": "Yes, we offer free initial consultations. When would you like to schedule yours?",
            "category": "Fees & Payment",
            "tags": ["free consultation", "consultation", "free"]
        },
        
        # 3. Case Process & Timeline
        {
            "question": "How long will my case take?",
            "answer": "The timeline depends on the type of case and details involved. Some cases settle quickly, while others may take longer. An attorney can give you a better estimate after reviewing your case.",
            "category": "Case Process & Timeline",
            "tags": ["timeline", "how long", "duration", "process"]
        },
        {
            "question": "What information do I need to start?",
            "answer": "Typically, details like the date of the incident, any documents, and witness information are helpful. Don't worry—we'll guide you through everything during your consultation.",
            "category": "Case Process & Timeline",
            "tags": ["information needed", "documents", "evidence", "start case"]
        },
        
        # 4. Communication & Availability
        {
            "question": "How do I contact my lawyer?",
            "answer": "You can reach us by phone, email, or schedule an appointment. After your consultation, we'll make sure you have direct contact details for your attorney.",
            "category": "Communication & Availability",
            "tags": ["contact", "lawyer", "attorney", "communication"]
        },
        {
            "question": "How quickly do you respond?",
            "answer": "We aim to respond within 24 hours or sooner. Urgent matters are prioritized immediately.",
            "category": "Communication & Availability",
            "tags": ["response time", "quick", "urgent", "timely"]
        },
        
        # 5. Location & Jurisdiction
        {
            "question": "Do you only work in [State Name]?",
            "answer": "We are licensed in [State Name], but we may assist with referrals if your case is in another state. Can you tell me where your case is based?",
            "category": "Location & Jurisdiction",
            "tags": ["location", "state", "jurisdiction", "licensed"]
        },
        {
            "question": "Can you represent me if I live out of state?",
            "answer": "In some cases, yes. Please share where you're located, and we'll confirm if we can help or connect you with a trusted partner.",
            "category": "Location & Jurisdiction",
            "tags": ["out of state", "location", "representation", "jurisdiction"]
        },
        
        # 6. Next Steps for Clients
        {
            "question": "What should I do right now?",
            "answer": "The best next step is to schedule a free consultation. We'll review your case and explain your options. Would you like me to help book a time?",
            "category": "Next Steps for Clients",
            "tags": ["next steps", "what to do", "consultation", "schedule"]
        },
        {
            "question": "Can I bring documents or photos?",
            "answer": "Yes, please do. Documents, photos, and any evidence you have can be very helpful for your case review.",
            "category": "Next Steps for Clients",
            "tags": ["documents", "photos", "evidence", "bring"]
        }
    ]
    
    # Add each FAQ to the database
    for i, faq_data in enumerate(test_faqs):
        try:
            # Create FAQ document
            faq_doc = {
                "org_id": org_id,
                "question": faq_data["question"],
                "answer": faq_data["answer"],
                "category": faq_data["category"],
                "tags": faq_data["tags"],
                "is_active": True,
                "persistent_menu": True,  # Show in suggested FAQs
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
            
            # Insert into MongoDB
            result = db.faqs.insert_one(faq_doc)
            faq_id = str(result.inserted_id)
            
            print(f"Added FAQ {i+1}: {faq_data['question'][:50]}... (ID: {faq_id})")
            
            # Add to vector database for semantic search
            try:
                import asyncio
                asyncio.run(upsert_faq_embedding(
                    faq_id=faq_id,
                    question=faq_data["question"],
                    org_id=org_id,
                    namespace=""
                ))
                print(f"  ✓ Added to vector database")
            except Exception as e:
                print(f"  ✗ Error adding to vector database: {str(e)}")
                
        except Exception as e:
            print(f"Error adding FAQ {i+1}: {str(e)}")
    
    print(f"\n✅ Added {len(test_faqs)} test FAQs to the database")
    print(f"Organization ID: {org_id}")
    print("\nYou can now test these responses in your chatbot!")

if __name__ == "__main__":
    add_test_faqs()
