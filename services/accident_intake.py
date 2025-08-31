#!/usr/bin/env python3
"""
Car Accident Intake Service for Carter Injury Law
Handles structured accident information collection with specific data extraction
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import pytz

class AccidentIntakeService:
    """Service for handling car accident intake conversations"""
    
    # Asia/Dhaka timezone
    DHAKA_TZ = pytz.timezone('Asia/Dhaka')
    
    # Today's date for relative date conversion
    TODAY = datetime.now(DHAKA_TZ).date()
    
    def __init__(self):
        self.intake_data = {
            "incident_date": None,
            "incident_time": None,
            "location": None,
            "crash_type": None,
            "vehicles_involved": None,
            "injuries": [],
            "medical_care_to_date": None,
            "police_present": None,
            "police_report_number": None,
            "photos_evidence": None,
            "witnesses": [],
            "client_insurer": None,
            "other_insurer": None,
            "adjuster_contacted": None,
            "client_name": None,
            "client_email": None,
            "client_phone": None
        }
        self.conversation_step = 0
        self.lead_capture_attempted = False
        
    def reset_intake(self):
        """Reset intake data for new conversation"""
        self.intake_data = {
            "incident_date": None,
            "incident_time": None,
            "location": None,
            "crash_type": None,
            "vehicles_involved": None,
            "injuries": [],
            "medical_care_to_date": None,
            "police_present": None,
            "police_report_number": None,
            "photos_evidence": None,
            "witnesses": [],
            "client_insurer": None,
            "other_insurer": None,
            "adjuster_contacted": None,
            "client_name": None,
            "client_email": None,
            "client_phone": None
        }
        self.conversation_step = 0
        self.lead_capture_attempted = False
    
    def convert_relative_date(self, date_text: str) -> Optional[str]:
        """Convert relative dates to absolute dates using Asia/Dhaka timezone"""
        date_text = date_text.lower().strip()
        
        # Today
        if date_text in ["today", "this morning", "this afternoon", "this evening"]:
            return self.TODAY.strftime("%Y-%m-%d")
        
        # Yesterday
        if date_text in ["yesterday", "last night"]:
            yesterday = self.TODAY - timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")
        
        # Days ago
        days_ago_match = re.search(r'(\d+)\s*days?\s*ago', date_text)
        if days_ago_match:
            days = int(days_ago_match.group(1))
            target_date = self.TODAY - timedelta(days=days)
            return target_date.strftime("%Y-%m-%d")
        
        # Specific date patterns
        date_patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})-(\d{1,2})-(\d{4})',  # MM-DD-YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_text)
            if match:
                if len(match.groups()) == 3:
                    if len(match.group(1)) == 4:  # YYYY-MM-DD
                        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                    else:  # MM/DD/YYYY or MM-DD-YYYY
                        return f"{match.group(3)}-{match.group(1).zfill(2)}-{match.group(2).zfill(2)}"
        
        return None
    
    def extract_time(self, time_text: str) -> Optional[str]:
        """Extract time from text and convert to 24-hour format"""
        time_text = time_text.lower().strip()
        
        # 24-hour format (check first to avoid conflicts)
        time_24_pattern = r'(\d{1,2}):(\d{2})(?!\s*(am|pm))'  # 14:30 (not 2:30 PM)
        time_24_match = re.search(time_24_pattern, time_text)
        if time_24_match:
            hour = int(time_24_match.group(1))
            minute = int(time_24_match.group(2))
            return f"{hour:02d}:{minute:02d}"
        
        # 12-hour format with AM/PM
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)',  # 2:30 PM
            r'(\d{1,2})\s*(am|pm)',  # 2 PM
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, time_text)
            if match:
                if len(match.groups()) == 3:  # 2:30 PM
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    period = match.group(3)
                    
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    return f"{hour:02d}:{minute:02d}"
                elif len(match.groups()) == 2:  # 2 PM
                    hour = int(match.group(1))
                    period = match.group(2)
                    
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    return f"{hour:02d}:00"
        
        return None
    
    def extract_location(self, location_text: str) -> str:
        """Extract and standardize location information"""
        location_text = location_text.strip()
        
        # Add Dhaka if not specified
        if 'dhaka' not in location_text.lower():
            location_text += ', Dhaka'
        
        return location_text
    
    def extract_crash_type(self, crash_text: str) -> str:
        """Extract crash type from description"""
        crash_text = crash_text.lower()
        
        crash_types = {
            'rear-end': ['rear end', 'rear-ended', 'rear ended', 'hit from behind', 'backed into'],
            'side impact': ['side impact', 't-bone', 't bone', 'side collision', 'broadside'],
            'head-on': ['head on', 'head-on', 'front to front'],
            'hit-and-run': ['hit and run', 'hit-and-run', 'fled the scene', 'driver left'],
            'sideswipe': ['sideswipe', 'side swipe', 'grazed'],
            'rollover': ['rollover', 'rolled over', 'flipped'],
            'rideshare passenger collision': ['rideshare', 'uber', 'lyft', 'passenger in'],
        }
        
        for crash_type, keywords in crash_types.items():
            if any(keyword in crash_text for keyword in keywords):
                return crash_type
        
        return 'other'
    
    def extract_vehicles_involved(self, vehicle_text: str) -> int:
        """Extract number of vehicles involved"""
        vehicle_text = vehicle_text.lower()
        
        # Look for specific numbers
        number_match = re.search(r'(\d+)\s*(?:cars?|vehicles?)', vehicle_text)
        if number_match:
            return int(number_match.group(1))
        
        # Default to 2 for most accidents
        return 2
    
    def extract_injuries(self, injury_text: str) -> List[str]:
        """Extract injuries from text"""
        injury_text = injury_text.lower()
        injuries = []
        
        injury_keywords = [
            'neck pain', 'neck stiffness', 'back pain', 'headache', 'shoulder pain',
            'knee pain', 'wrist pain', 'chest pain', 'numbness', 'dizziness',
            'soreness', 'bruising', 'cuts', 'scrapes', 'whiplash'
        ]
        
        for injury in injury_keywords:
            if injury in injury_text:
                injuries.append(injury)
        
        # Add general soreness if mentioned
        if 'sore' in injury_text or 'soreness' in injury_text:
            injuries.append('general soreness')
        
        return injuries
    
    def extract_contact_info(self, contact_text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract name, email, and phone from contact information"""
        name = None
        email = None
        phone = None
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, contact_text)
        if email_match:
            email = email_match.group(0)
        
        # Extract phone (Bangladesh format)
        phone_patterns = [
            r'(\+880|880)?\s*(\d{11})',  # +880 01711000222
            r'(\d{4,5})-(\d{3})-(\d{6})',  # 0171-100-0222 or 01711-000-222
            r'(\d{11})',  # 01711000222
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, contact_text)
            if phone_match:
                if len(phone_match.groups()) == 2:  # +880 01711000222
                    phone = phone_match.group(2)
                elif len(phone_match.groups()) == 3:  # 0171-100-0222
                    phone = phone_match.group(1) + phone_match.group(2) + phone_match.group(3)
                else:  # 01711000222
                    phone = phone_match.group(1)
                break
        
        # Extract name (everything before email/phone, excluding common words)
        name_text = contact_text
        
        # Remove email and phone from text for name extraction
        if email:
            name_text = name_text.replace(email, '')
        if phone:
            # Remove the phone number pattern from the text
            for pattern in phone_patterns:
                name_text = re.sub(pattern, '', name_text)
            # Also remove any remaining phone-like patterns
            name_text = re.sub(r'\d{4}-\d{3}-\d{6}', '', name_text)  # 0171-100-0222
            name_text = re.sub(r'\d{11}', '', name_text)  # 01711000222
        
        # Clean up name
        name_text = re.sub(r'\b(?:i\'m|i am|my name is|call me|name is)\b', '', name_text, flags=re.IGNORECASE)
        name_text = re.sub(r'[^\w\s]', '', name_text).strip()
        
        if len(name_text) > 1:
            name = name_text
        
        return name, email, phone
    
    def process_message(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Process user message and return appropriate response"""
        user_message = user_message.strip()
        
        # Check for safety first
        if self.conversation_step == 0:
            return self._handle_safety_check(user_message, user_data)
        
        # Check for red-flag symptoms
        if self._has_red_flag_symptoms(user_message):
            return self._handle_red_flags(user_message, user_data)
        
        # Handle recorded statement requests
        if self._is_recorded_statement_request(user_message):
            return self._handle_recorded_statement(user_message, user_data)
        
        # Continue with intake flow
        return self._continue_intake(user_message, user_data)
    
    def _handle_safety_check(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle initial safety check"""
        if any(word in user_message.lower() for word in ['safe', 'okay', 'fine', 'alright']):
            self.conversation_step = 1
            return ("To confirm, was the crash on " + self.TODAY.strftime("%B %d, %Y") + 
                   "? What time and where (street/city/state)?", user_data)
        else:
            return ("I'm sorry you're going through this—are you safe right now or need urgent medical help?", user_data)
    
    def _has_red_flag_symptoms(self, message: str) -> bool:
        """Check for red-flag symptoms"""
        red_flags = [
            'severe headache', 'vision changes', 'chest pain', 'numbness',
            'dizziness', 'confusion', 'loss of consciousness', 'difficulty breathing'
        ]
        return any(flag in message.lower() for flag in red_flags)
    
    def _handle_red_flags(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle red-flag symptoms"""
        return ("Please seek immediate medical care for those symptoms. Your health comes first. "
                "Once you're safe, we can continue with the intake process.", user_data)
    
    def _is_recorded_statement_request(self, message: str) -> bool:
        """Check if user mentions recorded statement requests"""
        keywords = ['recorded statement', 'insurance wants', 'adjuster called', 'statement request']
        return any(keyword in message.lower() for keyword in keywords)
    
    def _handle_recorded_statement(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle recorded statement requests"""
        self.intake_data["adjuster_contacted"] = True
        return ("Thanks for telling me. For now, please avoid recorded statements or broad medical releases "
                "until our attorney reviews your case. When was the crash and where?", user_data)
    
    def _continue_intake(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Continue with structured intake flow"""
        
        if self.conversation_step == 1:  # Date/time/location
            return self._handle_date_time_location(user_message, user_data)
        elif self.conversation_step == 2:  # How it happened
            return self._handle_crash_details(user_message, user_data)
        elif self.conversation_step == 3:  # Injuries/medical care
            return self._handle_injuries_medical(user_message, user_data)
        elif self.conversation_step == 4:  # Police/photos/witnesses
            return self._handle_police_evidence(user_message, user_data)
        elif self.conversation_step == 5:  # Insurance
            return self._handle_insurance(user_message, user_data)
        elif self.conversation_step == 6:  # Lead capture
            return self._handle_lead_capture(user_message, user_data)
        else:
            return self._handle_completion(user_message, user_data)
    
    def _handle_date_time_location(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle date, time, and location extraction"""
        # Extract date
        date_match = re.search(r'(yesterday|today|\d+ days? ago|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{1,2}-\d{1,2})', user_message.lower())
        if date_match:
            self.intake_data["incident_date"] = self.convert_relative_date(date_match.group(1))
        
        # Extract time
        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))', user_message.lower())
        if time_match:
            self.intake_data["incident_time"] = self.extract_time(time_match.group(1))
        
        # Extract location
        location_keywords = ['at', 'near', 'in', 'on', 'around']
        words = user_message.split()
        location_start = None
        
        for i, word in enumerate(words):
            if word.lower() in location_keywords:
                location_start = i + 1
                break
        
        if location_start:
            location_text = ' '.join(words[location_start:])
            self.intake_data["location"] = self.extract_location(location_text)
        
        self.conversation_step = 2
        return ("Thanks. How did it happen and how many vehicles were involved? Any injuries or doctor visit yet?", user_data)
    
    def _handle_crash_details(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle crash type and vehicle count"""
        self.intake_data["crash_type"] = self.extract_crash_type(user_message)
        self.intake_data["vehicles_involved"] = self.extract_vehicles_involved(user_message)
        
        self.conversation_step = 3
        return ("Understood. Any symptoms today and did you see a doctor yet? Did police respond or CCTV nearby?", user_data)
    
    def _handle_injuries_medical(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle injuries and medical care"""
        self.intake_data["injuries"] = self.extract_injuries(user_message)
        
        if any(word in user_message.lower() for word in ['doctor', 'er', 'hospital', 'clinic']):
            self.intake_data["medical_care_to_date"] = "medical care received"
        else:
            self.intake_data["medical_care_to_date"] = "none"
        
        self.conversation_step = 4
        return ("Noted. Did police come or a report get filed? Any photos or witnesses?", user_data)
    
    def _handle_police_evidence(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle police presence and evidence"""
        if any(word in user_message.lower() for word in ['police', 'officer', 'report']):
            self.intake_data["police_present"] = True
        else:
            self.intake_data["police_present"] = False
        
        if 'photo' in user_message.lower():
            self.intake_data["photos_evidence"] = True
        
        if 'witness' in user_message.lower():
            self.intake_data["witnesses"] = ["witnesses present"]
        
        self.conversation_step = 5
        return ("Got it. Who is your insurer and do you know the other driver's? Also, may I have your full name and best email so our legal team can follow up?", user_data)
    
    def _handle_insurance(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle insurance information"""
        # Extract client insurer
        if 'my insurer' in user_message.lower() or 'i have' in user_message.lower():
            # Look for insurance company names
            insurers = ['metlife', 'city general', 'eastern insurance', 'pragati', 'sena kalyan']
            for insurer in insurers:
                if insurer in user_message.lower():
                    self.intake_data["client_insurer"] = insurer.title()
                    break
        
        # Extract other driver's insurer
        if 'other driver' in user_message.lower() or 'other' in user_message.lower():
            if 'unknown' in user_message.lower():
                self.intake_data["other_insurer"] = "unknown"
            elif 'uninsured' in user_message.lower():
                self.intake_data["other_insurer"] = "uninsured at-fault driver"
            else:
                insurers = ['metlife', 'city general', 'eastern insurance', 'pragati', 'sena kalyan']
                for insurer in insurers:
                    if insurer in user_message.lower():
                        self.intake_data["other_insurer"] = insurer.title()
                        break
        
        self.conversation_step = 6
        return ("Could I have your full name and best email (or phone) so our legal team can follow up?", user_data)
    
    def _handle_lead_capture(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle lead capture (name, email, phone)"""
        name, email, phone = self.extract_contact_info(user_message)
        
        if name:
            self.intake_data["client_name"] = name
        if email:
            self.intake_data["client_email"] = email
        if phone:
            self.intake_data["client_phone"] = phone
        
        self.lead_capture_attempted = True
        
        if name or email or phone:
            self.conversation_step = 7
            return ("Thank you. I've captured your information. Our legal team will review your case and contact you soon. "
                    "Please consider seeking medical evaluation to document any symptoms.", user_data)
        else:
            self.conversation_step = 7
            return ("No worries, we can collect that later. Who is your auto insurer? Is the car drivable?", user_data)
    
    def _handle_completion(self, user_message: str, user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle completion of intake"""
        # Update user_data with intake information
        user_data["accident_intake"] = self.intake_data
        user_data["intake_completed"] = True
        
        return ("Thank you for providing this information. Our team will review your case and contact you soon. "
                "Remember to seek medical care if you experience any symptoms, and avoid recorded statements until we advise.", user_data)
    
    def get_intake_data(self) -> Dict[str, Any]:
        """Get the collected intake data"""
        return self.intake_data.copy()
    
    def is_intake_complete(self) -> bool:
        """Check if intake is complete"""
        return self.conversation_step >= 7

# Global instance for managing intake sessions
intake_sessions = {}

def get_intake_service(session_id: str) -> AccidentIntakeService:
    """Get or create intake service for session"""
    if session_id not in intake_sessions:
        intake_sessions[session_id] = AccidentIntakeService()
    return intake_sessions[session_id]

def reset_intake_session(session_id: str):
    """Reset intake session"""
    if session_id in intake_sessions:
        intake_sessions[session_id].reset_intake()
