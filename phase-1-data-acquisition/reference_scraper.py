from __future__ import annotations

from datetime import datetime
from typing import List

import requests
from bs4 import BeautifulSoup

# Support both package and direct-script imports
try:  # pragma: no cover - import flexibility
    from .config import REFERENCE_PAGES, ReferencePage
    from .models import FaqPage
except ImportError:
    from config import REFERENCE_PAGES, ReferencePage
    from models import FaqPage


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RAGMutualFundBot/0.1; +https://example.com/bot)",
}


def _fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    # Gracefully handle 4xx/5xx errors so a single bad URL doesn't break Phase 1.
    if not response.ok:
        return ""
    return response.text


def _extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for selector in ("article", "main", "div.content", "div#content"):
        container = soup.select_one(selector)
        if container:
            return container.get_text("\n", strip=True)

    return soup.get_text("\n", strip=True)


def scrape_reference_page(page: ReferencePage) -> FaqPage:
    html = _fetch_html(page.url)
    clean_text = _extract_main_text(html) if html else ""

    return FaqPage(
        source=page.source,
        topic=page.topic,
        url=page.url,
        clean_text=clean_text,
        scraped_at=datetime.utcnow(),
    )


def scrape_all_reference_pages() -> List[FaqPage]:
    faqs: List[FaqPage] = [scrape_reference_page(page) for page in REFERENCE_PAGES]

    # Add a synthetic FAQ describing chatbot scope so that Phase 2 / RAG
    # can reinforce out-of-scope handling for non-scheme questions.
    faqs.append(
        FaqPage(
            source="System",
            topic="Chatbot scope and limitations",
            url="https://www.indmoney.com/",
            clean_text=(
                "This INDMoney mutual fund chatbot is intended only for questions about the "
                "specific mutual fund schemes it knows about (for example, NAV, exit load, "
                "lock-in period, AUM, or returns for a given scheme) and for how-to questions "
                "like downloading mutual fund or capital gains statements from official sites. "
                "Any user question that is not about these supported mutual fund schemes or "
                "related statements should be answered with: "
                "'This question is out of scope for this INDMoney chatbot.'"
            ),
            scraped_at=datetime.utcnow(),
        )
    )

    return faqs

