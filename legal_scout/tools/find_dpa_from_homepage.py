from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


COMMON_DPA_PATHS = [
    "data-processing-agreement",
    "dpa",
    "data-processing-addendum",
    "privacy/data-processing-agreement",
    "legal/data-processing-agreement",
    "legal/us-data-processing-agreement",
    "legal/dpa",
    "privacy",
    "legal/privacy-policy",
]

HOMEPAGE_MATCH_KEYWORDS = [
    "data processing agreement",
    "data processing addendum",
    "dpa",
    "sub-processor",
    "subprocessor",
    "security measures",
    "specification of data processing",
]

ANNEX_MATCH_KEYWORDS = [
    "sub-processor",
    "subprocessor",
    "security measures",
    "specification of data processing",
    "data processing",
    "security",
]

BLOCKED_STATUS_CODES = {401, 403, 429}


def _build_fallback_dpa_urls(base_url: str) -> list[str]:
    base = base_url if base_url.endswith("/") else f"{base_url}/"
    candidates: list[str] = []
    seen: set[str] = set()

    for token in COMMON_DPA_PATHS:
        slug = token.strip().lower().replace(" ", "-").strip("/")
        candidate = urljoin(base, f"{slug}/")
        if candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    return candidates


def _request(url: str, headers: dict[str, str]) -> requests.Response | None:
    try:
        return requests.get(url, headers=headers, timeout=10)
    except requests.RequestException:
        return None


def _extract_annex_links(page_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    annex_links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True).lower()
        href = anchor["href"]
        href = href[0] if isinstance(href, list) else href
        href = href.strip()

        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue

        absolute_href = urljoin(page_url, href)
        haystack = f"{text} {absolute_href.lower()}"
        if any(keyword in haystack for keyword in ANNEX_MATCH_KEYWORDS) and absolute_href not in seen:
            seen.add(absolute_href)
            annex_links.append(absolute_href)

    return annex_links


def find_dpa_from_homepage(base_url: str) -> dict[str, list[str]]:
    headers = {"User-Agent": "Mozilla/5.0"}
    valid_links: list[str] = []
    blocked_links: list[str] = []
    seen_valid: set[str] = set()
    seen_blocked: set[str] = set()

    def add_valid(url: str) -> None:
        if url not in seen_valid:
            seen_valid.add(url)
            valid_links.append(url)

    def add_blocked(url: str) -> None:
        if url not in seen_blocked and url not in seen_valid:
            seen_blocked.add(url)
            blocked_links.append(url)

    initial_response = _request(base_url, headers)
    candidate_pages: list[tuple[str, str]] = []

    if initial_response is not None:
        if initial_response.ok:
            haystack = f"{initial_response.url.lower()} {initial_response.text[:12000].lower()}"
            if any(keyword in haystack for keyword in HOMEPAGE_MATCH_KEYWORDS):
                add_valid(initial_response.url)
                candidate_pages.append((initial_response.url, initial_response.text))
            else:
                soup = BeautifulSoup(initial_response.text, "html.parser")
                for anchor in soup.find_all("a", href=True):
                    text = anchor.get_text(" ", strip=True).lower()
                    href = anchor["href"]
                    href = href[0] if isinstance(href, list) else href
                    href = href.strip()

                    if not href or href.startswith("javascript:") or href.startswith("#"):
                        continue

                    absolute_href = urljoin(base_url, href)
                    haystack = f"{text} {absolute_href.lower()}"
                    if any(keyword in haystack for keyword in HOMEPAGE_MATCH_KEYWORDS):
                        linked_response = _request(absolute_href, headers)
                        if linked_response is None:
                            continue
                        if linked_response.status_code in BLOCKED_STATUS_CODES:
                            add_blocked(absolute_href)
                            continue
                        if linked_response.ok:
                            add_valid(linked_response.url)
                            candidate_pages.append((linked_response.url, linked_response.text))
        elif initial_response.status_code in BLOCKED_STATUS_CODES:
            add_blocked(base_url)

    if not valid_links:
        for candidate_url in _build_fallback_dpa_urls(base_url):
            response = _request(candidate_url, headers)
            if response is None:
                continue
            if response.status_code in BLOCKED_STATUS_CODES:
                add_blocked(candidate_url)
                continue
            if not response.ok:
                continue

            haystack = f"{response.url.lower()} {response.text[:12000].lower()}"
            if any(keyword in haystack for keyword in HOMEPAGE_MATCH_KEYWORDS):
                add_valid(response.url)
                candidate_pages.append((response.url, response.text))

    for page_url, html in candidate_pages:
        for annex_link in _extract_annex_links(page_url, html):
            response = _request(annex_link, headers)
            if response is None:
                continue
            if response.status_code in BLOCKED_STATUS_CODES:
                add_blocked(annex_link)
                continue
            if response.ok:
                add_valid(response.url)

    return {"valid": valid_links, "blocked": blocked_links}