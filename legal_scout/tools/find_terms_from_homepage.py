from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

COMMON_TERMS_PATHS = [
    "terms",
    "terms-of-service",
    "terms-of-use",
    "terms-and-conditions",
    "tos",
    "legal",
    "user-agreement",
    "user-terms",
    "conditions",
    "policies",
    "policies/terms-of-use/"
]

HOMEPAGE_MATCH_KEYWORDS = [
    "terms",
    "terms-of-service",
    "terms-of-use",
    "terms-and-conditions",
    "terms and conditions",
    "terms of service",
    "terms of use",
    "user-agreement",
    "user terms",
    "user-terms",
    "conditions",
    "legal",
]

BLOCKED_STATUS_CODES = {401, 403, 429}
BLOCKED_FALLBACK_KEYWORDS = (
    "terms",
    "terms-of-use",
    "terms-of-service",
    "terms-and-conditions",
    "tos",
)


def _build_fallback_terms_urls(base_url: str) -> list[str]:
    """Generate deduplicated candidate terms-policy URLs from common path tokens.

    Args:
        base_url: Website root URL used to build absolute candidate links.

    Returns:
        A list of absolute URLs (for example, `/terms/`, `/legal/`) that can be
        probed when homepage parsing does not produce a terms link.
    """
    base = base_url if base_url.endswith("/") else f"{base_url}/"
    candidates = []
    seen = set()

    for token in COMMON_TERMS_PATHS:
        slug = token.strip().lower().replace(" ", "-").strip("/")
        candidate = urljoin(base, f"{slug}/")
        if candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    return candidates

def find_terms_from_homepage(base_url: str) -> dict[str, list[str]]:
    """Find likely Terms of Service URLs for a website.

    The function first parses homepage anchor tags and matches links whose text
    or URL contains known legal keywords. If the homepage cannot be parsed or no
    match is found (for example due to bot-check pages), it probes a set of
    common legal paths directly.

    Args:
        base_url: Homepage URL to inspect, such as "https://example.com/".

    Returns:
        A dictionary with two lists:
        - "valid": deduplicated absolute URLs confirmed as likely terms/legal pages.
        - "blocked": deduplicated candidate terms URLs that returned blocked
          status codes (for example 401/403/429) and could not be validated.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    soup = None
    homepage_blocked = False

    try:
        r = requests.get(base_url, headers=headers, timeout=10)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
        elif r.status_code in BLOCKED_STATUS_CODES:
            homepage_blocked = True
    except requests.RequestException:
        soup = None

    valid_links = []
    blocked_links = []
    seen_valid = set()
    seen_blocked = set()
    
    if soup is not None:
        for anchor in soup.find_all("a", href=True):
            text = anchor.get_text(" ", strip=True).lower()
            raw_href = anchor["href"]
            href = raw_href[0] if isinstance(raw_href, list) else raw_href
            href = href.strip()

            if not href or href.startswith("javascript:") or href.startswith("#"):
                continue

            absolute_href = urljoin(base_url, href)
            haystack = f"{text} {absolute_href.lower()}"
            
            if any(keyword in haystack for keyword in HOMEPAGE_MATCH_KEYWORDS) and absolute_href not in seen_valid:
                seen_valid.add(absolute_href)
                valid_links.append(absolute_href)

    if len(valid_links) > 0:
        return {"valid": valid_links, "blocked": blocked_links}

    if homepage_blocked and base_url not in seen_blocked:
        seen_blocked.add(base_url)
        blocked_links.append(base_url)

    # Some websites return bot-check shells on the homepage; probe common legal paths directly.
    fallback_signals = ("terms", "terms of service", "terms and conditions", "terms of use")
    for candidate_url in _build_fallback_terms_urls(base_url):
        try:
            resp = requests.get(candidate_url, headers=headers, timeout=10)
        except requests.RequestException:
            continue

        if resp.status_code in BLOCKED_STATUS_CODES:
            if (
                any(keyword in candidate_url.lower() for keyword in BLOCKED_FALLBACK_KEYWORDS)
                and candidate_url not in seen_valid
                and candidate_url not in seen_blocked
            ):
                seen_blocked.add(candidate_url)
                blocked_links.append(candidate_url)
            continue

        if resp.status_code >= 400:
            continue

        final_url = resp.url
        haystack = f"{final_url.lower()} {resp.text[:8000].lower()}"
        if any(signal in haystack for signal in fallback_signals) and final_url not in seen_valid:
            seen_valid.add(final_url)
            valid_links.append(final_url)
    
    return {"valid": valid_links, "blocked": blocked_links}