from __future__ import annotations

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from api.schemas import LinkPreview


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


def _normalize_hostname(url: str) -> str:
    hostname = urlparse(url).netloc
    return hostname.removeprefix("www.") or "Unknown source"


def _extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    title_candidates = [
        soup.find("meta", property="og:title"),
        soup.find("meta", attrs={"name": "twitter:title"}),
    ]

    for candidate in title_candidates:
        content = candidate.get("content") if candidate else None
        if content and content.strip():
            return content.strip()

    if soup.title and soup.title.string and soup.title.string.strip():
        return soup.title.string.strip()

    heading = soup.find("h1")
    if heading:
        heading_text = heading.get_text(" ", strip=True)
        if heading_text:
            return heading_text

    return None


def fetch_link_preview(url: str) -> LinkPreview:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=10, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        hostname = _normalize_hostname(url)
        return LinkPreview(
            requested_url=url,
            resolved_url=url,
            title=None,
            hostname=hostname,
            content_type=None,
        )

    resolved_url = response.url or url
    hostname = _normalize_hostname(resolved_url)
    content_type = response.headers.get("Content-Type")
    title = None

    if content_type and "html" in content_type.lower():
        title = _extract_title(response.text)

    return LinkPreview(
        requested_url=url,
        resolved_url=resolved_url,
        title=title,
        hostname=hostname,
        content_type=content_type,
    )


def fetch_link_previews(urls: list[str]) -> list[LinkPreview]:
    return [fetch_link_preview(url) for url in urls]