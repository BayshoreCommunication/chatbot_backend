from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
import random
from typing import List
from services.database import get_organization_by_api_key

router = APIRouter()

# Helper function to generate random data
def generate_monthly_data():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    data = []
    for month in months:
        data.append({
            'name': month,
            'thisYear': random.randint(8000, 30000),
            'lastYear': random.randint(5000, 25000)
        })
    return data

@router.get("/analytics")
async def get_analytics_data():
    """Get analytics data for the chart"""
    try:
        data = generate_monthly_data()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/traffic-sources")
async def get_traffic_sources():
    """Get traffic sources data"""
    try:
        sources = [
            {"name": "Google", "percentage": random.randint(30, 50)},
            {"name": "Direct", "percentage": random.randint(20, 40)},
            {"name": "Social Media", "percentage": random.randint(10, 30)},
            {"name": "Referral", "percentage": random.randint(5, 20)},
            {"name": "Email", "percentage": random.randint(5, 15)}
        ]
        return sources
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications")
async def get_notifications():
    """Get notifications data"""
    try:
        notifications = [
            {
                "id": 1,
                "icon": "message",
                "title": "New message from John Doe",
                "time": "Just now"
            },
            {
                "id": 2,
                "icon": "user",
                "title": "New user registered",
                "time": "5 minutes ago"
            },
            {
                "id": 3,
                "icon": "alert",
                "title": "System update completed",
                "time": "1 hour ago"
            },
            {
                "id": 4,
                "icon": "success",
                "title": "Payment received",
                "time": "2 hours ago"
            }
        ]
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-users")
async def get_active_users():
    """Get active users data"""
    try:
        users = [
            {
                "id": 1,
                "name": "John Doe",
                "avatar": "/avatars/01.png",
                "status": "online",
                "initials": "JD"
            },
            {
                "id": 2,
                "name": "Jane Smith",
                "avatar": "/avatars/02.png",
                "status": "online",
                "initials": "JS"
            },
            {
                "id": 3,
                "name": "Mike Johnson",
                "avatar": "/avatars/03.png",
                "status": "offline",
                "initials": "MJ"
            },
            {
                "id": 4,
                "name": "Sarah Wilson",
                "avatar": "/avatars/04.png",
                "status": "online",
                "initials": "SW"
            }
        ]
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 