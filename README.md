# AI Chatbot Backend

A powerful AI-driven chatbot backend for businesses with multiple modes and integrations.

## Features

1. **AI FAQ Bot**
   - Learn from your website, brochure, Google My Business, and PDF menus
   - Instantly answer questions like opening times, services, and location

2. **Lead Capture Mode**
   - Collects name, email, phone number, and inquiry
   - Auto-saves to dashboard + email notification to owner
   - Integrates with HubSpot, Mailchimp, Notion, etc.

3. **Appointment & Booking Integration**
   - Integrates with Calendly, Google Calendar, Square Appointments, etc.
   - AI can suggest available appointment times

4. **Sales Assistant Mode**
   - Recommends products/services
   - Offers discounts/coupons
   - Can email product information to customers

5. **Language Support**
   - Detects customer language (e.g., English, Bangla, Spanish)
   - Responds in the detected language

6. **Live Chat Escalation**
   - If AI can't answer, it pings business owner
   - Redirects to WhatsApp, Messenger, or Email

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

The API will be available at https://chatbot.bayshorecommunication.com, and the interactive documentation at https://chatbot.bayshorecommunication.com/docs.

## API Endpoints

### Chatbot

- `POST /chatbot/ask` - Ask a question to the AI
- `POST /chatbot/change_mode` - Change the chatbot mode
- `POST /chatbot/upload_document` - Upload documents to the knowledge base
- `POST /chatbot/escalate` - Escalate a conversation to a human

### Lead Management

- `POST /lead/submit` - Submit a new lead
- `GET /lead/list` - List all leads (admin only)
- `POST /lead/search` - Search leads by criteria

### Appointment Booking

- `GET /appointment/available-slots` - Get available appointment slots
- `POST /appointment/book` - Book an appointment
- `GET /appointment/services` - List available service types

### Sales Assistant

- `GET /sales/products` - List all products
- `GET /sales/products/{product_id}` - Get product details
- `GET /sales/search` - Search for products
- `POST /sales/recommend` - Get product recommendations
- `GET /sales/discounts` - Get available discounts
- `POST /sales/email-products` - Email product information to a customer

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