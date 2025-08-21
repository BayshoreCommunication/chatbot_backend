#!/usr/bin/env python3
"""
Test script for hardcoded FAQ responses
"""

from hardcoded_faq_responses import get_hardcoded_response

def test_hardcoded_responses():
    """Test the hardcoded responses"""
    
    # Test questions
    test_questions = [
        "Do you handle personal injury cases?",
        "Do you take car accident cases?",
        "Do you handle family law cases like divorce or custody?",
        "How much do you charge?",
        "Do you offer free consultations?",
        "How long will my case take?",
        "What information do I need to start?",
        "How do I contact my lawyer?",
        "How quickly do you respond?",
        "Do you only work in California?",
        "Can you represent me if I live out of state?",
        "What should I do right now?",
        "Can I bring documents or photos?"
    ]
    
    print("Testing Hardcoded FAQ Responses")
    print("=" * 50)
    
    passed = 0
    total = len(test_questions)
    
    for i, question in enumerate(test_questions):
        print(f"\nTest {i+1}: {question}")
        print("-" * 40)
        
        response = get_hardcoded_response(question)
        
        if response:
            print(f"Response: {response['answer']}")
            print(f"Category: {response['category']}")
            print("PASS - Found hardcoded response")
            passed += 1
        else:
            print("FAIL - No hardcoded response found")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("All hardcoded responses are working correctly!")
    else:
        print("Some responses failed. Check the hardcoded FAQ data.")

if __name__ == "__main__":
    test_hardcoded_responses()
