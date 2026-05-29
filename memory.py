import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-mpnet-base-v2"
)

def get_memory_client():
    db_path = os.getenv("CHROMA_DB_PATH", "./chroma_data")
    client = chromadb.PersistentClient(
        path=db_path,
        settings=Settings(anonymized_telemetry=False)
    )
    return client

def get_or_create_collection(client, name: str):
    return client.get_or_create_collection(
        name=name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

def save_memory(collection, doc_id: str, text: str, metadata: dict = {}):
    collection.upsert(
        documents=[text],
        metadatas=[metadata],
        ids=[doc_id]
    )

def search_memory(collection, query: str, n_results: int = 3) -> list:
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results["documents"][0] if results["documents"] else []
    except Exception:
        return []
