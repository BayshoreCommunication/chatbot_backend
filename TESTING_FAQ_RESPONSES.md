# Testing Chatbot FAQ Responses

This guide will help you test the chatbot with the specific Q&A responses you requested.

## 🎯 What We're Testing

The chatbot should respond naturally to these specific questions with the exact answers you provided:

### 1. Case Type & Services
- **Q:** "Do you handle personal injury cases?"
- **A:** "Yes, we handle personal injury cases. Could you tell me a little more about what happened so I can better understand your situation?"

- **Q:** "Do you take car accident cases?"
- **A:** "Absolutely, we work with clients involved in car accidents. Were you the driver, passenger, or pedestrian?"

- **Q:** "Do you handle family law cases like divorce or custody?"
- **A:** "Yes, we handle family law matters, including divorce and custody. Would you like me to connect you with our attorney for a consultation?"

### 2. Fees & Payment
- **Q:** "How much do you charge?"
- **A:** "Many of our cases are handled on a contingency fee basis, meaning you don't pay unless we win. For other case types, we can explain fees in your consultation. Would you like to schedule one?"

- **Q:** "Do you offer free consultations?"
- **A:** "Yes, we offer free initial consultations. When would you like to schedule yours?"

### 3. Case Process & Timeline
- **Q:** "How long will my case take?"
- **A:** "The timeline depends on the type of case and details involved. Some cases settle quickly, while others may take longer. An attorney can give you a better estimate after reviewing your case."

- **Q:** "What information do I need to start?"
- **A:** "Typically, details like the date of the incident, any documents, and witness information are helpful. Don't worry—we'll guide you through everything during your consultation."

### 4. Communication & Availability
- **Q:** "How do I contact my lawyer?"
- **A:** "You can reach us by phone, email, or schedule an appointment. After your consultation, we'll make sure you have direct contact details for your attorney."

- **Q:** "How quickly do you respond?"
- **A:** "We aim to respond within 24 hours or sooner. Urgent matters are prioritized immediately."

### 5. Location & Jurisdiction
- **Q:** "Do you only work in [State Name]?"
- **A:** "We are licensed in [State Name], but we may assist with referrals if your case is in another state. Can you tell me where your case is based?"

- **Q:** "Can you represent me if I live out of state?"
- **A:** "In some cases, yes. Please share where you're located, and we'll confirm if we can help or connect you with a trusted partner."

### 6. Next Steps for Clients
- **Q:** "What should I do right now?"
- **A:** "The best next step is to schedule a free consultation. We'll review your case and explain your options. Would you like me to help book a time?"

- **Q:** "Can I bring documents or photos?"
- **A:** "Yes, please do. Documents, photos, and any evidence you have can be very helpful for your case review."

## 🚀 Quick Start Testing

### Option 1: Automated Test (Recommended)
```bash
# Run the comprehensive test
python run_test.py
```

### Option 2: Manual Testing
```bash
# 1. Add the test FAQs to your database
python add_test_faqs.py

# 2. Start your backend server (if not already running)
python main.py

# 3. Test individual responses
python test_chatbot_responses.py
```

## ⚙️ Configuration

Before running the tests, update these values in the test files:

1. **Organization ID**: Update `org_id` in `add_test_faqs.py`
2. **API Key**: Update `api_key` in test files
3. **Server URL**: Update `base_url` if your server runs on a different port

## 📊 Expected Results

When you ask any of the test questions, the chatbot should:

1. ✅ Return the exact response you specified
2. ✅ Use natural, conversational language
3. ✅ Provide helpful follow-up suggestions
4. ✅ Maintain professional lawyer tone

## 🔧 Troubleshooting

### FAQ Not Found
- Check that the organization ID matches your actual org
- Verify the FAQs were added successfully to the database
- Check the vector database embeddings

### Wrong Responses
- Verify the FAQ matching threshold in `faq_matcher.py`
- Check that the vector embeddings were created correctly
- Ensure the FAQ is marked as `is_active: true`

### Server Connection Issues
- Make sure your backend server is running on the correct port
- Check that the API key is valid
- Verify the server health endpoint

## 🎯 Testing with Widget

To test with the actual chatbot widget:

1. Start your backend server
2. Open the widget in your browser
3. Ask the test questions
4. Verify the responses match exactly

## 📝 Notes

- The responses are designed to be natural and conversational
- They include follow-up questions to engage users
- They maintain a professional lawyer tone
- They guide users toward consultation scheduling

## 🆘 Need Help?

If the tests aren't working as expected:

1. Check the server logs for errors
2. Verify database connectivity
3. Test with a simple question first
4. Check the FAQ matching similarity threshold
