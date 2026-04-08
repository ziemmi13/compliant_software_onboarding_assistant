from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_PAGES = 4
MAX_CHARS_PER_PAGE = 4000


@dataclass
class SourcePageExcerpt:
    url: str
    content: str


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    return " ".join(text.split())


def fetch_source_page_excerpts(urls: list[str], *, max_pages: int = MAX_PAGES) -> list[SourcePageExcerpt]:
    excerpts: list[SourcePageExcerpt] = []

    for url in urls[:max_pages]:
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=10, allow_redirects=True)
        except requests.RequestException:
            continue

        if not response.ok:
            continue

        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            continue

        text = _extract_text(response.text)
        if not text:
            continue

        excerpts.append(SourcePageExcerpt(url=response.url, content=text[:MAX_CHARS_PER_PAGE]))

    return excerpts