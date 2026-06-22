import math

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer

from config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL, PROCESSED_DIR


def batch_iter(df: pd.DataFrame, size: int = 64):
    for start in range(0, len(df), size):
        yield df.iloc[start : start + size]


def build_vector_store(reset: bool = True):
    chunks_file = PROCESSED_DIR / "chunks.csv"
    if not chunks_file.exists():
        raise FileNotFoundError("chunks.csv not found. Run: python processing/chunk.py")

    df = pd.read_csv(chunks_file).fillna("")
    if df.empty:
        raise ValueError("chunks.csv is empty. Check collection and processing steps.")

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "SAP strategic intelligence knowledge base"},
    )

    model = SentenceTransformer(EMBEDDING_MODEL)

    total_batches = math.ceil(len(df) / 64)
    for batch_no, batch in enumerate(batch_iter(df, 64), start=1):
        texts = batch["chunk"].tolist()
        embeddings = model.encode(texts, normalize_embeddings=True).tolist()

        metadatas = []
        for _, row in batch.iterrows():
            metadatas.append({
                "doc_id": str(row["doc_id"]),
                "title": str(row["title"]),
                "source": str(row["source"]),
                "source_category": str(row["source_category"]),
                "url": str(row["url"]),
                "published": str(row["published"]),
                "chunk_no": int(row["chunk_no"]),
            })

        collection.add(
            ids=batch["chunk_id"].astype(str).tolist(),
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        print(f"Indexed batch {batch_no}/{total_batches}")

    print(f"Vector DB ready: {collection.count()} chunks in '{COLLECTION_NAME}'")
    return collection


if __name__ == "__main__":
    build_vector_store(reset=True)
