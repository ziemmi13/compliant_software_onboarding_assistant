from __future__ import annotations

from typing import Any
import logging

MAX_RETRIES = 3


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
                continue

            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())

        return "\n".join(parts)

    return ""


async def invoke_with_retry(
    *,
    llm: Any,
    messages: list[Any],
    logger: logging.Logger,
    label: str,
    max_retries: int = MAX_RETRIES,
) -> str:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = await llm.ainvoke(messages)
        except Exception as exc:
            last_error = exc
            logger.warning("%s invocation failed (attempt %d/%d): %s", label, attempt, max_retries, exc)
            continue

        final_text = _extract_text_content(getattr(response, "content", ""))
        if final_text:
            if attempt > 1:
                logger.info("%s succeeded on attempt %d/%d", label, attempt, max_retries)
            return final_text

        logger.warning("%s returned empty response (attempt %d/%d)", label, attempt, max_retries)

    if last_error is not None:
        raise RuntimeError(f"{label} failed after {max_retries} attempts.") from last_error

    raise RuntimeError(f"{label} returned no text after {max_retries} attempts.")
