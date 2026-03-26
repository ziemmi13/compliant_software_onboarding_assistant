from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import google_search

_INSTRUCTION = (Path(__file__).parent / 'terms_agent.md').read_text(encoding='utf-8')

terms_agent = Agent(
    model='gemini-2.5-flash',
    name='terms_agent',
    description='A sub-agent for searching website terms & conditions.',
    instruction=_INSTRUCTION,
    tools=[google_search],
    # output_key='terms_url',
)
