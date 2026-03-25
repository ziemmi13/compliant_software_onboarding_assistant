from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import google_search

from .tools.link_cleaner import replace_redirect_with_clean_url

_INSTRUCTION = (Path(__file__).parent / 'terms_search_agent.md').read_text(encoding='utf-8')

terms_search_agent = Agent(
    model='gemini-2.5-flash',
    name='terms_search_agent',
    description='A sub-agent for searching website terms & conditions.',
    instruction=_INSTRUCTION,
    tools=[google_search],
    after_model_callback=replace_redirect_with_clean_url,
    output_key='terms_url',
)
