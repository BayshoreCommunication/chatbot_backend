from fastapi import APIRouter, Request, HTTPException
from services.sales_assistant import (
    get_all_products, 
    get_product_by_id, 
    search_products,
    get_product_recommendations,
    get_available_discounts,
    send_product_info
)
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import json
import os
from dotenv import load_dotenv
from datetime import datetime
from services.notification import send_email_notification

# Load environment variables
load_dotenv()

router = APIRouter()

# Mock database for products
products = [
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
    },
    {
        "id": "svc_contract_review",
        "name": "Contract Review",
        "description": "Professional review of contracts with detailed analysis and recommendations.",
        "price": 150.00,
        "category": "services",
        "image_url": "https://example.com/images/contract_review.jpg",
        "tags": ["contract", "legal review", "document"]
    },
    {
        "id": "prd_legal_guide",
        "name": "Legal Self-Help Guide",
        "description": "Comprehensive guide for understanding basic legal concepts and processes.",
        "price": 49.99,
        "category": "products",
        "image_url": "https://example.com/images/legal_guide.jpg",
        "tags": ["guide", "self-help", "legal education"]
    }
]

# Mock discounts database
discounts = [
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

class ProductSearchParams(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    max_price: Optional[float] = None
    tags: Optional[List[str]] = None

class RecommendationRequest(BaseModel):
    query: str
    user_data: Optional[dict] = None

class EmailProductsRequest(BaseModel):
    email: str
    product_ids: List[str]
    message: Optional[str] = None

@router.get("/products")
async def get_products():
    """List all products and services"""
    return {"products": products}

@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get detailed information about a specific product"""
    for product in products:
        if product["id"] == product_id:
            return product
    
    raise HTTPException(status_code=404, detail="Product not found")

@router.get("/search")
async def search_products(query: Optional[str] = None, category: Optional[str] = None):
    """Search for products based on query text"""
    results = products.copy()
    
    if query:
        query = query.lower()
        results = [p for p in results if 
                  query in p["name"].lower() or 
                  query in p["description"].lower() or
                  any(query in tag for tag in p["tags"])]
    
    if category:
        results = [p for p in results if p["category"] == category]
    
    return {"products": results}

@router.post("/recommend")
async def recommend_products(request: RecommendationRequest):
    """Get product recommendations based on user query"""
    query = request.query.lower()
    
    # Simple keyword-based recommendation logic
    recommended = []
    
    # Look for keywords in the query
    if any(word in query for word in ["will", "testament", "estate", "death"]):
        recommended.extend([p for p in products if "will" in p["tags"]])
    
    if any(word in query for word in ["contract", "agreement", "document", "review"]):
        recommended.extend([p for p in products if "contract" in p["tags"]])
    
    if any(word in query for word in ["consult", "advice", "talk", "speak"]):
        recommended.extend([p for p in products if "consultation" in p["tags"]])
    
    if any(word in query for word in ["learn", "understand", "education", "guide"]):
        recommended.extend([p for p in products if "guide" in p["tags"]])
    
    # If no specific recommendations, return top services
    if not recommended:
        recommended = [p for p in products if p["category"] == "services"][:2]
    
    # De-duplicate
    unique_ids = set()
    unique_recommendations = []
    for product in recommended:
        if product["id"] not in unique_ids:
            unique_ids.add(product["id"])
            unique_recommendations.append(product)
    
    return {
        "recommendations": unique_recommendations,
        "query": query
    }

@router.get("/discounts")
async def get_discounts():
    """Get available discounts and promotions"""
    return {"discounts": discounts}

@router.post("/email-products")
async def email_products(request: EmailProductsRequest):
    """Email product information to a customer"""
    # Find the requested products
    selected_products = []
    for product_id in request.product_ids:
        for product in products:
            if product["id"] == product_id:
                selected_products.append(product)
    
    if not selected_products:
        raise HTTPException(status_code=400, detail="No valid products selected")
    
    # Format email content
    subject = "Information about our Legal Services"
    
    body = f"Thank you for your interest in our services.\n\n"
    if request.message:
        body += f"Message: {request.message}\n\n"
    
    body += "Here are the details of the products/services you inquired about:\n\n"
    
    for product in selected_products:
        body += f"• {product['name']}\n"
        body += f"  {product['description']}\n"
        body += f"  Price: ${product['price']:.2f}\n\n"
    
    body += "Please contact us if you have any questions or would like to proceed."
    
    # In a real application, send the actual email
    # For demo purposes, just log it
    print(f"Would send email to {request.email} with subject: {subject}")
    
    # Attempt to send notification (this would be a real email in production)
    try:
        send_email_notification(subject, body, [request.email])
        email_sent = True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        email_sent = False
    
    return {
        "status": "success" if email_sent else "partial_success",
        "message": "Product information has been emailed to the customer" if email_sent else "Email could not be sent, but request was processed",
        "products_sent": [p["name"] for p in selected_products],
        "email": request.email
    } 