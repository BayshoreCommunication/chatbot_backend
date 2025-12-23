"""
Real-time FAQ Intelligence Service
Analyzes organization data and provides actionable feedback
NO DATA STORAGE - only real-time analysis when requested
"""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from typing import List, Dict, Optional
import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import tempfile
import json


class FAQIntelligenceService:
    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=openai_api_key
        )
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200
        )

    async def analyze_organization(
        self,
        organization: Dict,
        existing_faqs: List[Dict],
        conversation_history: List[Dict],
        uploaded_documents: List[Dict]
    ) -> Dict:
        """
        Real-time analysis of organization's FAQ readiness
        
        Returns comprehensive feedback with alerts and suggestions
        """
        
        print(f"🔍 [FAQ-INTELLIGENCE] Starting real-time analysis...")
        
        feedback = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "alerts": [],
            "suggestions": [],
            "analysis": {},
            "readiness_score": 0
        }
        
        # STEP 1: Check Organization Profile Completeness
        profile_check = self._check_organization_profile(organization)
        feedback["alerts"].extend(profile_check["alerts"])
        feedback["analysis"]["profile"] = profile_check
        
        # STEP 2: Check FAQ Availability
        faq_check = self._check_faq_availability(existing_faqs)
        feedback["alerts"].extend(faq_check["alerts"])
        feedback["analysis"]["faqs"] = faq_check
        
        # If critical info missing, return early
        if profile_check["missing_critical_fields"]:
            feedback["readiness_score"] = 20
            feedback["status"] = "incomplete_setup"
            return feedback
        
        # STEP 3: Analyze Website Content (if website exists)
        website_analysis = None
        if organization.get("website"):
            website_analysis = await self._analyze_website(
                organization["website"],
                organization.get("company_organization_type", "General Business")
            )
            feedback["analysis"]["website"] = website_analysis
            if website_analysis.get("alerts"):
                feedback["alerts"].extend(website_analysis["alerts"])
        
        # STEP 4: Analyze Uploaded Documents (PDFs, etc.)
        document_analysis = None
        if uploaded_documents:
            document_analysis = await self._analyze_documents(
                uploaded_documents,
                organization.get("company_organization_type", "General Business")
            )
            feedback["analysis"]["documents"] = document_analysis
            if document_analysis.get("suggestions"):
                feedback["suggestions"].extend(document_analysis["suggestions"])
        else:
            feedback["alerts"].append({
                "type": "warning",
                "category": "documents",
                "message": "No training documents found",
                "suggestion": "Upload PDF documents about your services, policies, or procedures to improve AI responses"
            })
        
        # STEP 5: Analyze Conversation History for Patterns
        if conversation_history:
            conversation_analysis = await self._analyze_conversations(
                conversation_history,
                existing_faqs,
                organization.get("company_organization_type", "General Business")
            )
            feedback["analysis"]["conversations"] = conversation_analysis
            if conversation_analysis.get("suggestions"):
                feedback["suggestions"].extend(conversation_analysis["suggestions"])
        
        # STEP 6: Generate Missing FAQ Suggestions
        if not profile_check["missing_critical_fields"]:
            faq_suggestions = await self._generate_faq_suggestions(
                organization=organization,
                existing_faqs=existing_faqs,
                website_content=website_analysis.get("content") if website_analysis else None,
                conversation_patterns=conversation_analysis.get("common_questions") if conversation_history else []
            )
            feedback["suggestions"].extend(faq_suggestions)
        
        # Calculate readiness score
        feedback["readiness_score"] = self._calculate_readiness_score(
            profile_check, faq_check, website_analysis, document_analysis, conversation_history
        )
        
        print(f"✅ [FAQ-INTELLIGENCE] Analysis complete - Score: {feedback['readiness_score']}/100")
        
        return feedback

    def _check_organization_profile(self, organization: Dict) -> Dict:
        """Check if organization profile is complete (using exact user model fields)"""
        
        alerts = []
        missing_fields = []
        
        # Required fields from user model: organization_name, website (Optional), company_organization_type (Optional)
        required_fields = {
            "organization_name": "Organization Name",
            "website": "Website URL",
            "company_organization_type": "Company/Organization Type"
        }
        
        for field, display_name in required_fields.items():
            if not organization.get(field):
                missing_fields.append(field)
                alerts.append({
                    "type": "critical",
                    "category": "profile",
                    "field": field,
                    "message": f"⚠️ Missing {display_name}",
                    "action": f"Please add your {display_name} in your organization settings to enable intelligent FAQ suggestions"
                })
        
        return {
            "complete": len(missing_fields) == 0,
            "missing_critical_fields": missing_fields,
            "alerts": alerts,
            "completion_percentage": ((3 - len(missing_fields)) / 3) * 100
        }

    def _check_faq_availability(self, existing_faqs: List[Dict]) -> Dict:
        """Check FAQ availability and quality"""
        
        alerts = []
        faq_count = len(existing_faqs)
        
        if faq_count == 0:
            alerts.append({
                "type": "critical",
                "category": "faqs",
                "message": "❌ No FAQs found in your knowledge base",
                "action": "Add at least 5-10 frequently asked questions to help the AI provide better responses"
            })
            return {
                "has_faqs": False,
                "count": 0,
                "quality": "none",
                "alerts": alerts
            }
        
        elif faq_count < 5:
            alerts.append({
                "type": "warning",
                "category": "faqs",
                "message": f"⚠️ Only {faq_count} FAQ(s) found",
                "action": "We recommend adding at least 5-10 FAQs for comprehensive coverage"
            })
            quality = "minimal"
        
        elif faq_count < 10:
            alerts.append({
                "type": "info",
                "category": "faqs",
                "message": f"ℹ️ {faq_count} FAQs found - Good start!",
                "action": "Consider adding more FAQs to cover additional topics"
            })
            quality = "good"
        
        else:
            quality = "excellent"
        
        return {
            "has_faqs": True,
            "count": faq_count,
            "quality": quality,
            "alerts": alerts
        }

    async def _analyze_website(self, website_url: str, company_type: str) -> Dict:
        """Analyze website content for training potential"""
        
        print(f"🌐 [FAQ-INTELLIGENCE] Analyzing website: {website_url}")
        
        try:
            # Scrape website
            loader = WebBaseLoader(website_url)
            docs = loader.load()
            
            if not docs or len(docs) == 0:
                return {
                    "success": False,
                    "alerts": [{
                        "type": "warning",
                        "category": "website",
                        "message": "Could not fetch website content",
                        "action": "Ensure your website is publicly accessible"
                    }]
                }
            
            # Combine all content
            content = "\n\n".join([doc.page_content for doc in docs])
            word_count = len(content.split())
            
            # Analyze content quality
            prompt = f"""Analyze this {company_type} website content and provide feedback.

Website Content (first 3000 chars):
{content[:3000]}

Provide analysis in JSON format:
{{
    "has_useful_content": true/false,
    "content_quality": "excellent/good/fair/poor",
    "found_topics": ["topic1", "topic2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}

Only return valid JSON."""

            response = await self.llm.ainvoke(prompt)
            
            # Try to parse JSON response
            try:
                # Clean the response content - remove markdown code blocks if present
                response_text = response.content.strip()
                if response_text.startswith("```json"):
                    response_text = response_text.replace("```json", "").replace("```", "").strip()
                elif response_text.startswith("```"):
                    response_text = response_text.replace("```", "").strip()
                
                analysis = json.loads(response_text)
            except json.JSONDecodeError as je:
                print(f"⚠️ [FAQ-INTELLIGENCE] JSON parse error: {je}")
                print(f"Response content: {response.content}")
                # Fallback to basic analysis
                analysis = {
                    "has_useful_content": word_count > 500,
                    "content_quality": "good" if word_count > 1000 else "fair",
                    "found_topics": [],
                    "suggestions": ["Could not fully analyze website content - using basic metrics"]
                }
            
            return {
                "success": True,
                "word_count": word_count,
                "content": content[:5000],  # Store first 5000 chars for FAQ generation
                "analysis": analysis,
                "alerts": [] if analysis.get("has_useful_content") else [{
                    "type": "warning",
                    "category": "website",
                    "message": "Website content is limited",
                    "action": "Add more detailed information about your services on your website"
                }]
            }
            
        except Exception as e:
            print(f"❌ [FAQ-INTELLIGENCE] Website analysis error: {e}")
            import traceback
            print(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "alerts": [{
                    "type": "error",
                    "category": "website",
                    "message": f"Could not analyze website: {str(e)}",
                    "action": "Check if your website URL is correct and accessible"
                }]
            }

    async def _analyze_documents(self, documents: List[Dict], company_type: str) -> Dict:
        """Analyze uploaded documents (PDFs, CSVs, etc.)"""
        
        print(f"📄 [FAQ-INTELLIGENCE] Checking {len(documents)} documents")
        print(f"📄 [FAQ-INTELLIGENCE] Document data received: {documents}")
        
        # NOTE: Documents uploaded via /upload_document are processed and stored in vector DB
        # The original files are deleted after embedding, so we can't re-analyze them
        # We can only confirm they exist in upload_history
        
        if not documents or len(documents) == 0:
            return {
                "success": False,
                "suggestions": [{
                    "type": "document",
                    "message": "No training documents found",
                    "action": "Upload PDF documents about your services, policies, or procedures"
                }]
            }
        
        # Count documents by type
        doc_types = {}
        for doc in documents:
            doc_type = doc.get("type", "unknown")
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        print(f"📊 [FAQ-INTELLIGENCE] Document types: {doc_types}")
        
        # Documents exist and are already embedded in vector DB
        # This is good for the AI chatbot
        return {
            "success": True,
            "document_count": len(documents),
            "document_types": doc_types,
            "message": f"Found {len(documents)} training document(s) in knowledge base",
            "suggestions": [] if len(documents) >= 3 else [{
                "type": "document",
                "message": f"You have {len(documents)} document(s). Consider adding more for better coverage",
                "action": "Upload additional PDFs about your services, FAQs, or policies"
            }]
        }

    async def _analyze_conversations(
        self,
        conversations: List[Dict],
        existing_faqs: List[Dict],
        company_type: str
    ) -> Dict:
        """Analyze conversation history for unanswered questions"""
        
        print(f"💬 [FAQ-INTELLIGENCE] Analyzing {len(conversations)} conversations")
        
        # Get user messages (questions)
        user_questions = [
            conv["content"] 
            for conv in conversations 
            if conv.get("role") == "user"
        ][:50]  # Last 50 questions
        
        if not user_questions:
            return {"suggestions": []}
        
        # Analyze for patterns
        questions_text = "\n".join([f"- {q}" for q in user_questions])
        existing_q = "\n".join([f"- {faq['question']}" for faq in existing_faqs[:20]])
        
        prompt = f"""You are analyzing customer conversations for a {company_type}.

RECENT CUSTOMER QUESTIONS:
{questions_text}

EXISTING FAQs:
{existing_q}

Identify:
1. Common questions that are NOT in existing FAQs
2. Topics that customers frequently ask about
3. Questions that indicate missing information

Return JSON:
{{
    "common_questions": ["question1", "question2"],
    "missing_topics": ["topic1", "topic2"],
    "priority_suggestions": [
        {{
            "question": "suggested FAQ question",
            "reasoning": "why this is important based on conversations"
        }}
    ]
}}

Only return valid JSON."""

        try:
            response = await self.llm.ainvoke(prompt)
            analysis = json.loads(response.content)
            
            suggestions = []
            for item in analysis.get("priority_suggestions", [])[:5]:
                suggestions.append({
                    "type": "conversation_pattern",
                    "priority": "high",
                    "question": item["question"],
                    "reasoning": item["reasoning"],
                    "source": "customer_conversations"
                })
            
            return {
                "analyzed_count": len(user_questions),
                "common_questions": analysis.get("common_questions", []),
                "missing_topics": analysis.get("missing_topics", []),
                "suggestions": suggestions
            }
            
        except Exception as e:
            print(f"❌ [FAQ-INTELLIGENCE] Conversation analysis error: {e}")
            return {"suggestions": []}

    async def _generate_faq_suggestions(
        self,
        organization: Dict,
        existing_faqs: List[Dict],
        website_content: Optional[str],
        conversation_patterns: List[str]
    ) -> List[Dict]:
        """Generate intelligent FAQ suggestions"""
        
        print(f"🤖 [FAQ-INTELLIGENCE] Generating FAQ suggestions")
        
        company_type = organization.get("company_organization_type", "General Business")
        company_name = organization.get("organization_name", "")
        
        existing_q = "\n".join([f"- {faq['question']}" for faq in existing_faqs])
        
        context = f"Company: {company_name}\nType: {company_type}\n"
        if website_content:
            context += f"\nWebsite Info:\n{website_content[:2000]}"
        if conversation_patterns:
            context += f"\n\nCustomers often ask about:\n" + "\n".join([f"- {p}" for p in conversation_patterns[:5]])
        
        prompt = f"""You are an FAQ expert for {company_type} businesses.

{context}

EXISTING FAQs:
{existing_q}

Generate 5-8 ESSENTIAL missing FAQs that would improve AI chatbot responses.

Requirements:
- Do NOT duplicate existing FAQs
- Focus on common {company_type} customer questions
- Provide clear, helpful answer templates
- Prioritize by importance

Return ONLY valid JSON array:
[
    {{
        "question": "clear question text",
        "suggested_answer": "detailed answer based on company context",
        "priority": "high/medium/low",
        "category": "Service/Pricing/Process/General/etc",
        "reasoning": "why this FAQ is important"
    }}
]"""

        try:
            response = await self.llm.ainvoke(prompt)
            suggestions_raw = json.loads(response.content)
            
            suggestions = []
            for item in suggestions_raw[:8]:
                suggestions.append({
                    "type": "missing_faq",
                    "priority": item.get("priority", "medium"),
                    "category": item.get("category", "General"),
                    "question": item["question"],
                    "suggested_answer": item.get("suggested_answer", ""),
                    "reasoning": item.get("reasoning", ""),
                    "source": "ai_analysis"
                })
            
            return suggestions
            
        except Exception as e:
            print(f"❌ [FAQ-INTELLIGENCE] FAQ generation error: {e}")
            return []

    def _calculate_readiness_score(
        self,
        profile_check: Dict,
        faq_check: Dict,
        website_analysis: Optional[Dict],
        document_analysis: Optional[Dict],
        conversation_history: List[Dict]
    ) -> int:
        """Calculate overall FAQ readiness score (0-100)"""
        
        score = 0
        
        # Profile completeness (30 points)
        score += profile_check["completion_percentage"] * 0.3
        
        # FAQ availability (40 points)
        if faq_check["has_faqs"]:
            if faq_check["count"] >= 10:
                score += 40
            elif faq_check["count"] >= 5:
                score += 30
            else:
                score += 20
        
        # Website content (15 points)
        if website_analysis and website_analysis.get("success"):
            if website_analysis.get("word_count", 0) > 500:
                score += 15
            else:
                score += 8
        
        # Document training (10 points)
        if document_analysis and document_analysis.get("success"):
            score += 10
        
        # Conversation data (5 points)
        if conversation_history and len(conversation_history) > 10:
            score += 5
        
        return min(100, int(score))
