from fastapi import APIRouter, Depends, HTTPException, Header
from datetime import datetime, timedelta
import random
from typing import List, Optional
from services.database import get_organization_by_api_key, get_database
from bson import ObjectId
from collections import defaultdict

router = APIRouter()

@router.get("/analytics")
async def get_analytics_data(x_api_key: Optional[str] = Header(None)):
    """Get analytics data for the chart"""
    try:
        print(f"Received analytics request with API key: {x_api_key[:8]}...")
        
        if not x_api_key:
            print("No API key provided in request")
            raise HTTPException(status_code=401, detail="API key is required")

        # Get organization from API key
        print("Fetching organization by API key...")
        org = get_organization_by_api_key(x_api_key)
        if not org:
            print("Invalid API key - no organization found")
            raise HTTPException(status_code=401, detail="Invalid API key")

        org_id = org.get('id')
        print(f"Found organization with ID: {org_id}")
        
        db = get_database()
        print("Database connection established")

        # Get current year and last year
        current_year = datetime.now().year
        last_year = current_year - 1
        print(f"Fetching data for years: {current_year} and {last_year}")

        # Get chat data for current year and last year
        current_year_data = defaultdict(int)
        last_year_data = defaultdict(int)
        visitor_current_year = defaultdict(set)
        visitor_last_year = defaultdict(set)

        # Get chat data from conversations collection
        query = {
            'organization_id': str(org_id),
            'created_at': {
                '$gte': datetime(last_year, 1, 1),
                '$lte': datetime(current_year, 12, 31)
            }
        }
        print(f"Querying conversations with filter: {query}")
        
        conversations = db.conversations.find(query)
        print(f"Found conversations: {conversations}")
        conversation_count = 0

        # Process conversations data
        for conv in conversations:
            conversation_count += 1
            created_at = conv.get('created_at')
            if isinstance(created_at, dict) and '$date' in created_at:
                created_at = datetime.fromisoformat(created_at['$date'].replace('Z', '+00:00'))
            elif isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            month = created_at.strftime('%b')
            year = created_at.year
            visitor_id = conv.get('visitor_id')
            
            if year == current_year:
                current_year_data[month] += 1
                if visitor_id:
                    visitor_current_year[month].add(visitor_id)
            else:
                last_year_data[month] += 1
                if visitor_id:
                    visitor_last_year[month].add(visitor_id)

        print(f"Processed {conversation_count} conversations")

        # Format data for response
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        data = []
        
        for month in months:
            data.append({
                'name': month,
                'thisYear': current_year_data[month],
                'lastYear': last_year_data[month],
                'visitorThisYear': len(visitor_current_year[month]),
                'visitorLastYear': len(visitor_last_year[month])
            })

        print(f"Returning data for {len(data)} months")
        print(f"Data: {data}")
        return data
    except Exception as e:
        print(f"Error in analytics endpoint: {str(e)}")
        import traceback
        print(traceback.format_exc())
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