"""Fetcher agent: downloads T&C page content from a URL in session state."""

from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools.function_tool import FunctionTool

from .tools.fetch_page import fetch_page

_INSTRUCTION = (Path(__file__).parent / 'terms_fetcher_agent.md').read_text(encoding='utf-8')

terms_fetcher_agent = Agent(
    model='gemini-2.5-flash',
    name='terms_fetcher_agent',
    description='Downloads and extracts plain text from a Terms & Conditions page URL.',
    instruction=_INSTRUCTION,
    tools=[FunctionTool(fetch_page)],
    output_key='terms_text',
)
