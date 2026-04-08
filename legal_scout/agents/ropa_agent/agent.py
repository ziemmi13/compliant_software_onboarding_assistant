from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_INSTRUCTION = (Path(__file__).parent / "ropa_agent.md").read_text(encoding="utf-8")

ropa_agent = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
)


def build_ropa_messages(prompt: str) -> list[SystemMessage | HumanMessage]:
    return [SystemMessage(content=_INSTRUCTION), HumanMessage(content=prompt)]