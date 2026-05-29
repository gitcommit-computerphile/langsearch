from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    route: str          # "tools" | "vectordb" | "internal"
    sources: list[dict] # [{title, url, type, snippet}]
    session_id: str
