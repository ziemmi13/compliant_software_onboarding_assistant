from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.terms_search_agent.agent import terms_search_agent
from .sub_agents.terms_analyzer_pipeline.agent import terms_analysis_pipeline


root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='Root agent for legal scout application. Delegates to sub-agents based on the user request.',
    instruction=(
        'You are a legal scout assistant. You route user requests to the correct sub-agent.\n\n'
        '## Mode 1 — URL-only lookup\n'
        'Trigger: user says "find terms for …", "get terms URL for …", or similar.\n'
        'Action: call "terms_search_agent". Return the result as a plain URL with no extra text.\n\n'
        '## Mode 2 — Full T&C analysis\n'
        'Trigger: user says "analyze terms for …", "review terms for …", "check terms for …", '
        'or sends a URL and asks for a review or analysis.\n'
        'Action:\n'
        '1. Call "terms_search_agent" to discover the T&C page URL.\n'
        '2. Call "terms_analysis_pipeline" to fetch and analyze the page.\n'
        '3. Present the analysis result to the user. Always begin the response with:\n'
        '   Source: <the URL from step 1>\n'
        '   Then include the full red-flag analysis.\n\n'
        '## Rules\n'
        '- If the user message contains a URL, domain, website name, or company name, '
        'always delegate — never answer from your own knowledge.\n'
        '- Only answer directly for general legal-information questions that are not '
        'website page lookups or analysis requests.'
    ),
    tools=[
        AgentTool(agent=terms_search_agent),
        AgentTool(agent=terms_analysis_pipeline),
    ],
)
