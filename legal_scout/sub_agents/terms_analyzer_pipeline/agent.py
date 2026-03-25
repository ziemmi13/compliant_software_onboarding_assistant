"""Sequential pipeline: fetch T&C page → analyze for red flags."""

from google.adk.agents.sequential_agent import SequentialAgent

from .terms_fetcher_agent import terms_fetcher_agent
from .terms_analyzer_agent import terms_analyzer_agent

terms_analysis_pipeline = SequentialAgent(
    name='terms_analysis_pipeline',
    description='Fetches a T&C page and analyzes it for red-flag clauses.',
    sub_agents=[terms_fetcher_agent, terms_analyzer_agent],
)
