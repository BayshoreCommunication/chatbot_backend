import os
import subprocess
import time

# Set dimension for all tests
os.environ["PINECONE_DIMENSION"] = "1024"

def run_test(script_name, description):
    """Run a test script and display its results"""
    print("\n" + "=" * 80)
    print(f"Running test: {description}")
    print("=" * 80 + "\n")
    
    result = subprocess.run(["python", script_name], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("ERRORS:")
        print(result.stderr)
    
    print("\n" + "-" * 80)
    print(f"Test completed with exit code: {result.returncode}")
    print("-" * 80 + "\n")
    
    # Short pause between tests
    time.sleep(1)

def main():
    """Run all vector store multi-tenancy tests"""
    print("Running all vector store multi-tenancy tests...\n")
    
    # Make sure the dimension mismatch is fixed first
    run_test("fix_dimension_mismatch.py", "Fix dimension mismatch")
    
    # Run tests in order of increasing complexity
    run_test("test_vectorstore_directly.py", "Direct vector store test")
    run_test("test_organization_vectorstore_directly.py", "Organization vector store test")
    
    # Only run this if the server is running
    server_running = True
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/docs")
        if response.status_code != 200:
            server_running = False
    except:
        server_running = False
    
    if server_running:
        run_test("test_document_upload.py", "Document upload test")
        run_test("test_full_api_chain.py", "Full API chain test")
    else:
        print("\nSERVER NOT RUNNING - Skipping API tests")
        print("Run 'uvicorn main:app --reload' to start the server")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main() 