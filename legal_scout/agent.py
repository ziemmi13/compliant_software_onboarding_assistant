from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.terms_search_agent.agent import terms_search_agent


root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='Root agent for legal scout application. Delegates to sub-agents based on the user request.',
    instruction=(
        'You are a legal scout assistant. You have access to a tool sub-agent called "terms_search_agent". '
        'If the user message contains a URL, domain, website name, or company name, you must call '
        '"terms_search_agent". If the user asks to find terms, privacy, legal, policy, conditions, or similar '
        'website pages, you must call "terms_search_agent". For those lookup requests, do not answer from your '
        'own knowledge and do not provide a generic fallback response. Return the tool result to the user exactly '
        'as a plain human-readable URL string, with no markdown formatting, no link labels, and no extra text. '
        'Only answer directly when the request is clearly a general legal-information question and not a website '
        'page lookup task.'
    ),
    tools=[AgentTool(agent=terms_search_agent)],
)
