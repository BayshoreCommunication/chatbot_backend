@echo off
echo Setting up AI Chatbot environment...

REM Create a virtual environment
python -m venv venv

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Install requirements
pip install -r requirements.txt

echo Environment setup complete!
echo To run the server: uvicorn main:app --reload
echo.
echo To activate the environment in the future, run: venv\Scripts\activate.bat 