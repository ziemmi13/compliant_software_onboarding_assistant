from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import google_search

from .tools.link_cleaner import replace_redirect_with_clean_url

terms_search_agent = Agent(
    model='gemini-2.5-flash',
    name='terms_search_agent',
    description='A sub-agent for searching website terms & conditions.',
    instruction='You are a terms search assistant. Your task is to find the terms and conditions page for a given website. You will be provided with a user query that may contain a URL, domain, website name, or company name. Use the google_search tool to find the relevant page. Return a single final answer in one of these formats only: 1) the plain canonical page URL, or 2) NOT_FOUND. The URL must be human-readable: use the real destination page URL, include the https:// scheme when available, avoid Google redirect or tracking URLs, avoid markdown formatting, avoid link labels, avoid code fences, and avoid any extra words or punctuation.',
    tools=[google_search],
    after_model_callback=replace_redirect_with_clean_url,
    output_key='terms_url',
)
