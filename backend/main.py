import os
import uuid
import json
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from graph.graph_builder import get_graph
from memory.persistence import (
    create_session,
    get_all_sessions,
    delete_session,
    session_exists,
    update_session_name,
    append_messages,
    load_messages,
)
from vectorstore.chroma import ingest_file, collection_count

app = FastAPI(title="Neural Search API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class NewSessionRequest(BaseModel):
    name: str = ""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "docs_count": collection_count()}


@app.post("/api/sessions")
def new_session(req: NewSessionRequest):
    session_id = str(uuid.uuid4())
    session = create_session(session_id, req.name)
    return session


@app.get("/api/sessions")
def list_sessions():
    return get_all_sessions()


@app.delete("/api/sessions/{session_id}")
def remove_session(session_id: str):
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    return {"session_id": session_id, "messages": load_messages(session_id)}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if not session_exists(req.session_id):
        first_words = " ".join(req.message.split()[:6])
        create_session(req.session_id, first_words)

    graph = get_graph()
    config = {"configurable": {"thread_id": req.session_id}}

    async def generate():
        try:
            result = graph.invoke(
                {"messages": [HumanMessage(content=req.message)]},
                config=config,
            )

            messages = result.get("messages", [])
            route = result.get("route", "internal")
            sources = result.get("sources", [])

            last_ai = next(
                (m for m in reversed(messages) if m.type == "ai"), None
            )
            content = last_ai.content if last_ai else "No response generated."

            # Persist messages to disk
            append_messages(req.session_id, req.message, content)

            # Update session name from first message
            existing = load_messages(req.session_id)
            if len([m for m in existing if m["role"] == "user"]) == 1:
                name = " ".join(req.message.split()[:6])
                update_session_name(req.session_id, name)

            payload = json.dumps({
                "content": content,
                "route": route,
                "sources": sources,
                "session_id": req.session_id,
            })
            yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            error_payload = json.dumps({"error": str(e)})
            yield f"data: {error_payload}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    allowed = {".pdf", ".txt", ".md"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' not supported. Use PDF, TXT, or MD.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        chunk_count = ingest_file(tmp_path)
    finally:
        os.unlink(tmp_path)

    return {
        "filename": file.filename,
        "chunks_ingested": chunk_count,
        "total_docs": collection_count(),
    }
