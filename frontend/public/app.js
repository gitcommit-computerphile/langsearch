/* ── Marked.js config ─────────────────────────────────────────────────── */
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  },
});

/* ── State ───────────────────────────────────────────────────────────────── */
let currentSessionId = null;
let sessions = [];
let isLoading = false;

/* ── DOM refs ────────────────────────────────────────────────────────────── */
const sessionsList = document.getElementById("sessionsList");
const messagesContainer = document.getElementById("messagesContainer");
const welcomeScreen = document.getElementById("welcomeScreen");
const chatArea = document.getElementById("chatArea");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const charCount = document.getElementById("charCount");
const sessionInfo = document.getElementById("sessionInfo");
const routeIndicator = document.getElementById("routeIndicator");
const routeLabel = document.getElementById("routeLabel");
const routeDot = document.getElementById("routeDot");
const docsCount = document.getElementById("docsCount");
const uploadStatus = document.getElementById("uploadStatus");
const toastContainer = document.getElementById("toastContainer");

/* ── Activity bar panel switching ───────────────────────────────────────── */
document.getElementById("activityChat").addEventListener("click", () => {
  switchPanel("sessions");
});
document.getElementById("activityDocs").addEventListener("click", () => {
  switchPanel("docs");
});

function switchPanel(panel) {
  document.getElementById("panelSessions").style.display = panel === "sessions" ? "flex" : "none";
  document.getElementById("panelDocs").style.display = panel === "docs" ? "flex" : "none";
  document.getElementById("activityChat").classList.toggle("active", panel === "sessions");
  document.getElementById("activityDocs").classList.toggle("active", panel === "docs");
  if (panel === "docs") loadDocsCount();
}

/* ── Session management ──────────────────────────────────────────────────── */
async function loadSessions() {
  try {
    const res = await fetch("/api/sessions");
    sessions = await res.json();
    renderSessionsList();
  } catch (e) {
    console.error("Failed to load sessions:", e);
  }
}

function renderSessionsList() {
  if (sessions.length === 0) {
    sessionsList.innerHTML = '<div class="empty-state">No sessions yet.<br/>Click + to start.</div>';
    return;
  }
  sessionsList.innerHTML = sessions
    .map(
      (s) => `
    <div class="session-item ${s.id === currentSessionId ? "active" : ""}"
         onclick="selectSession('${s.id}')" data-id="${s.id}">
      <div class="session-dot"></div>
      <span class="session-name" title="${escHtml(s.name)}">${escHtml(s.name)}</span>
      <button class="session-delete" onclick="deleteSession(event, '${s.id}')" title="Delete">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>`
    )
    .join("");
}

async function selectSession(id) {
  currentSessionId = id;
  renderSessionsList();
  messagesContainer.innerHTML = "";
  welcomeScreen.style.display = "none";
  messagesContainer.style.display = "flex";
  hideRouteIndicator();

  const s = sessions.find((x) => x.id === id);
  sessionInfo.textContent = s ? `Session: ${s.name.substring(0, 30)}` : `Session: ${id.substring(0, 8)}...`;

  try {
    const res = await fetch(`/api/history/${id}`);
    const data = await res.json();
    if (data.messages && data.messages.length > 0) {
      data.messages.forEach((msg) => {
        if (msg.role === "user") appendUserMessage(msg.content);
        else appendAssistantMessage(msg.content, null, null);
      });
      scrollToBottom();
    }
  } catch (e) {
    console.error("Failed to load history:", e);
  }
}

async function createNewSession() {
  try {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "" }),
    });
    const session = await res.json();
    sessions.unshift(session);
    renderSessionsList();
    await selectSession(session.id);
    messageInput.focus();
  } catch (e) {
    showToast("Failed to create session", "error");
  }
}

async function deleteSession(event, id) {
  event.stopPropagation();
  try {
    await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    sessions = sessions.filter((s) => s.id !== id);
    if (currentSessionId === id) {
      currentSessionId = null;
      messagesContainer.innerHTML = "";
      messagesContainer.style.display = "none";
      welcomeScreen.style.display = "flex";
      sessionInfo.textContent = "No session selected";
      hideRouteIndicator();
    }
    renderSessionsList();
    showToast("Session deleted", "success");
  } catch (e) {
    showToast("Failed to delete session", "error");
  }
}

document.getElementById("btnNewChat").addEventListener("click", createNewSession);

/* ── Chat ────────────────────────────────────────────────────────────────── */
function insertPrompt(text) {
  if (!currentSessionId) createNewSession().then(() => { messageInput.value = text; autoResize(); });
  else { messageInput.value = text; autoResize(); messageInput.focus(); }
}
window.insertPrompt = insertPrompt;

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isLoading) return;

  if (!currentSessionId) {
    await createNewSession();
  }

  isLoading = true;
  setSendingState(true);

  welcomeScreen.style.display = "none";
  messagesContainer.style.display = "flex";
  messageInput.value = "";
  charCount.textContent = "0 / 4000";
  autoResize();

  appendUserMessage(text);
  const typingEl = appendTypingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: currentSessionId, message: text }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") break;
        try {
          const payload = JSON.parse(data);
          typingEl.remove();
          if (payload.error) {
            appendErrorMessage(payload.error);
          } else {
            appendAssistantMessage(payload.content, payload.route, payload.sources);
            showRouteIndicator(payload.route);

            // Refresh session name from server
            const idx = sessions.findIndex((s) => s.id === currentSessionId);
            if (idx !== -1) {
              const sessionRes = await fetch("/api/sessions");
              sessions = await sessionRes.json();
              renderSessionsList();
            }
          }
        } catch (_) {}
      }
    }
  } catch (e) {
    typingEl.remove();
    appendErrorMessage("Network error: " + e.message);
  } finally {
    isLoading = false;
    setSendingState(false);
    scrollToBottom();
  }
}

function setSendingState(sending) {
  sendBtn.disabled = sending;
  messageInput.disabled = sending;
}

/* ── Message rendering ───────────────────────────────────────────────────── */
function appendUserMessage(content) {
  const el = document.createElement("div");
  el.className = "message user";
  el.innerHTML = `
    <div class="message-avatar">U</div>
    <div class="message-body">
      <div class="message-header">
        <span class="message-role">You</span>
      </div>
      <div class="message-content">${escHtml(content)}</div>
    </div>`;
  messagesContainer.appendChild(el);
  scrollToBottom();
}

function appendAssistantMessage(content, route, sources) {
  const el = document.createElement("div");
  el.className = "message assistant";

  const routeBadge = route
    ? `<span class="route-badge ${route}">${routeLabel_(route)}</span>`
    : "";

  const sourcesBar = buildSourcesBar(sources);

  el.innerHTML = `
    <div class="message-avatar">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>
      </svg>
    </div>
    <div class="message-body">
      <div class="message-header">
        <span class="message-role">Neural Search</span>
        ${routeBadge}
      </div>
      <div class="message-content">${marked.parse(content)}</div>
      ${sourcesBar}
    </div>`;

  // Apply syntax highlighting to code blocks
  el.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));

  messagesContainer.appendChild(el);
  scrollToBottom();
}

function appendTypingIndicator() {
  const el = document.createElement("div");
  el.className = "typing-indicator";
  el.innerHTML = `
    <div class="message-avatar" style="background:linear-gradient(135deg,#264f78,#1a3a5c);display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:4px;flex-shrink:0;">
      <svg viewBox="0 0 24 24" fill="none" stroke="#007acc" stroke-width="1.5" style="width:16px;height:16px;">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>
      </svg>
    </div>
    <div class="typing-dots">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  messagesContainer.appendChild(el);
  scrollToBottom();
  return el;
}

function appendErrorMessage(text) {
  const el = document.createElement("div");
  el.className = "message assistant";
  el.innerHTML = `
    <div class="message-avatar" style="background:#3a1a1a;color:#f44747;font-size:16px;width:28px;height:28px;border-radius:4px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">!</div>
    <div class="message-body">
      <div class="message-header"><span class="message-role" style="color:#f44747;">Error</span></div>
      <div class="message-content" style="color:#f44747;">${escHtml(text)}</div>
    </div>`;
  messagesContainer.appendChild(el);
}

function buildSourcesBar(sources) {
  if (!sources || sources.length === 0) return "";
  const chips = sources
    .map((s) => `<span class="source-chip" title="${escHtml(s.snippet || '')}">${escHtml(s.title)}</span>`)
    .join("");
  return `<div class="sources-bar"><span class="sources-label">Sources</span>${chips}</div>`;
}

/* ── Route indicator ─────────────────────────────────────────────────────── */
function showRouteIndicator(route) {
  if (!route) return;
  routeIndicator.style.display = "flex";
  routeIndicator.className = `route-indicator route-${route}`;
  routeLabel.textContent = routeLabel_(route);
}

function hideRouteIndicator() {
  routeIndicator.style.display = "none";
}

function routeLabel_(route) {
  return { tools: "Tools", vectordb: "Vector DB", internal: "Internal" }[route] || route;
}

/* ── Document upload ─────────────────────────────────────────────────────── */
async function uploadFile(file) {
  const allowed = [".pdf", ".txt", ".md"];
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!allowed.includes(ext)) {
    showUploadStatus(`File type '${ext}' not supported`, "error");
    return;
  }

  showUploadStatus("Uploading...", "");
  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch("/api/documents", { method: "POST", body: form });
    const data = await res.json();
    if (res.ok) {
      showUploadStatus(`✓ ${data.filename} — ${data.chunks_ingested} chunks ingested`, "success");
      loadDocsCount();
      showToast(`Uploaded: ${data.filename}`, "success");
    } else {
      showUploadStatus(data.detail || "Upload failed", "error");
    }
  } catch (e) {
    showUploadStatus("Upload failed: " + e.message, "error");
  }
}

function showUploadStatus(msg, type) {
  uploadStatus.style.display = "block";
  uploadStatus.textContent = msg;
  uploadStatus.className = `upload-status ${type}`;
}

async function loadDocsCount() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    docsCount.textContent = `${data.docs_count} document chunks indexed`;
  } catch (_) {
    docsCount.textContent = "Unable to reach backend";
  }
}

// File inputs
["fileInput", "fileInput2"].forEach((id) => {
  document.getElementById(id).addEventListener("change", (e) => {
    if (e.target.files[0]) uploadFile(e.target.files[0]);
    e.target.value = "";
  });
});

// Drag-drop on upload zone
const uploadZone = document.getElementById("uploadZone");
uploadZone.addEventListener("dragover", (e) => { e.preventDefault(); uploadZone.style.borderColor = "var(--accent)"; });
uploadZone.addEventListener("dragleave", () => { uploadZone.style.borderColor = ""; });
uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.style.borderColor = "";
  if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});

/* ── Input handling ──────────────────────────────────────────────────────── */
messageInput.addEventListener("input", () => {
  autoResize();
  charCount.textContent = `${messageInput.value.length} / 4000`;
});

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

function autoResize() {
  messageInput.style.height = "auto";
  messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + "px";
}

/* ── Utilities ───────────────────────────────────────────────────────────── */
function scrollToBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function showToast(msg, type = "") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

/* ── Init ────────────────────────────────────────────────────────────────── */
loadSessions();
messageInput.focus();
