# AI Chatbot Backend

A powerful AI-driven chatbot backend for businesses with multiple modes and integrations.

## Features

1. **AI FAQ Bot**
   - Learn from your website, brochure, Google My Business, and PDF menus
   - Instantly answer questions like opening times, services, and location
   - Semantic search for accurate answers
   - Multi-language support for FAQs
   - Suggested FAQs for follow-up questions

2. **Lead Capture Mode**
   - Collects name, email, phone number, and inquiry
   - Auto-saves to dashboard + email notification to owner
   - Integrates with HubSpot, Mailchimp, Notion, etc.
   - Anonymous user support
   - Returning user recognition

3. **Appointment & Booking Integration**
   - Integrates with Calendly, Google Calendar, Square Appointments, etc.
   - AI can suggest available appointment times
   - Appointment rescheduling and cancellation
   - Automated appointment reminders
   - Booking confirmation system

4. **Sales Assistant Mode**
   - Recommends products/services
   - Offers discounts/coupons
   - Can email product information to customers
   - Product search and filtering
   - Personalized recommendations

5. **Language Support**
   - Detects customer language (e.g., English, Bangla, Spanish)
   - Responds in the detected language
   - Real-time language translation
   - Multi-language knowledge base

6. **Live Chat Escalation**
   - If AI can't answer, it pings business owner
   - Redirects to WhatsApp, Messenger, or Email
   - Smart escalation based on query complexity
   - Conversation history preservation

7. **Knowledge Base Management**
   - Upload and process multiple document types (PDF, URLs, text)
   - Website scraping capability
   - Vector database integration with Pinecone
   - Automatic content chunking and indexing
   - Real-time knowledge base updates

8. **User Management**
   - Session-based conversation tracking
   - User profile management
   - Conversation history storage
   - Privacy-focused data collection
   - Optional information sharing

9. **Multi-tenant Support**
   - Organization-specific knowledge bases
   - Custom API keys per organization
   - Isolated conversation histories
   - Organization-specific configurations

10. **Payment Processing**
    - Stripe integration for payments
    - Secure payment handling
    - Transaction history
    - Payment confirmation system

11. **Analytics & Reporting**
    - Conversation analytics
    - User engagement metrics
    - Response accuracy tracking
    - Usage statistics
    - Performance monitoring

## Setup

### Prerequisites

- Python 3.9+
- MongoDB (local or cloud)
- Pinecone account (for vector database)
- OpenAI API key

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd ai-chatbot-backend
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on `.env.example`:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file with your credentials.

### Running the Application

```
uvicorn main:app --reload
```

The API will be available at http://localhost:8000, and the interactive documentation at http://localhost:8000/docs.

## API Endpoints

### Chatbot

- `POST /chatbot/ask` - Ask a question to the AI
- `POST /chatbot/change_mode` - Change the chatbot mode
- `POST /chatbot/upload_document` - Upload documents to the knowledge base
- `POST /chatbot/escalate` - Escalate a conversation to a human
- `GET /chatbot/history/{session_id}` - Get conversation history

### Lead Management

- `POST /lead/submit` - Submit a new lead
- `GET /lead/list` - List all leads (admin only)
- `POST /lead/search` - Search leads by criteria

### Appointment Booking

- `GET /appointment/available-slots` - Get available appointment slots
- `POST /appointment/book` - Book an appointment
- `GET /appointment/services` - List available service types
- `POST /appointment/reschedule` - Reschedule an appointment
- `POST /appointment/cancel` - Cancel an appointment

### Sales Assistant

- `GET /sales/products` - List all products
- `GET /sales/products/{product_id}` - Get product details
- `GET /sales/search` - Search for products
- `POST /sales/recommend` - Get product recommendations
- `GET /sales/discounts` - Get available discounts
- `POST /sales/email-products` - Email product information to a customer

### Organization Management

- `POST /organization/create` - Create a new organization
- `GET /organization/profile` - Get organization profile
- `PUT /organization/update` - Update organization settings
- `POST /organization/api-key` - Generate new API key

### User Management

- `POST /user/profile` - Create/Update user profile
- `GET /user/history` - Get user interaction history
- `GET /user/preferences` - Get user preferences
- `PUT /user/preferences` - Update user preferences

## Adding Knowledge to the Chatbot

You can upload documents to the chatbot's knowledge base using the `/chatbot/upload_document` endpoint:

- Upload PDF files
- Provide URLs for the chatbot to scrape
- Directly input text content

## Environment Variables

See `.env.example` for all required and optional environment variables.

## Integrations

### CRM Systems
- HubSpot
- Mailchimp

### Calendar Systems
- Google Calendar
- Calendly

## License

[MIT License](LICENSE) 