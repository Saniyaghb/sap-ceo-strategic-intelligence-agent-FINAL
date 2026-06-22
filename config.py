from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CHROMA_DIR = BASE_DIR / "chroma_db"

COMPANY_NAME = "SAP"
INDUSTRY = "Enterprise Software / ERP / Cloud / Business AI"
COLLECTION_NAME = "sap_strategic_intelligence"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
OLLAMA_MODEL = "phi4-mini"
AUTO_REFRESH_HOURS = 4
SCHEDULER_STATUS_FILE = PROCESSED_DIR / "scheduler_status.json"


# Source groups: SAP official feeds, Google News feeds, and arXiv research API.
SOURCES = [
    {
        "name": "SAP News Center",
        "category": "company",
        "kind": "rss",
        "url": "https://news.sap.com/feed/",
        "limit": 90,
    },
    
    {
        "name": "Google News - SAP",
        "category": "news",
        "kind": "google_news",
        "query": 'SAP enterprise software OR SAP cloud OR SAP AI when:30d',
        "limit": 90,
    },
    {
        "name": "Google News - SAP Investor Relations",
        "category": "market",
        "kind": "google_news",
        "query": 'SAP earnings OR SAP quarterly results OR SAP investor relations when:365d',
        "limit": 90,
    },
    {
        "name": "Google News - Competitors",
        "category": "competitor",
        "kind": "google_news",
        "query": '(Oracle ERP OR Salesforce AI OR Microsoft Dynamics 365 OR Workday ERP) when:30d',
        "limit": 90,
    },
    {
        "name": "Google News - Enterprise AI Trends",
        "category": "trend",
        "kind": "google_news",
        "query": 'enterprise AI ERP cloud data platform automation when:30d',
        "limit": 90,
    },
    {
        "name": "arXiv - Enterprise AI Research",
        "category": "research",
        "kind": "arxiv",
        "query": 'all:"enterprise AI" OR all:"business AI" OR all:"ERP" OR all:"cloud computing"',
        "limit": 90,
    },
    {
        "name": "arXiv - RAG and AI Agents Research",
        "category": "research",
        "kind": "arxiv",
        "query": 'all:"retrieval augmented generation" OR all:"AI agents" OR all:"business intelligence"',
        "limit": 90,
    },
]
