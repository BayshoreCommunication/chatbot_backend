#!/usr/bin/env python3
"""
Script to add created_at timestamps to existing visitor records
"""

from datetime import datetime
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import get_database

def update_visitors_created_at():
    """Update visitor records that don't have created_at field"""
    db = get_database()
    
    # Find visitors without created_at field
    visitors_without_created_at = list(db.visitors.find({"created_at": {"$exists": False}}))
    
    print(f"Found {len(visitors_without_created_at)} visitors without created_at field")
    
    if len(visitors_without_created_at) == 0:
        print("All visitors already have created_at field!")
        return
    
    # Update each visitor
    updated_count = 0
    for visitor in visitors_without_created_at:
        try:
            # Use ObjectId timestamp as created_at if available
            if "_id" in visitor:
                created_at = visitor["_id"].generation_time
            else:
                # Fallback to current time if no ObjectId
                created_at = datetime.utcnow()
            
            # Update the visitor with created_at field
            result = db.visitors.update_one(
                {"_id": visitor["_id"]},
                {"$set": {"created_at": created_at}}
            )
            
            if result.modified_count > 0:
                updated_count += 1
                print(f"Updated visitor {visitor.get('id', 'unknown')} with created_at: {created_at}")
        
        except Exception as e:
            print(f"Error updating visitor {visitor.get('id', 'unknown')}: {e}")
    
    print(f"\nSummary:")
    print(f"Total visitors found without created_at: {len(visitors_without_created_at)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Failed to update: {len(visitors_without_created_at) - updated_count}")

if __name__ == "__main__":
    print("Starting visitor created_at update script...")
    update_visitors_created_at()
    print("Script completed!") 