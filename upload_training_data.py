#!/usr/bin/env python3
"""
Upload Training Data to Vector Database
Uploads comprehensive training data to Pinecone for better AI responses
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.langchain.engine import add_document
from training_data import get_training_data, get_specific_faq_data
import time

def upload_training_data(api_key):
    """Upload comprehensive training data to the vector database"""
    
    print("🚀 Starting training data upload...")
    
    # Upload main training data
    print("\n📚 Uploading comprehensive firm information...")
    main_data = get_training_data()
    
    result = add_document(text=main_data, api_key=api_key)
    
    if result and result.get("status") == "success":
        print(f"✅ Main training data uploaded successfully!")
        print(f"   Documents added: {result.get('documents_added', 0)}")
    else:
        print(f"❌ Failed to upload main training data: {result}")
        return False
    
    # Small delay to avoid rate limiting
    time.sleep(2)
    
    # Upload specific FAQ data
    print("\n❓ Uploading specific FAQ responses...")
    faq_data = get_specific_faq_data()
    
    for topic, answer in faq_data.items():
        faq_text = f"FAQ Topic: {topic.replace('_', ' ').title()}\n\nQuestion: {topic}\nAnswer: {answer}\n\nThis is a frequently asked question about {topic.replace('_', ' ')} at Carter Injury Law."
        
        result = add_document(text=faq_text, api_key=api_key)
        
        if result and result.get("status") == "success":
            print(f"✅ FAQ uploaded: {topic}")
        else:
            print(f"❌ Failed to upload FAQ: {topic}")
        
        time.sleep(1)  # Small delay between uploads
    
    print("\n🎯 Training data upload completed!")
    return True

def test_retrieval(api_key):
    """Test if the uploaded data can be retrieved"""
    print("\n🔍 Testing data retrieval...")
    
    from services.langchain.engine import ask_bot
    
    test_queries = [
        "What are your office hours?",
        "How much do you charge?", 
        "What types of cases do you handle?",
        "Tell me about the attorneys",
        "What is your 30-day guarantee?"
    ]
    
    for query in test_queries:
        try:
            response = ask_bot(
                query=query,
                mode="faq",
                session_id=f"test_{int(time.time())}",
                api_key=api_key
            )
            
            if response and response.get("answer"):
                answer = response.get("answer", "")
                print(f"✅ Query: '{query}' - Response length: {len(answer)} chars")
            else:
                print(f"❌ Query: '{query}' - No response")
                
        except Exception as e:
            print(f"❌ Query: '{query}' - Error: {str(e)}")
        
        time.sleep(1)

def main():
    """Main function to upload training data"""
    
    # Try to read API key from file
    api_key = None
    try:
        with open('test_api_key.txt', 'r') as f:
            api_key = f.read().strip()
    except FileNotFoundError:
        print("❌ API key file not found. Please run setup_test_org.py first.")
        return False
    
    if not api_key:
        print("❌ No API key found. Please run setup_test_org.py first.")
        return False
    
    print(f"🔑 Using API key: {api_key[:8]}...")
    
    # Upload training data
    success = upload_training_data(api_key)
    
    if success:
        # Test retrieval
        test_retrieval(api_key)
        print("\n🎉 Training data upload and testing completed successfully!")
        return True
    else:
        print("\n💥 Training data upload failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

