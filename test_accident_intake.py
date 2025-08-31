#!/usr/bin/env python3
"""
Test script for Car Accident Intake System
Tests the demo conversations provided by the user
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.accident_intake import AccidentIntakeService

def test_demo_1_rear_end():
    """Test Demo 1 - Rear-end yesterday (user gives name + email)"""
    print("=== Demo 1: Rear-end yesterday ===")
    
    intake = AccidentIntakeService()
    user_data = {}
    
    # User: I had a car accident yesterday.
    response, user_data = intake.process_message("I had a car accident yesterday.", user_data)
    print(f"Bot: {response}")
    
    # User: I'm safe.
    response, user_data = intake.process_message("I'm safe.", user_data)
    print(f"Bot: {response}")
    
    # User: Yes, around 6:15 PM at Mirpur Rd & Dhanmondi 27, Dhaka.
    response, user_data = intake.process_message("Yes, around 6:15 PM at Mirpur Rd & Dhanmondi 27, Dhaka.", user_data)
    print(f"Bot: {response}")
    
    # User: I was rear-ended at a light, two cars total. Neck stiffness; no doctor yet.
    response, user_data = intake.process_message("I was rear-ended at a light, two cars total. Neck stiffness; no doctor yet.", user_data)
    print(f"Bot: {response}")
    
    # User: No police; I took photos; no witnesses.
    response, user_data = intake.process_message("No police; I took photos; no witnesses.", user_data)
    print(f"Bot: {response}")
    
    # User: My insurer is MetLife; other driver unknown. I'm Samir Hasan, samir@exmail.com
    response, user_data = intake.process_message("My insurer is MetLife; other driver unknown. I'm Samir Hasan, samir@exmail.com", user_data)
    print(f"Bot: {response}")
    
    print(f"\nExtracted Data: {intake.get_intake_data()}")
    print("=" * 50)

def test_demo_2_hit_and_run():
    """Test Demo 2 - Hit-and-run last night (user skips lead capture)"""
    print("=== Demo 2: Hit-and-run last night ===")
    
    intake = AccidentIntakeService()
    user_data = {}
    
    # User: It was a hit-and-run last night near Banani.
    response, user_data = intake.process_message("It was a hit-and-run last night near Banani.", user_data)
    print(f"Bot: {response}")
    
    # User: I'm okay.
    response, user_data = intake.process_message("I'm okay.", user_data)
    print(f"Bot: {response}")
    
    # User: Around 11:30 PM, Banani 11 Rd & Kemal Ataturk Ave.
    response, user_data = intake.process_message("Around 11:30 PM, Banani 11 Rd & Kemal Ataturk Ave.", user_data)
    print(f"Bot: {response}")
    
    # User: Headache and shoulder pain; no doctor yet. Police report filed; lots of shop cameras.
    response, user_data = intake.process_message("Headache and shoulder pain; no doctor yet. Police report filed; lots of shop cameras.", user_data)
    print(f"Bot: {response}")
    
    # User: (no reply) - simulate no response
    response, user_data = intake.process_message("", user_data)
    print(f"Bot: {response}")
    
    # User: City General; car is drivable.
    response, user_data = intake.process_message("City General; car is drivable.", user_data)
    print(f"Bot: {response}")
    
    print(f"\nExtracted Data: {intake.get_intake_data()}")
    print("=" * 50)

def test_demo_3_recorded_statement():
    """Test Demo 3 - Recorded statement request (bot protects claim)"""
    print("=== Demo 3: Recorded statement request ===")
    
    intake = AccidentIntakeService()
    user_data = {}
    
    # User: The other driver's insurer wants a recorded statement.
    response, user_data = intake.process_message("The other driver's insurer wants a recorded statement.", user_data)
    print(f"Bot: {response}")
    
    # User: Two days ago in Gulshan 2 circle.
    response, user_data = intake.process_message("Two days ago in Gulshan 2 circle.", user_data)
    print(f"Bot: {response}")
    
    # User: 4:10 PM, side impact at the roundabout. Back pain; went to ER.
    response, user_data = intake.process_message("4:10 PM, side impact at the roundabout. Back pain; went to ER.", user_data)
    print(f"Bot: {response}")
    
    # User: Yes, police came; I have the number at home.
    response, user_data = intake.process_message("Yes, police came; I have the number at home.", user_data)
    print(f"Bot: {response}")
    
    # User: It was Eastern Insurance. I'm Nabila K, nabila.k@email.com
    response, user_data = intake.process_message("It was Eastern Insurance. I'm Nabila K, nabila.k@email.com", user_data)
    print(f"Bot: {response}")
    
    print(f"\nExtracted Data: {intake.get_intake_data()}")
    print("=" * 50)

def test_demo_4_rideshare():
    """Test Demo 4 - Rideshare passenger (bot asks once; user gives phone only)"""
    print("=== Demo 4: Rideshare passenger ===")
    
    intake = AccidentIntakeService()
    user_data = {}
    
    # User: I was a passenger in a rideshare when we got hit.
    response, user_data = intake.process_message("I was a passenger in a rideshare when we got hit.", user_data)
    print(f"Bot: {response}")
    
    # User: I'm safe.
    response, user_data = intake.process_message("I'm safe.", user_data)
    print(f"Bot: {response}")
    
    # User: Today at 9:20 AM, Progoti Sharani near Notun Bazar, Dhaka.
    response, user_data = intake.process_message("Today at 9:20 AM, Progoti Sharani near Notun Bazar, Dhaka.", user_data)
    print(f"Bot: {response}")
    
    # User: Knee pain; no doctor yet; police came.
    response, user_data = intake.process_message("Knee pain; no doctor yet; police came.", user_data)
    print(f"Bot: {response}")
    
    # User: Uber ride; not sure about insurers. I'm Rafiul; call me at 01711-000222.
    response, user_data = intake.process_message("Uber ride; not sure about insurers. I'm Rafiul; call me at 01711-000222.", user_data)
    print(f"Bot: {response}")
    
    print(f"\nExtracted Data: {intake.get_intake_data()}")
    print("=" * 50)

def test_demo_5_minor_damage():
    """Test Demo 5 - Minor property damage, symptoms next day (lead skipped)"""
    print("=== Demo 5: Minor property damage ===")
    
    intake = AccidentIntakeService()
    user_data = {}
    
    # User: Small fender-bender yesterday in Uttara, but I'm sore today.
    response, user_data = intake.process_message("Small fender-bender yesterday in Uttara, but I'm sore today.", user_data)
    print(f"Bot: {response}")
    
    # User: Yes.
    response, user_data = intake.process_message("Yes.", user_data)
    print(f"Bot: {response}")
    
    # User: 2:45 PM near Sector 7 Park.
    response, user_data = intake.process_message("2:45 PM near Sector 7 Park.", user_data)
    print(f"Bot: {response}")
    
    # User: I was sideswiped while merging; two cars; I took photos.
    response, user_data = intake.process_message("I was sideswiped while merging; two cars; I took photos.", user_data)
    print(f"Bot: {response}")
    
    # User: (no reply) - simulate no response
    response, user_data = intake.process_message("", user_data)
    print(f"Bot: {response}")
    
    # User: No police.
    response, user_data = intake.process_message("No police.", user_data)
    print(f"Bot: {response}")
    
    print(f"\nExtracted Data: {intake.get_intake_data()}")
    print("=" * 50)

def test_demo_6_uninsured():
    """Test Demo 6 - Uninsured other driver (user gives name only)"""
    print("=== Demo 6: Uninsured other driver ===")
    
    intake = AccidentIntakeService()
    user_data = {}
    
    # User: The other driver had no insurance.
    response, user_data = intake.process_message("The other driver had no insurance.", user_data)
    print(f"Bot: {response}")
    
    # User: I'm safe.
    response, user_data = intake.process_message("I'm safe.", user_data)
    print(f"Bot: {response}")
    
    # User: This morning 8:10 AM, Airport Rd near Kurmitola; head-on at low speed.
    response, user_data = intake.process_message("This morning 8:10 AM, Airport Rd near Kurmitola; head-on at low speed.", user_data)
    print(f"Bot: {response}")
    
    # User: Wrist pain; no doctor yet.
    response, user_data = intake.process_message("Wrist pain; no doctor yet.", user_data)
    print(f"Bot: {response}")
    
    # User: Police came; I have photos. I think I have UM. Name is Mahin Chowdhury.
    response, user_data = intake.process_message("Police came; I have photos. I think I have UM. Name is Mahin Chowdhury.", user_data)
    print(f"Bot: {response}")
    
    print(f"\nExtracted Data: {intake.get_intake_data()}")
    print("=" * 50)

def test_date_conversion():
    """Test date conversion functionality"""
    print("=== Testing Date Conversion ===")
    
    intake = AccidentIntakeService()
    
    test_cases = [
        ("yesterday", "2025-08-30"),
        ("today", "2025-08-31"),
        ("2 days ago", "2025-08-29"),
        ("last night", "2025-08-30"),
        ("this morning", "2025-08-31"),
    ]
    
    for input_date, expected in test_cases:
        result = intake.convert_relative_date(input_date)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{input_date}' -> Expected: {expected}, Got: {result}")

def test_time_extraction():
    """Test time extraction functionality"""
    print("\n=== Testing Time Extraction ===")
    
    intake = AccidentIntakeService()
    
    test_cases = [
        ("6:15 PM", "18:15"),
        ("2:30 AM", "02:30"),
        ("14:30", "14:30"),
        ("9:20 AM", "09:20"),
        ("11:30 PM", "23:30"),
    ]
    
    for input_time, expected in test_cases:
        result = intake.extract_time(input_time)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{input_time}' -> Expected: {expected}, Got: {result}")

def test_contact_extraction():
    """Test contact information extraction"""
    print("\n=== Testing Contact Extraction ===")
    
    intake = AccidentIntakeService()
    
    test_cases = [
        ("I'm Samir Hasan, samir@exmail.com", ("Samir Hasan", "samir@exmail.com", None)),
        ("I'm Rafiul; call me at 01711-000222", ("Rafiul", None, "01711000222")),
        ("Name is Mahin Chowdhury", ("Mahin Chowdhury", None, None)),
        ("I'm Nabila K, nabila.k@email.com", ("Nabila K", "nabila.k@email.com", None)),
    ]
    
    for input_contact, expected in test_cases:
        result = intake.extract_contact_info(input_contact)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{input_contact}' -> Expected: {expected}, Got: {result}")

if __name__ == "__main__":
    print("Testing Car Accident Intake System")
    print("=" * 50)
    
    test_date_conversion()
    test_time_extraction()
    test_contact_extraction()
    
    print("\n" + "=" * 50)
    print("Testing Demo Conversations")
    print("=" * 50)
    
    test_demo_1_rear_end()
    test_demo_2_hit_and_run()
    test_demo_3_recorded_statement()
    test_demo_4_rideshare()
    test_demo_5_minor_damage()
    test_demo_6_uninsured()
    
    print("\n" + "=" * 50)
    print("Test completed!")
