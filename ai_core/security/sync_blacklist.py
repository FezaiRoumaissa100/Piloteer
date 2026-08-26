"""
security/sync_blacklist.py
One-shot script: populates the security_blacklist ChromaDB collection
from the DANGEROUS_INTENTIONS list in blacklist.py.

Run once (or after updating blacklist.py):
    python src/security/sync_blacklist.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from security.embedder import get_security_collection, embed_text
from security.blacklist import DANGEROUS_INTENTIONS


def sync():
    collection = get_security_collection()
    print(f"[Security Sync] Syncing {len(DANGEROUS_INTENTIONS)} intentions...")

    for i, intention in enumerate(DANGEROUS_INTENTIONS):
        vector = embed_text(intention)
        collection.upsert(
            ids=[f"risk_{i}"],
            embeddings=[vector],
            documents=[intention],
            metadatas=[{"category": "dangerous_intention", "index": i}]
        )
        print(f"  [{i+1}/{len(DANGEROUS_INTENTIONS)}] ✓ {intention[:60]}...")

    print(f"\n[Security Sync] Done. Collection '{collection.name}' has {collection.count()} entries.")


if __name__ == "__main__":
    sync()
