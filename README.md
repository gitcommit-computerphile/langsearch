# LangSearch

A chatbot that figures out where to look before it answers. Ask who Alan Turing was and it checks Wikipedia. Ask it to explain a decorator in Python and it just answers. Ask about something you uploaded and it searches your documents instead.

## How it works

A small, fast model (`llama-3.1-8b-instant`) reads each message and decides where it should go, without answering it.

Real world questions, papers, and video requests get handed to a tool step that picks between Wikipedia, ArXiv, and YouTube search, sometimes more than one, then writes up the results into an answer. Groq's bigger model doesn't play nice with LangChain's native tool calling, so tool selection is just done by asking the LLM for a small JSON plan and running it manually.

Questions about uploaded files go to ChromaDB. Follow ups get rewritten into standalone questions first, so "what about the second one" still means something once it hits the vector store. Embeddings run locally, no extra API needed.

Everything else (reasoning, code, writing, general knowledge) goes straight to the larger model (`llama-3.3-70b-versatile`) with the conversation history attached.

It's all wired together in LangGraph. Message history is also written to JSON files per session, since the SQLite checkpointer doesn't have a Python 3.14 build yet.

## Stack

Groq, LangGraph, ChromaDB, FastAPI backend, Express frontend with a VS Code style dark UI.

## Running it

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

```bash
cd frontend
node server.js
```

Open `http://localhost:3000`. You'll need a Groq key in `backend/.env`:

```
GROQ_API_KEY=your_key_here
```