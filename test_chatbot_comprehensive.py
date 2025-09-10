#!/usr/bin/env python3
"""
Comprehensive Chatbot Testing Script
Tests all aspects of the AI chatbot system including:
- API responses
- Pinecone integration
- Visitor tracking
- OpenAI integration
- LangChain functionality
- Appointment booking
"""

import requests
import json
import time
import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_API_KEY = "test_carter_law_2024"  # We'll create this

class ChatbotTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session_id = f"test_session_{int(time.time())}"
        self.api_key = TEST_API_KEY
        self.test_results = []
        
    def log_result(self, test_name, success, message, response_data=None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        if response_data and not success:
            print(f"   Response: {json.dumps(response_data, indent=2)}")
    
    def create_test_organization(self):
        """Create a test organization for testing"""
        try:
            # First, try to create organization via API
            org_data = {
                "name": "Carter Injury Law Test",
                "email": "test@carterinjurylaw.com",
                "phone": "(813) 922-0228",
                "address": "3114 N. Boulevard, Tampa, FL 33603",
                "website": "https://www.carterinjurylaw.com",
                "industry": "Legal Services",
                "description": "Premier personal injury law firm in Tampa, Florida"
            }
            
            response = requests.post(f"{self.base_url}/organization/create", json=org_data)
            if response.status_code == 200:
                result = response.json()
                self.api_key = result.get("api_key", self.api_key)
                self.log_result("Create Test Organization", True, f"Organization created with API key: {self.api_key[:8]}...")
                return True
            else:
                self.log_result("Create Test Organization", False, f"Failed to create organization: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Create Test Organization", False, f"Error creating organization: {str(e)}")
            return False
    
    def test_basic_connectivity(self):
        """Test basic API connectivity"""
        try:
            response = requests.get(f"{self.base_url}/")
            if response.status_code == 200:
                data = response.json()
                self.log_result("Basic Connectivity", True, "API server is running", data)
                return True
            else:
                self.log_result("Basic Connectivity", False, f"Server returned {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Basic Connectivity", False, f"Connection error: {str(e)}")
            return False
    
    def test_chatbot_response_quality(self):
        """Test chatbot response quality and naturalness"""
        test_queries = [
            {
                "question": "Hello, I was in a car accident yesterday and I'm not sure what to do",
                "expected_topics": ["accident", "help", "legal", "consultation"],
                "test_name": "Car Accident Query"
            },
            {
                "question": "What types of cases do you handle?",
                "expected_topics": ["personal injury", "cases", "legal services"],
                "test_name": "Services Query"
            },
            {
                "question": "How much do you charge for your services?",
                "expected_topics": ["fee", "cost", "contingency", "no fee"],
                "test_name": "Pricing Query"
            },
            {
                "question": "Can you help me schedule an appointment?",
                "expected_topics": ["appointment", "schedule", "consultation"],
                "test_name": "Appointment Request"
            }
        ]
        
        for query in test_queries:
            try:
                payload = {
                    "question": query["question"],
                    "mode": "faq",
                    "session_id": self.session_id,
                    "api_key": self.api_key
                }
                
                response = requests.post(f"{self.base_url}/api/chatbot/ask", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "")
                    
                    # Check if response contains expected topics
                    topics_found = sum(1 for topic in query["expected_topics"] if topic.lower() in answer.lower())
                    quality_score = topics_found / len(query["expected_topics"])
                    
                    if quality_score > 0.5 and len(answer) > 50:
                        self.log_result(f"Response Quality - {query['test_name']}", True, 
                                      f"Good response quality (score: {quality_score:.1f})", 
                                      {"question": query["question"], "answer": answer[:200]})
                    else:
                        self.log_result(f"Response Quality - {query['test_name']}", False, 
                                      f"Poor response quality (score: {quality_score:.1f})", 
                                      {"question": query["question"], "answer": answer})
                else:
                    self.log_result(f"Response Quality - {query['test_name']}", False, 
                                  f"API error: {response.status_code}", response.json())
                    
            except Exception as e:
                self.log_result(f"Response Quality - {query['test_name']}", False, f"Error: {str(e)}")
    
    def test_visitor_tracking(self):
        """Test visitor tracking functionality"""
        try:
            # Test conversation with name and email collection
            test_conversation = [
                "Hi, I need help with a slip and fall accident",
                "My name is John Doe",
                "My email is john.doe@email.com",
                "I slipped at a grocery store and hurt my back"
            ]
            
            for i, message in enumerate(test_conversation):
                payload = {
                    "question": message,
                    "mode": "faq",
                    "session_id": self.session_id + "_tracking",
                    "api_key": self.api_key
                }
                
                response = requests.post(f"{self.base_url}/api/chatbot/ask", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    user_data = data.get("user_data", {})
                    
                    # Check if name was captured
                    if i >= 1 and "john" not in user_data.get("name", "").lower():
                        self.log_result("Visitor Tracking - Name", False, "Name not captured properly", user_data)
                    
                    # Check if email was captured  
                    if i >= 2 and "john.doe@email.com" not in user_data.get("email", ""):
                        self.log_result("Visitor Tracking - Email", False, "Email not captured properly", user_data)
                
                time.sleep(1)  # Small delay between messages
            
            self.log_result("Visitor Tracking", True, "Visitor tracking test completed")
            
        except Exception as e:
            self.log_result("Visitor Tracking", False, f"Error: {str(e)}")
    
    def test_pinecone_integration(self):
        """Test Pinecone vector database integration"""
        try:
            # Test document upload
            test_document = {
                "text": f"TEST-DOC-{int(time.time())}: Carter Injury Law is a premier personal injury law firm in Tampa, Florida. We handle car accidents, slip and fall cases, and medical malpractice. Our experienced attorneys David J. Carter and Robert Johnson have helped thousands of clients recover millions in compensation.",
                "api_key": self.api_key
            }
            
            response = requests.post(f"{self.base_url}/api/chatbot/add_document", json=test_document)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.log_result("Pinecone Integration - Upload", True, "Document uploaded successfully", data)
                    
                    # Test retrieval
                    time.sleep(2)  # Wait for indexing
                    
                    retrieval_payload = {
                        "question": "Tell me about Carter Injury Law",
                        "mode": "faq",
                        "session_id": self.session_id + "_pinecone",
                        "api_key": self.api_key
                    }
                    
                    retrieval_response = requests.post(f"{self.base_url}/api/chatbot/ask", json=retrieval_payload)
                    
                    if retrieval_response.status_code == 200:
                        retrieval_data = retrieval_response.json()
                        answer = retrieval_data.get("answer", "")
                        
                        if "carter injury law" in answer.lower():
                            self.log_result("Pinecone Integration - Retrieval", True, "Document retrieval working", 
                                          {"answer": answer[:200]})
                        else:
                            self.log_result("Pinecone Integration - Retrieval", False, "Document not retrieved properly", 
                                          {"answer": answer})
                    else:
                        self.log_result("Pinecone Integration - Retrieval", False, f"Retrieval API error: {retrieval_response.status_code}")
                else:
                    self.log_result("Pinecone Integration - Upload", False, "Document upload failed", data)
            else:
                self.log_result("Pinecone Integration - Upload", False, f"Upload API error: {response.status_code}")
                
        except Exception as e:
            self.log_result("Pinecone Integration", False, f"Error: {str(e)}")
    
    def test_duplicate_detection(self):
        """Test duplicate question detection"""
        try:
            # Ask the same question multiple times
            duplicate_question = "What are your office hours?"
            
            responses = []
            for i in range(3):
                payload = {
                    "question": duplicate_question,
                    "mode": "faq", 
                    "session_id": self.session_id + "_duplicate",
                    "api_key": self.api_key
                }
                
                response = requests.post(f"{self.base_url}/api/chatbot/ask", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    responses.append(data.get("answer", ""))
                
                time.sleep(1)
            
            # Check if responses are similar (indicating caching/duplicate detection)
            if len(responses) == 3:
                if responses[0] == responses[1] == responses[2]:
                    self.log_result("Duplicate Detection", True, "Consistent responses for duplicate questions")
                else:
                    self.log_result("Duplicate Detection", False, "Inconsistent responses for duplicate questions", 
                                  {"responses": responses})
            else:
                self.log_result("Duplicate Detection", False, "Failed to get all responses")
                
        except Exception as e:
            self.log_result("Duplicate Detection", False, f"Error: {str(e)}")
    
    def test_appointment_booking(self):
        """Test appointment booking functionality"""
        try:
            appointment_queries = [
                "I'd like to schedule a consultation",
                "What times are available for an appointment?",
                "Can I book an appointment for next week?"
            ]
            
            for query in appointment_queries:
                payload = {
                    "question": query,
                    "mode": "appointment",
                    "session_id": self.session_id + "_appointment", 
                    "api_key": self.api_key
                }
                
                response = requests.post(f"{self.base_url}/api/chatbot/ask", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "")
                    
                    # Check for appointment-related keywords
                    appointment_keywords = ["appointment", "schedule", "consultation", "available", "book"]
                    keywords_found = sum(1 for keyword in appointment_keywords if keyword.lower() in answer.lower())
                    
                    if keywords_found >= 2:
                        self.log_result(f"Appointment Booking - {query[:30]}...", True, 
                                      f"Good appointment response", {"answer": answer[:200]})
                    else:
                        self.log_result(f"Appointment Booking - {query[:30]}...", False, 
                                      f"Poor appointment response", {"answer": answer})
                else:
                    self.log_result(f"Appointment Booking - {query[:30]}...", False, 
                                  f"API error: {response.status_code}")
                
                time.sleep(1)
                
        except Exception as e:
            self.log_result("Appointment Booking", False, f"Error: {str(e)}")
    
    def test_openai_langchain_integration(self):
        """Test OpenAI and LangChain integration"""
        try:
            # Test a complex query that requires AI processing
            complex_query = "I was injured in a car accident that wasn't my fault. The other driver ran a red light and hit me. I have medical bills and missed work. What should I do and how much compensation might I expect?"
            
            payload = {
                "question": complex_query,
                "mode": "faq",
                "session_id": self.session_id + "_ai_test",
                "api_key": self.api_key
            }
            
            response = requests.post(f"{self.base_url}/api/chatbot/ask", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                
                # Check for AI-generated response characteristics
                ai_indicators = ["compensation", "medical bills", "legal", "attorney", "case", "injury"]
                indicators_found = sum(1 for indicator in ai_indicators if indicator.lower() in answer.lower())
                
                if indicators_found >= 3 and len(answer) > 100:
                    self.log_result("OpenAI/LangChain Integration", True, 
                                  f"AI processing working well (indicators: {indicators_found})", 
                                  {"answer": answer[:300]})
                else:
                    self.log_result("OpenAI/LangChain Integration", False, 
                                  f"AI processing seems limited (indicators: {indicators_found})", 
                                  {"answer": answer})
            else:
                self.log_result("OpenAI/LangChain Integration", False, f"API error: {response.status_code}")
                
        except Exception as e:
            self.log_result("OpenAI/LangChain Integration", False, f"Error: {str(e)}")
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Chatbot Testing")
        print("=" * 50)
        
        # Run tests in order
        self.test_basic_connectivity()
        self.create_test_organization()
        self.test_chatbot_response_quality()
        self.test_visitor_tracking()
        self.test_pinecone_integration()
        self.test_duplicate_detection()
        self.test_appointment_booking()
        self.test_openai_langchain_integration()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        # Save results to file
        with open("test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: test_results.json")
        
        return passed_tests, failed_tests

if __name__ == "__main__":
    tester = ChatbotTester()
    passed, failed = tester.run_all_tests()
    
    # Exit with error code if tests failed
    sys.exit(0 if failed == 0 else 1)

