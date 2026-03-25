"""Analyzer agent: scans T&C text for red-flag clauses."""

from pathlib import Path

from google.adk.agents.llm_agent import Agent

_INSTRUCTION = (Path(__file__).parent / 'terms_analyzer_agent.md').read_text(encoding='utf-8')

terms_analyzer_agent = Agent(
    model='gemini-2.5-flash',
    name='terms_analyzer_agent',
    description='Analyzes Terms & Conditions text for red-flag clauses.',
    instruction=_INSTRUCTION,
    output_key='analysis_result',
)
