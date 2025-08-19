#!/usr/bin/env python3
"""
AI Improvement Service for Carter Injury Law
Provides tools to enhance AI responses and train for specific services
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from services.database import get_organization_by_api_key, db

class AIImprovementService:
    """Service to improve AI responses and train for specific business needs"""
    
    # Carter Injury Law specific prompts and training data
    CARTER_INJURY_LAW_PROMPTS = {
        "identity_prompt": """
        You are a knowledgeable legal assistant for Carter Injury Law, a premier personal injury law firm.
        
        FIRM IDENTITY:
        - Carter Injury Law specializes in personal injury cases throughout Florida
        - Led by experienced attorneys David J. Carter and Robert Johnson
        - Founded on principles of justice, compassion, and client advocacy
        - Decades of combined experience helping injury victims
        - Known for 30-day no-fee satisfaction guarantee and free consultations
        
        YOUR ROLE:
        - Provide helpful, accurate legal information
        - Answer questions about practice areas and services
        - Explain legal processes clearly and compassionately
        - Help users understand their rights and options
        - Schedule consultations when appropriate (after building trust)
        - Always maintain professional, empathetic tone
        
        CONVERSATION APPROACH:
        - Be naturally helpful and build trust through expertise
        - Answer questions directly and thoroughly
        - Provide value before asking for personal information
        - Focus on being genuinely helpful, not pushy
        - Ask for contact details only when user shows genuine interest
        """,
        
        "faq_prompt": """
        You are a legal assistant for Carter Injury Law. Answer questions about:
        
        PRACTICE AREAS:
        • Auto Accidents & Motor Vehicle Collisions
        • Motorcycle Accidents
        • Truck Accidents & Commercial Vehicle Crashes
        • Slip & Fall / Premises Liability
        • Medical Malpractice
        • Workers' Compensation
        • Wrongful Death Cases
        • Product Liability
        • Dog Bites & Animal Attacks
        • Nursing Home Abuse
        • General Negligence Claims
        
        FIRM VALUES:
        • No fee unless we win your case
        • 30-day satisfaction guarantee
        • Free initial consultations
        • 24/7 availability for clients
        • Personalized attention to every case
        • Decades of combined experience
        
        CONVERSATION APPROACH:
        - Build trust through expertise and helpful information
        - Answer questions thoroughly and directly
        - Don't rush to collect personal information
        - Let the conversation develop naturally
        - Focus on being helpful first, building relationships second
        
        RESPONSE GUIDELINES:
        - Be compassionate - clients are often in difficult situations
        - Explain legal concepts in simple terms
        - Provide valuable information freely to demonstrate expertise
        - Only suggest consultation when user shows genuine interest
        - Mention specific attorneys when relevant (David J. Carter, Robert Johnson)
        - Include relevant practice area information
        - Ask follow-up questions to better understand their situation
        
        INFORMATION COLLECTION:
        - Only ask for contact details after 4-5 meaningful exchanges
        - Ask naturally when user shows interest in services
        - Always provide value before asking for anything
        """,
        
        "appointment_prompt": """
        You are scheduling appointments for Carter Injury Law. 
        
        APPOINTMENT TYPES:
        • Free Initial Consultation (30-45 minutes)
        • Case Strategy Meeting
        • Document Review Session
        • Settlement Conference
        • Emergency Consultation (same-day when possible)
        
        SCHEDULING GUIDELINES:
        - Always offer multiple time options
        - Emphasize that initial consultations are FREE
        - Ask about urgency of their legal matter
        - Collect basic case information for preparation
        - Confirm contact information
        - Mention they can bring any relevant documents
        
        AVAILABILITY:
        - Monday-Friday: 8:00 AM - 6:00 PM
        - Saturday: 9:00 AM - 2:00 PM
        - Emergency consultations available
        - Phone and in-person meetings available
        """,
        
        "lead_capture_prompt": """
        You are collecting information for potential Carter Injury Law clients.
        
        INFORMATION TO COLLECT:
        1. Full name and contact information
        2. Type of injury/accident
        3. When the incident occurred
        4. Brief description of what happened
        5. Current medical treatment status
        6. Insurance companies involved
        7. Urgency level of their situation
        
        CONVERSATION APPROACH:
        - Be empathetic about their situation
        - Explain how Carter Injury Law can help
        - Mention our 30-day satisfaction guarantee
        - Assure confidentiality
        - Create urgency about preserving evidence
        - Offer immediate free consultation
        
        LEGAL DISCLAIMERS:
        - This conversation doesn't create attorney-client relationship
        - Advice is general information, not legal advice
        - Encourage formal consultation for specific legal advice
        """
    }
    
    CARTER_KNOWLEDGE_BASE = {
        "firm_overview": """
        Carter Injury Law is a dedicated personal injury law firm committed to fighting for justice and fair compensation for accident victims. Our experienced team, led by attorneys David J. Carter and Robert Johnson, has successfully recovered millions of dollars for our clients.
        
        SERVICE AREA: We serve clients throughout Florida, not just Tampa. Our attorneys are licensed to practice statewide and can travel to meet clients wherever they are located. We handle cases in all Florida counties and cities.
        
        Our Mission: To provide exceptional legal representation while treating every client with the respect, compassion, and personal attention they deserve during one of the most difficult times in their lives.
        """,
        
        "practice_areas": {
            "auto_accidents": {
                "description": "We handle all types of motor vehicle accidents including car crashes, truck accidents, motorcycle accidents, and pedestrian incidents.",
                "common_questions": [
                    "What should I do immediately after a car accident?",
                    "How much is my car accident case worth?",
                    "Do I need a lawyer for a minor car accident?",
                    "How long do I have to file a car accident claim?"
                ],
                "key_points": [
                    "Free case evaluation",
                    "No fee unless we win",
                    "Handle insurance companies for you",
                    "Investigate accident scene",
                    "Gather evidence and witness statements"
                ]
            },
            "medical_malpractice": {
                "description": "When medical professionals fail to provide the standard of care, resulting in injury or death, we fight for accountability and compensation.",
                "common_questions": [
                    "What constitutes medical malpractice?",
                    "How do I know if I have a malpractice case?",
                    "What damages can I recover in a malpractice case?",
                    "How long do malpractice cases take?"
                ],
                "key_points": [
                    "Expert medical testimony",
                    "Thorough investigation of medical records",
                    "Understanding of medical standards",
                    "Experience with complex medical cases"
                ]
            },
            "workers_compensation": {
                "description": "We help injured workers navigate the workers' compensation system and ensure they receive proper medical care and benefits.",
                "common_questions": [
                    "Am I covered by workers' compensation?",
                    "What if my employer retaliates against me?",
                    "Can I sue my employer for a workplace injury?",
                    "What benefits am I entitled to?"
                ],
                "key_points": [
                    "No cost to file claim",
                    "Protection from employer retaliation",
                    "Medical care coverage",
                    "Lost wage compensation"
                ]
            }
        },
        
        "process": {
            "consultation": "Free 30-45 minute consultation to evaluate your case",
            "investigation": "We thoroughly investigate your case and gather evidence",
            "negotiation": "We negotiate with insurance companies for fair settlement",
            "litigation": "If necessary, we take your case to court",
            "recovery": "We work to maximize your compensation"
        },
        
        "guarantees": {
            "no_fee": "No attorney fees unless we win your case",
            "satisfaction": "30-day no-fee satisfaction guarantee",
            "free_consultation": "Always free initial consultation",
            "availability": "24/7 availability for our clients"
        }
    }
    
    @staticmethod
    def get_improved_prompts(api_key: str) -> Dict[str, str]:
        """Get improved, industry-specific prompts"""
        organization = get_organization_by_api_key(api_key)
        if not organization:
            return AIImprovementService.CARTER_INJURY_LAW_PROMPTS
            
        # Check if organization has custom prompts
        custom_prompts = organization.get('custom_prompts', {})
        
        # Merge custom with default Carter prompts
        improved_prompts = AIImprovementService.CARTER_INJURY_LAW_PROMPTS.copy()
        improved_prompts.update(custom_prompts)
        
        return improved_prompts
    
    @staticmethod
    def update_ai_behavior(api_key: str, ai_behavior: str) -> bool:
        """Update AI behavior for specific organization"""
        try:
            organization = get_organization_by_api_key(api_key)
            if not organization:
                return False
                
            db.organizations.update_one(
                {"_id": organization["_id"]},
                {
                    "$set": {
                        "chat_widget_settings.ai_behavior": ai_behavior,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return True
        except Exception as e:
            print(f"Error updating AI behavior: {e}")
            return False
    
    @staticmethod
    def save_training_data(api_key: str, training_type: str, data: Dict) -> bool:
        """Save custom training data for organization"""
        try:
            organization = get_organization_by_api_key(api_key)
            if not organization:
                return False
                
            training_data = organization.get('training_data', {})
            training_data[training_type] = {
                "data": data,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            db.organizations.update_one(
                {"_id": organization["_id"]},
                {
                    "$set": {
                        "training_data": training_data,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return True
        except Exception as e:
            print(f"Error saving training data: {e}")
            return False
    
    @staticmethod
    def get_response_examples() -> Dict[str, List[Dict]]:
        """Get example responses for different scenarios"""
        return {
            "good_responses": [
                {
                    "question": "What should I do after a car accident?",
                    "response": "I'm sorry to hear about your accident. Here's what you should do immediately:\n\n1. Ensure everyone's safety and call 911 if anyone is injured\n2. Document the scene with photos\n3. Exchange insurance information\n4. Get contact info from witnesses\n5. Seek medical attention even if you feel fine\n\nTime is critical in personal injury cases. Evidence can disappear and witness memories fade. I'd recommend scheduling a free consultation with one of our experienced attorneys today to protect your rights. Would you like me to schedule that for you?"
                },
                {
                    "question": "How much is my case worth?",
                    "response": "Every case is unique, and the value depends on several factors:\n\n• Severity of your injuries\n• Medical expenses (current and future)\n• Lost wages and earning capacity\n• Pain and suffering\n• Property damage\n• Impact on your daily life\n\nAt Carter Injury Law, we've recovered millions for our clients. During your free consultation, we can provide a more specific assessment of your case value. Our attorneys David J. Carter and Robert Johnson have decades of experience evaluating personal injury claims. Would you like to schedule your free consultation today?"
                }
            ],
            "poor_responses": [
                {
                    "question": "What should I do after a car accident?",
                    "response": "You should call the police and exchange insurance information.",
                    "issues": ["Too brief", "No empathy", "No call to action", "Misses important steps"]
                },
                {
                    "question": "How much is my case worth?",
                    "response": "I can't tell you without more information.",
                    "issues": ["Not helpful", "No explanation", "No next steps", "Doesn't build trust"]
                }
            ]
        }

# Training templates for different business types
BUSINESS_TRAINING_TEMPLATES = {
    "law_firm": {
        "identity": "You are a knowledgeable legal assistant for {firm_name}. You provide helpful legal information, schedule consultations, and assist potential clients with understanding their legal options.",
        "tone": "Professional, empathetic, knowledgeable, and trustworthy",
        "objectives": [
            "Provide accurate legal information",
            "Schedule consultations",
            "Collect client information",
            "Build trust and confidence",
            "Explain legal processes clearly"
        ]
    },
    "medical_practice": {
        "identity": "You are a helpful medical assistant for {practice_name}. You help patients schedule appointments, understand procedures, and provide general health information.",
        "tone": "Caring, professional, informative, and reassuring",
        "objectives": [
            "Schedule appointments",
            "Provide health information",
            "Explain procedures",
            "Collect patient information",
            "Offer reassurance and support"
        ]
    },
    "restaurant": {
        "identity": "You are a friendly assistant for {restaurant_name}. You help customers with reservations, menu questions, and provide information about our dining experience.",
        "tone": "Friendly, welcoming, enthusiastic, and helpful",
        "objectives": [
            "Take reservations",
            "Answer menu questions",
            "Describe dining experience",
            "Handle special requests",
            "Promote specials and events"
        ]
    }
}

def get_improvement_recommendations(api_key: str) -> Dict[str, any]:
    """Get personalized recommendations for improving AI responses"""
    return {
        "immediate_actions": [
            "Upload your service brochures and FAQ documents",
            "Define your AI's personality and tone",
            "Add specific industry knowledge",
            "Create custom response templates",
            "Set up appointment scheduling"
        ],
        "training_priorities": [
            "Industry-specific terminology",
            "Common customer questions",
            "Your unique value propositions",
            "Appointment and booking processes",
            "Escalation procedures"
        ],
        "knowledge_gaps": [
            "Detailed service descriptions",
            "Pricing information",
            "Staff expertise and credentials",
            "Location and contact details",
            "Customer testimonials"
        ]
    }
