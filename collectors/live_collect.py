import argparse
import hashlib
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import pandas as pd
from bs4 import BeautifulSoup

from config import RAW_DIR, SOURCES


def clean_html(value: str) -> str:
    """Convert RSS HTML snippets into readable text."""
    value = "" if value is None else str(value)
    value = unescape(value)
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def entry_content(entry) -> str:
    pieces = []

    if entry.get("summary"):
        pieces.append(entry.get("summary"))

    if entry.get("description"):
        pieces.append(entry.get("description"))

    for item in entry.get("content", []) or []:
        if isinstance(item, dict) and item.get("value"):
            pieces.append(item.get("value"))

    cleaned = [clean_html(piece) for piece in pieces if clean_html(piece)]
    return " ".join(dict.fromkeys(cleaned))


def normalize_entry(entry, source: dict) -> dict:
    title = clean_html(entry.get("title", ""))
    content = entry_content(entry)
    url = entry.get("link", "") or entry.get("id", "")
    published = entry.get("published", "") or entry.get("updated", "")

    
    publisher = ""
    if " - " in title:
        publisher = title.rsplit(" - ", 1)[-1].strip()

    text = re.sub(r"\s+", " ", f"{title}. {content}".strip()).strip()

    return {
        "id": stable_id(title, url, source["name"]),
        "title": title,
        "content": content,
        "text": text,
        "url": url,
        "published": published,
        "source": source["name"],
        "source_category": source["category"],
        "publisher": publisher,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def build_url(source: dict) -> str:
    if source["kind"] == "google_news":
        query = quote_plus(source["query"])
        return f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    if source["kind"] == "arxiv":
        query = quote_plus(source["query"])
        limit = source.get("limit", 90)
        return (
            "https://export.arxiv.org/api/query?"
            f"search_query={query}&start=0&max_results={limit}"
            "&sortBy=submittedDate&sortOrder=descending"
        )

    return source["url"]


def collect_source(source: dict) -> list[dict]:
    url = build_url(source)
    feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})

    if getattr(feed, "bozo", False):
        print(f"Warning: feedparser reported an issue for {source['name']}: {feed.bozo_exception}")

    rows = []
    for entry in feed.entries[: source.get("limit", 90)]:
        row = normalize_entry(entry, source)
        if row["title"] and row["text"]:
            rows.append(row)

    return rows


def collect_all() -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []

    for source in SOURCES:
        rows = collect_source(source)
        all_rows.extend(rows)

        out_file = RAW_DIR / f"{source['name'].lower().replace(' ', '_').replace('-', '').replace('/', '_')}.csv"
        pd.DataFrame(rows).to_csv(out_file, index=False)
        print(f"Collected {len(rows):>3} rows from {source['name']}")

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["id"]).reset_index(drop=True)

    combined = RAW_DIR / "all_sources.csv"
    df.to_csv(combined, index=False)
    print(f"\nTotal collected documents: {len(df)}")
    print(f"Saved combined raw data to: {combined}")
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect live strategic intelligence data for SAP.")
    parser.parse_args()
    collect_all()


if __name__ == "__main__":
    main()
