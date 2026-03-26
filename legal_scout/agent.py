from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.terms_agent.agent import terms_agent
from .tools.find_terms_from_homepage import find_terms_from_homepage

_INSTRUCTION = (Path(__file__).parent / 'root_agent.md').read_text(encoding='utf-8')

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='Root agent for legal help with software compliance checks.',
    instruction=_INSTRUCTION,
    tools=[
        AgentTool(agent=terms_agent),
        find_terms_from_homepage
    ],
)
