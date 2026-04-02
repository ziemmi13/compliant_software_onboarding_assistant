from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4

from google.adk.apps.app import App
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.utils.context_utils import Aclosing
from google.genai import types

from legal_scout import root_agent
from legal_scout.tools.find_terms_from_homepage import find_terms_from_homepage


@dataclass
class AgentAnalysisResult:
    raw_analysis: str
    source_links: list[str]
    blocked_links: list[str]


def validate_input_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed.")

    if not parsed.netloc:
        raise ValueError("URL must include a valid domain.")

    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Localhost URLs are not allowed.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Non-IP hosts are expected for normal domains.
        ip = None

    if ip and (ip.is_private or ip.is_loopback or ip.is_reserved):
        raise ValueError("Private or loopback IP URLs are not allowed.")

    return parsed.geturl()


async def run_terms_analysis(url: str) -> AgentAnalysisResult:
    discovered = find_terms_from_homepage(url)
    source_links = discovered.get("valid", [])
    blocked_links = discovered.get("blocked", [])

    app = App(name="legal_scout_web", root_agent=root_agent)
    session_service = InMemorySessionService()
    runner = Runner(
        app=app,
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
        credential_service=InMemoryCredentialService(),
    )

    user_id = "web_user"
    session_id = str(uuid4())
    await session_service.create_session(
        app_name=app.name,
        user_id=user_id,
        session_id=session_id,
    )

    prompt = (
        f"Analyze the Terms and Conditions for: {url}\n"
        "Return a concise summary and key clause highlights."
    )

    final_text = ""
    try:
        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        async with Aclosing(
            runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
        ) as event_stream:
            async for event in event_stream:
                if not event.content or not event.content.parts:
                    continue

                if event.author != "root_agent" or not event.is_final_response():
                    continue

                text_parts = [part.text or "" for part in event.content.parts if part.text]
                combined = "\n".join(part.strip() for part in text_parts if part.strip())
                if combined:
                    final_text = combined
    finally:
        await runner.close()

    if not final_text:
        raise RuntimeError("No analysis text was returned by the agent.")

    return AgentAnalysisResult(
        raw_analysis=final_text,
        source_links=source_links,
        blocked_links=blocked_links,
    )
