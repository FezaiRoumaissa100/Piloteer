import os
import pathlib
import chromadb
from google import genai
from dotenv import load_dotenv

load_dotenv()

_RAG_DB_PATH = str(pathlib.Path(__file__).resolve().parent.parent.parent.parent / "rag_db")
_DEFAULT_COLLECTION = os.getenv("RAG_COLLECTION", "saas_docs")
_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

_embd_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_chroma_client = chromadb.PersistentClient(path=_RAG_DB_PATH)

def embed_query(text: str) -> list[float]:
    result = _embd_client.models.embed_content(
        model=_EMBEDDING_MODEL,
        contents=text
    )
    return result.embeddings[0].values

def get_saas_context(query: str, collection_name: str = _DEFAULT_COLLECTION, n_results: int = 3) -> str:
    try:
        collection = _chroma_client.get_collection(collection_name)
    except Exception:
        print("[RAG] Warning: ChromaDB collection not found")
        return ""

    try:
        query_vector = embed_query(query)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=n_results
        )

        if not results or not results["documents"] or not results["documents"][0]:
            return ""

        context_blocks = []
        for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
            source = metadata.get("source", "Unknown Source")
            context_blocks.append(f"[Source: {source}]\n{doc}")

        return "\n\n---\n\n".join(context_blocks)

    except Exception as e:
        print(f"[RAG] Error during retrieval: {e}")
        return ""
