import os
import pathlib
import chromadb
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from langchain_text_splitters import RecursiveCharacterTextSplitter
from google import genai

load_dotenv()

_RAG_DB_PATH = str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "rag_db")
_DEFAULT_COLLECTION = os.getenv("RAG_COLLECTION", "saas_docs")
_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

_CONTENT_SELECTORS = [
    "article",
    "[role='article']",
    ".prose",
    "[class*='prose']",
    "[class*='content']",
    "[class*='article']",
    "[role='main']",
    "main",
    "body",
]

_MIN_LINE_LENGTH = 60

def _filter_navigation_text(text: str) -> str:
    meaningful_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "" or len(stripped) >= _MIN_LINE_LENGTH:
            meaningful_lines.append(line)

    result = "\n".join(meaningful_lines)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result.strip()

def scrape_doc_page(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")

        text = ""
        for selector in _CONTENT_SELECTORS:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0:
                    candidate = locator.inner_text(timeout=2000).strip()
                    candidate = _filter_navigation_text(candidate)
                    if len(candidate) > 150:
                        text = candidate
                        break
            except Exception:
                continue

        if not text:
            print("Warning: No content found ")

        browser.close()
        return text

def embed_text(text: str) -> list[float]:
    result = client.models.embed_content(
        model=_EMBEDDING_MODEL,
        contents=text
    )
    return result.embeddings[0].values

def ingest_url(url: str, collection_name: str = _DEFAULT_COLLECTION):
    raw_text = scrape_doc_page(url)
    if not raw_text.strip():
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50
    )
    chunks = splitter.split_text(raw_text)

    if not chunks:
        return

    
    vectors = [embed_text(chunk) for chunk in chunks]
    db_client = chromadb.PersistentClient(path=_RAG_DB_PATH)
    collection = db_client.get_or_create_collection(collection_name)

    try:
        existing = collection.get(where={"source": url})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
           
    except Exception:
        pass

    safe_url = (
        url.replace("https://", "")
           .replace("http://", "")
           .replace("/", "_")
           .replace(".", "_")
    )
    ids = [f"{safe_url}_chunk_{i}" for i in range(len(chunks))]

    collection.add(
        documents=chunks,
        embeddings=vectors,
        ids=ids,
        metadatas=[{"source": url} for _ in chunks]
    )
   


