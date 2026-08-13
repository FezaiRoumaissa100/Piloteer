"""
security/embedder.py
Self-contained embedding + ChromaDB client for the security module.
Does NOT import anything from utils/rag — fully independent.
"""
import os
import time
import pathlib
import chromadb
from google import genai
from dotenv import load_dotenv

load_dotenv()


_DB_PATH         = str(pathlib.Path(__file__).resolve().parent.parent.parent / "rag_db")
_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
_COLLECTION_NAME = "security_blacklist"

_embd_client   = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_chroma_client = chromadb.PersistentClient(path=_DB_PATH)


def get_security_collection():
    return _chroma_client.get_or_create_collection(_COLLECTION_NAME)


def embed_text(text: str) -> list[float]:
    
    for attempt in range(1, 4):
        try:
            result = _embd_client.models.embed_content(
                model=_EMBEDDING_MODEL,
                contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            if attempt == 3:
                raise e
            time.sleep(1)
    raise RuntimeError("[Security] Failed to generate embedding after 3 attempts.")
