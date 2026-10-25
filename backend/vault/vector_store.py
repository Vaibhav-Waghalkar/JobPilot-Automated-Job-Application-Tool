import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.config import settings

_chroma_client = None
_collection = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=str(settings.data_path / "chroma_db"),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _chroma_client

def get_vault_collection():
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name="jobpilot_vault",
            metadata={"description": "Authoritative vault facts for job applications"}
        )
    return _collection

def upsert_vault_fact_embedding(fact_id: str, content: str, metadata: dict):
    collection = get_vault_collection()
    # Flatten or clean metadata for Chroma compatibility (strings, ints, floats, bools)
    clean_meta = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)):
            clean_meta[k] = v
        else:
            clean_meta[k] = str(v)
            
    collection.upsert(
        ids=[fact_id],
        documents=[content],
        metadatas=[clean_meta]
    )

def delete_vault_fact_embedding(fact_id: str):
    collection = get_vault_collection()
    try:
        collection.delete(ids=[fact_id])
    except Exception:
        pass

def query_vault_facts(query_text: str, n_results: int = 5, section: str = None):
    collection = get_vault_collection()
    where_filter = {"section": section} if section else None
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_filter
    )
    return results
