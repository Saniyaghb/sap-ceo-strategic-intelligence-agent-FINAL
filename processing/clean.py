import re
from html import unescape

import pandas as pd
from bs4 import BeautifulSoup

from config import PROCESSED_DIR, RAW_DIR

REQUIRED_COLUMNS = [
    "id",
    "title",
    "content",
    "text",
    "url",
    "published",
    "source",
    "source_category",
    "publisher",
    "collected_at",
]


def clean_text(value: str) -> str:
    value = "" if value is None else str(value)
    value = unescape(value)
    value = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    
    rename_map = {
        "link": "url",
        "date": "published",
        "summary": "content",
        "description": "content",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["title"] = df["title"].map(clean_text)
    df["content"] = df["content"].map(clean_text)
    df["text"] = df.apply(
        lambda row: clean_text(row["text"]) or clean_text(f"{row['title']}. {row['content']}"),
        axis=1,
    )
    df["url"] = df["url"].fillna("").astype(str)
    df["source"] = df["source"].replace("", "Unknown Source")
    df["source_category"] = df["source_category"].replace("", "unknown")

    return df[REQUIRED_COLUMNS]


def prepare_master_data() -> pd.DataFrame:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    raw_file = RAW_DIR / "all_sources.csv"
    if raw_file.exists():
        files = [raw_file]
    else:
        files = sorted(RAW_DIR.glob("*.csv"))

    if not files:
        raise FileNotFoundError("No raw data found. Run: python collectors/live_collect.py")

    frames = []
    for file in files:
        try:
            df = pd.read_csv(file).fillna("")
            frames.append(normalize_columns(df))
        except Exception as exc:
            print(f"Skipping {file}: {exc}")

    if not frames:
        raise ValueError("Raw files were found, but none could be loaded.")

    master = pd.concat(frames, ignore_index=True)
    master = master[master["title"].str.len() > 0]
    master = master[master["text"].str.len() > 20]

    master["dedupe_key"] = (
        master["title"].str.lower().str.replace(r"\W+", "", regex=True)
        + "_"
        + master["url"].str.lower()
    )
    master = master.drop_duplicates(subset=["dedupe_key"]).drop(columns=["dedupe_key"])

    master["published_dt"] = pd.to_datetime(master["published"], errors="coerce", utc=True)
    master = master.sort_values(["published_dt", "source"], ascending=[False, True])
    master = master.drop(columns=["published_dt"]).reset_index(drop=True)
    master["doc_id"] = [f"doc_{i:05d}" for i in range(len(master))]

    out_file = PROCESSED_DIR / "master_data.csv"
    master.to_csv(out_file, index=False)

    print(f"Prepared {len(master)} clean documents")
    print(f"Sources: {master['source'].nunique()}")
    print(f"Saved: {out_file}")
    return master


if __name__ == "__main__":
    prepare_master_data()
