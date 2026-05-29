import json
from datetime import datetime
from pathlib import Path

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    _USE_SQLITE = True
except (ModuleNotFoundError, ImportError):
    from langgraph.checkpoint.memory import MemorySaver
    _USE_SQLITE = False

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "checkpoints.db"
SESSIONS_PATH = DATA_DIR / "sessions.json"
MESSAGES_DIR = DATA_DIR / "messages"

# Keep a single MemorySaver instance so history survives reloads within same process
_memory_saver = None


def get_checkpointer():
    global _memory_saver
    DATA_DIR.mkdir(exist_ok=True)
    if _USE_SQLITE:
        return SqliteSaver.from_conn_string(str(DB_PATH))
    if _memory_saver is None:
        _memory_saver = MemorySaver()
    return _memory_saver


# ── JSON message history (persists across restarts) ───────────────────────────

def save_messages(session_id: str, messages: list) -> None:
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = MESSAGES_DIR / f"{session_id}.json"
    serializable = []
    for msg in messages:
        if hasattr(msg, "type") and hasattr(msg, "content") and msg.type in ("human", "ai"):
            serializable.append({
                "role": "user" if msg.type == "human" else "assistant",
                "content": msg.content,
            })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def load_messages(session_id: str) -> list[dict]:
    path = MESSAGES_DIR / f"{session_id}.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_messages(session_id: str, user_text: str, assistant_text: str) -> None:
    existing = load_messages(session_id)
    existing.append({"role": "user",      "content": user_text})
    existing.append({"role": "assistant", "content": assistant_text})
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = MESSAGES_DIR / f"{session_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def delete_messages(session_id: str) -> None:
    path = MESSAGES_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


# ── Session metadata ──────────────────────────────────────────────────────────

def _load_sessions() -> dict:
    if SESSIONS_PATH.exists():
        with open(SESSIONS_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_sessions(sessions: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(SESSIONS_PATH, "w") as f:
        json.dump(sessions, f, indent=2)


def create_session(session_id: str, name: str = "") -> dict:
    sessions = _load_sessions()
    session = {
        "id": session_id,
        "name": name or f"Chat {len(sessions) + 1}",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    sessions[session_id] = session
    _save_sessions(sessions)
    return session


def update_session_name(session_id: str, name: str) -> None:
    sessions = _load_sessions()
    if session_id in sessions:
        sessions[session_id]["name"] = name[:60]
        sessions[session_id]["updated_at"] = datetime.utcnow().isoformat()
        _save_sessions(sessions)


def get_all_sessions() -> list[dict]:
    sessions = _load_sessions()
    return sorted(sessions.values(), key=lambda s: s["updated_at"], reverse=True)


def delete_session(session_id: str) -> bool:
    sessions = _load_sessions()
    if session_id not in sessions:
        return False
    del sessions[session_id]
    _save_sessions(sessions)
    delete_messages(session_id)
    return True


def session_exists(session_id: str) -> bool:
    return session_id in _load_sessions()