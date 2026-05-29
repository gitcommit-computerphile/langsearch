import os
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from vectorstore.chroma import get_retriever, collection_count
from graph.state import ChatState

CONTEXTUALIZE_PROMPT = """Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."""

QA_SYSTEM_PROMPT = """You are an assistant for question-answering tasks using retrieved document context. Use the following pieces of retrieved context to answer the question. If you don't know the answer from the context, say that you don't know. Keep the answer concise and accurate.

Context:
{context}"""


def get_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.1,
        max_tokens=2048,
    )


def vector_db_node(state: ChatState) -> ChatState:
    if collection_count() == 0:
        return {
            "messages": [AIMessage(content=(
                "No documents have been uploaded to the knowledge base yet. "
                "Please upload a PDF or text file using the upload button, then ask your question again."
            ))],
            "sources": [{"type": "vectordb", "title": "Knowledge Base (empty)", "url": ""}],
        }

    llm = get_llm()
    retriever = get_retriever(k=4)
    messages = list(state["messages"])

    last_human = next((m for m in reversed(messages) if m.type == "human"), None)
    query = last_human.content if last_human else ""
    chat_history = messages[:-1] if messages else []

    # Step 1: reformulate query to be standalone (history-aware)
    if chat_history:
        contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system", CONTEXTUALIZE_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        standalone_chain = contextualize_prompt | llm | StrOutputParser()
        standalone_q = standalone_chain.invoke({"input": query, "chat_history": chat_history})
    else:
        standalone_q = query

    # Step 2: retrieve relevant chunks
    docs = retriever.invoke(standalone_q)
    context = "\n\n".join(doc.page_content for doc in docs)

    # Step 3: answer using retrieved context
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", QA_SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    qa_chain = qa_prompt | llm | StrOutputParser()
    answer = qa_chain.invoke({"input": query, "chat_history": chat_history, "context": context})

    # Build source list
    sources = []
    seen = set()
    for doc in docs:
        src = doc.metadata.get("source", "Uploaded Document")
        if src not in seen:
            seen.add(src)
            sources.append({
                "type": "vectordb",
                "title": src,
                "url": "",
                "snippet": doc.page_content[:150],
            })

    return {
        "messages": [AIMessage(content=answer)],
        "sources": sources or [{"type": "vectordb", "title": "Knowledge Base", "url": ""}],
    }