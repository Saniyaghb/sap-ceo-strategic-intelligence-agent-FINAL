import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, PROCESSED_DIR


def create_embedding_file() -> np.ndarray:
    input_file = PROCESSED_DIR / "chunks.csv"
    if not input_file.exists():
        raise FileNotFoundError("chunks.csv not found. Run: python processing/chunk.py")

    df = pd.read_csv(input_file).fillna("")
    model = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = model.encode(
        df["chunk"].tolist(),
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    out_file = PROCESSED_DIR / "embeddings.npy"
    np.save(out_file, embeddings)
    print(f"Embeddings shape: {embeddings.shape}")
    print(f"Saved: {out_file}")
    return embeddings


if __name__ == "__main__":
    create_embedding_file()
