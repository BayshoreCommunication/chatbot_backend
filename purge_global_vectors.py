from dotenv import load_dotenv
import os
from pinecone import Pinecone
import time

# Load environment variables
load_dotenv()

def purge_global_vectors():
    """Purge all vectors from the global namespace (no namespace) in Pinecone"""
    print("Initializing Pinecone connection...")
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX", "bayshoreai")
    
    # Connect to the index
    try:
        print(f"Connecting to index: {index_name}")
        index = pc.Index(index_name)
        
        # Get stats before deletion
        stats_before = index.describe_index_stats()
        total_vectors_before = stats_before.total_vector_count
        global_vectors_before = stats_before.namespaces.get("", {}).vector_count if hasattr(stats_before.namespaces.get("", {}), "vector_count") else 0
        
        print(f"Total vectors before: {total_vectors_before}")
        print(f"Global namespace vectors before: {global_vectors_before}")
        
        # List all namespaces
        print("\nCurrent namespaces:")
        for namespace, details in stats_before.namespaces.items():
            ns_name = namespace if namespace else "global (default)"
            vector_count = details.vector_count if hasattr(details, "vector_count") else 0
            print(f"  - {ns_name}: {vector_count} vectors")
        
        # Confirm deletion
        confirm = input("\nAre you sure you want to delete ALL vectors in the global namespace? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            return
        
        # Delete all vectors in the global namespace (empty string namespace)
        print("\nDeleting all vectors in the global namespace...")
        index.delete(delete_all=True, namespace="")
        
        # Wait a moment for deletion to complete
        time.sleep(3)
        
        # Get stats after deletion
        stats_after = index.describe_index_stats()
        total_vectors_after = stats_after.total_vector_count
        global_vectors_after = stats_after.namespaces.get("", {}).vector_count if hasattr(stats_after.namespaces.get("", {}), "vector_count") else 0
        
        print(f"Total vectors after: {total_vectors_after}")
        print(f"Global namespace vectors after: {global_vectors_after}")
        print(f"Deleted approximately {total_vectors_before - total_vectors_after} vectors")
        
        # List all namespaces after deletion
        print("\nRemaining namespaces:")
        for namespace, details in stats_after.namespaces.items():
            ns_name = namespace if namespace else "global (default)"
            vector_count = details.vector_count if hasattr(details, "vector_count") else 0
            print(f"  - {ns_name}: {vector_count} vectors")
        
        print("\nPurge completed successfully.")
        print("Organization-specific namespaces were preserved.")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    purge_global_vectors() 