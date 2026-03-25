"""Fetcher agent: downloads T&C page content from a URL in session state."""

from google.adk.agents.llm_agent import Agent
from google.adk.tools.function_tool import FunctionTool

from .tools.fetch_page import fetch_page

terms_fetcher_agent = Agent(
    model='gemini-2.5-flash',
    name='terms_fetcher_agent',
    description='Downloads and extracts plain text from a Terms & Conditions page URL.',
    instruction=(
        'You receive a T&C page URL from the session state key `terms_url`. '
        'Call the `fetch_page` tool with that exact URL. '
        'Return the fetched text verbatim — do not summarize, modify, or analyze it. '
        'If the result starts with FETCH_ERROR, return that error message as-is.'
    ),
    tools=[FunctionTool(fetch_page)],
    output_key='terms_text',
)
