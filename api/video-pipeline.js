const OPENAI_BASE_URL = "https://api.openai.com/v1";
const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta";

const IMAGE_MODELS = new Set(["gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"]);
const GOOGLE_IMAGE_MODELS = new Set(["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", "gemini-2.5-flash-image"]);
const VIDEO_MODELS = new Set(["sora-2", "sora-2-pro"]);
const GOOGLE_VIDEO_MODELS = new Set([
  "veo-3.1-generate-preview",
  "veo-3.1-fast-generate-preview",
  "veo-3.1-lite-generate-preview",
]);
const EXTERNAL_VIDEO_MODELS = new Set(["seedance", "kling"]);
const IMAGE_QUALITIES = new Set(["low", "medium", "high", "auto"]);
const VIDEO_SIZES = new Set(["720x1280", "1280x720", "1024x1792", "1792x1024"]);
const VIDEO_SECONDS = new Set(["4", "6", "8", "15", "22", "29", "36", "57", "85", "120", "148"]);
const OPENAI_VIDEO_SECONDS = new Set(["4", "8", "12"]);

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    sendJson(res, 405, { ok: false, error: "Method not allowed" });
    return;
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    if (body.action === "generate_image") {
      await generateImage(body, res);
      return;
    }
    if (body.action === "generate_video") {
      await generateVideo(body, res);
      return;
    }
    if (body.action === "extend_video") {
      await extendVideo(body, res);
      return;
    }
    if (body.action === "poll_video") {
      await pollVideo(body, res);
      return;
    }
    if (body.action === "list_videos") {
      await listVideos(body, res);
      return;
    }
    sendJson(res, 400, { ok: false, error: "Unknown video pipeline action" });
  } catch (error) {
    sendJson(res, 500, { ok: false, error: error.message || "video pipeline failed" });
  }
};

async function generateImage(body, res) {
  const model = String(body.model || "gemini-3.1-flash-image-preview");
  if (GOOGLE_IMAGE_MODELS.has(model)) {
    await generateGoogleImage(body, res, model);
    return;
  }
  if (!IMAGE_MODELS.has(model)) {
    const providerName = model === "external" ? "外部图片模型" : model;
    sendJson(res, 501, { ok: false, error: `${providerName} 尚未配置真实 API endpoint/key。` });
    return;
  }

  const apiKey = requireOpenAIKey(body, res);
  if (!apiKey) return;

  const prompt = String(body.prompt || "").trim();
  if (!prompt) {
    sendJson(res, 400, { ok: false, error: "prompt is required" });
    return;
  }

  const step = String(body.step || "product_reference");
  const quality = IMAGE_QUALITIES.has(String(body.quality)) ? String(body.quality) : "medium";
  const size = imageSizeForStep(step, body.videoSize);
  const outputFormat = "jpeg";
  const payload = { model, prompt, size, quality, output_format: outputFormat, output_compression: 86 };
  const data = await openAIJson("/images/generations", apiKey, payload);
  const image = data.data?.[0];
  const b64 = image?.b64_json;
  const imageDataUrl = b64 ? `data:image/${outputFormat};base64,${b64}` : image?.url;

  if (!imageDataUrl) {
    sendJson(res, 502, { ok: false, error: "OpenAI image response did not include image data" });
    return;
  }

  sendJson(res, 200, {
    ok: true,
    step,
    model,
    size,
    quality,
    outputFormat,
    imageDataUrl,
    usage: data.usage || null,
  });
}

async function generateGoogleImage(body, res, model) {
  const apiKey = requireGoogleKey(body, res);
  if (!apiKey) return;

  const prompt = String(body.prompt || "").trim();
  if (!prompt) {
    sendJson(res, 400, { ok: false, error: "prompt is required" });
    return;
  }

  const step = String(body.step || "product_reference");
  const quality = IMAGE_QUALITIES.has(String(body.quality)) ? String(body.quality) : "medium";
  const size = imageSizeForStep(step, body.videoSize);
  const aspectRatio = aspectRatioForSize(size);
  const imageSize = quality === "high" ? "2K" : "1K";
  const direction = [
    prompt,
    "",
    `Output one clean image only, no captions, no UI text, no watermark-like text. Target canvas ${size}, aspect ratio ${aspectRatio}.`,
    quality === "high" ? "Use high fidelity product detail, crisp edges, realistic materials." : "Use clean product detail and stable composition.",
  ].join("\n");

  const data = await googleImageJson(
    `/models/${encodeURIComponent(model)}:generateContent`,
    apiKey,
    {
      contents: [{ parts: [{ text: direction }] }],
      generationConfig: {
        responseModalities: ["TEXT", "IMAGE"],
        imageConfig: {
          aspectRatio,
          ...(model === "gemini-2.5-flash-image" ? {} : { imageSize }),
        },
      },
    },
  );
  const imagePart = findGoogleImagePart(data);
  if (!imagePart) {
    const text = findGoogleTextPart(data);
    throw new Error(text || "Google Gemini image response did not include image data");
  }

  const mimeType = imagePart.mimeType || imagePart.mime_type || "image/png";
  const imageDataUrl = `data:${mimeType};base64,${imagePart.data}`;
  sendJson(res, 200, {
    ok: true,
    step,
    provider: "google",
    model,
    size,
    quality,
    outputFormat: mimeType.split("/")[1] || "png",
    imageDataUrl,
    usage: data.usageMetadata || data.usage_metadata || null,
  });
}

async function generateVideo(body, res) {
  const model = String(body.model || "sora-2");
  if (GOOGLE_VIDEO_MODELS.has(model)) {
    await generateGoogleVideo(body, res, model);
    return;
  }
  if (EXTERNAL_VIDEO_MODELS.has(model)) {
    sendJson(res, 501, {
      ok: false,
      error: `${model} 还没有配置真实 API endpoint/key；当前已接 OpenAI Sora 和 Google Veo 3.1。`,
    });
    return;
  }
  if (!VIDEO_MODELS.has(model)) {
    sendJson(res, 400, { ok: false, error: "Unsupported video model" });
    return;
  }

  const apiKey = requireOpenAIKey(body, res);
  if (!apiKey) return;

  const prompt = String(body.prompt || "").trim();
  if (!prompt) {
    sendJson(res, 400, { ok: false, error: "prompt is required" });
    return;
  }

  const size = VIDEO_SIZES.has(String(body.size)) ? String(body.size) : "720x1280";
  const seconds = OPENAI_VIDEO_SECONDS.has(String(body.seconds)) ? String(body.seconds) : "4";
  const form = new FormData();
  form.append("model", model);
  form.append("prompt", prompt);
  form.append("size", size);
  form.append("seconds", seconds);
  const imageUrl = body.inputReference?.image_url;
  if (imageUrl) {
    if (String(imageUrl).length > 20 * 1024 * 1024) {
      sendJson(res, 400, { ok: false, error: "input_reference 超过 OpenAI 20MB data URL 限制。" });
      return;
    }
    const referenceFile = dataUrlToFile(imageUrl, "input_reference.jpg");
    form.append("input_reference", referenceFile, "input_reference.jpg");
  }

  const video = await openAIForm("/videos", apiKey, form);
  sendJson(res, 200, {
    ok: true,
    video,
    id: video.id,
    status: video.status,
    inputReferenceStep: body.inputReference?.step || null,
  });
}

async function listVideos(body, res) {
  if (String(body.provider || "").toLowerCase() === "google") {
    sendJson(res, 200, { ok: true, videos: [], object: "google_veo_operations", note: "Google Veo operations are checked by operation id." });
    return;
  }
  const apiKey = requireOpenAIKey(body, res);
  if (!apiKey) return;

  const limit = Math.max(1, Math.min(20, Number(body.limit || 8)));
  const order = body.order === "asc" ? "asc" : "desc";
  const payload = await openAIRequest(`/videos?limit=${limit}&order=${order}`, apiKey);
  sendJson(res, 200, { ok: true, videos: payload.data || [], object: payload.object || "list" });
}

async function extendVideo(body, res) {
  const model = String(body.model || "veo-3.1-generate-preview");
  if (!GOOGLE_VIDEO_MODELS.has(model)) {
    sendJson(res, 400, { ok: false, error: "Only Google Veo 3.1 videos can be extended here." });
    return;
  }
  if (model === "veo-3.1-lite-generate-preview") {
    sendJson(res, 400, { ok: false, error: "Veo 3.1 Lite 不支持视频延长；请选择 Google Veo 3.1 或 Fast。" });
    return;
  }

  const apiKey = requireGoogleKey(body, res);
  if (!apiKey) return;

  const videoUri = String(body.videoUri || "").trim();
  if (!videoUri) {
    sendJson(res, 400, { ok: false, error: "videoUri is required for Veo extension" });
    return;
  }

  const prompt = extensionPrompt(String(body.prompt || "").trim());
  const currentSeconds = Math.max(8, Number(body.currentSeconds || 8));
  const targetSeconds = normalizeGoogleTargetSeconds(body.targetSeconds || body.seconds || currentSeconds + 7);
  const nextSeconds = Math.min(148, Math.min(targetSeconds, currentSeconds + 7));
  const video = await fetchGoogleVideoInlineData(videoUri, apiKey);

  const operation = await googleJson(
    `/models/${encodeURIComponent(model)}:predictLongRunning`,
    apiKey,
    {
      instances: [{ prompt, video: { inlineData: video } }],
      parameters: {
        numberOfVideos: 1,
        resolution: "720p",
      },
    },
  );
  const extended = normalizeGoogleOperation(operation, {
    model,
    size: normalizeLongVideoSize(body.size),
    seconds: nextSeconds,
    targetSeconds,
    resolution: "720p",
  });
  sendJson(res, 200, {
    ok: true,
    video: extended,
    id: extended.id,
    status: extended.status,
  });
}

async function generateGoogleVideo(body, res, model) {
  const apiKey = requireGoogleKey(body, res);
  if (!apiKey) return;

  const prompt = String(body.prompt || "").trim();
  if (!prompt) {
    sendJson(res, 400, { ok: false, error: "prompt is required" });
    return;
  }

  const imageUrl = body.inputReference?.image_url;
  const targetSeconds = normalizeGoogleTargetSeconds(body.seconds);
  const longVideo = targetSeconds > 8;
  const size = longVideo ? normalizeLongVideoSize(body.size) : VIDEO_SIZES.has(String(body.size)) ? String(body.size) : "720x1280";
  const requestedSeconds = targetSeconds <= 8 ? targetSeconds : 8;
  const resolution = longVideo ? "720p" : size.includes("1024") || size.includes("1792") ? "1080p" : "720p";
  const durationSeconds = resolution === "720p" ? requestedSeconds : 8;
  const parameters = {
    aspectRatio: size.includes("x1280") || size.includes("x1792") ? "9:16" : "16:9",
    durationSeconds,
    resolution,
    personGeneration: imageUrl ? "allow_adult" : "allow_all",
    negativePrompt:
      "captions, subtitles, fake marketplace UI, fake logo, distorted hands, changing product shape, low quality",
  };

  const instance = { prompt };
  if (imageUrl) {
    const image = dataUrlToInlineData(imageUrl);
    instance.image = { bytesBase64Encoded: image.data, mimeType: image.mimeType };
  }

  let operation;
  try {
    operation = await googleJson(
      `/models/${encodeURIComponent(model)}:predictLongRunning`,
      apiKey,
      { instances: [instance], parameters },
    );
  } catch (error) {
    if (!imageUrl || !/image|inlineData|bytesBase64Encoded|supported/i.test(error.message || "")) throw error;
    operation = await googleJson(
      `/models/${encodeURIComponent(model)}:predictLongRunning`,
      apiKey,
      { instances: [{ prompt }], parameters: { ...parameters, personGeneration: "allow_all" } },
    );
  }
  const video = normalizeGoogleOperation(operation, { model, size, seconds: durationSeconds });
  video.targetSeconds = targetSeconds;
  video.resolution = resolution;
  sendJson(res, 200, {
    ok: true,
    video,
    id: video.id,
    status: video.status,
    inputReferenceStep: body.inputReference?.step || null,
  });
}

async function pollVideo(body, res) {
  if (isGoogleOperationId(body.id)) {
    await pollGoogleVideo(body, res);
    return;
  }
  const apiKey = requireOpenAIKey(body, res);
  if (!apiKey) return;

  const id = String(body.id || "").trim();
  if (!id) {
    sendJson(res, 400, { ok: false, error: "video id is required" });
    return;
  }

  const video = await openAIRequest(`/videos/${encodeURIComponent(id)}`, apiKey);
  sendJson(res, 200, {
    ok: true,
    video,
    contentUrl:
      video.status === "completed"
        ? buildVideoContentUrl(id, process.env.OPENAI_API_KEY ? "" : apiKey)
        : null,
  });
}

async function pollGoogleVideo(body, res) {
  const apiKey = requireGoogleKey(body, res);
  if (!apiKey) return;

  const id = String(body.id || "").trim();
  if (!id) {
    sendJson(res, 400, { ok: false, error: "operation id is required" });
    return;
  }

  const operation = await googleGet(`/${id.replace(/^\/+/, "")}`, apiKey);
  const video = normalizeGoogleOperation(operation, body);
  const uri = operation.response?.generateVideoResponse?.generatedSamples?.[0]?.video?.uri;
  sendJson(res, 200, {
    ok: true,
    video,
    contentUrl: uri ? buildGoogleVideoContentUrl(uri, process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY ? "" : apiKey) : null,
  });
}

async function openAIJson(path, apiKey, payload) {
  return openAIRequest(path, apiKey, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function openAIForm(path, apiKey, form) {
  return openAIRequest(path, apiKey, {
    method: "POST",
    body: form,
  });
}

async function openAIRequest(path, apiKey, init = {}) {
  const response = await fetch(`${OPENAI_BASE_URL}${path}`, {
    method: "GET",
    ...init,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      ...(init.headers || {}),
    },
  });
  const text = await response.text();
  const data = text ? safeJson(text) : {};
  if (!response.ok) {
    const message = data.error?.message || data.message || text || `OpenAI HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

async function googleJson(path, apiKey, payload) {
  return googleRequest(path, apiKey, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function googleImageJson(path, apiKey, payload) {
  return googleRequest(path, apiKey, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function googleGet(path, apiKey) {
  return googleRequest(path, apiKey);
}

async function googleRequest(path, apiKey, init = {}) {
  const { baseUrl = GEMINI_BASE_URL, ...requestInit } = init;
  const response = await fetch(`${baseUrl}${path}`, {
    method: "GET",
    ...requestInit,
    headers: {
      "x-goog-api-key": apiKey,
      ...(requestInit.headers || {}),
    },
  });
  const text = await response.text();
  const data = text ? safeJson(text) : {};
  if (!response.ok) {
    const message = data.error?.message || data.message || text || `Google Gemini HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

function requireOpenAIKey(body, res) {
  const apiKey = String(body.apiKey || process.env.OPENAI_API_KEY || "").trim();
  if (!apiKey) {
    sendJson(res, 400, {
      ok: false,
      error: "OpenAI API key 未填写；可以在网页测试输入框填 key，或配置 OPENAI_API_KEY。",
    });
    return "";
  }
  return apiKey;
}

function requireGoogleKey(body, res) {
  const apiKey = String(body.googleApiKey || process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY || "").trim();
  if (!apiKey) {
    sendJson(res, 400, {
      ok: false,
      error: "Google Gemini API key 未填写；请在网页 Google Gemini API Key 输入框填 AIza...，或配置 GOOGLE_API_KEY/GEMINI_API_KEY。",
    });
    return "";
  }
  return apiKey;
}

function buildVideoContentUrl(id, clientApiKey) {
  const params = new URLSearchParams({ id });
  if (clientApiKey) params.set("client_key", clientApiKey);
  return `/api/video-content?${params.toString()}`;
}

function buildGoogleVideoContentUrl(uri, clientApiKey) {
  const params = new URLSearchParams({ provider: "google", uri });
  if (clientApiKey) params.set("client_key", clientApiKey);
  return `/api/video-content?${params.toString()}`;
}

async function fetchGoogleVideoInlineData(uri, apiKey) {
  const target = uri.startsWith("http") ? uri : `${GEMINI_BASE_URL}/${uri.replace(/^\/+/, "")}`;
  const response = await fetch(target, {
    headers: { "x-goog-api-key": apiKey },
    redirect: "follow",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Google Gemini HTTP ${response.status}`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  return {
    mimeType: response.headers.get("content-type") || "video/mp4",
    data: buffer.toString("base64"),
  };
}

function dataUrlToFile(dataUrl, filename) {
  const match = String(dataUrl).match(/^data:([^;,]+)?(;base64)?,(.*)$/);
  if (!match) throw new Error("input_reference 必须是 data URL");
  const mimeType = match[1] || "image/jpeg";
  const isBase64 = Boolean(match[2]);
  const payload = match[3] || "";
  const buffer = isBase64 ? Buffer.from(payload, "base64") : Buffer.from(decodeURIComponent(payload));
  return new File([buffer], filename, { type: mimeType });
}

function dataUrlToInlineData(dataUrl) {
  const match = String(dataUrl).match(/^data:([^;,]+)?(;base64)?,(.*)$/);
  if (!match) throw new Error("input_reference 必须是 data URL");
  const mimeType = match[1] || "image/jpeg";
  const isBase64 = Boolean(match[2]);
  const payload = match[3] || "";
  const data = isBase64 ? payload : Buffer.from(decodeURIComponent(payload)).toString("base64");
  return { mimeType, data };
}

function findGoogleImagePart(data) {
  const parts = data.candidates?.[0]?.content?.parts || [];
  for (const part of parts) {
    const inlineData = part.inlineData || part.inline_data;
    if (inlineData?.data) return inlineData;
  }
  return null;
}

function findGoogleTextPart(data) {
  const parts = data.candidates?.[0]?.content?.parts || [];
  return parts.find((part) => part.text)?.text || "";
}

function normalizeGoogleOperation(operation, fallback = {}) {
  const done = Boolean(operation.done);
  const error = operation.error || null;
  const status = error ? "failed" : done ? "completed" : "in_progress";
  const sample = operation.response?.generateVideoResponse?.generatedSamples?.[0];
  const metadataProgress = Number(
    operation.metadata?.progressPercentage ??
      operation.metadata?.progress_percent ??
      operation.metadata?.progress ??
      0,
  );
  return {
    id: operation.name || fallback.id || "",
    object: "google_veo_operation",
    provider: "google",
    model: fallback.model || operation.metadata?.model || "veo-3.1-generate-preview",
    status,
    progress: done ? 100 : Number.isFinite(metadataProgress) ? Math.max(0, Math.min(99, metadataProgress)) : 0,
    size: fallback.size || null,
    seconds: fallback.seconds || null,
    targetSeconds: fallback.targetSeconds || fallback.seconds || null,
    resolution: fallback.resolution || null,
    created_at: fallback.created_at || Math.floor(Date.now() / 1000),
    completed_at: done ? Math.floor(Date.now() / 1000) : null,
    error,
    videoUri: sample?.video?.uri || null,
  };
}

function isGoogleOperationId(id) {
  return /(^|\/)operations\//.test(String(id || ""));
}

function aspectRatioForSize(size) {
  const [width, height] = String(size || "").split("x").map(Number);
  if (!width || !height) return "2:3";
  if (width === height) return "1:1";
  if (width > height) return width / height > 1.6 ? "16:9" : "3:2";
  return height / width > 1.6 ? "9:16" : "2:3";
}

function normalizeGoogleTargetSeconds(value) {
  const seconds = Number(value || 8);
  const allowed = [4, 6, 8, 15, 22, 29, 36, 57, 85, 120, 148];
  return allowed.includes(seconds) ? seconds : 8;
}

function normalizeLongVideoSize(size) {
  const selected = String(size || "720x1280");
  return selected.includes("x720") || selected.includes("x1024") ? "1280x720" : "720x1280";
}

function extensionPrompt(prompt) {
  const clean = prompt || "Continue the same product demonstration with consistent product shape, lighting, and camera language.";
  return [
    "Continue the same Veo-generated product demo from the final moment of the input video.",
    "Keep product identity, actor/hand identity, lighting, color, scene continuity, and camera language consistent.",
    "Add the next useful product demonstration beat without subtitles, captions, fake UI, or logo hallucinations.",
    clean,
  ].join("\n");
}

function imageSizeForStep(step, videoSize) {
  if (step === "tone_reference" && VIDEO_SIZES.has(String(videoSize))) return String(videoSize);
  if (step === "storyboard" && ["1280x720", "1792x1024"].includes(String(videoSize))) return "1536x1024";
  if (step === "product_reference") return "1536x1024";
  return "1024x1536";
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
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
