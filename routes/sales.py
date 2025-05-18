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

router = APIRouter()

class RecommendationRequest(BaseModel):
    preferences: List[str]
    budget: Optional[float] = None

class EmailProductsRequest(BaseModel):
    email: EmailStr
    product_ids: List[str]
    include_discounts: Optional[bool] = True

@router.get("/products")
async def products():
    """List all available products"""
    return {"products": get_all_products()}

@router.get("/products/{product_id}")
async def product_detail(product_id: str):
    """Get details for a specific product"""
    product = get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.get("/search")
async def search(q: str, category: Optional[str] = None):
    """Search for products by name, description, or tags"""
    results = search_products(q, category)
    return {"results": results, "count": len(results)}

@router.post("/recommend")
async def recommend(request: RecommendationRequest):
    """Get product recommendations based on user preferences"""
    recommendations = get_product_recommendations(
        user_preferences=request.preferences,
        budget=request.budget
    )
    return {"recommendations": recommendations}

@router.get("/discounts")
async def discounts(product_ids: Optional[List[str]] = None):
    """Get available discounts for products"""
    discounts = get_available_discounts(product_ids)
    return {"discounts": discounts}

@router.post("/email-products")
async def email_products(request: EmailProductsRequest):
    """Send product information to user's email"""
    result = send_product_info(
        user_email=request.email,
        product_ids=request.product_ids,
        add_discounts=request.include_discounts
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result 