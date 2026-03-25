from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.terms_search_agent.agent import terms_search_agent
from .sub_agents.terms_analyzer_pipeline.agent import terms_analysis_pipeline

_INSTRUCTION = (Path(__file__).parent / 'root_agent.md').read_text(encoding='utf-8')

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='Root agent for legal scout application. Delegates to sub-agents based on the user request.',
    instruction=_INSTRUCTION,
    tools=[
        AgentTool(agent=terms_search_agent),
        AgentTool(agent=terms_analysis_pipeline),
    ],
)
