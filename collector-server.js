#!/usr/bin/env node

const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");
const apiHandler = require("./api/marketplace-collect.js");
const videoPipelineHandler = require("./api/video-pipeline.js");
const videoContentHandler = require("./api/video-content.js");
const parseUploadHandler = require("./api/parse-upload.js");
const exportKeywordXlsxHandler = require("./api/export-keyword-xlsx.js");

const rootDir = __dirname;
loadLocalEnv(path.join(rootDir, ".env.local"));
const port = Number(process.env.PORT || 8066);

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".txt": "text/plain; charset=utf-8",
};

const server = http.createServer(async (req, res) => {
  try {
    setCors(res);
    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }
    const url = new URL(req.url, `http://${req.headers.host || "127.0.0.1"}`);
    if (req.method === "POST" && url.pathname === "/api/marketplace-collect") {
      req.body = await readJson(req);
      await apiHandler(req, wrapResponse(res));
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/video-pipeline") {
      req.body = await readJson(req);
      await videoPipelineHandler(req, wrapResponse(res));
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/parse-upload") {
      req.body = await readJson(req);
      await parseUploadHandler(req, wrapResponse(res));
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/export-keyword-xlsx") {
      req.body = await readJson(req);
      await exportKeywordXlsxHandler(req, wrapResponse(res));
      return;
    }
    if (req.method === "GET" && url.pathname === "/api/video-content") {
      req.query = Object.fromEntries(url.searchParams.entries());
      await videoContentHandler(req, wrapResponse(res));
      return;
    }
    if (req.method === "GET" || req.method === "HEAD") {
      await serveStatic(url.pathname, req, res);
      return;
    }
    sendText(res, 405, "Method not allowed");
  } catch (error) {
    res.statusCode = 500;
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ ok: false, error: error.message || "server error" }));
  }
});

function loadLocalEnv(filePath) {
  try {
    const content = require("node:fs").readFileSync(filePath, "utf8");
    for (const line of content.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const index = trimmed.indexOf("=");
      const key = trimmed.slice(0, index).trim();
      const value = trimmed.slice(index + 1).trim().replace(/^["']|["']$/g, "");
      if (key && process.env[key] === undefined) process.env[key] = value;
    }
  } catch {
    // .env.local is optional for local development.
  }
}

server.listen(port, "::", () => {
  console.log(`Marketplace Listing Agent running at http://127.0.0.1:${port}`);
});

function setCors(res) {
  res.setHeader("access-control-allow-origin", "*");
  res.setHeader("access-control-allow-methods", "GET,POST,OPTIONS");
  res.setHeader("access-control-allow-headers", "content-type");
}

async function serveStatic(pathname, req, res) {
  const safePath = pathname === "/" ? "/index.html" : pathname;
  const filePath = path.normalize(path.join(rootDir, safePath));
  if (!filePath.startsWith(rootDir)) {
    sendText(res, 403, "Forbidden");
    return;
  }
  try {
    const content = await fs.readFile(filePath);
    res.writeHead(200, {
      "content-type": mimeTypes[path.extname(filePath).toLowerCase()] || "application/octet-stream",
      "cache-control": "no-store",
    });
    if (req.method === "HEAD") res.end();
    else res.end(content);
  } catch {
    sendText(res, 404, "Not found");
  }
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 24 * 1024 * 1024) {
        reject(new Error("Request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(body || "{}"));
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

function wrapResponse(res) {
  return {
    status(code) {
      res.statusCode = code;
      return this;
    },
    setHeader(name, value) {
      res.setHeader(name, value);
      return this;
    },
    json(payload) {
      res.setHeader("content-type", "application/json; charset=utf-8");
      res.end(JSON.stringify(payload));
    },
    end(payload) {
      res.end(payload);
    },
  };
}

function sendText(res, status, text) {
  res.writeHead(status, { "content-type": "text/plain; charset=utf-8" });
  res.end(text);
}
