import os
import sys
import fastapi
import uvicorn
import langchain
import openai
import pinecone
import pymongo
from dotenv import load_dotenv

print("Python version:", sys.version)
print("All imports successful!")

# Print installed packages
import pkg_resources
print("\nInstalled packages:")
for pkg in pkg_resources.working_set:
    print(f"{pkg.key}=={pkg.version}") 