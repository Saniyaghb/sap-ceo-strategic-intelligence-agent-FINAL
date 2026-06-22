import re
import pandas as pd

from config import PROCESSED_DIR


def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences while keeping the sentence-ending punctuation.

    This makes chunks cleaner because they do not start or end
    in the middle of words or sentences.
    """

    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)

    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)

    return [sentence.strip() for sentence in sentences if sentence.strip()]


def get_overlap_sentences(sentences: list[str], overlap_chars: int) -> list[str]:
    """
    Keep the last few sentences from the previous chunk as overlap.

    Instead of cutting exactly 150 characters, this keeps complete sentences
    whose total length is close to the overlap size.
    """

    if not sentences or overlap_chars <= 0:
        return []

    overlap = []
    total_length = 0

    for sentence in reversed(sentences):
        sentence_length = len(sentence)

        if total_length + sentence_length > overlap_chars and overlap:
            break

        overlap.insert(0, sentence)
        total_length += sentence_length

    return overlap


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    """
    Create sentence-aware chunks.

    Old logic used fixed character slicing:
        text[start:end]

    That could cut words like:
        "supply" -> "ply"

    This version keeps sentences intact and uses sentence-level overlap.
    """

    text = str(text or "").strip()

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    sentences = split_into_sentences(text)

    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence)

        
        if sentence_length > chunk_size:
            words = sentence.split()
            temp = ""

            for word in words:
                if len(temp) + len(word) + 1 <= chunk_size:
                    temp = f"{temp} {word}".strip()
                else:
                    if temp:
                        chunks.append(temp)
                    temp = word

            if temp:
                chunks.append(temp)

            current_sentences = []
            current_length = 0
            continue

        
        if current_sentences and current_length + sentence_length > chunk_size:
            chunks.append(" ".join(current_sentences).strip())

            current_sentences = get_overlap_sentences(
                current_sentences,
                overlap
            )
            current_length = sum(len(s) for s in current_sentences)

        current_sentences.append(sentence)
        current_length += sentence_length

    if current_sentences:
        chunks.append(" ".join(current_sentences).strip())

    return chunks


def create_chunks(chunk_size: int = 900, overlap: int = 150) -> pd.DataFrame:
    input_file = PROCESSED_DIR / "master_data.csv"

    if not input_file.exists():
        raise FileNotFoundError(
            "master_data.csv not found. Run: python processing/clean.py"
        )

    df = pd.read_csv(input_file).fillna("")
    rows = []

    for _, row in df.iterrows():
        base_text = (
            f"Title: {row['title']}\n"
            f"Source: {row['source']}\n"
            f"Published: {row['published']}\n"
            f"Content: {row['text']}"
        )

        for chunk_no, chunk in enumerate(chunk_text(base_text, chunk_size, overlap)):
            rows.append({
                "chunk_id": f"{row['doc_id']}_chunk_{chunk_no:03d}",
                "doc_id": row["doc_id"],
                "title": row["title"],
                "source": row["source"],
                "source_category": row["source_category"],
                "url": row["url"],
                "published": row["published"],
                "chunk_no": chunk_no,
                "chunk": chunk,
            })

    chunk_df = pd.DataFrame(rows)

    out_file = PROCESSED_DIR / "chunks.csv"
    chunk_df.to_csv(out_file, index=False)

    print(f"Created {len(chunk_df)} chunks from {df.shape[0]} documents")
    print(f"Saved: {out_file}")

    return chunk_df


if __name__ == "__main__":
    create_chunks()