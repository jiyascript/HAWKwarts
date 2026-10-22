"""Sematic retreival"""
import os
from dotenv import load_dotenv
from pinecone import Pinecone
from catalog_lib import get_model

load_dotenv()
_model = None
_index = None

def search_catalog(query:str, top_k: int=7) -> list[dict]:
    """Search the catalog for relevant courses, minors, programs, or specializations."""
    global _model, _index

    if _model is None:
        _model = get_model()

    if _index is None:
        pinecone_key = os.environ.get("PINECONE_API_KEY")
        if not pinecone_key:
            raise SystemExit("PINECONE_API_KEY not set. Copy .env.example to .env and fill it in.")
        index_name = os.environ.get("PINECONE_INDEX_NAME", "iit-catalog")
        pc = Pinecone(api_key=pinecone_key)
        _index = pc.Index(index_name)
    embedding = _model.encode(query, normalize_embeddings=True).tolist()
    results = []
    for namspace in ["", "requirements"]:
        response = _index.query(
            vector=embedding, 
            top_k=top_k,
            namespace=namspace,
            include_metadata = True
        )
        for match in response.matches:
            results.append(
                {
                    "id": match.id,
                    "score": match.score, #pinecone uses approximate nearest neighbor search.
                    "metadata": match.metadata,
                    "namespace": namspace
                }
            )
    results.sort(
        key=lambda result: result["score"],
        reverse=True
    )
    return results[:top_k]