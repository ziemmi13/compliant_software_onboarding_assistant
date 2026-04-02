from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import google_search

_INSTRUCTION = (Path(__file__).parent / "dpa_agent.md").read_text(encoding="utf-8")

dpa_agent = Agent(
    model="gemini-2.5-flash",
    name="dpa_agent",
    description="An agent for reviewing data processing agreements and annexes.",
    instruction=_INSTRUCTION,
    tools=[google_search],
)