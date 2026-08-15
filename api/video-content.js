const OPENAI_BASE_URL = "https://api.openai.com/v1";
const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta";

module.exports = async function handler(req, res) {
  if (req.method !== "GET") {
    sendJson(res, 405, { ok: false, error: "Method not allowed" });
    return;
  }

  if (String(getQueryValue(req, "provider")).toLowerCase() === "google") {
    await downloadGoogleVideo(req, res);
    return;
  }

  const apiKey = String(process.env.OPENAI_API_KEY || getQueryValue(req, "client_key") || "").trim();
  if (!apiKey) {
    sendJson(res, 400, {
      ok: false,
      error: "OpenAI API key 未填写；无法下载真实视频内容。",
    });
    return;
  }

  const id = getQueryValue(req, "id");
  if (!id) {
    sendJson(res, 400, { ok: false, error: "video id is required" });
    return;
  }

  try {
    const upstream = await fetch(`${OPENAI_BASE_URL}/videos/${encodeURIComponent(id)}/content`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!upstream.ok) {
      const text = await upstream.text();
      sendJson(res, upstream.status, { ok: false, error: text || `OpenAI HTTP ${upstream.status}` });
      return;
    }

    const buffer = Buffer.from(await upstream.arrayBuffer());
    res.statusCode = 200;
    res.setHeader("content-type", upstream.headers.get("content-type") || "video/mp4");
    res.setHeader("cache-control", "no-store");
    res.end(buffer);
  } catch (error) {
    sendJson(res, 500, { ok: false, error: error.message || "video download failed" });
  }
};

async function downloadGoogleVideo(req, res) {
  const apiKey = String(process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY || getQueryValue(req, "client_key") || "").trim();
  if (!apiKey) {
    sendJson(res, 400, {
      ok: false,
      error: "Google Gemini API key 未填写；无法下载 Veo 视频内容。",
    });
    return;
  }

  const uri = getQueryValue(req, "uri");
  if (!uri) {
    sendJson(res, 400, { ok: false, error: "google video uri is required" });
    return;
  }

  try {
    const target = uri.startsWith("http") ? uri : `${GEMINI_BASE_URL}/${uri.replace(/^\/+/, "")}`;
    const upstream = await fetch(target, {
      headers: { "x-goog-api-key": apiKey },
      redirect: "follow",
    });
    if (!upstream.ok) {
      const text = await upstream.text();
      sendJson(res, upstream.status, { ok: false, error: text || `Google Gemini HTTP ${upstream.status}` });
      return;
    }

    const buffer = Buffer.from(await upstream.arrayBuffer());
    res.statusCode = 200;
    res.setHeader("content-type", upstream.headers.get("content-type") || "video/mp4");
    res.setHeader("cache-control", "no-store");
    res.end(buffer);
  } catch (error) {
    sendJson(res, 500, { ok: false, error: error.message || "google video download failed" });
  }
}

function getQueryValue(req, key) {
  if (req.query && req.query[key]) return String(req.query[key]);
  const parsed = new URL(req.url || "/", `http://${req.headers?.host || "127.0.0.1"}`);
  return parsed.searchParams.get(key) || "";
}

function sendJson(res, status, payload) {
  if (typeof res.status === "function") {
    res.status(status).json(payload);
    return;
  }
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}
