"""
OrangeHRM Documentation Ingestion and Cleanup.

This script cleans up old unused collections (GitLab, Forum) from ChromaDB,
and ingests basic documentation for the OrangeHRM SaaS Demo.
"""
import sys
import pathlib
import chromadb
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

from utils.rag.ingest import ingest_url

ORANGEHRM_KNOWLEDGE = """
# OrangeHRM SaaS User Guide

## Authentication
To access the OrangeHRM demo system, use the following default credentials:
- Username: Admin
- Password: admin123

## Main Navigation (Sidebar)
The main navigation is located on the left sidebar and contains several modules:
- **Admin**: Used for User Management (viewing system users), Job titles, Pay Grades, and Organization structure.
- **PIM** (Personal Information Management): The core HR module. Used to manage employee records, add new employees ("Add Employee"), and view employee lists.
- **Leave**: Used to manage time off, view Leave Lists, and assign leave.
- **Time**: For timesheets and attendance tracking.
- **Recruitment**: For managing job candidates and vacancies.
- **My Info**: To view your personal employee profile.
- **Dashboard**: The home screen with quick widgets.

## Common Actions
- **Add a New Employee**: Navigate to the PIM module, then click on the "Add Employee" tab in the top navigation bar. You must enter a First Name and Last Name.
- **Search for a User**: Navigate to the Admin module. Under User Management, you can filter by Username, User Role (e.g., Admin or ESS), Employee Name, or Status.
- **Approve Leave**: Navigate to the Leave module, click on "Leave List", filter by the desired date range, and click "Approve" on pending requests.
"""

def mock_scrape(url: str) -> str:
    return ORANGEHRM_KNOWLEDGE

def cleanup_old_collections():
    load_dotenv()
    db_path = str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "rag_db")
    client = chromadb.PersistentClient(path=db_path)
    
    for coll_name in ["forum_docs", "gitlab_docs"]:
        try:
            client.delete_collection(coll_name)
            print(f"[Cleanup] Deleted old collection: {coll_name}")
        except Exception:
            pass

def main():
    cleanup_old_collections()
    
    print(f"[Ingest] Starting OrangeHRM documentation ingestion")
    import utils.rag.ingest as ingest_module
    original_scrape = ingest_module.scrape_doc_page
    
    try:
        # Override the scraper to return our markdown knowledge base
        ingest_module.scrape_doc_page = mock_scrape
        ingest_module.ingest_url("https://opensource-demo.orangehrmlive.com/docs", collection_name="orangehrm_docs")
        print(f"[Ingest] Successfully ingested OrangeHRM knowledge base into 'orangehrm_docs'")
    except Exception as e:
        print(f"[Ingest] Failed: {e}")
    finally:
        ingest_module.scrape_doc_page = original_scrape

if __name__ == "__main__":
    main()
