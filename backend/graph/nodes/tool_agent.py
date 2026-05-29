import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from tools.search_tools import search_wikipedia, search_arxiv, search_youtube
from graph.state import ChatState

TOOLS = {
    "search_wikipedia": search_wikipedia,
    "search_arxiv": search_arxiv,
    "search_youtube": search_youtube,
}

SELECTOR_PROMPT = """You are a tool selector. Given a user query, decide which search tool(s) to use.

Available tools:
- search_wikipedia: people, places, history, biography, general facts
- search_arxiv: academic papers, research, science, machine learning, physics
- search_youtube: videos, tutorials, lectures, music, media

Important rules:
- If the query contains a YouTube URL (youtube.com/watch), extract a descriptive search query from the URL context or the surrounding text and use search_youtube.
- If the user explicitly asks for videos or YouTube content, always use search_youtube.
- The "query" must be a descriptive search phrase, never a URL.

Respond with a JSON array only. No explanation. Example:
[{"tool": "search_youtube", "query": "PyTorch neural network tutorial"}]

You may include multiple tools if needed."""

SYNTHESIS_PROMPT = """You are a helpful assistant. Using the search results below, answer the user's question clearly and concisely. Use markdown formatting where helpful.

{results}"""


def get_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.1,
        max_tokens=2048,
    )


def tool_agent_node(state: ChatState) -> ChatState:
    messages = list(state["messages"])
    last_human = next((m for m in reversed(messages) if m.type == "human"), None)
    query = last_human.content if last_human else ""
    llm = get_llm()

    # Step 1: select tools
    selector_response = llm.invoke([
        SystemMessage(content=SELECTOR_PROMPT),
        HumanMessage(content=query),
    ])

    try:
        raw = selector_response.content.strip()
        # Extract JSON array even if wrapped in markdown
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        tool_calls = json.loads(raw)
        if isinstance(tool_calls, dict):
            tool_calls = [tool_calls]
    except Exception:
        tool_calls = [{"tool": "search_wikipedia", "query": query}]

    # Step 2: execute tools
    results_text = []
    sources = []

    for call in tool_calls:
        tool_name = call.get("tool", "search_wikipedia")
        tool_query = call.get("query", query)

        if tool_name not in TOOLS:
            continue

        try:
            result = TOOLS[tool_name].invoke({"query": tool_query})
        except Exception as e:
            result = f"Search failed: {e}"

        results_text.append(f"### {tool_name.replace('_', ' ').title()}\n{result}")

        source_map = {
            "search_wikipedia": {"title": "Wikipedia", "url": "https://wikipedia.org"},
            "search_arxiv":     {"title": "ArXiv",     "url": "https://arxiv.org"},
            "search_youtube":   {"title": "YouTube",   "url": "https://youtube.com"},
        }
        if tool_name in source_map:
            sources.append({
                "type": tool_name,
                **source_map[tool_name],
                "snippet": str(result)[:200],
            })

    # Step 3: synthesize answer
    combined = "\n\n".join(results_text) if results_text else "No search results found."
    synthesis_response = llm.invoke([
        SystemMessage(content=SYNTHESIS_PROMPT.format(results=combined)),
        *messages,
    ])

    return {
        "messages": [AIMessage(content=synthesis_response.content)],
        "sources": sources,
    }