import json
import re
import subprocess
import sys
from pathlib import Path
import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ceo_agent import generate_ceo_response
from config import (
    AUTO_REFRESH_HOURS,
    COMPANY_NAME,
    INDUSTRY,
    OLLAMA_MODEL,
    PROCESSED_DIR,
    SCHEDULER_STATUS_FILE,
    SOURCES,
)
from rag.retriever import format_evidence, retrieve_documents


# Page configuration

st.set_page_config(
    page_title="SAP Strategic Intelligence Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

BERLIN_TZ = ZoneInfo("Europe/Berlin")

# Keywords used for lightweight dashboard monitoring

OPPORTUNITY_KEYWORDS = [
    "ai", "business ai", "cloud", "growth", "partnership", "automation",
    "data", "platform", "customer", "expansion", "innovation", "sapphire",
]

RISK_KEYWORDS = [
    "risk", "regulation", "lawsuit", "competition", "competitor", "decline",
    "outage", "security", "cyber", "privacy", "slowdown", "cost", "layoff",
]

TREND_KEYWORDS = [
    "generative ai", "agent", "automation", "cloud erp", "data platform",
    "sovereign cloud", "sustainability", "compliance", "productivity",
]

POSITIVE_WORDS = {
    "growth", "increase", "partnership", "wins", "strong", "record",
    "innovation", "success", "profit", "expansion", "launch", "leader",
}

NEGATIVE_WORDS = {
    "risk", "decline", "lawsuit", "delay", "outage", "loss", "cuts",
    "concern", "weak", "pressure", "breach", "slowdown",
}


# Styling

st.markdown(
    """
    <style>
        :root {
            --card-bg: rgba(255, 255, 255, 0.055);
            --card-border: rgba(255, 255, 255, 0.12);
            --muted: #a8b3c7;
            --text: #f8fafc;
            --accent: #38bdf8;
            --accent-2: #2563eb;
            --good: #22c55e;
            --warn: #f59e0b;
            --bad: #ef4444;
        }

        .block-container {
            padding-top: 2.1rem;
            padding-bottom: 4rem;
            max-width: 1280px;
        }

        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        .hero {
            border: 1px solid rgba(56, 189, 248, 0.30);
            background:
                radial-gradient(circle at top left, rgba(56, 189, 248, 0.24), transparent 32%),
                linear-gradient(135deg, rgba(15,23,42,1) 0%, rgba(30,64,175,0.92) 55%, rgba(14,165,233,0.82) 100%);
            border-radius: 28px;
            padding: 34px 38px;
            margin-bottom: 20px;
            box-shadow: 0 18px 60px rgba(0, 0, 0, 0.32);
        }

        .hero-eyebrow {
            color: #bae6fd;
            text-transform: uppercase;
            font-size: 0.78rem;
            letter-spacing: 0.16em;
            font-weight: 800;
            margin-bottom: 12px;
        }

        .hero h1 {
            color: white;
            margin: 0;
            font-size: 2.5rem;
            line-height: 1.08;
            font-weight: 900;
            letter-spacing: -0.04em;
        }

        .hero p {
            color: #e0f2fe;
            margin-top: 14px;
            max-width: 920px;
            font-size: 1.04rem;
            line-height: 1.6;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
            margin: 18px 0 18px 0;
        }

        .metric-card-dark {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 18px 18px;
            box-shadow: 0 12px 34px rgba(0, 0, 0, 0.14);
        }

        .metric-label-dark {
            color: var(--muted);
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .metric-value-dark {
            color: var(--text);
            font-size: 1.34rem;
            line-height: 1.25;
            font-weight: 850;
            word-break: break-word;
        }

        .section-card {
            background: rgba(15, 23, 42, 0.52);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 24px;
            padding: 22px;
            margin: 16px 0;
            box-shadow: 0 10px 36px rgba(0,0,0,0.18);
        }

        .section-title {
            color: #ffffff;
            font-size: 1.45rem;
            font-weight: 850;
            margin: 0 0 6px 0;
            letter-spacing: -0.02em;
        }

        .section-subtitle {
            color: var(--muted);
            font-size: 0.95rem;
            margin-bottom: 16px;
        }

        .news-card {
            background: rgba(255,255,255,0.055);
            border: 1px solid rgba(255,255,255,0.105);
            border-radius: 18px;
            padding: 16px 18px;
            margin-bottom: 12px;
            overflow-wrap: anywhere;
            word-break: normal;
        }

        .news-card h3 {
            margin: 0 0 8px 0;
            color: #f8fafc;
            font-size: 1.02rem;
            line-height: 1.36;
            font-weight: 780;
        }

        .meta-line {
            color: #cbd5e1;
            font-size: 0.82rem;
            margin-bottom: 8px;
        }

        .summary-text {
            color: #dbeafe;
            font-size: 0.92rem;
            line-height: 1.55;
            margin-top: 8px;
            overflow-wrap: anywhere;
        }

        .pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(56, 189, 248, 0.15);
            border: 1px solid rgba(56, 189, 248, 0.34);
            color: #bae6fd;
            font-size: 0.74rem;
            font-weight: 800;
            margin-right: 6px;
            margin-bottom: 6px;
        }

        .pill.good { background: rgba(34,197,94,0.15); border-color: rgba(34,197,94,0.32); color: #bbf7d0; }
        .pill.warn { background: rgba(245,158,11,0.15); border-color: rgba(245,158,11,0.35); color: #fde68a; }
        .pill.bad { background: rgba(239,68,68,0.15); border-color: rgba(239,68,68,0.35); color: #fecaca; }

        .source-link {
            display: inline-block;
            color: #7dd3fc !important;
            text-decoration: none !important;
            font-weight: 750;
            margin-top: 8px;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .evidence-card {
            background: rgba(14, 116, 144, 0.15);
            border: 1px solid rgba(125, 211, 252, 0.22);
            border-radius: 18px;
            padding: 16px 18px;
            margin-bottom: 14px;
            overflow-wrap: anywhere;
            word-break: normal;
        }

        .evidence-card h4 {
            margin: 0 0 8px 0;
            color: #f8fafc;
            font-size: 1.0rem;
            line-height: 1.35;
        }

        .evidence-text {
            color: #dbeafe;
            line-height: 1.62;
            white-space: normal;
            overflow-wrap: anywhere;
            word-break: normal;
            margin-top: 10px;
        }

        .empty-card {
            background: rgba(148, 163, 184, 0.10);
            border: 1px dashed rgba(148, 163, 184, 0.35);
            color: #cbd5e1;
            border-radius: 18px;
            padding: 20px;
            margin-top: 10px;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.08);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.09);
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(255,255,255,0.04);
            border-radius: 999px 999px 0 0;
            padding: 10px 16px;
        }

        .stTabs [aria-selected="true"] {
            background: rgba(56,189,248,0.16) !important;
        }

        @media (max-width: 900px) {
            .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .hero h1 { font-size: 2rem; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# Data loading 

@st.cache_data(show_spinner=False, ttl=300)
def load_master_data() -> pd.DataFrame:
    file = PROCESSED_DIR / "master_data.csv"
    if not file.exists():
        return pd.DataFrame()

    df = pd.read_csv(file).fillna("")

    if "published" in df.columns:
        df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
        df = df.sort_values("published_dt", ascending=False)

    
    if "source_category" not in df.columns:
        df["source_category"] = "unknown"

    df["category_clean"] = df.apply(infer_category, axis=1)
    return df


def infer_category(row) -> str:
    category = str(row.get("source_category", "")).strip().lower()
    source = str(row.get("source", "")).strip().lower()

    if "competitor" in source or "competitor" in category:
        return "competitor"
    if category:
        return category
    return "unknown"


def safe_html(value) -> str:
    return html.escape(str(value))


def short_text(value, max_chars: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def clean_markdown(text: str) -> str:
    """Fix common LLM markdown issue: '#Heading' -> '# Heading'."""
    text = str(text)
    text = re.sub(r"(?m)^(#{1,6})([^#\s])", r"\1 \2", text)
    return text


def keyword_score(text: str, keywords: list[str]) -> int:
    text = str(text).lower()
    return sum(1 for keyword in keywords if keyword.lower() in text)


def sentiment_label(text: str) -> str:
    words = set(str(text).lower().replace("-", " ").split())
    score = len(words & POSITIVE_WORDS) - len(words & NEGATIVE_WORDS)
    if score > 0:
        return "Positive"
    if score < 0:
        return "Negative"
    return "Neutral"


def level_from_score(score: int) -> str:
    if score >= 4:
        return "High"
    if score >= 2:
        return "Medium"
    return "Low"


def level_class(level: str) -> str:
    level = str(level).lower()
    if level == "high":
        return "good"
    if level == "medium":
        return "warn"
    return "bad"


def format_date(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return str(value)
    return parsed.tz_convert(BERLIN_TZ).strftime("%d %b %Y, %H:%M")


def format_last_update(master: pd.DataFrame) -> tuple[str, str]:
    master_file = PROCESSED_DIR / "master_data.csv"
    timestamp = None
    source_note = "Pipeline timestamp"

    if not master.empty and "collected_at" in master.columns:
        parsed = pd.to_datetime(master["collected_at"], errors="coerce", utc=True).dropna()
        if not parsed.empty:
            timestamp = parsed.max()
            source_note = "Latest pipeline collection time"

    if timestamp is None and not master.empty and "published_dt" in master.columns:
        parsed = master["published_dt"].dropna()
        if not parsed.empty:
            timestamp = parsed.max()
            source_note = "Latest document publication date"

    if timestamp is None and master_file.exists():
        timestamp = pd.Timestamp(datetime.fromtimestamp(master_file.stat().st_mtime, tz=timezone.utc))
        source_note = "Processed file modified time"

    if timestamp is None:
        return "Not available", "Run the pipeline first"

    timestamp_berlin = timestamp.tz_convert(BERLIN_TZ)
    return timestamp_berlin.strftime("%A, %d %B %Y at %H:%M %Z"), source_note


@st.cache_data(show_spinner=False, ttl=60)
def load_scheduler_status() -> dict:
    if not SCHEDULER_STATUS_FILE.exists():
        return {}
    try:
        return json.loads(SCHEDULER_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_pipeline_run() -> tuple[bool, str]:
    command = [sys.executable, str(ROOT / "run_pipeline.py")]
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode == 0, output


def make_monitor(df: pd.DataFrame, keywords: list[str], label_col: str, level_name: str, top_n: int = 8) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    work["score"] = work["text"].apply(lambda value: keyword_score(value, keywords))
    work = work[work["score"] > 0].sort_values(["score", "published_dt"], ascending=[False, False], na_position="last")

    if work.empty:
        return pd.DataFrame()

    return pd.DataFrame({
        label_col: work["title"],
        level_name: work["score"].apply(level_from_score),
        "Evidence": work["source"] + " | " + work["published"].astype(str),
        "Confidence": work["score"].apply(lambda s: min(0.95, round(0.45 + (s * 0.12), 2))),
        "URL": work["url"],
    }).head(top_n)


def render_metric(label: str, value: str):
    st.markdown(
        f"""
        <div class="metric-card-dark">
            <div class="metric-label-dark">{safe_html(label)}</div>
            <div class="metric-value-dark">{safe_html(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = ""):
    subtitle_html = f'<div class="section-subtitle">{safe_html(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">{safe_html(title)}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_news_card(row, show_summary: bool = True):
    title = safe_html(row.get("title", "Untitled"))
    source = safe_html(row.get("source", "Unknown source"))
    category = safe_html(row.get("category_clean", row.get("source_category", "unknown")))
    published = safe_html(format_date(row.get("published", "")))
    url = safe_html(row.get("url", ""))
    summary = safe_html(short_text(row.get("text", row.get("content", "")), 340))

    link_html = ""
    if url:
        link_html = f'<a class="source-link" href="{url}" target="_blank">Open source ↗</a>'

    summary_html = f'<div class="summary-text">{summary}</div>' if show_summary and summary else ""

    st.markdown(
        f"""
        <div class="news-card">
            <span class="pill">{category}</span>
            <h3>{title}</h3>
            <div class="meta-line">{source} • {published}</div>
            {summary_html}
            {link_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_monitor_cards(df: pd.DataFrame, title_col: str, level_col: str):
    if df.empty:
        st.markdown(
            """
            <div class="empty-card">
                No matching items found in the current dataset for this section. The data is still valid; this only means the current refresh did not classify any record into this view.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for _, row in df.iterrows():
        title = safe_html(row.get(title_col, "Untitled"))
        level = safe_html(row.get(level_col, "Low"))
        css_class = level_class(row.get(level_col, "Low"))
        evidence = safe_html(row.get("Evidence", ""))
        confidence = safe_html(row.get("Confidence", ""))
        url = safe_html(row.get("URL", ""))
        link_html = f'<a class="source-link" href="{url}" target="_blank">Open evidence ↗</a>' if url else ""

        st.markdown(
            f"""
            <div class="news-card">
                <span class="pill {css_class}">{level}</span>
                <span class="pill">confidence {confidence}</span>
                <h3>{title}</h3>
                <div class="meta-line">{evidence}</div>
                {link_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_news_list(df: pd.DataFrame, limit: int = 8, empty_label: str = "No records found for this view."):
    if df.empty:
        st.markdown(f'<div class="empty-card">{safe_html(empty_label)}</div>', unsafe_allow_html=True)
        return

    for _, row in df.head(limit).iterrows():
        render_news_card(row)


def table_view(df: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Title", "Source", "Category", "Published", "Open"])

    work = df.head(limit).copy()
    out = pd.DataFrame({
        "Title": work.get("title", ""),
        "Source": work.get("source", ""),
        "Category": work.get("category_clean", work.get("source_category", "")),
        "Published": work.get("published", "").apply(format_date) if "published" in work else "",
        "Open": work.get("url", ""),
    })
    return out


def show_link_table(df: pd.DataFrame, limit: int = 12):
    view = table_view(df, limit)
    if view.empty:
        st.markdown('<div class="empty-card">No records found for this view.</div>', unsafe_allow_html=True)
        return

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Title": st.column_config.TextColumn("Title", width="large"),
            "Source": st.column_config.TextColumn("Source", width="medium"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Published": st.column_config.TextColumn("Published", width="medium"),
            "Open": st.column_config.LinkColumn("Open", display_text="Open ↗", width="small"),
        },
    )


# Load data
master = load_master_data()
scheduler_status = load_scheduler_status()


# Sidebar

with st.sidebar:
    st.header("Controls")
    st.markdown(f"LLM: `{OLLAMA_MODEL}`")
    st.markdown(f"Auto-refresh: every **{AUTO_REFRESH_HOURS} hours**")

    if scheduler_status:
        status = scheduler_status.get("status", "unknown")
        st.caption(f"Scheduler status: `{status}`")
        if scheduler_status.get("last_success_at"):
            st.caption(f"Last scheduler success: {scheduler_status['last_success_at']}")
    else:
        st.caption("Scheduler status: not started")

    if st.button("Refresh live data and rebuild index", use_container_width=True):
        with st.spinner("Collecting live data, cleaning it, chunking it, and rebuilding ChromaDB..."):
            ok, output = safe_pipeline_run()
        if ok:
            st.cache_data.clear()
            st.success("Pipeline finished successfully. Dashboard data refreshed.")
            st.rerun()
        else:
            st.error("Pipeline failed. Check the logs below.")
        with st.expander("Pipeline log"):
            st.code(output)


# Header

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-eyebrow">Local RAG dashboard • SAP strategic intelligence</div>
        <h1>{safe_html(COMPANY_NAME)} Strategic Intelligence Agent</h1>
        <p>
            Executive monitoring of SAP announcements, market signals, competitors, emerging technology,
            opportunities, risks, sentiment, and evidence-backed CEO recommendations.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if master.empty:
    st.warning("No processed data found. Run `python start_dashboard.py` from the project root first.")
    st.stop()

source_count = master["source"].nunique() if "source" in master.columns else len(SOURCES)
category_count = master["category_clean"].nunique() if "category_clean" in master.columns else 0
last_update, last_update_note = format_last_update(master)

metric_cols = st.columns(4)
with metric_cols[0]:
    render_metric("Company", COMPANY_NAME)
with metric_cols[1]:
    render_metric("Industry", INDUSTRY)
with metric_cols[2]:
    render_metric("Collected documents", f"{len(master):,}")
with metric_cols[3]:
    render_metric("Data sources", str(source_count))

st.markdown(
    f"""
    <div class="section-card">
        <div class="section-title">Last Data Update</div>
        <div class="metric-value-dark">{safe_html(last_update)}</div>
        <div class="section-subtitle">{safe_html(last_update_note)} • {category_count} source categories monitored • {len(SOURCES)} configured pipeline sources</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# Prepare filtered views

recent = master.head(12)
market_df = master[master["category_clean"].isin(["news", "market"])]
competitor_df = master[(master["category_clean"] == "competitor") | (master["source"].str.lower().str.contains("competitor", na=False))]
tech_df = master[master["text"].str.lower().apply(lambda text: keyword_score(text, TREND_KEYWORDS) > 0)]
company_df = master[master["category_clean"] == "company"]
research_df = master[master["category_clean"] == "research"]

opportunities = make_monitor(master, OPPORTUNITY_KEYWORDS, "Opportunity Title", "Impact Level")
risks = make_monitor(master, RISK_KEYWORDS, "Risk Title", "Severity Level")
master["sentiment"] = master["text"].apply(sentiment_label)
sentiment_counts = master.groupby(["category_clean", "sentiment"]).size().reset_index(name="count")


# Main tabs

overview_tab, intel_tab, monitor_tab, sentiment_tab, briefing_tab, data_tab = st.tabs([
    "1. Overview",
    "2. Market Intelligence",
    "3. Opportunity & Risk",
    "4. Sentiment",
    "5. CEO Briefing",
    "6. Data Explorer",
])

with overview_tab:
    section_header("Executive Snapshot")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Company records", len(company_df))
        st.metric("Market/news records", len(market_df))
    with c2:
        st.metric("Competitor records", len(competitor_df))
        st.metric("Research records", len(research_df))
    with c3:
        st.metric("Opportunity signals", len(opportunities))
        st.metric("Risk signals", len(risks))

    section_header("Latest Signals", "Most recent items from the processed intelligence dataset.")
    render_news_list(recent, limit=5)

with intel_tab:
    section_header("Market Intelligence", "Use the tabs below to inspect specific intelligence streams.")
    sub_market, sub_competitor, sub_tech, sub_company, sub_research = st.tabs([
        "Market News",
        "Competitor Activities",
        "Emerging Technologies",
        "Company Announcements",
        "Research Signals",
    ])

    with sub_market:
        render_news_list(market_df, limit=8, empty_label="No market/news records found in the current refresh.")

    with sub_competitor:
        render_news_list(
            competitor_df,
            limit=8,
            empty_label="No competitor records found in the current refresh. If this appears unexpectedly, check that the Google News - Competitors source is present in master_data.csv.",
        )

    with sub_tech:
        render_news_list(tech_df, limit=8, empty_label="No emerging technology records matched the current keyword set.")

    with sub_company:
        render_news_list(company_df, limit=8, empty_label="No SAP company announcements found in the current refresh.")

    with sub_research:
        render_news_list(research_df, limit=8, empty_label="No research records found in the current refresh.")


with monitor_tab:
    left, right = st.columns(2)
    with left:
        section_header("3. Opportunity Monitor", "Keyword-scored opportunity signals from collected evidence.")
        render_monitor_cards(opportunities, "Opportunity Title", "Impact Level")
    
    with right:
        section_header("4. Risk Monitor", "Keyword-scored risk signals from collected evidence.")
        render_monitor_cards(risks, "Risk Title", "Severity Level")
    
with sentiment_tab:
    section_header("5. Sentiment Analysis", "A sentiment view using positive and negative business keywords.")
    c1, c2 = st.columns([1, 1.2])
    with c1:
        st.subheader("Overall sentiment")
        st.bar_chart(master["sentiment"].value_counts())
    with c2:
        st.subheader("Sentiment by source category")
        st.dataframe(sentiment_counts, use_container_width=True, hide_index=True)

with briefing_tab:
    section_header("6. Strategic Recommendations", "Ask a management-level question. The system retrieves evidence from ChromaDB before sending it to the local Ollama model.")

    default_question = "If you were the CEO of SAP today, what should management do next and why?"
    question = st.text_area("Strategic question", value=default_question, height=110)

    generate = st.button("Generate CEO Briefing", type="primary", use_container_width=False)

    if generate:
        try:
            with st.spinner("Retrieving evidence from ChromaDB..."):
                evidence_items = retrieve_documents(question, n_results=10)
                evidence = format_evidence(evidence_items)

            with st.spinner("Generating executive recommendation with local Ollama model..."):
                answer = generate_ceo_response(question, evidence)

            section_header("7. CEO Briefing", "Generated from retrieved evidence. The evidence is shown below for traceability.")
            st.markdown(clean_markdown(answer))
        
            section_header("Supporting Evidence")
            for index, item in enumerate(evidence_items, start=1):
                meta = item.get("metadata", {})
                title = safe_html(meta.get("title", "Untitled evidence"))
                source = safe_html(meta.get("source", "Unknown source"))
                published = safe_html(format_date(meta.get("published", "")))
                similarity = item.get("similarity")
                if isinstance(similarity, float):
                    similarity_text = f"{similarity:.3f}"
                else:
                    similarity_text = safe_html(similarity)
                url = safe_html(meta.get("url", ""))
                text = safe_html(short_text(item.get("text", ""), 1200))
                link_html = f'<a class="source-link" href="{url}" target="_blank">Open source ↗</a>' if url else ""

                st.markdown(
                    f"""
                    <div class="evidence-card">
                        <span class="pill">Evidence {index}</span>
                        <span class="pill">similarity {similarity_text}</span>
                        <h4>{title}</h4>
                        <div class="meta-line">{source} • {published}</div>
                        {link_html}
                        <div class="evidence-text">{text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        
        except Exception as exc:
            st.error("Could not generate briefing. Make sure the pipeline has run and Ollama is running.")
            st.code(str(exc))

with data_tab:
    section_header("Data Explorer")

    category_options = ["All"] + sorted(master["category_clean"].dropna().unique().tolist())
    selected_category = st.selectbox("Filter by category", category_options)

    if selected_category == "All":
        filtered = master
    else:
        filtered = master[master["category_clean"] == selected_category]

    show_link_table(filtered, limit=30)
