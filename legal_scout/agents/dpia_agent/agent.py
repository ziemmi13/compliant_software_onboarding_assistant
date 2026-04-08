from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import google_search

_INSTRUCTION = (Path(__file__).parent / "dpia_agent.md").read_text(encoding="utf-8")

dpia_agent = Agent(
    model="gemini-2.5-flash",
    name="dpia_agent",
    description="An agent for screening whether a DPIA is required and producing a preliminary DPIA under GDPR Article 35.",
    instruction=_INSTRUCTION,
    tools=[google_search],
)
