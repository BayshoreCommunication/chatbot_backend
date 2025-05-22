# AI Chatbot SaaS Platform API Documentation

This document provides comprehensive details for all API endpoints available in the AI Chatbot SaaS Platform. Frontend integration teams can use this documentation to build dashboards and integrate with the platform.

## Base URL

All API endpoints are relative to the base URL of the deployed application.

## Authentication

Most endpoints require authentication using an API key. Include the API key in the request headers:

```
X-API-Key: your_organization_api_key
```

## API Endpoints

### Root Endpoint

#### GET /

Returns basic information about the platform.

**Response Example:**
```json
{
  "message": "AI Chatbot SaaS Platform is running.",
  "documentation": "/docs",
  "features": [
    "Multi-tenant organization support",
    "AI FAQ Bot with knowledge base",
    "Lead Capture Mode",
    "Appointment & Booking Integration",
    "Sales Assistant Mode",
    "Language Support",
    "Live Chat Escalation"
  ]
}
```

### Health Check

#### GET /health

Provides health status information about the API.

**Response Example:**
```json
{
  "status": "healthy"
}
```

### Organization Management

#### POST /organization/register

Register a new organization and generate an API key.

**Request Body:**
```json
{
  "name": "Acme Corporation",
  "subscription_tier": "standard"
}
```

**Response Example:**
```json
{
  "status": "success",
  "message": "Organization registered successfully",
  "organization": {
    "id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
    "name": "Acme Corporation",
    "api_key": "org_sk_1234567890abcdef",
    "subscription_tier": "standard",
    "subscription_status": "active",
    "pinecone_namespace": "org_1a2b3c4d5e6f"
  }
}
```

#### GET /organization/me

Get details of the current organization (authenticated via API key).

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Response Example:**
```json
{
  "status": "success",
  "organization": {
    "id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
    "name": "Acme Corporation",
    "subscription_tier": "standard",
    "subscription_status": "active",
    "pinecone_namespace": "org_1a2b3c4d5e6f",
    "settings": {}
  }
}
```

#### PUT /organization/update

Update organization details.

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Request Body:**
```json
{
  "name": "Acme Corp Updated",
  "subscription_tier": "premium",
  "settings": {
    "welcome_message": "Welcome to Acme Corp!",
    "theme_color": "#00ff00"
  }
}
```

**Response Example:**
```json
{
  "status": "success",
  "message": "Organization updated successfully",
  "organization": {
    "id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
    "name": "Acme Corp Updated",
    "subscription_tier": "premium",
    "subscription_status": "active",
    "settings": {
      "welcome_message": "Welcome to Acme Corp!",
      "theme_color": "#00ff00"
    }
  }
}
```

#### GET /organization/usage

Get organization usage statistics.

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Response Example:**
```json
{
  "status": "success",
  "usage": {
    "api_calls": 1250,
    "vector_embeddings": 156,
    "storage_used": 638976,
    "documents": 15,
    "last_updated": "2023-06-01T12:30:45.123Z"
  }
}
```

### Chatbot

#### POST /chatbot/ask

Send a question to the chatbot.

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Request Body:**
```json
{
  "question": "What services do you offer?",
  "session_id": "unique-session-identifier",
  "mode": "faq",
  "user_data": {
    "name": "John Doe",
    "email": "john@example.com"
  },
  "available_slots": null
}
```

**Response Example:**
```json
{
  "answer": "We offer a range of legal services including legal consultation, will preparation, and contract review.",
  "sources": [
    {
      "source": "legal_services.pdf",
      "page": 2
    }
  ],
  "user_data": {
    "name": "John Doe",
    "email": "john@example.com",
    "returning_user": true
  }
}
```

#### GET /chatbot/history/{session_id}

Retrieve chat history for a specific session.

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Response Example:**
```json
{
  "status": "success",
  "conversation": [
    {
      "role": "user",
      "content": "What services do you offer?",
      "timestamp": "2023-06-01T12:00:00.000Z"
    },
    {
      "role": "assistant",
      "content": "We offer a range of legal services including legal consultation, will preparation, and contract review.",
      "timestamp": "2023-06-01T12:00:05.000Z"
    }
  ]
}
```

#### POST /chatbot/change_mode

Change the chatbot mode.

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Request Body:**
```json
{
  "session_id": "unique-session-identifier",
  "mode": "appointment"
}
```

**Response Example:**
```json
{
  "status": "success",
  "message": "Chatbot mode changed to appointment",
  "mode": "appointment"
}
```

#### POST /chatbot/upload_document

Upload a document to the chatbot knowledge base.

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Form Data:**
- `file`: File upload (optional)
- `url`: URL to document (optional)
- `text`: Text content (optional)
- `scrape_website`: Boolean (optional, default: false)
- `max_pages`: Integer (optional, default: 10)

**Response Example:**
```json
{
  "status": "success",
  "message": "Document processed successfully",
  "document": {
    "id": "doc_1a2b3c4d5e6f",
    "title": "Legal Services Overview",
    "type": "pdf",
    "num_chunks": 15
  }
}
```

#### POST /chatbot/escalate

Escalate a conversation to a human agent.

**Headers:**
```
X-API-Key: your_organization_api_key
```

**Request Body:**
```json
{
  "session_id": "unique-session-identifier",
  "issue": "Complex legal question",
  "conversation_history": [
    {
      "role": "user",
      "content": "I need help with a complicated trust issue."
    },
    {
      "role": "assistant",
      "content": "I'll try to help with your trust issue. What specifically do you need assistance with?"
    }
  ]
}
```

**Response Example:**
```json
{
  "status": "success",
  "message": "Conversation escalated successfully",
  "escalation_id": "esc_1a2b3c4d5e6f",
  "estimated_response_time": "30 minutes"
}
```

### Lead Management

#### POST /lead/submit

Submit a new lead.

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "inquiry": "I'm interested in your legal services.",
  "source": "chatbot"
}
```

**Response Example:**
```json
{
  "lead_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
  "status": "success",
  "message": "Lead submitted successfully"
}
```

#### GET /lead/list

List all leads (admin only).

**Headers:**
```
Authorization: Bearer admin_api_key
```

**Response Example:**
```json
{
  "leads": [
    {
      "lead_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1234567890",
      "inquiry": "I'm interested in your legal services.",
      "source": "chatbot",
      "timestamp": "2023-06-01T12:00:00.000Z",
      "status": "new"
    }
  ]
}
```

#### POST /lead/search

Search leads by criteria (admin only).

**Headers:**
```
Authorization: Bearer admin_api_key
```

**Request Body:**
```json
{
  "name": "John",
  "email": null,
  "status": "new",
  "date_from": "2023-06-01T00:00:00.000Z",
  "date_to": "2023-06-30T23:59:59.999Z"
}
```

**Response Example:**
```json
{
  "leads": [
    {
      "lead_id": "1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1234567890",
      "inquiry": "I'm interested in your legal services.",
      "source": "chatbot",
      "timestamp": "2023-06-01T12:00:00.000Z",
      "status": "new"
    }
  ]
}
```

### Appointment Booking

#### GET /appointment/available-slots

Get available appointment slots.

**Response Example:**
```json
{
  "slots": [
    {
      "id": "slot_1a2b3c4d",
      "date": "2023-06-15",
      "time": "10:00",
      "available": true
    },
    {
      "id": "slot_2b3c4d5e",
      "date": "2023-06-15",
      "time": "14:30",
      "available": true
    }
  ]
}
```

#### POST /appointment/book

Book an appointment.

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "service": "legal_consultation",
  "slot_id": "slot_1a2b3c4d",
  "date": "2023-06-15",
  "time": "10:00",
  "notes": "Initial consultation about contract review"
}
```

**Response Example:**
```json
{
  "status": "success",
  "message": "Appointment booked successfully",
  "booking_info": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "service": "legal_consultation",
    "slot_id": "slot_1a2b3c4d",
    "date": "2023-06-15",
    "time": "10:00",
    "booking_reference": "BOOK-20230601123045",
    "status": "confirmed"
  }
}
```

#### GET /appointment/services

Get available service types for appointments.

**Response Example:**
```json
{
  "services": [
    {
      "id": "legal_consultation",
      "name": "Legal Consultation",
      "duration": 60,
      "price": 200
    },
    {
      "id": "document_review",
      "name": "Document Review",
      "duration": 30,
      "price": 100
    },
    {
      "id": "case_evaluation",
      "name": "Case Evaluation",
      "duration": 90,
      "price": 300
    },
    {
      "id": "will_testament",
      "name": "Will & Testament",
      "duration": 60,
      "price": 250
    }
  ]
}
```

### Sales Assistant

#### GET /sales/products

List all products and services.

**Response Example:**
```json
{
  "products": [
    {
      "id": "svc_legal_consultation",
      "name": "Legal Consultation",
      "description": "One-hour consultation with an experienced lawyer to discuss your legal matters.",
      "price": 200.00,
      "category": "services",
      "image_url": "https://example.com/images/legal_consultation.jpg",
      "tags": ["consultation", "legal advice", "attorney"]
    },
    {
      "id": "svc_will_preparation",
      "name": "Will Preparation",
      "description": "Complete will preparation service including document drafting and legal verification.",
      "price": 350.00,
      "category": "services",
      "image_url": "https://example.com/images/will_preparation.jpg",
      "tags": ["will", "testament", "estate planning"]
    }
  ]
}
```

#### GET /sales/products/{product_id}

Get detailed information about a specific product.

**Response Example:**
```json
{
  "id": "svc_legal_consultation",
  "name": "Legal Consultation",
  "description": "One-hour consultation with an experienced lawyer to discuss your legal matters.",
  "price": 200.00,
  "category": "services",
  "image_url": "https://example.com/images/legal_consultation.jpg",
  "tags": ["consultation", "legal advice", "attorney"]
}
```

#### GET /sales/search

Search for products based on query text.

**Query Parameters:**
- `query`: Search term
- `category`: Filter by category

**Response Example:**
```json
{
  "products": [
    {
      "id": "svc_legal_consultation",
      "name": "Legal Consultation",
      "description": "One-hour consultation with an experienced lawyer to discuss your legal matters.",
      "price": 200.00,
      "category": "services",
      "image_url": "https://example.com/images/legal_consultation.jpg",
      "tags": ["consultation", "legal advice", "attorney"]
    }
  ]
}
```

#### POST /sales/recommend

Get product recommendations based on user query.

**Request Body:**
```json
{
  "query": "I need help with creating a will",
  "user_data": {
    "previous_purchases": ["svc_legal_consultation"]
  }
}
```

**Response Example:**
```json
{
  "recommendations": [
    {
      "id": "svc_will_preparation",
      "name": "Will Preparation",
      "description": "Complete will preparation service including document drafting and legal verification.",
      "price": 350.00,
      "category": "services",
      "image_url": "https://example.com/images/will_preparation.jpg",
      "tags": ["will", "testament", "estate planning"]
    }
  ],
  "query": "I need help with creating a will"
}
```

#### GET /sales/discounts

Get available discounts and promotions.

**Response Example:**
```json
{
  "discounts": [
    {
      "id": "disc_10_percent",
      "name": "10% Off First Consultation",
      "description": "Get 10% off your first legal consultation",
      "percent": 10,
      "code": "FIRST10",
      "valid_until": "2023-12-31"
    },
    {
      "id": "disc_free_guide",
      "name": "Free Legal Guide",
      "description": "Get our Legal Self-Help Guide free with any service purchase",
      "code": "FREEGUIDE",
      "valid_until": "2023-12-31"
    }
  ]
}
```

#### POST /sales/email-products

Email product information to a customer.

**Request Body:**
```json
{
  "email": "customer@example.com",
  "product_ids": ["svc_legal_consultation", "svc_will_preparation"],
  "message": "Here's the information you requested about our services."
}
```

**Response Example:**
```json
{
  "status": "success",
  "message": "Product information sent successfully",
  "sent_to": "customer@example.com",
  "products": [
    {
      "id": "svc_legal_consultation",
      "name": "Legal Consultation"
    },
    {
      "id": "svc_will_preparation",
      "name": "Will Preparation"
    }
  ]
}
```

## Error Responses

All endpoints follow a consistent error response format:

```json
{
  "status": "error",
  "detail": "Error message explaining what went wrong"
}
```

Common HTTP status codes:
- 400: Bad Request - Invalid input parameters
- 401: Unauthorized - Missing or invalid API key
- 404: Not Found - Resource not found
- 500: Internal Server Error - Server-side error

## Rate Limits

Rate limits vary by subscription tier:
- Free: 100 requests per day
- Standard: 1,000 requests per day
- Premium: 10,000 requests per day

When a rate limit is exceeded, the API returns:

```json
{
  "status": "error",
  "detail": "Rate limit exceeded",
  "reset_at": "2023-06-02T00:00:00.000Z"
}
``` 