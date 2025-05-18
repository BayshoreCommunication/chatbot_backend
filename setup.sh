#!/bin/bash
echo "Setting up AI Chatbot environment..."

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

echo "Environment setup complete!"
echo "To run the server: uvicorn main:app --reload"
echo ""
echo "To activate the environment in the future, run: source venv/bin/activate" 