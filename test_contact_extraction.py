#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.accident_intake import AccidentIntakeService

def test_contact_extraction():
    """Test contact extraction specifically"""
    intake = AccidentIntakeService()
    
    test_cases = [
        ("I'm Samir Hasan, samir@exmail.com", ("Samir Hasan", "samir@exmail.com", None)),
        ("I'm Rafiul; call me at 01711-000222", ("Rafiul", None, "01711000222")),
        ("Name is Mahin Chowdhury", ("Mahin Chowdhury", None, None)),
        ("I'm Nabila K, nabila.k@email.com", ("Nabila K", "nabila.k@email.com", None)),
    ]
    
    print("Testing Contact Extraction")
    print("=" * 50)
    
    for test_input, expected in test_cases:
        result = intake.extract_contact_info(test_input)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{test_input}' -> Expected: {expected}, Got: {result}")

if __name__ == "__main__":
    test_contact_extraction()
