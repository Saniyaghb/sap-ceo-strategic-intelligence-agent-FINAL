from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

from config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION_NAME)


def retrieve_documents(query: str, n_results: int = 8) -> list[dict]:
    model = get_model()
    collection = get_collection()
    query_embedding = model.encode([query], normalize_embeddings=True).tolist()[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    items = []
    for doc, meta, distance in zip(documents, metadatas, distances):
        items.append({
            "text": doc,
            "metadata": meta,
            "distance": distance,
            "similarity": round(1 / (1 + float(distance)), 4),
        })
    return items


def format_evidence(items: list[dict], max_chars: int = 7000) -> str:
    blocks = []
    used = 0

    for idx, item in enumerate(items, start=1):
        meta = item["metadata"]
        block = (
            f"Evidence {idx}\n"
            f"Title: {meta.get('title', '')}\n"
            f"Source: {meta.get('source', '')}\n"
            f"Date: {meta.get('published', '')}\n"
            f"URL: {meta.get('url', '')}\n"
            f"Text: {item['text']}"
        )
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)

    return "\n\n".join(blocks)
