import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import json
from services.notification import send_email_notification

load_dotenv()

# Sample product data (in a real app, this would come from a database)
PRODUCTS = [
    {
        "id": "product1",
        "name": "Premium Service Package",
        "description": "Comprehensive service with priority support",
        "price": 299.99,
        "category": "service",
        "tags": ["premium", "support", "priority"],
        "discount_available": True,
        "discount_amount": 50.00,
        "discount_code": "PREMIUM50"
    },
    {
        "id": "product2",
        "name": "Basic Service Package",
        "description": "Essential service features for small businesses",
        "price": 99.99,
        "category": "service",
        "tags": ["basic", "essential", "small business"],
        "discount_available": True,
        "discount_amount": 20.00,
        "discount_code": "BASIC20"
    },
    {
        "id": "product3",
        "name": "Enterprise Solution",
        "description": "Complete enterprise-grade solution",
        "price": 999.99,
        "category": "solution",
        "tags": ["enterprise", "complete", "business"],
        "discount_available": False,
        "discount_amount": 0,
        "discount_code": ""
    },
    {
        "id": "product4",
        "name": "Consultation Package",
        "description": "Expert consultation for your specific needs",
        "price": 199.99,
        "category": "service",
        "tags": ["expert", "consultation", "custom"],
        "discount_available": True,
        "discount_amount": 30.00,
        "discount_code": "CONSULT30"
    }
]

def get_all_products():
    """Return all products"""
    return PRODUCTS

def get_product_by_id(product_id: str):
    """Get a product by its ID"""
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    return None

def search_products(query: str, category: str = None):
    """Search products by query and optionally filter by category"""
    results = []
    query = query.lower()
    
    for product in PRODUCTS:
        # Match by name, description, or tags
        if (query in product["name"].lower() or 
            query in product["description"].lower() or 
            any(query in tag.lower() for tag in product["tags"])):
            
            # Apply category filter if provided
            if category and product["category"] != category:
                continue
                
            results.append(product)
    
    return results

def get_product_recommendations(user_preferences: List[str], budget: float = None):
    """Get product recommendations based on user preferences and budget"""
    scores = []
    
    for product in PRODUCTS:
        # Initialize score
        score = 0
        
        # Score based on matching preferences with product tags and category
        for pref in user_preferences:
            if pref.lower() in product["category"].lower():
                score += 2  # Higher score for category match
            
            if any(pref.lower() in tag.lower() for tag in product["tags"]):
                score += 1  # Score for tag match
        
        # Apply budget filter if provided
        if budget:
            if product["price"] <= budget:
                score += 1  # Bonus for being within budget
            else:
                score -= 2  # Penalty for being over budget
        
        if score > 0:  # Only include products with positive scores
            scores.append((product, score))
    
    # Sort by score, descending
    scores.sort(key=lambda x: x[1], reverse=True)
    
    # Return the products with their scores
    return [{"product": item[0], "score": item[1]} for item in scores]

def get_available_discounts(product_ids: List[str] = None):
    """Get available discounts for all products or specific products"""
    discounts = []
    
    for product in PRODUCTS:
        if product["discount_available"]:
            if product_ids is None or product["id"] in product_ids:
                discounts.append({
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "discount_amount": product["discount_amount"],
                    "discount_code": product["discount_code"],
                    "percent_off": round((product["discount_amount"] / product["price"]) * 100)
                })
    
    return discounts

def send_product_info(user_email: str, product_ids: List[str], add_discounts: bool = True):
    """Send product information to user's email"""
    products = []
    discounts = []
    
    for product_id in product_ids:
        product = get_product_by_id(product_id)
        if product:
            products.append(product)
            
            if add_discounts and product["discount_available"]:
                discounts.append({
                    "product_id": product["id"],
                    "discount_amount": product["discount_amount"],
                    "discount_code": product["discount_code"]
                })
    
    if not products:
        return {
            "status": "error",
            "message": "No valid products found"
        }
    
    # Compose email message
    subject = "Product Information You Requested"
    
    message = "Here's the information you requested:\n\n"
    
    for product in products:
        price = product["price"]
        if add_discounts and product["discount_available"]:
            price = product["price"] - product["discount_amount"]
        
        message += f"Product: {product['name']}\n"
        message += f"Description: {product['description']}\n"
        message += f"Price: ${price:.2f}"
        
        if add_discounts and product["discount_available"]:
            message += f" (Save ${product['discount_amount']:.2f} with code {product['discount_code']})"
        
        message += "\n\n"
    
    message += "Thank you for your interest in our products. Please contact us if you have any questions."
    
    # Send email
    send_email_notification(subject, message, user_email)
    
    return {
        "status": "success",
        "message": f"Product information sent to {user_email}",
        "products": [p["id"] for p in products],
        "discounts_included": add_discounts and len(discounts) > 0
    } 