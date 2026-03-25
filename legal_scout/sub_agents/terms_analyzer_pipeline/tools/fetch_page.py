"""Fetch and strip HTML from a T&C page URL."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import requests

_HEADERS = {'User-Agent': 'LegalScout/1.0'}
_MAX_BYTES = 100_000
_MAX_TEXT_CHARS = 80_000


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML-to-text converter using stdlib only."""

    _SKIP_TAGS = frozenset(('script', 'style', 'noscript', 'svg', 'head'))

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        return ' '.join(self._pieces)


def _strip_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    text = extractor.get_text()
    # Collapse whitespace runs into single spaces / newlines
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_page(url: str) -> str:
    """Fetch *url*, strip HTML, return plain text (max ~80 K chars).

    Returns a FETCH_ERROR message on failure so the caller can report it.
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '')
        if 'html' not in content_type and 'text' not in content_type:
            return f'FETCH_ERROR: unexpected content type ({content_type})'

        # Read up to _MAX_BYTES to avoid downloading huge files
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=8192):
            chunks.append(chunk)
            total += len(chunk)
            if total >= _MAX_BYTES:
                break
        resp.close()

        html = b''.join(chunks).decode(resp.encoding or 'utf-8', errors='replace')
        text = _strip_html(html)
        return text[:_MAX_TEXT_CHARS]

    except requests.exceptions.Timeout:
        return 'FETCH_ERROR: request timed out'
    except requests.exceptions.HTTPError as exc:
        return f'FETCH_ERROR: HTTP {exc.response.status_code}'
    except Exception as exc:
        return f'FETCH_ERROR: {exc}'
