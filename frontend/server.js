const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const path = require("path");

const app = express();
const PORT = 3000;
const BACKEND_URL = "http://localhost:8000";

// Proxy all /api/* requests to the Python backend (preserve /api prefix)
app.use(
  "/api",
  createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    pathRewrite: { "^": "/api" },
    on: {
      proxyReq: (proxyReq) => {
        proxyReq.setHeader("Connection", "keep-alive");
      },
    },
  })
);

// Serve static frontend files
app.use(express.static(path.join(__dirname, "public")));

// Fallback to index.html for SPA routing
app.get("*", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.listen(PORT, () => {
  console.log(`\n🚀 Neural Search running at http://localhost:${PORT}`);
  console.log(`   Backend API: ${BACKEND_URL}\n`);
});
