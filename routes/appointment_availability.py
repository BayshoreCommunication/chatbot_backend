from fastapi import APIRouter, Request, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import pymongo
from services.database import get_organization_by_api_key, db

router = APIRouter()

# Initialize appointment availability collection
appointment_availability_collection = db.appointment_availability
appointment_availability_collection.create_index("organization_id")
appointment_availability_collection.create_index([("organization_id", pymongo.ASCENDING), ("date", pymongo.ASCENDING)])

def convert_24_to_12_hour(time_str: str) -> str:
    """Convert 24-hour format to 12-hour AM/PM format"""
    try:
        time_obj = datetime.strptime(time_str, "%H:%M")
        return time_obj.strftime("%I:%M %p")
    except ValueError:
        # If it's already in AM/PM format, return as is
        return time_str

def convert_12_to_24_hour(time_str: str) -> str:
    """Convert 12-hour AM/PM format to 24-hour format for validation"""
    try:
        # If already in 24-hour format
        datetime.strptime(time_str, "%H:%M")
        return time_str
    except ValueError:
        try:
            # Convert from AM/PM format to 24-hour
            time_obj = datetime.strptime(time_str, "%I:%M %p")
            return time_obj.strftime("%H:%M")
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}")

class TimeSlot(BaseModel):
    id: str
    start_time: str
    end_time: str

class AppointmentAvailabilityRequest(BaseModel):
    date: str
    time_slots: List[TimeSlot]

class AppointmentAvailabilityResponse(BaseModel):
    date: str
    time_slots: List[TimeSlot]

class DeleteTimeSlotRequest(BaseModel):
    date: str
    slot_id: str

async def get_organization_from_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to get organization from API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    
    organization = get_organization_by_api_key(api_key)
    if not organization:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return organization

@router.post("/availability")
async def save_appointment_availability(
    request: AppointmentAvailabilityRequest,
    organization=Depends(get_organization_from_api_key)
):
    """Save or update appointment availability for a specific date"""
    org_id = organization["id"]
    
    try:
        # Validate date format
        try:
            parsed_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check if date is in the past
        if parsed_date < date.today():
            raise HTTPException(status_code=400, detail="Cannot set availability for past dates")
        
        # Validate time slots and convert to AM/PM format
        processed_time_slots = []
        for slot in request.time_slots:
            try:
                # Convert to 24-hour format for validation
                start_24 = convert_12_to_24_hour(slot.start_time)
                end_24 = convert_12_to_24_hour(slot.end_time)
                
                start_time = datetime.strptime(start_24, "%H:%M").time()
                end_time = datetime.strptime(end_24, "%H:%M").time()
                
                if start_time >= end_time:
                    raise HTTPException(status_code=400, detail=f"End time must be after start time for slot {slot.id}")
                
                # Convert to AM/PM format for storage
                start_ampm = convert_24_to_12_hour(start_24)
                end_ampm = convert_24_to_12_hour(end_24)
                
                processed_time_slots.append({
                    "id": slot.id,
                    "start_time": start_ampm,
                    "end_time": end_ampm
                })
                    
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid time format for slot {slot.id}. Use HH:MM or HH:MM AM/PM format")
        
        # Update or insert availability
        result = appointment_availability_collection.update_one(
            {
                "organization_id": org_id,
                "date": request.date
            },
            {
                "$set": {
                    "organization_id": org_id,
                    "date": request.date,
                    "time_slots": processed_time_slots,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return {
            "status": "success",
            "message": "Appointment availability saved successfully",
            "date": request.date,
            "time_slots_count": len(processed_time_slots)
        }
        
    except Exception as e:
        print(f"Error saving appointment availability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/availability/slot")
async def delete_time_slot(
    request: DeleteTimeSlotRequest,
    organization=Depends(get_organization_from_api_key)
):
    """Delete a specific time slot from a date"""
    org_id = organization["id"]
    
    try:
        # Validate date format
        try:
            datetime.strptime(request.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Find the availability document
        availability = appointment_availability_collection.find_one({
            "organization_id": org_id,
            "date": request.date
        })
        
        if not availability:
            raise HTTPException(status_code=404, detail="No availability found for the specified date")
        
        # Remove the specific time slot
        updated_slots = [
            slot for slot in availability.get("time_slots", [])
            if slot.get("id") != request.slot_id
        ]
        
        if len(updated_slots) == len(availability.get("time_slots", [])):
            raise HTTPException(status_code=404, detail="Time slot not found")
        
        # Update the document with the remaining slots
        if updated_slots:
            # Update with remaining slots
            appointment_availability_collection.update_one(
                {
                    "organization_id": org_id,
                    "date": request.date
                },
                {
                    "$set": {
                        "time_slots": updated_slots,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        else:
            # Delete the entire availability document if no slots remain
            appointment_availability_collection.delete_one({
                "organization_id": org_id,
                "date": request.date
            })
        
        return {
            "status": "success",
            "message": "Time slot deleted successfully",
            "remaining_slots": len(updated_slots)
        }
        
    except Exception as e:
        print(f"Error deleting time slot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/availability", response_model=List[AppointmentAvailabilityResponse])
async def get_appointment_availability(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    organization=Depends(get_organization_from_api_key)
):
    """Get appointment availability for an organization"""
    org_id = organization["id"]
    
    try:
        # Build query
        query = {"organization_id": org_id}
        
        # Add date range filter if provided
        if start_date or end_date:
            date_filter = {}
            if start_date:
                try:
                    datetime.strptime(start_date, "%Y-%m-%d")
                    date_filter["$gte"] = start_date
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
                    
            if end_date:
                try:
                    datetime.strptime(end_date, "%Y-%m-%d")
                    date_filter["$lte"] = end_date
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
                    
            if date_filter:
                query["date"] = date_filter
        
        # Get availabilities from database
        availabilities = list(appointment_availability_collection.find(
            query,
            {"_id": 0}  # Exclude MongoDB _id field
        ).sort("date", 1))
        
        # Convert to response format
        result = []
        for availability in availabilities:
            time_slots = [
                TimeSlot(
                    id=slot["id"],
                    start_time=slot["start_time"],
                    end_time=slot["end_time"]
                )
                for slot in availability.get("time_slots", [])
            ]
            
            result.append(AppointmentAvailabilityResponse(
                date=availability["date"],
                time_slots=time_slots
            ))
        
        return result
        
    except Exception as e:
        print(f"Error getting appointment availability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/availability/{date}")
async def delete_appointment_availability(
    date: str,
    organization=Depends(get_organization_from_api_key)
):
    """Delete appointment availability for a specific date"""
    org_id = organization["id"]
    
    try:
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Delete availability
        result = appointment_availability_collection.delete_one({
            "organization_id": org_id,
            "date": date
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No availability found for the specified date")
        
        return {
            "status": "success",
            "message": f"Appointment availability for {date} deleted successfully"
        }
        
    except Exception as e:
        print(f"Error deleting appointment availability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/availability/{date}", response_model=AppointmentAvailabilityResponse)
async def get_appointment_availability_by_date(
    date: str,
    organization=Depends(get_organization_from_api_key)
):
    """Get appointment availability for a specific date"""
    org_id = organization["id"]
    
    try:
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Get availability from database
        availability = appointment_availability_collection.find_one({
            "organization_id": org_id,
            "date": date
        }, {"_id": 0})
        
        if not availability:
            raise HTTPException(status_code=404, detail="No availability found for the specified date")
        
        # Convert to response format
        time_slots = [
            TimeSlot(
                id=slot["id"],
                start_time=slot["start_time"],
                end_time=slot["end_time"]
            )
            for slot in availability.get("time_slots", [])
        ]
        
        return AppointmentAvailabilityResponse(
            date=availability["date"],
            time_slots=time_slots
        )
        
    except Exception as e:
        print(f"Error getting appointment availability by date: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/availability/stats")
async def get_availability_stats(
    organization=Depends(get_organization_from_api_key)
):
    """Get statistics about appointment availability"""
    org_id = organization["id"]
    
    try:
        # Get total number of days with availability
        total_days = appointment_availability_collection.count_documents({
            "organization_id": org_id
        })
        
        # Get total number of time slots
        pipeline = [
            {"$match": {"organization_id": org_id}},
            {"$project": {"slot_count": {"$size": "$time_slots"}}},
            {"$group": {"_id": None, "total_slots": {"$sum": "$slot_count"}}}
        ]
        
        result = list(appointment_availability_collection.aggregate(pipeline))
        total_slots = result[0]["total_slots"] if result else 0
        
        # Get upcoming availability (future dates)
        today = date.today().strftime("%Y-%m-%d")
        upcoming_days = appointment_availability_collection.count_documents({
            "organization_id": org_id,
            "date": {"$gte": today}
        })
        
        return {
            "total_days_with_availability": total_days,
            "total_time_slots": total_slots,
            "upcoming_days_with_availability": upcoming_days,
            "organization_id": org_id
        }
        
    except Exception as e:
        print(f"Error getting availability stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 