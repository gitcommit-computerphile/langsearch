from langgraph.graph import StateGraph, END
from graph.state import ChatState
from graph.nodes.router import router_node
from graph.nodes.tool_agent import tool_agent_node
from graph.nodes.vector_db import vector_db_node
from graph.nodes.internal import internal_knowledge_node
from memory.persistence import get_checkpointer


def route_decision(state: ChatState) -> str:
    route = state.get("route", "internal")
    if route == "tools":
        return "tool_agent"
    elif route == "vectordb":
        return "vector_db"
    return "internal_knowledge"


def build_graph():
    graph = StateGraph(ChatState)

    graph.add_node("router", router_node)
    graph.add_node("tool_agent", tool_agent_node)
    graph.add_node("vector_db", vector_db_node)
    graph.add_node("internal_knowledge", internal_knowledge_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "tool_agent": "tool_agent",
            "vector_db": "vector_db",
            "internal_knowledge": "internal_knowledge",
        },
    )

    graph.add_edge("tool_agent", END)
    graph.add_edge("vector_db", END)
    graph.add_edge("internal_knowledge", END)

    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
