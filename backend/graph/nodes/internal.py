import os
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, AIMessage
from graph.state import ChatState

INTERNAL_SYSTEM_PROMPT = """You are a knowledgeable and helpful AI assistant. Answer questions clearly and concisely using your internal knowledge.

When answering:
- Be accurate and thoughtful
- Use markdown formatting for code, lists, and structured content
- If you're uncertain about something, say so
- For technical topics, provide concrete examples when helpful"""


def get_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.3,
        max_tokens=2048,
    )


def internal_knowledge_node(state: ChatState) -> ChatState:
    messages = state["messages"]
    llm = get_llm()

    all_messages = [SystemMessage(content=INTERNAL_SYSTEM_PROMPT)] + list(messages)
    response = llm.invoke(all_messages)

    return {
        "messages": [response],
        "sources": [{"type": "internal", "title": "Internal Knowledge", "url": ""}],
    }
