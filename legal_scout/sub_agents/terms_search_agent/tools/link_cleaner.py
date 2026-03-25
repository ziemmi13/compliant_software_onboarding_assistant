
from __future__ import annotations

from typing import Optional

import requests

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

_VERTEX_REDIRECT_PREFIX = 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/'
_HEADERS = {'User-Agent': 'LegalScout/1.0'}


def _resolve_redirect(url: str) -> str:
    """Follow a redirect chain via HEAD only. Returns the exact destination URL."""
    try:
        resp = requests.head(url, headers=_HEADERS, allow_redirects=True, timeout=5)
        return resp.url
    except Exception:
        return url


def clean_links_from_response(response: LlmResponse) -> Optional[str]:
    # Primary path: grounding metadata attached to the response
    grounding_metadata = getattr(response, 'grounding_metadata', None)
    if grounding_metadata and grounding_metadata.grounding_chunks:
        for chunk in grounding_metadata.grounding_chunks:
            web = getattr(chunk, 'web', None)
            uri = getattr(web, 'uri', None)
            if uri:
                return _resolve_redirect(uri.strip())

    # Fallback: the model emitted the URL as plain text
    content = getattr(response, 'content', None)
    if not content or not content.parts:
        return None
    for part in content.parts:
        text = getattr(part, 'text', None)
        if not text:
            continue
        url = text.strip()
        if url.startswith(_VERTEX_REDIRECT_PREFIX) or url.startswith('http'):
            return _resolve_redirect(url)

    return None


async def replace_redirect_with_clean_url(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    del callback_context

    clean_url = clean_links_from_response(llm_response)
    if not clean_url:
        # Return None so intermediate streaming events pass through unchanged
        return None
    
    print(f'Original URL: {getattr(llm_response, "content", "")}\nClean URL: {clean_url}')

    return LlmResponse(
        content=types.Content(
            role='model',
            parts=[types.Part.from_text(text=clean_url)],
        )
    )
