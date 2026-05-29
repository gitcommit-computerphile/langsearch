import os
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from graph.state import ChatState

ROUTER_SYSTEM_PROMPT = """You are a query router. Classify the user message into exactly one of three categories:

- "tools": Use this when the user wants to search for information externally. Examples:
  * Questions about real people, places, or events ("who is X", "what is X")
  * Requests for YouTube videos ("find videos", "show me videos", "give me youtube", "tutorials on X")
  * YouTube URLs (youtube.com links)
  * Academic paper searches ("papers on X", "research about X", "arxiv")
  * Any search or lookup of factual/current information

- "vectordb": Use this ONLY when the user explicitly references uploaded documents or files. Examples:
  * "in the document", "from the PDF", "according to the file", "what does the document say"

- "internal": Use this for reasoning, coding, math, creative writing, or general knowledge that doesn't need a search. Examples:
  * "explain X", "write code for X", "what is the difference between X and Y", "how does X work"

When in doubt between tools and internal, prefer "tools".
Reply with ONLY one word: tools, vectordb, or internal."""


def get_router_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0,
        max_tokens=10,
    )


def router_node(state: ChatState) -> ChatState:
    messages = state["messages"]
    last_human = next(
        (m for m in reversed(messages) if m.type == "human"), None
    )
    query = last_human.content if last_human else ""

    llm = get_router_llm()
    response = llm.invoke([
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ])

    raw = response.content.strip().lower()
    if "vectordb" in raw or "vector" in raw or "document" in raw:
        route = "vectordb"
    elif "tools" in raw or "tool" in raw:
        route = "tools"
    else:
        route = "internal"

    return {"route": route, "sources": []}
