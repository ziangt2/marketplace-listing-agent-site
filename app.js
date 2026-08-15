const state = {
  platform: "amazon",
  uploads: [],
  collection: null,
  autoProductText: "",
  autoReviewText: "",
  trendLookup: new Map(),
  rows: [],
  packageText: "",
  videoAssets: {},
  videoJob: null,
  videoPollTimer: null,
  videoElapsedTimer: null,
  videoStartedAt: 0,
  videoContentUrl: "",
  videoPrompts: {},
  pipelineLogs: [],
};

const stopWords = new Set([
  "about",
  "after",
  "again",
  "also",
  "amazon",
  "and",
  "are",
  "al",
  "best",
  "bing",
  "but",
  "can",
  "como",
  "con",
  "cuál",
  "cual",
  "de",
  "del",
  "donde",
  "dónde",
  "el",
  "en",
  "es",
  "for",
  "from",
  "has",
  "have",
  "into",
  "just",
  "like",
  "la",
  "las",
  "los",
  "made",
  "mas",
  "más",
  "mejor",
  "mejores",
  "does",
  "google",
  "how",
  "more",
  "near",
  "not",
  "out",
  "para",
  "por",
  "public",
  "query",
  "que",
  "qué",
  "related",
  "search",
  "shop",
  "should",
  "sin",
  "son",
  "source",
  "sources",
  "suggestion",
  "suggestions",
  "that",
  "the",
  "this",
  "tiktok",
  "too",
  "under",
  "use",
  "un",
  "una",
  "uno",
  "video",
  "was",
  "what",
  "with",
  "which",
  "why",
  "you",
  "your",
  "的",
  "了",
  "和",
  "是",
  "我",
  "有",
  "就",
  "都",
  "很",
  "也",
  "在",
]);

const singleTokenNoiseWords = new Set(["non", "slip", "one", "two", "three"]);

const templateHeaders = [
  "高频词类型",
  "特征词",
  "Weight",
  "出现次数",
  "原始搜索词",
  "地区/语种",
  "结论",
];

const painMarkers = [
  "annoying",
  "bad",
  "broke",
  "cheap",
  "confusing",
  "difficult",
  "expensive",
  "hard",
  "hate",
  "issue",
  "leak",
  "messy",
  "noisy",
  "problem",
  "slow",
  "waste",
  "weak",
  "worried",
  "pain",
  "slip",
  "smell",
  "痛",
  "麻烦",
  "不好",
  "太贵",
  "坏",
  "难",
  "慢",
  "漏",
  "吵",
  "担心",
];

const benefitMarkers = [
  "portable",
  "easy",
  "fast",
  "compact",
  "quiet",
  "durable",
  "wireless",
  "rechargeable",
  "leakproof",
  "waterproof",
  "lightweight",
  "safe",
  "travel",
  "clean",
  "non slip",
  "thick",
  "cushion",
  "grip",
  "便携",
  "轻便",
  "防漏",
  "静音",
  "耐用",
  "省时",
  "好清洗",
  "安全",
];

const hookMarkers = [
  "before you buy",
  "don't buy",
  "i tried",
  "this is why",
  "watch this",
  "stop",
  "pov",
  "you need",
  "tested",
  "viral",
  "review",
  "worth it",
  "三秒",
  "别买",
  "实测",
  "你需要",
  "爆款",
  "避雷",
];

const videoImageSteps = ["product_reference", "actor_reference", "storyboard", "tone_reference"];

const els = {
  connectionStatus: document.querySelector("#connectionStatus"),
  platformButtons: document.querySelectorAll(".platform-button"),
  keyword: document.querySelector("#keywordInput"),
  region: document.querySelector("#regionInput"),
  buyer: document.querySelector("#buyerInput"),
  price: document.querySelector("#priceInput"),
  localMode: document.querySelector("#localModeInput"),
  localUrl: document.querySelector("#localUrlInput"),
  collectButton: document.querySelector("#collectButton"),
  buildButton: document.querySelector("#buildButton"),
  clearButton: document.querySelector("#clearButton"),
  sampleButton: document.querySelector("#sampleButton"),
  progress: document.querySelector("#progressText"),
  productText: document.querySelector("#productText"),
  reviewText: document.querySelector("#reviewText"),
  reportText: document.querySelector("#reportText"),
  fileInput: document.querySelector("#fileInput"),
  uploadList: document.querySelector("#uploadList"),
  sourceCount: document.querySelector("#sourceCount"),
  keywordCount: document.querySelector("#keywordCount"),
  reportCount: document.querySelector("#reportCount"),
  table: document.querySelector("#keywordTable"),
  packageOutput: document.querySelector("#packageOutput"),
  downloadCsv: document.querySelector("#downloadCsvButton"),
  downloadXlsx: document.querySelector("#downloadXlsxButton"),
  copy: document.querySelector("#copyButton"),
  downloadTxt: document.querySelector("#downloadTxtButton"),
  refreshVideoPrompts: document.querySelector("#refreshVideoPromptsButton"),
  checkRecentVideos: document.querySelector("#checkRecentVideosButton"),
  runVideoPipeline: document.querySelector("#runVideoPipelineButton"),
  openaiApiKey: document.querySelector("#openaiApiKeyInput"),
  googleApiKey: document.querySelector("#googleApiKeyInput"),
  imageModel: document.querySelector("#imageModelSelect"),
  imageQuality: document.querySelector("#imageQualitySelect"),
  videoModel: document.querySelector("#videoModelSelect"),
  videoSize: document.querySelector("#videoSizeSelect"),
  videoSeconds: document.querySelector("#videoSecondsSelect"),
  productReferencePrompt: document.querySelector("#productReferencePrompt"),
  actorReferencePrompt: document.querySelector("#actorReferencePrompt"),
  storyboardPrompt: document.querySelector("#storyboardPrompt"),
  toneReferencePrompt: document.querySelector("#toneReferencePrompt"),
  videoPrompt: document.querySelector("#videoPrompt"),
  productReferencePreview: document.querySelector("#productReferencePreview"),
  actorReferencePreview: document.querySelector("#actorReferencePreview"),
  storyboardPreview: document.querySelector("#storyboardPreview"),
  toneReferencePreview: document.querySelector("#toneReferencePreview"),
  videoPreview: document.querySelector("#videoPreview"),
  productReferenceStatus: document.querySelector("#productReferenceStatus"),
  actorReferenceStatus: document.querySelector("#actorReferenceStatus"),
  storyboardStatus: document.querySelector("#storyboardStatus"),
  toneReferenceStatus: document.querySelector("#toneReferenceStatus"),
  videoStatus: document.querySelector("#videoStatus"),
  generateVideo: document.querySelector("#generateVideoButton"),
  pollVideo: document.querySelector("#pollVideoButton"),
  quickRetryVideo: document.querySelector("#quickRetryVideoButton"),
  localPreviewVideo: document.querySelector("#localPreviewVideoButton"),
  downloadVideo: document.querySelector("#downloadVideoButton"),
  pipelineStatus: document.querySelector("#pipelineStatus"),
  pipelinePercent: document.querySelector("#pipelinePercent"),
  pipelineBar: document.querySelector("#pipelineBar"),
  pipelineLog: document.querySelector("#pipelineLog"),
};

els.platformButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.platform = button.dataset.platform;
    els.platformButtons.forEach((item) => item.classList.toggle("is-active", item === button));
    setProgress(`${platformLabel()} 模式。不会模拟缺失数据。`);
    refreshVideoPrompts();
  });
});

els.localMode.addEventListener("change", updateConnectionLabel);
els.localUrl.addEventListener("input", updateConnectionLabel);
els.collectButton.addEventListener("click", collectKeyword);
els.buildButton.addEventListener("click", buildFromCurrentText);
els.clearButton.addEventListener("click", clearAll);
els.sampleButton.addEventListener("click", loadSample);
els.fileInput.addEventListener("change", (event) => handleFiles(event.target.files));
els.downloadCsv.addEventListener("click", downloadCsv);
els.downloadXlsx.addEventListener("click", () => downloadXlsx().catch((error) => setProgress(`XLSX 下载失败：${error.message}`, "error")));
els.copy.addEventListener("click", copyPackage);
els.downloadTxt.addEventListener("click", downloadTxt);
els.openaiApiKey.value = localStorage.getItem("marketplace_openai_api_key") || "";
els.openaiApiKey.addEventListener("input", () => {
  localStorage.setItem("marketplace_openai_api_key", els.openaiApiKey.value.trim());
});
els.googleApiKey.value = localStorage.getItem("marketplace_google_api_key") || "";
els.googleApiKey.addEventListener("input", () => {
  localStorage.setItem("marketplace_google_api_key", els.googleApiKey.value.trim());
  syncGooglePipelineDefaults();
});
syncGooglePipelineDefaults();
els.refreshVideoPrompts.addEventListener("click", refreshVideoPrompts);
els.checkRecentVideos.addEventListener("click", checkRecentVideos);
els.runVideoPipeline.addEventListener("click", runVideoPipeline);
document.querySelectorAll("[data-generate-step]").forEach((button) => {
  button.addEventListener("click", () => generateImageStep(button.dataset.generateStep).catch(() => {}));
});
els.generateVideo.addEventListener("click", () => generateVideo().catch(() => {}));
els.pollVideo.addEventListener("click", pollVideo);
els.quickRetryVideo.addEventListener("click", () => quickRetryVideo().catch(() => {}));
els.localPreviewVideo.addEventListener("click", () => createLocalPreviewVideo().catch((error) => {
  setStepStatus("video", error.message, "error");
  addPipelineLog(`本地预览失败：${error.message}`);
}));
els.downloadVideo.addEventListener("click", downloadGeneratedVideo);
[els.videoSize, els.videoSeconds].forEach((control) => {
  control.addEventListener("change", () => {
    syncGooglePipelineDefaults();
    const prompts = buildVideoPrompts();
    state.videoPrompts = prompts;
    els.videoPrompt.value = prompts.video;
  });
});
els.videoModel.addEventListener("change", syncGooglePipelineDefaults);

updateConnectionLabel();
refreshVideoPrompts();

async function collectKeyword() {
  const keyword = els.keyword.value.trim();
  if (!keyword) {
    els.keyword.focus();
    setProgress("先输入产品关键词。", "error");
    return;
  }

  els.collectButton.disabled = true;
  setProgress(`正在采集 ${platformLabel()} 公开来源：${keyword}...`, "working");

  try {
    const payload = {
      platform: state.platform,
      keyword,
      region: els.region.value,
      buyer: els.buyer.value.trim(),
    };
    const { data, mode } = await requestCollection(payload);

    state.collection = data;
    state.autoProductText = data.sourceTexts?.product || "";
    state.autoReviewText = data.sourceTexts?.review || "";
    els.productText.value = state.autoProductText;
    els.reviewText.value = state.autoReviewText;
    setProgress(`采集完成：${data.items?.length || 0} 条真实公开来源。来源模式：${mode}。`, "");
    buildFromCurrentText();
  } catch (error) {
    setProgress(`采集失败：${error.message}。没有数据时不会生成模拟字段。`, "error");
  } finally {
    els.collectButton.disabled = false;
  }
}

async function requestCollection(payload) {
  if (els.localMode.checked) {
    try {
      const data = await postJson(getLocalEndpoint(), payload);
      return { data, mode: "localhost" };
    } catch (error) {
      setProgress(`localhost 未连接，正在回退到 Vercel API...`, "working");
    }
  }
  const data = await postJson("/api/marketplace-collect", payload);
  return { data, mode: "Vercel API" };
}

async function postJson(endpoint, payload) {
  const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || "collect failed");
  return data;
}

function getLocalEndpoint() {
  return `${els.localUrl.value.replace(/\/$/, "")}/api/marketplace-collect`;
}

function buildFromCurrentText() {
  const sources = collectTextSources();
  state.trendLookup = extractTrendLookup(sources);
  const rows = buildKeywordRows(sources);
  state.rows = rows;
  state.packageText = buildPackage(rows, sources);
  renderAll();
  refreshVideoPrompts();
}

function collectTextSources() {
  const sources = [];
  const canUseStructuredCollection =
    state.collection?.items?.length &&
    els.productText.value === state.autoProductText &&
    els.reviewText.value === state.autoReviewText;

  if (canUseStructuredCollection) {
    const includeQuerySeeds = Boolean(state.collection?.market?.spanish || state.collection?.markets?.some((market) => market.spanish));
    const querySeeds = new Set();
    for (const item of state.collection.items) {
      addSource(sources, item.sourceType || "product_title", item.title || item.url || "公开来源", `${item.title || ""}. ${item.snippet || ""}`, {
        query: item.query || "",
        region: [item.region || state.collection.market?.label || state.collection.region || els.region.value, item.language || state.collection.market?.language || ""].filter(Boolean).join(" / "),
        url: item.url || "",
      });
      if (includeQuerySeeds && item.query && !querySeeds.has(item.query)) {
        querySeeds.add(item.query);
        addSource(sources, "query_seed", "原始搜索词", item.query, {
          query: item.query,
          region: [item.region || state.collection.market?.label || state.collection.region || els.region.value, item.language || state.collection.market?.language || ""].filter(Boolean).join(" / "),
          url: item.url || "",
        });
      }
    }
  } else {
    addSource(sources, "product_title", "商品标题/竞品标题", els.productText.value, { region: els.region.value });
    addSource(sources, "review_text", "评论/评测/FAQ", els.reviewText.value, { region: els.region.value });
  }

  addSource(sources, inferReportTextType(els.reportText.value), "Google Trends / Ads / SQP 真实报告", els.reportText.value, { region: els.region.value });
  for (const upload of state.uploads) {
    if (upload.text) addSource(sources, upload.type, upload.name, upload.text, { region: els.region.value });
  }
  return sources;
}

function addSource(sources, type, label, text, meta = {}) {
  const clean = String(text || "").trim();
  if (clean) sources.push({ type, label, text: clean, ...meta });
}

function inferReportTextType(text) {
  return /google trends|trends|讨论热度|讨论总量|上升速度|增长速度|growth|volume|月份\/周|地区\/语种/i.test(String(text || ""))
    ? "trend_report"
    : "official_report";
}

function extractTrendLookup(sources) {
  const lookup = new Map();
  for (const source of sources) {
    const lines = String(source.text || "").split(/\r?\n/);
    let header = null;
    for (const line of lines) {
      if (/^##\s*Sheet:/i.test(line)) {
        header = null;
        continue;
      }
      const cells = line.split(/\t|,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map((cell) => cell.replace(/^"|"$/g, "").trim());
      const termIndex = findHeaderIndex(cells, ["特征词", "关键词", "keyword", "query", "term", "search term"]);
      const heatIndex = findHeaderIndex(cells, ["讨论热度", "热度", "interest", "trend score", "trends score", "google trends"]);
      const totalIndex = findHeaderIndex(cells, ["讨论总量", "总量", "需求总量", "声量", "搜索量", "播放量", "浏览量", "帖子数", "评论数", "mentions", "volume", "views", "posts", "comments"]);
      const growthIndex = findHeaderIndex(cells, ["上升速度", "增长速度", "增量", "增长率", "环比", "同比", "rise speed", "growth", "growth rate", "wow", "mom"]);
      if (termIndex >= 0 && (heatIndex >= 0 || totalIndex >= 0 || growthIndex >= 0 || cells.includes("地区/语种"))) {
        header = {
          term: termIndex,
          heat: heatIndex,
          total: totalIndex,
          growth: growthIndex,
          raw: findHeaderIndex(cells, ["原始搜索词", "source query", "query source", "raw query"]),
          region: findHeaderIndex(cells, ["地区/语种", "地区", "市场", "国家", "language", "region", "locale"]),
          period: findHeaderIndex(cells, ["月份/周", "月份", "周", "日期", "period", "week", "month", "date"]),
          meaning: findHeaderIndex(cells, ["词义", "意图", "meaning", "intent"]),
        };
        continue;
      }
      if (!header || !cells.length) continue;
      const term = cells[header.term] || "";
      if (!term || term === "特征词") continue;
      lookup.set(term.toLowerCase(), {
        heat: header.heat >= 0 ? cells[header.heat] || "" : "",
        total: header.total >= 0 ? cells[header.total] || "" : "",
        growth: header.growth >= 0 ? cells[header.growth] || "" : "",
        raw: header.raw >= 0 ? cells[header.raw] || "" : "",
        region: header.region >= 0 ? cells[header.region] || "" : "",
        period: header.period >= 0 ? cells[header.period] || "" : "",
        meaning: header.meaning >= 0 ? cells[header.meaning] || "" : "",
      });
    }
  }
  return lookup;
}

function findHeaderIndex(cells, names) {
  const normalizedNames = names.map(normalizeHeader);
  return cells.findIndex((cell) => normalizedNames.includes(normalizeHeader(cell)));
}

function normalizeHeader(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[\s_/-]+/g, " ")
    .trim();
}

function buildKeywordRows(sources) {
  const map = new Map();
  for (const source of sources) {
    for (const term of extractTermsForSource(source)) {
      const field = classifyTerm(term, source.type);
      const key = `${term}__${field}`;
      const row = map.get(key) || {
        term,
        field,
        sourceTypes: new Set(),
        sourceQueries: new Set(),
        regions: new Set(),
        periods: new Set(),
        count: 0,
      };
      row.count += 1;
      row.sourceTypes.add(source.type);
      if (source.query) row.sourceQueries.add(source.query);
      if (source.region) row.regions.add(source.region);
      if (source.period) row.periods.add(source.period);
      map.set(key, row);
    }
  }

  return Array.from(map.values())
    .filter((row) => row.term.length > 1)
    .sort((a, b) => b.count - a.count || a.term.localeCompare(b.term))
    .slice(0, 3000);
}

function extractTermsForSource(source) {
  if (source.type === "trend_report") {
    const structuredTerms = extractStructuredColumn(source.text, "特征词");
    if (structuredTerms.length) return structuredTerms;
  }
  return extractTerms(source.text);
}

function extractStructuredColumn(text, headerName) {
  const terms = [];
  const lines = String(text || "").split(/\r?\n/);
  let columnIndex = -1;
  for (const line of lines) {
    if (/^##\s*Sheet:/i.test(line)) {
      columnIndex = -1;
      continue;
    }
    const cells = line.split(/\t|,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map((cell) => cell.replace(/^"|"$/g, "").trim());
    const headerIndex = cells.indexOf(headerName);
    if (headerIndex >= 0) {
      columnIndex = headerIndex;
      continue;
    }
    if (columnIndex < 0) continue;
    const term = cells[columnIndex] || "";
    if (term && term !== headerName) terms.push(term.toLowerCase());
  }
  return terms;
}

function extractTerms(text) {
  const terms = [];
  const lower = text.toLowerCase();
  const words = (lower.match(/[a-z][a-z0-9-]{2,}/g) || []).filter(
    (word) => !stopWords.has(word) && !/^\d+$/.test(word),
  );
  for (const word of words) {
    if (!singleTokenNoiseWords.has(word)) terms.push(word);
  }
  for (const size of [2, 3, 4]) {
    for (let index = 0; index <= words.length - size; index += 1) {
      const phrase = words.slice(index, index + size);
      if (phrase.some((word) => stopWords.has(word))) continue;
      terms.push(phrase.join(" "));
    }
  }
  const hashtags = text.match(/#[\p{L}\p{N}_-]+/gu) || [];
  terms.push(...hashtags.map((tag) => tag.toLowerCase()));
  const chineseRuns = text.match(/[\u4e00-\u9fff]{2,}/g) || [];
  for (const run of chineseRuns) {
    const length = Math.min(run.length, 18);
    for (let size = 2; size <= 4; size += 1) {
      for (let index = 0; index <= length - size; index += 1) terms.push(run.slice(index, index + size));
    }
  }
  return terms;
}

function classifyTerm(term, sourceType) {
  const lower = term.toLowerCase();
  if (sourceType === "query_seed") return "搜索种子词";
  if (sourceType === "trend_report") return "Google Trends词";
  if (sourceType === "official_report") return "真实报告词";
  if (lower.startsWith("#")) return "Hashtag";
  if (painMarkers.some((marker) => lower.includes(marker))) return "痛点/评论词";
  if (hookMarkers.some((marker) => lower.includes(marker))) return "视频钩子词";
  if (benefitMarkers.some((marker) => lower.includes(marker))) return "卖点/功能词";
  if (/\b(title|review|demo|routine|gift|comparison|before|after|setup)\b/.test(lower)) return "内容场景词";
  return state.platform === "amazon" ? "Amazon 搜索长尾词" : "TikTok 搜索长尾词";
}

function buildPackage(rows, sources) {
  const product = els.keyword.value.trim() || "无关键词";
  const reports = sources.filter((source) => source.type === "official_report" || source.type === "trend_report");
  const reportStatus = reports.length ? `${reports.length} 个真实报告/趋势来源` : "无真实报告/趋势来源，指标列保持空白";
  const collectionStats = state.collection?.stats;
  const templateRows = buildTemplateRows(rows);
  const categoryCounts = templateRows.reduce((map, row) => {
    map[row.category] = (map[row.category] || 0) + 1;
    return map;
  }, {});
  const allKeywordBlocks = chunk(templateRows.slice(0, 1200).map((row) => `${row.category || ""}\t${row.term}\tWeight:${row.weight || ""}\t出现次数:${row.count || ""}`), 80);

  if (!rows.length) {
    return [
      `Marketplace Keyword Library`,
      `Platform: ${platformLabel()}`,
      `Product: ${product}`,
      ``,
      `NO DATA`,
      `没有采集到公开来源，也没有上传/粘贴真实数据。`,
      `不会生成模拟 ABA、模拟广告搜索词、模拟 Google Trends 热度、模拟销量、模拟搜索量或模拟评论数。`,
    ].join("\n");
  }

  return [
    `Marketplace Keyword Library`,
    `Platform: ${platformLabel()}`,
    `Product: ${product}`,
    `Region: ${els.region.value}`,
    ``,
    `TEMPLATE COLUMNS`,
    templateHeaders.join(" | "),
    ``,
    `DATA RULES`,
    `- 词库只来自公开搜索片段、用户粘贴文本、上传文件或真实报告。`,
    `- Weight 是派生排序分：出现次数、来源覆盖、真实趋势热度、意图强度、长尾具体度综合计算，非外部搜索量。`,
    `- 所有词条按 Weight 从高到低排序。`,
    `- 公开采集默认只填“出现次数”，并在可追溯时填“原始搜索词”和“地区/语种”。`,
    `- 真实趋势字段：${reportStatus}；没有 Google Trends、TikTok 或后台报告就保持空白。`,
    `- 结论优先使用真实趋势数据；没有真实趋势数据时只给候选方向，不当作预测。`,
    `- 空白就是没有真实数据；不会用 -、0、估算值或模型编造值补齐。`,
    ``,
    `SOURCE AUDIT`,
    `- Public collection items: ${state.collection?.items?.length || 0}`,
    `- Market / language: ${state.collection?.market?.label || els.region.value} / ${state.collection?.market?.language || ""}`,
    `- Public source queries: ${state.collection?.sourceQueries?.length || 0}`,
    `- Public source breakdown: ${collectionStats ? JSON.stringify(collectionStats.sourceTypes) : "无"}`,
    `- Uploaded / pasted sources: ${sources.length}`,
    `- Collection errors recorded: ${collectionStats?.errors ?? 0}`,
    ``,
    `CATEGORY COUNTS`,
    ...Object.entries(categoryCounts).map(([category, count]) => `- ${category}: ${count}`),
    ``,
    `NEXT REAL DATA TO ADD FOR BLANK METRIC COLUMNS`,
    state.platform === "amazon"
      ? `- Google Trends export for 讨论热度 / 月份/周\n- Amazon Ads Search Term Report\n- Brand Analytics / ABA export\n- Search Query Performance report\n- Real review export or pasted review text`
      : `- TikTok Creative Center keyword/hashtag export\n- Google Trends export\n- TikTok Ads product-level report\n- TikTok Shop Seller Center product performance export\n- Creator / affiliate performance CSV`,
    ``,
    `KEYWORD BANK EXCERPT - TOP ${Math.min(1200, templateRows.length)} OF ${templateRows.length}`,
    ...allKeywordBlocks.map((block, index) => `Batch ${index + 1}\n${block.join(", ")}`),
  ].join("\n");
}

function buildTitleOptions(product, terms) {
  const cleanTerms = terms.filter((term) => term && term !== product).slice(0, 24);
  if (!cleanTerms.length) return [`${product}`];
  const options = [];
  for (let index = 0; index < Math.min(8, cleanTerms.length); index += 1) {
    const term = cleanTerms[index];
    const next = cleanTerms[index + 8] || cleanTerms[index + 1] || "";
    const tail = cleanTerms[index + 16] || "";
    options.push([product, term, next, tail].filter(Boolean).join(" | "));
  }
  return Array.from(new Set(options));
}

function chunk(items, size) {
  const groups = [];
  for (let index = 0; index < items.length; index += size) {
    groups.push(items.slice(index, index + size));
  }
  return groups;
}

function joinSet(value, limit = 3) {
  if (!value) return "";
  const items = Array.from(value).filter(Boolean);
  return items.slice(0, limit).join(" | ");
}

function refreshVideoPrompts() {
  const prompts = buildVideoPrompts();
  state.videoPrompts = prompts;
  els.productReferencePrompt.value = prompts.product_reference;
  els.actorReferencePrompt.value = prompts.actor_reference;
  els.storyboardPrompt.value = prompts.storyboard;
  els.toneReferencePrompt.value = prompts.tone_reference;
  els.videoPrompt.value = prompts.video;
  setStepStatus("product_reference", "提示词已准备。");
  setStepStatus("actor_reference", "提示词已准备。");
  setStepStatus("storyboard", "提示词已准备。");
  setStepStatus("tone_reference", "提示词已准备。");
}

function buildVideoPrompts() {
  const product = els.keyword.value.trim() || "current product keyword";
  const buyer = els.buyer.value.trim() || "target buyer not filled";
  const price = els.price.value.trim() || "price band not filled";
  const topTerms = state.rows.slice(0, 24).map((row) => row.term);
  const benefitTerms = state.rows.filter((row) => row.field === "卖点/功能词").slice(0, 12).map((row) => row.term);
  const painTerms = state.rows.filter((row) => row.field === "痛点/评论词").slice(0, 10).map((row) => row.term);
  const hookTerms = state.rows.filter((row) => row.field === "视频钩子词").slice(0, 8).map((row) => row.term);
  const sceneTerms = state.rows.filter((row) => row.field === "内容场景词").slice(0, 8).map((row) => row.term);
  const termLine = topTerms.join(", ") || "no collected terms yet; use only the typed product keyword";
  const benefitLine = benefitTerms.join(", ") || "no real benefit terms yet";
  const painLine = painTerms.join(", ") || "no real review pain terms yet";
  const hookLine = hookTerms.join(" | ") || "simple product reveal hook";
  const sceneLine = sceneTerms.join(", ") || "clean daily-use scene";
  const aspect = els.videoSize.value.includes("x1280") || els.videoSize.value.includes("x1792") ? "vertical 9:16" : "horizontal 16:9";
  const seconds = els.videoSeconds.value;
  const platform = platformLabel();
  const noDataRule =
    "Do not invent marketplace metrics, fake review quotes, fake Amazon/TikTok UI, fake brand logos, certifications, awards, or unsupported claims.";

  return {
    product_reference: [
      `Create a Lovart-style commercial product reference board for "${product}".`,
      `Marketplace context: ${platform}. Buyer: ${buyer}. Price band: ${price}.`,
      `Observed keyword language: ${termLine}. Benefits to visualize only if supported by terms: ${benefitLine}.`,
      `If no actual product image is provided, make a generic, believable product visualization from the keyword only; avoid specific brand marks and unsupported details.`,
      `Board layout: clean black canvas, one white rounded reference sheet, front view, side view, back view, top/detail view, material close-up, scale-in-hand view, packaging/accessory view if relevant.`,
      `Keep product shape, color family, material, edges, buttons, seams, texture, and proportions consistent across all views. High detail, sharp lighting, no extra props.`,
      noDataRule,
    ].join("\n"),
    actor_reference: [
      `Generate a fixed hand/actor reference for a realistic UGC product demo of "${product}".`,
      `Default to hands-only if the product does not require a face. If a person is needed, use one ordinary adult actor, neutral outfit, natural skin texture, no celebrity likeness.`,
      `The reference should include: front hand pose, side hand pose, holding/using the product, close-up grip/contact, neutral background. Keep hands anatomically correct.`,
      `Buyer mood: practical, trustworthy, not over-acted. Target buyer: ${buyer}.`,
      `Use the same product appearance from the product reference board when available.`,
      noDataRule,
    ].join("\n"),
    storyboard: [
      `Create a ${aspect} product demo storyboard board for "${product}" in 6-9 panels.`,
      `Style: black-and-white pencil storyboard, rough but clear Lovart-like production board, with simple colored annotations.`,
      `Shot order: 1 hook/reveal, 2 product in hand, 3 key feature proof, 4 macro detail, 5 real-use moment, 6 pain point solved, 7 comparison/scale if relevant, 8 final clean hero shot.`,
      `Use observed terms as story triggers: hooks=${hookLine}; benefits=${benefitLine}; pain/review language=${painLine}; scenes=${sceneLine}.`,
      `Annotations: red arrows for product/hand motion, blue arrows for camera movement, green notes for feature callout, orange notes for lighting, purple notes for hook/dialogue idea.`,
      `No subtitles, no timeline text, no marketplace UI screenshots. Keep product and hand/actor consistent across every panel.`,
      noDataRule,
    ].join("\n"),
    tone_reference: [
      `Generate the final tone/first-frame reference image for a ${aspect} ${platform} product demo video about "${product}".`,
      `This image should be usable as the first visual anchor for a video model: one clear scene, not a collage.`,
      `Scene: realistic lifestyle or tabletop demo setting that fits the product; warm natural light; clean composition; shallow depth of field; believable hand/actor interaction; product is large and inspectable.`,
      `Visual mood: premium but not ad-like, UGC-real, stable product texture, readable shape, no clutter, no fake UI.`,
      `Use keyword cues: ${termLine}. Benefits to imply visually: ${benefitLine}.`,
      `If no real product image was supplied, keep the product generic and brand-free.`,
      noDataRule,
    ].join("\n"),
    video: [
      `Create a ${seconds}-second ${aspect} product demonstration video for "${product}" for ${platform}.`,
      `Use the input_reference image as the first frame and visual anchor. Preserve product shape, material, color, scale, hand/actor identity, and scene tone from the prepared boards.`,
      `Follow the prepared storyboard order: hook/reveal -> product in hand -> feature proof -> macro detail -> real use -> final clean hero shot. Do not jump around.`,
      `Camera language: steady handheld UGC realism, slow push-in, macro close-up, clear product movement, no fast cuts that hide the product.`,
      `Keywords driving the content: ${termLine}. Benefits to show: ${benefitLine}. Pain points to answer visually: ${painLine}.`,
      `No subtitles, no captions, no BGM request, no fake UI, no unsupported performance claims, no warped hands, no changing product shape, no hallucinated logo.`,
      `If the selected provider can create audio, keep only natural room/product handling sound.`,
    ].join("\n"),
  };
}

async function runVideoPipeline() {
  els.runVideoPipeline.disabled = true;
  clearVideoPolling();
  state.pipelineLogs = [];
  updatePipelineProgress(0, "开始生成流程");
  setProgress("正在按 Lovart 流程生成：产品板 -> 人物/手模 -> 故事板 -> 调性图 -> 视频任务。", "working");
  try {
    refreshVideoPrompts();
    let completed = 0;
    for (const step of videoImageSteps) {
      const config = getVideoStepConfig(step);
      updatePipelineProgress(completed * 18, `正在生成：${config.label}`);
      addPipelineLog(`开始 ${config.label}`);
      await generateImageStep(step, { pipeline: true });
      completed += 1;
      updatePipelineProgress(completed * 18, `完成：${config.label}`);
    }
    updatePipelineProgress(82, "正在提交视频任务");
    await generateVideo();
  } catch (error) {
    updatePipelineProgress(null, "生成停止");
    addPipelineLog(`失败：${error.message}`);
    setProgress(`视频流程停止：${error.message}`, "error");
  } finally {
    els.runVideoPipeline.disabled = false;
  }
}

async function generateImageStep(step, options = {}) {
  syncGooglePipelineDefaults();
  const config = getVideoStepConfig(step);
  const prompt = config.prompt.value.trim();
  if (!prompt) {
    setStepStatus(step, "先生成或填写提示词。", "error");
    throw new Error(`${config.label} 缺少提示词`);
  }

  config.button.disabled = true;
  renderWorkingPreview(step, `${config.label} 生成中`);
  setStepStatus(step, `正在生成 ${config.label}...`, "working");
  if (!options.pipeline) {
    updatePipelineProgress(10, `正在生成：${config.label}`);
    addPipelineLog(`开始 ${config.label}`);
  }
  try {
    const data = await postVideoJson({
      action: "generate_image",
      step,
      model: els.imageModel.value,
      quality: els.imageQuality.value,
      videoSize: els.videoSize.value,
      prompt,
    });
    state.videoAssets[step] = {
      dataUrl: data.imageDataUrl,
      model: data.model,
      size: data.size,
    };
    renderImagePreview(step, data.imageDataUrl);
    setStepStatus(step, `已生成：${data.model} / ${data.size} / ${data.quality}`);
    addPipelineLog(`完成 ${config.label}：${data.model} / ${data.size}`);
    if (!options.pipeline) updatePipelineProgress(100, `${config.label} 完成`);
    return data;
  } catch (error) {
    config.preview.classList.remove("is-working");
    config.preview.textContent = `${config.label} 失败`;
    setStepStatus(step, error.message, "error");
    addPipelineLog(`${config.label} 失败：${error.message}`);
    if (!options.pipeline) updatePipelineProgress(null, `${config.label} 失败`);
    throw error;
  } finally {
    config.button.disabled = false;
  }
}

async function generateVideo() {
  syncGooglePipelineDefaults();
  const prompt = els.videoPrompt.value.trim();
  if (!prompt) {
    setStepStatus("video", "先生成或填写视频提示词。", "error");
    return;
  }

  els.generateVideo.disabled = true;
  els.pollVideo.disabled = true;
  state.videoContentUrl = "";
  els.downloadVideo.disabled = true;
  renderWorkingPreview("video", "提交视频任务中");
  updatePipelineProgress(Math.max(currentPipelinePercent(), 82), "正在提交视频任务");
  addPipelineLog("提交视频任务");
  setStepStatus("video", "正在提交视频生成任务...", "working");
  try {
    const inputReference = chooseVideoInputReference();
    if (!inputReference && Object.keys(state.videoAssets).length) {
      setStepStatus("video", "参考图尺寸与当前视频清晰度不一致，将用纯文字提交。", "working");
    }
    const data = await postVideoJson({
      action: "generate_video",
      model: els.videoModel.value,
      size: els.videoSize.value,
      seconds: els.videoSeconds.value,
      prompt,
      inputReference,
    });
    state.videoJob = data.video || { id: data.id, status: data.status };
    state.videoStartedAt = Date.now();
    startVideoElapsedTimer();
    renderVideoJob(state.videoJob);
    setStepStatus("video", `任务已提交：${state.videoJob.id || "无 id"}，状态 ${state.videoJob.status || "queued"}`);
    updatePipelineProgress(88, `视频任务已提交：${state.videoJob.status || "queued"}`);
    addPipelineLog(`视频任务 id：${state.videoJob.id || "无 id"}`);
    addPipelineLog(`${state.videoJob.provider === "google" ? "已提交到 Google Veo 3.1 / Gemini API。" : "已按 OpenAI multipart 文件上传方式提交首帧参考。"}`);
    if (state.videoJob.provider === "google") {
      addPipelineLog("Veo 返回的是长任务 operation；如果没有百分比，会显示状态和已等待时间。");
      if (Number(state.videoJob.targetSeconds || state.videoJob.seconds || 0) > 8) {
        addPipelineLog(`长视频模式：先生成 8 秒，然后每次延长约 7 秒，目标约 ${state.videoJob.targetSeconds} 秒。`);
      }
    }
    setProgress(`视频任务已提交：${state.videoJob.id || "无 id"}。系统会自动刷新进度。`);
    els.pollVideo.disabled = !state.videoJob.id;
    scheduleVideoPolling();
    return data;
  } catch (error) {
    els.videoPreview.classList.remove("is-working");
    els.videoPreview.textContent = "视频提交失败";
    setStepStatus("video", error.message, "error");
    updatePipelineProgress(null, "视频提交失败");
    addPipelineLog(`视频提交失败：${error.message}`);
    throw error;
  } finally {
    els.generateVideo.disabled = false;
  }
}

async function pollVideo(options = {}) {
  if (!state.videoJob?.id) {
    setStepStatus("video", "还没有视频任务。", "error");
    return;
  }
  if (!options.silent) els.pollVideo.disabled = true;
  setStepStatus("video", "正在刷新视频进度...", "working");
  try {
    const data = await postVideoJson({
      action: "poll_video",
      id: state.videoJob.id,
      provider: state.videoJob.provider,
      model: state.videoJob.model,
      size: state.videoJob.size,
      seconds: state.videoJob.seconds,
      targetSeconds: state.videoJob.targetSeconds,
      created_at: state.videoJob.created_at,
    });
    state.videoJob = data.video;
    if (data.contentUrl) {
      state.videoContentUrl = data.contentUrl;
      if (shouldExtendGoogleVideo(state.videoJob)) {
        clearVideoPolling();
        clearVideoElapsedTimer();
        await extendGoogleVideo(state.videoJob);
        return;
      }
      clearVideoPolling();
      clearVideoElapsedTimer();
      els.videoPreview.innerHTML = `<video controls playsinline src="${escapeHtml(data.contentUrl)}"></video>`;
      setStepStatus("video", "视频已完成，可以播放。");
      updatePipelineProgress(100, "视频已完成");
      addPipelineLog("视频完成，可以播放");
      els.downloadVideo.disabled = false;
    } else if (["failed", "cancelled", "canceled", "expired"].includes(String(state.videoJob.status || "").toLowerCase())) {
      clearVideoPolling();
      clearVideoElapsedTimer();
      renderVideoJob(state.videoJob);
      const errorMessage = state.videoJob.error?.message ? `：${state.videoJob.error.message}` : "";
      setStepStatus("video", `视频任务失败：${state.videoJob.status}${errorMessage}`, "error");
      updatePipelineProgress(null, "视频任务失败");
      addPipelineLog(`视频任务失败：${state.videoJob.status}${errorMessage}`);
    } else {
      renderVideoJob(state.videoJob);
      setStepStatus("video", `状态：${state.videoJob.status || "unknown"}，进度 ${state.videoJob.progress ?? 0}%`);
      const progress = Number(state.videoJob.progress);
      const visualProgress = Number.isFinite(progress) && progress > 0 ? Math.min(98, 88 + progress * 0.1) : 92;
      updatePipelineProgress(visualProgress, `视频生成中：${state.videoJob.status || "unknown"}`);
      if (!options.silent) addPipelineLog(`视频状态：${state.videoJob.status || "unknown"} ${state.videoJob.progress ?? 0}%`);
      scheduleVideoPolling();
    }
  } catch (error) {
    setStepStatus("video", error.message, "error");
    if (state.videoContentUrl) els.downloadVideo.disabled = false;
    if (!options.silent) addPipelineLog(`刷新视频失败：${error.message}`);
  } finally {
    els.pollVideo.disabled = !state.videoJob?.id || state.videoJob.status === "completed";
  }
}

async function extendGoogleVideo(completedJob) {
  const currentSeconds = Number(completedJob.seconds || 8);
  const targetSeconds = Number(completedJob.targetSeconds || els.videoSeconds.value || currentSeconds);
  const nextSeconds = Math.min(targetSeconds, currentSeconds + 7);
  els.downloadVideo.disabled = true;
  renderWorkingPreview("video", `继续延长到约 ${nextSeconds} 秒`);
  setStepStatus("video", `当前 ${currentSeconds} 秒已完成，正在延长到约 ${nextSeconds}/${targetSeconds} 秒...`, "working");
  updatePipelineProgress(92, `正在延长视频：${nextSeconds}/${targetSeconds} 秒`);
  addPipelineLog(`开始延长：${currentSeconds}s -> ${nextSeconds}s / 目标 ${targetSeconds}s`);
  const data = await postVideoJson({
    action: "extend_video",
    model: completedJob.model || els.videoModel.value,
    size: completedJob.size || els.videoSize.value,
    currentSeconds,
    targetSeconds,
    videoUri: completedJob.videoUri,
    prompt: els.videoPrompt.value.trim(),
  });
  state.videoJob = data.video || { id: data.id, status: data.status };
  state.videoStartedAt = Date.now();
  startVideoElapsedTimer();
  renderVideoJob(state.videoJob);
  els.pollVideo.disabled = !state.videoJob.id;
  scheduleVideoPolling();
}

async function quickRetryVideo() {
  const originalSize = els.videoSize.value;
  const originalSeconds = els.videoSeconds.value;
  clearVideoPolling();
  els.videoSize.value = "720x1280";
  els.videoSeconds.value = "4";
  addPipelineLog(`重试：4秒 / 720x1280。原设置 ${originalSeconds}s / ${originalSize}`);
  updatePipelineProgress(80, "正在低清快速重试");
  await generateVideo();
}

async function checkRecentVideos() {
  els.checkRecentVideos.disabled = true;
  updatePipelineProgress(currentPipelinePercent(), "正在检查最近视频任务");
  try {
    const data = await postVideoJson({ action: "list_videos", limit: 8 });
    if (!data.videos.length) {
      addPipelineLog("最近没有视频任务。");
      return;
    }
    const lines = data.videos.map((video) => {
      const progress = video.progress ?? 0;
      return `${video.id} | ${video.provider || "openai"} | ${video.status || "unknown"} | ${progress}% | ${video.seconds || "?"}s | ${video.size || "?"} | ${videoAgeText(video)}`;
    });
    addPipelineLog(`最近任务：\n${lines.join("\n")}`);
    const stuck = data.videos.find((video) => isVideoWaiting(video) && Number(video.progress || 0) === 0);
    if (stuck) {
      setStepStatus("video", `OpenAI 队列中：${stuck.status} / ${videoAgeText(stuck)}。localhost 已经提交成功。`, "working");
      updatePipelineProgress(92, "OpenAI 队列中，不是 localhost 卡住");
      addPipelineLog("检测到 OpenAI 后台任务 progress 仍为 0；先不要重复提交新任务。");
    }
    const active = data.videos.find((video) => ["queued", "in_progress", "processing"].includes(String(video.status || "").toLowerCase()));
    if (active && !state.videoJob?.id) {
      state.videoJob = active;
      state.videoStartedAt = active.created_at ? active.created_at * 1000 : Date.now();
      startVideoElapsedTimer();
      renderVideoJob(active);
      setStepStatus("video", `已接管最近任务：${active.id}，状态 ${active.status || "unknown"}`, "working");
      scheduleVideoPolling();
    }
  } catch (error) {
    addPipelineLog(`检查最近任务失败：${error.message}`);
    setStepStatus("video", error.message, "error");
  } finally {
    els.checkRecentVideos.disabled = false;
  }
}

async function createLocalPreviewVideo() {
  if (!window.MediaRecorder) throw new Error("当前浏览器不支持 MediaRecorder 本地合成视频。");

  clearVideoPolling();
  clearVideoElapsedTimer();
  updatePipelineProgress(88, "正在本地合成预览视频");
  addPipelineLog("Sora 队列不动，开始本地合成预览视频。");
  setStepStatus("video", "正在本地合成预览视频...", "working");
  renderWorkingPreview("video", "本地合成视频中");

  const width = els.videoSize.value.includes("x720") ? 1280 : 720;
  const height = els.videoSize.value.includes("x720") ? 720 : 1280;
  const seconds = Math.max(4, Number(els.videoSeconds.value || 4));
  const fps = 30;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const stream = canvas.captureStream(fps);
  const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
    ? "video/webm;codecs=vp9"
    : "video/webm";
  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks = [];
  recorder.ondataavailable = (event) => {
    if (event.data?.size) chunks.push(event.data);
  };
  const done = new Promise((resolve) => {
    recorder.onstop = resolve;
  });

  const frames = await buildLocalPreviewFrames();
  const totalFrames = seconds * fps;
  recorder.start();
  for (let frame = 0; frame < totalFrames; frame += 1) {
    const progress = frame / totalFrames;
    drawPreviewFrame(ctx, width, height, frames, progress);
    if (frame % fps === 0) updatePipelineProgress(88 + progress * 12, `本地合成中 ${Math.round(progress * 100)}%`);
    await new Promise((resolve) => setTimeout(resolve, 1000 / fps));
  }
  recorder.stop();
  await done;

  const blob = new Blob(chunks, { type: mimeType });
  const url = URL.createObjectURL(blob);
  els.videoPreview.classList.remove("is-working");
  els.videoPreview.innerHTML = `<video controls playsinline src="${url}"></video>`;
  setStepStatus("video", "本地预览视频已生成。Sora 任务仍可继续等待。");
  updatePipelineProgress(100, "本地预览视频完成");
  addPipelineLog("本地预览视频完成，可先用于检查节奏和画板流程。");
}

async function buildLocalPreviewFrames() {
  const steps = ["tone_reference", "product_reference", "storyboard", "actor_reference"];
  const frames = [];
  for (const step of steps) {
    const config = getVideoStepConfig(step);
    const dataUrl = state.videoAssets[step]?.dataUrl;
    const image = dataUrl ? await loadImage(dataUrl).catch(() => null) : null;
    frames.push({ label: config.label, image });
  }
  if (!frames.some((frame) => frame.image)) {
    frames.push({ label: els.keyword.value.trim() || "Product Demo", image: null });
  }
  return frames;
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
}

function drawPreviewFrame(ctx, width, height, frames, progress) {
  const frameIndex = Math.min(frames.length - 1, Math.floor(progress * frames.length));
  const localProgress = progress * frames.length - frameIndex;
  const frame = frames[frameIndex];
  ctx.fillStyle = "#080b0b";
  ctx.fillRect(0, 0, width, height);

  const zoom = 1.02 + localProgress * 0.06;
  if (frame.image) {
    const ratio = Math.max(width / frame.image.width, height / frame.image.height) * zoom;
    const drawWidth = frame.image.width * ratio;
    const drawHeight = frame.image.height * ratio;
    const panX = (localProgress - 0.5) * width * 0.06;
    const panY = (0.5 - localProgress) * height * 0.04;
    ctx.drawImage(frame.image, (width - drawWidth) / 2 + panX, (height - drawHeight) / 2 + panY, drawWidth, drawHeight);
  } else {
    ctx.fillStyle = "#151b1a";
    ctx.fillRect(width * 0.08, height * 0.18, width * 0.84, height * 0.58);
    ctx.strokeStyle = "#f1c84a";
    ctx.lineWidth = 4;
    ctx.strokeRect(width * 0.08, height * 0.18, width * 0.84, height * 0.58);
    ctx.fillStyle = "#f5f7f6";
    ctx.font = `700 ${Math.round(width * 0.055)}px system-ui, sans-serif`;
    wrapCanvasText(ctx, frame.label, width * 0.14, height * 0.44, width * 0.72, width * 0.07);
  }

  const gradient = ctx.createLinearGradient(0, height * 0.65, 0, height);
  gradient.addColorStop(0, "rgba(8,11,11,0)");
  gradient.addColorStop(1, "rgba(8,11,11,0.82)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, height * 0.65, width, height * 0.35);
  ctx.fillStyle = "#f1c84a";
  ctx.font = `800 ${Math.round(width * 0.032)}px system-ui, sans-serif`;
  ctx.fillText(frame.label, width * 0.08, height * 0.88);
  ctx.fillStyle = "#f5f7f6";
  ctx.font = `700 ${Math.round(width * 0.044)}px system-ui, sans-serif`;
  wrapCanvasText(ctx, els.keyword.value.trim() || "Product Demo", width * 0.08, height * 0.93, width * 0.84, width * 0.06);
}

function wrapCanvasText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = String(text).split(/\s+/);
  let line = "";
  for (const word of words) {
    const testLine = line ? `${line} ${word}` : word;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      line = word;
      y += lineHeight;
    } else {
      line = testLine;
    }
  }
  if (line) ctx.fillText(line, x, y);
}

async function postVideoJson(payload) {
  const apiKey = els.openaiApiKey.value.trim();
  const googleApiKey = els.googleApiKey.value.trim();
  const requestPayload = {
    ...payload,
    ...(apiKey ? { apiKey } : {}),
    ...(googleApiKey ? { googleApiKey } : {}),
  };
  const response = await fetch("/api/video-pipeline", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestPayload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) throw new Error(data.error || "video pipeline request failed");
  return data;
}

function getVideoStepConfig(step) {
  const map = {
    product_reference: {
      label: "产品参考板",
      prompt: els.productReferencePrompt,
      preview: els.productReferencePreview,
      status: els.productReferenceStatus,
      button: document.querySelector('[data-generate-step="product_reference"]'),
    },
    actor_reference: {
      label: "手模/真人固定",
      prompt: els.actorReferencePrompt,
      preview: els.actorReferencePreview,
      status: els.actorReferenceStatus,
      button: document.querySelector('[data-generate-step="actor_reference"]'),
    },
    storyboard: {
      label: "故事板",
      prompt: els.storyboardPrompt,
      preview: els.storyboardPreview,
      status: els.storyboardStatus,
      button: document.querySelector('[data-generate-step="storyboard"]'),
    },
    tone_reference: {
      label: "调性/首帧图",
      prompt: els.toneReferencePrompt,
      preview: els.toneReferencePreview,
      status: els.toneReferenceStatus,
      button: document.querySelector('[data-generate-step="tone_reference"]'),
    },
    video: {
      label: "产品演示视频",
      prompt: els.videoPrompt,
      preview: els.videoPreview,
      status: els.videoStatus,
      button: els.generateVideo,
    },
  };
  return map[step];
}

function renderImagePreview(step, dataUrl) {
  const config = getVideoStepConfig(step);
  config.preview.classList.remove("is-working");
  config.preview.innerHTML = `<img alt="${escapeHtml(config.label)}" src="${dataUrl}" />`;
}

function renderWorkingPreview(step, label) {
  const config = getVideoStepConfig(step);
  config.preview.classList.add("is-working");
  config.preview.innerHTML = `<div>${escapeHtml(label)}<br>请求模型中，请稍等</div>`;
}

function renderVideoJob(job) {
  const id = job?.id || "pending";
  const status = job?.status || "queued";
  const progress = job?.progress ?? 0;
  const provider = job?.provider === "google" ? "Google Veo 3.1" : "OpenAI Sora";
  const seconds = job?.targetSeconds && Number(job.targetSeconds) > Number(job.seconds || 0)
    ? `${job.seconds || "?"}/${job.targetSeconds}s`
    : `${job?.seconds || "?"}s`;
  const elapsed = videoElapsedText();
  els.videoPreview.classList.remove("is-working");
  els.videoPreview.innerHTML = `<div>${escapeHtml(provider)} Job<br>${escapeHtml(id)}<br>${escapeHtml(status)} ${progress}%<br>${escapeHtml(seconds)}<br>${escapeHtml(elapsed)}</div>`;
}

function syncGooglePipelineDefaults() {
  const googleMode = els.googleApiKey.value.trim() && String(els.videoModel.value || "").startsWith("veo-");
  const targetSeconds = Number(els.videoSeconds.value || 8);
  if (googleMode && String(els.imageModel.value || "").startsWith("gpt-image")) {
    els.imageModel.value = "gemini-3.1-flash-image-preview";
  }
  if (googleMode && targetSeconds > 8) {
    if (els.videoModel.value === "veo-3.1-lite-generate-preview") els.videoModel.value = "veo-3.1-generate-preview";
    if (els.videoSize.value === "1024x1792") els.videoSize.value = "720x1280";
    if (els.videoSize.value === "1792x1024") els.videoSize.value = "1280x720";
  }
}

function shouldExtendGoogleVideo(job) {
  return (
    job?.provider === "google" &&
    String(job.model || "").includes("veo-3.1") &&
    job.model !== "veo-3.1-lite-generate-preview" &&
    Number(job.targetSeconds || 0) > Number(job.seconds || 0) &&
    Boolean(job.videoUri)
  );
}

function downloadGeneratedVideo() {
  if (!state.videoContentUrl) {
    setStepStatus("video", "还没有可下载的视频。", "error");
    return;
  }
  const link = document.createElement("a");
  const seconds = state.videoJob?.seconds || els.videoSeconds.value || "video";
  link.href = state.videoContentUrl;
  link.download = `product-demo-${seconds}s.mp4`;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function chooseVideoInputReference() {
  const targetSize = els.videoSize.value;
  for (const step of ["tone_reference", "product_reference", "storyboard", "actor_reference"]) {
    const asset = state.videoAssets[step];
    if (asset?.dataUrl && asset.size === targetSize) return { step, image_url: asset.dataUrl };
  }
  return null;
}

function setStepStatus(step, message, type = "") {
  const config = getVideoStepConfig(step);
  if (!config?.status) return;
  config.status.textContent = message;
  config.status.classList.toggle("is-working", type === "working");
  config.status.classList.toggle("is-error", type === "error");
}

function scheduleVideoPolling() {
  if (!state.videoJob?.id || state.videoJob.status === "completed" || state.videoPollTimer) return;
  state.videoPollTimer = window.setTimeout(async () => {
    state.videoPollTimer = null;
    if (state.videoJob?.id && state.videoJob.status !== "completed") await pollVideo({ silent: true });
  }, 5000);
}

function clearVideoPolling() {
  if (!state.videoPollTimer) return;
  window.clearTimeout(state.videoPollTimer);
  state.videoPollTimer = null;
}

function startVideoElapsedTimer() {
  clearVideoElapsedTimer();
  state.videoElapsedTimer = window.setInterval(() => {
    if (state.videoJob?.id && state.videoJob.status !== "completed") {
      renderVideoJob(state.videoJob);
      const elapsedSeconds = Math.floor((Date.now() - state.videoStartedAt) / 1000);
      if (elapsedSeconds === 300) addPipelineLog("已经等待 5 分钟；建议点击“查最近任务”确认状态，或点“4秒低清重试”。");
    }
  }, 1000);
}

function clearVideoElapsedTimer() {
  if (!state.videoElapsedTimer) return;
  window.clearInterval(state.videoElapsedTimer);
  state.videoElapsedTimer = null;
}

function videoElapsedText() {
  if (!state.videoStartedAt) return "elapsed 00:00";
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - state.videoStartedAt) / 1000));
  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const seconds = String(elapsedSeconds % 60).padStart(2, "0");
  return `elapsed ${minutes}:${seconds}`;
}

function videoAgeText(video) {
  if (!video?.created_at) return "age unknown";
  const ageSeconds = Math.max(0, Math.floor(Date.now() / 1000 - Number(video.created_at)));
  const minutes = Math.floor(ageSeconds / 60);
  const seconds = ageSeconds % 60;
  return `${minutes}m ${seconds}s ago`;
}

function isVideoWaiting(video) {
  return ["queued", "in_progress", "processing"].includes(String(video?.status || "").toLowerCase());
}

function updatePipelineProgress(percent, label) {
  if (label) els.pipelineStatus.textContent = label;
  if (typeof percent === "number") {
    const safePercent = Math.max(0, Math.min(100, Math.round(percent)));
    els.pipelinePercent.textContent = `${safePercent}%`;
    els.pipelineBar.style.width = `${safePercent}%`;
  }
}

function currentPipelinePercent() {
  return Number.parseInt(els.pipelinePercent.textContent, 10) || 0;
}

function addPipelineLog(message) {
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  state.pipelineLogs.push(`[${time}] ${message}`);
  state.pipelineLogs = state.pipelineLogs.slice(-8);
  els.pipelineLog.textContent = state.pipelineLogs.join("\n");
  els.pipelineLog.scrollTop = els.pipelineLog.scrollHeight;
}

function resetVideoStudio() {
  state.videoAssets = {};
  state.videoJob = null;
  state.videoContentUrl = "";
  clearVideoPolling();
  clearVideoElapsedTimer();
  state.videoStartedAt = 0;
  state.pipelineLogs = [];
  updatePipelineProgress(0, "等待开始");
  els.pipelineLog.textContent = "准备好后点击“按步骤生成”。";
  for (const step of videoImageSteps) {
    const config = getVideoStepConfig(step);
    config.preview.classList.remove("is-working");
    config.preview.textContent = config.label;
    setStepStatus(step, "等待");
  }
  els.videoPreview.classList.remove("is-working");
  els.videoPreview.textContent = "Video";
  els.pollVideo.disabled = true;
  els.downloadVideo.disabled = true;
  setStepStatus("video", "等待");
  refreshVideoPrompts();
}

async function handleFiles(fileList) {
  const files = Array.from(fileList || []);
  for (const file of files) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (["csv", "txt", "tsv"].includes(ext)) {
      const text = await file.text();
      const type = inferUploadType(file.name, text);
      state.uploads.push({ name: file.name, type, text: normalizeText(text), parsed: true });
    } else if (["xlsx", "xls"].includes(ext)) {
      try {
        const parsed = await postJson("/api/parse-upload", {
          name: file.name,
          dataUrl: await fileToDataUrl(file),
        });
        const type = inferUploadType(file.name, parsed.text);
        state.uploads.push({ name: file.name, type, text: normalizeText(parsed.text), parsed: true });
      } catch (error) {
        state.uploads.push({ name: file.name, type: "official_report", text: "", parsed: false, error: error.message });
      }
    } else {
      state.uploads.push({ name: file.name, type: "official_report", text: "", parsed: false });
    }
  }
  renderUploads();
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("file read failed"));
    reader.readAsDataURL(file);
  });
}

function inferUploadType(name, text) {
  const lower = `${name} ${text.slice(0, 500)}`.toLowerCase();
  if (/google trends|trends|讨论热度|讨论总量|上升速度|增长速度|growth|volume|月份\/周|地区\/语种/.test(lower)) {
    return "trend_report";
  }
  if (/brand analytics|search query performance|search term|campaign|impressions|clicks|spend|orders|sales/.test(lower)) {
    return "official_report";
  }
  return "review_text";
}

function normalizeText(text) {
  return String(text || "")
    .replace(/\r/g, "\n")
    .replace(/[;]/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function renderAll() {
  renderMetrics();
  renderTable();
  els.packageOutput.textContent = state.packageText;
  const enabled = Boolean(state.rows.length || state.packageText);
  els.downloadCsv.disabled = !enabled;
  els.downloadXlsx.disabled = !enabled;
  els.copy.disabled = !enabled;
  els.downloadTxt.disabled = !enabled;
}

function renderMetrics() {
  const sources = collectTextSources();
  const reportCount = sources.filter((source) => source.type === "official_report" || source.type === "trend_report").length;
  els.sourceCount.textContent = state.collection?.items?.length || sources.length;
  els.keywordCount.textContent = state.rows.length;
  els.reportCount.textContent = reportCount;
}

function renderTable() {
  if (!state.rows.length) {
    els.table.innerHTML = `<tr><td colspan="${templateHeaders.length}" class="empty-cell">没有词库数据</td></tr>`;
    return;
  }
  els.table.innerHTML = buildTemplateRows(state.rows)
    .slice(0, 500)
    .map((row) => {
      return `<tr>
        <td>${escapeHtml(row.displayCategory)}</td>
        <td>${escapeHtml(row.term)}</td>
        <td>${escapeHtml(row.weight)}</td>
        <td>${escapeHtml(row.count)}</td>
        <td>${escapeHtml(row.rawSearchTerm)}</td>
        <td>${escapeHtml(row.locale)}</td>
        <td>${escapeHtml(row.opportunity)}</td>
      </tr>`;
    })
    .join("");
}

function buildTemplateRows(rows) {
  const context = buildWeightContext(rows);
  return rows
    .filter((row) => row.term && row.term.length > 1)
    .map((row) => {
    const category = templateCategory(row);
      const trend = state.trendLookup.get(String(row.term || "").toLowerCase()) || {};
      return {
        displayCategory: category,
        category,
        term: row.term,
        weight: scoreKeywordRow(row, category, trend, context),
        discussionTotal: trend.total || "",
        growthSpeed: trend.growth || "",
        trendHeat: trend.heat || "",
        count: row.count || "",
        rawSearchTerm: trend.raw || joinSet(row.sourceQueries, 3),
        locale: trend.region || joinSet(row.regions, 2) || state.collection?.region || els.region.value,
        period: trend.period || joinSet(row.periods, 2),
        opportunity: demandOpportunity(row, category, trend),
        meaning: trend.meaning || "",
        sourceTypes: row.sourceTypes,
        field: row.field,
      };
    })
    .sort((a, b) => b.weight - a.weight || Number(b.count || 0) - Number(a.count || 0) || a.term.localeCompare(b.term));
}

function buildWeightContext(rows) {
  const maxCount = Math.max(1, ...rows.map((row) => Number(row.count || 0)));
  const maxQueries = Math.max(1, ...rows.map((row) => row.sourceQueries?.size || 0));
  const heatValues = Array.from(state.trendLookup.values())
    .map((trend) => parseTrendHeat(trend.heat))
    .filter((value) => value !== null);
  const maxHeat = Math.max(100, ...heatValues);
  return { maxCount, maxQueries, maxHeat };
}

function scoreKeywordRow(row, category, trend, context) {
  const count = Number(row.count || 0);
  const countScore = (Math.log1p(count) / Math.log1p(context.maxCount || 1)) * 45;
  const queryCoverage = row.sourceQueries?.size ? Math.min(1, row.sourceQueries.size / (context.maxQueries || 1)) : 0;
  const queryScore = queryCoverage * 15;
  const sourceScore = Math.min(1, (row.sourceTypes?.size || 0) / 3) * 10;
  const heat = parseTrendHeat(trend.heat);
  const trendScore = heat === null ? 0 : Math.min(1, heat / (context.maxHeat || 100)) * 15;
  const intentScore = categoryIntentWeight(category);
  const specificityScore = specificityWeight(row.term);
  return Math.max(1, Math.min(100, Math.round(countScore + queryScore + sourceScore + trendScore + intentScore + specificityScore)));
}

function parseTrendHeat(value) {
  const text = String(value ?? "").replace(/,/g, "").trim();
  if (!text) return null;
  const match = text.match(/\d+(?:\.\d+)?/);
  if (!match) return null;
  const number = Number(match[0]);
  return Number.isFinite(number) ? number : null;
}

function parseMetricNumber(value) {
  const text = String(value ?? "").replace(/,/g, "").trim().toLowerCase();
  if (!text) return null;
  const match = text.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  let number = Number(match[0]);
  if (!Number.isFinite(number)) return null;
  if (/%/.test(text)) return number;
  if (/\bk\b/.test(text)) number *= 1000;
  if (/\bm\b/.test(text)) number *= 1000000;
  return number;
}

function demandOpportunity(row, category, trend) {
  const total = parseMetricNumber(trend.total);
  const growth = parseMetricNumber(trend.growth);
  if (growth !== null && total !== null) {
    if (growth >= 30 && total >= 1000) return "高总量 + 高增长，优先做主方向";
    if (growth >= 30) return "增长快，适合测试新内容";
    if (total >= 1000) return "总量高，适合稳定铺量";
    if (growth > 0) return "有增长，继续观察";
    if (growth < 0) return "增速为负，谨慎投入";
  }
  if (growth !== null) return growth > 0 ? "有真实增速，适合跟踪" : "真实增速偏弱";
  if (total !== null) return "有真实总量，缺增速判断";
  if (Number(row.count || 0) >= 20 || category === "核心关键词") return "候选方向";
  return "";
}

function categoryIntentWeight(category) {
  const weights = {
    "核心关键词": 10,
    "Google Trends词": 10,
    "痛点评论词": 9,
    "功能特性": 8,
    "使用场景": 7,
    "内容场景词": 7,
    "规格参数": 6,
    "材质": 5,
    "目标受众": 5,
    "形状款式": 5,
    "变体": 4,
    Hashtag: 3,
    "品牌词": 2,
    "搜索种子词": 6,
    "真实报告词": 8,
  };
  return weights[category] || 4;
}

function specificityWeight(term) {
  const words = String(term || "").split(/\s+/).filter(Boolean).length;
  if (words >= 4) return 8;
  if (words === 3) return 7;
  if (words === 2) return 5;
  return String(term || "").length >= 8 ? 3 : 1;
}

function templateCategory(row) {
  const term = String(row.term || "").toLowerCase();
  if (row.field === "搜索种子词") return "搜索种子词";
  if (row.field === "Google Trends词") return "Google Trends词";
  if (row.field === "真实报告词") return "真实报告词";
  if (row.field === "Hashtag" || term.startsWith("#")) return "Hashtag";
  if (row.field === "痛点/评论词") return "痛点评论词";
  if (row.field === "视频钩子词" || row.field === "内容场景词") return "内容场景词";
  if (/\b(women|woman|men|man|kids|kid|girls|boys|beginner|beginners|teacher|student|mom|dad|family|adult|teen|teens|pet|pets)\b/.test(term)) return "目标受众";
  if (/\b(cotton|silicone|rubber|plastic|wood|bamboo|steel|metal|leather|mesh|foam|microfiber|fabric|linen|glass|ceramic|resin|nylon|polyester|suede|wool)\b/.test(term)) return "材质";
  if (/\b(size|small|medium|large|xl|mini|inch|cm|mm|oz|lb|pack|set|count|pcs|piece|pieces|wide|thick|thin|long|short|portable|foldable)\b/.test(term) || /^\d+(\.\d+)?$/.test(term)) return "规格参数";
  if (/\b(black|white|pink|blue|green|grey|gray|red|purple|brown|beige|clear|navy|gold|silver|color|colors|double|single|dual|multi|extra|pro)\b/.test(term)) return "变体";
  if (/\b(home|office|travel|gym|workout|desk|car|kitchen|bathroom|bedroom|outdoor|camping|school|business|daily|routine|studio|yoga|pilates)\b/.test(term)) return "使用场景";
  if (/\b(waterproof|non slip|nonslip|anti slip|portable|easy|fast|safe|compact|sturdy|lightweight|adjustable|reusable|washable|durable|resistant|compatible|multipurpose|multifunctional|soft|strong|secure|grip|support|cushion|absorbent)\b/.test(term)) return "功能特性";
  if (/\b(case|bag|box|pouch|holder|stand|organizer|mat|bottle|brush|clip|strap|rack|tray|kit|sleeve|cover|pad|cushion|towel|wrap|board|basket|container)\b/.test(term)) return "形状款式";
  if (/^[A-Z0-9][A-Za-z0-9-]{2,}$/.test(String(row.term || "")) && row.count <= 3) return "品牌词";
  return "核心关键词";
}

function useFor(row) {
  if (row.field === "真实报告词") return "真实报告优先字段";
  if (row.field === "痛点/评论词") return "评论痛点 / 视频开头冲突";
  if (row.field === "视频钩子词") return "前三秒 hook / 视频标题";
  if (row.field === "卖点/功能词") return "Listing bullet / 演示镜头";
  if (row.field === "Hashtag") return "TikTok 发布标签";
  if (row.field === "内容场景词") return "视频选题 / 场景脚本";
  return "搜索词 / 标题长尾";
}

function renderUploads() {
  els.uploadList.innerHTML = state.uploads
    .map((upload) => `<span class="upload-item">${escapeHtml(upload.name)} ${upload.parsed ? "已解析" : `未解析${upload.error ? `: ${upload.error}` : ""}`}</span>`)
    .join("");
  buildFromCurrentText();
}

function downloadCsv() {
  const rows = templateRowsMatrix();
  downloadFile(`${state.platform}_keyword_library_template.csv`, toCsv(rows), "text/csv;charset=utf-8");
}

function templateRowsMatrix() {
  const templateRows = buildTemplateRows(state.rows);
  return [
    templateHeaders,
    ...templateRows.map((row) => [
      row.displayCategory,
      row.term,
      row.weight,
      row.count,
      row.rawSearchTerm,
      row.locale,
      row.opportunity,
    ]),
  ];
}

function googleTrendsRowsMatrix() {
  const rows = buildTemplateRows(state.rows).filter((row) => row.discussionTotal || row.growthSpeed || row.trendHeat || row.period || row.meaning);
  if (!rows.length) {
    return [["趋势数据"], ["状态", "未上传真实 Google Trends / TikTok / Seller Center 趋势数据"]];
  }
  return [
    ["特征词", "讨论总量", "上升速度", "讨论热度", "地区/语种", "月份/周", "词义"],
    ...rows.map((row) => [row.term, row.discussionTotal, row.growthSpeed, row.trendHeat, row.locale, row.period, row.meaning]),
  ];
}

function summaryRowsMatrix() {
  const templateRows = buildTemplateRows(state.rows);
  const trendRows = templateRows.filter((row) => row.trendHeat || row.period || row.meaning);
  const totalRows = templateRows.filter((row) => parseMetricNumber(row.discussionTotal) !== null);
  const growthRows = templateRows.filter((row) => parseMetricNumber(row.growthSpeed) !== null);
  const collectionStats = state.collection?.stats;
  const topRow = templateRows[0] || {};
  const avgWeight = templateRows.length
    ? Math.round(templateRows.reduce((sum, row) => sum + Number(row.weight || 0), 0) / templateRows.length)
    : "";
  return [
    ["汇总分析"],
    ["结论", overallDemandConclusion(templateRows)],
    ["产品关键词", els.keyword.value.trim()],
    ["平台", platformLabel()],
    ["地区/语种", els.region.value],
    ["TK模板词条数", templateRows.length],
    ["平均Weight", avgWeight],
    ["最高Weight关键词", topRow.term || ""],
    ["最高Weight", topRow.weight || ""],
    ["真实趋势数据词条", trendRows.length + totalRows.length + growthRows.length],
    ["公开采集来源", state.collection?.items?.length || ""],
    ["公开来源查询数", state.collection?.sourceQueries?.length || ""],
    ["采集错误数", collectionStats?.errors ?? ""],
    ["数据规则", "没有真实趋势数据时，只给候选方向。"],
  ];
}

function overallDemandConclusion(templateRows = buildTemplateRows(state.rows)) {
  const totalRows = templateRows.filter((row) => parseMetricNumber(row.discussionTotal) !== null);
  const growthRows = templateRows.filter((row) => parseMetricNumber(row.growthSpeed) !== null);
  if (totalRows.length && growthRows.length) {
    const fastest = [...growthRows].sort((a, b) => parseMetricNumber(b.growthSpeed) - parseMetricNumber(a.growthSpeed))[0];
    const biggest = [...totalRows].sort((a, b) => parseMetricNumber(b.discussionTotal) - parseMetricNumber(a.discussionTotal))[0];
    return `可做真实需求判断：总量最高是「${biggest.term}」，增速最快是「${fastest.term}」。`;
  }
  if (growthRows.length) {
    const fastest = [...growthRows].sort((a, b) => parseMetricNumber(b.growthSpeed) - parseMetricNumber(a.growthSpeed))[0];
    return `已有真实增速但缺讨论总量：优先观察「${fastest.term}」，同时补充总量数据。`;
  }
  if (totalRows.length) {
    const biggest = [...totalRows].sort((a, b) => parseMetricNumber(b.discussionTotal) - parseMetricNumber(a.discussionTotal))[0];
    return `已有真实讨论总量但缺增速：总量最高是「${biggest.term}」，还不能判断是否正在上升。`;
  }
  if (templateRows.length) {
    const top = templateRows[0];
    return `当前只有公开搜索建议；先把「${top.term}」作为候选方向。`;
  }
  return "没有可分析数据。";
}

function agentAnalysisRowsMatrix() {
  const templateRows = buildTemplateRows(state.rows);
  const topByWeight = templateRows.slice(0, 20);
  const topByTotal = [...templateRows]
    .filter((row) => parseMetricNumber(row.discussionTotal) !== null)
    .sort((a, b) => parseMetricNumber(b.discussionTotal) - parseMetricNumber(a.discussionTotal))
    .slice(0, 20);
  const topByGrowth = [...templateRows]
    .filter((row) => parseMetricNumber(row.growthSpeed) !== null)
    .sort((a, b) => parseMetricNumber(b.growthSpeed) - parseMetricNumber(a.growthSpeed))
    .slice(0, 20);
  const rows = [
    ["Agent Analysis"],
    ["结论", overallDemandConclusion(templateRows)],
    ["口径", "当前采集只来自公开搜索建议/词频；没有真实趋势报告时，只输出候选方向。"],
    ["产品关键词", els.keyword.value.trim()],
    ["平台", platformLabel()],
    ["地区/语种", els.region.value],
    [],
  ];

  if (topByTotal.length || topByGrowth.length) {
    rows.push(["真实趋势 Top", "特征词", "讨论总量", "上升速度", "Weight", "结论"]);
    const metricRows = [...new Map([...topByGrowth, ...topByTotal].map((row) => [row.term, row])).values()]
      .slice(0, 20)
      .map((row, index) => [index + 1, row.term, row.discussionTotal, row.growthSpeed, row.weight, row.opportunity]);
    rows.push(...metricRows, []);
  }

  rows.push(
    ["候选方向 Top", "特征词", "Weight", "出现次数", "原始搜索词", "结论"],
    ...topByWeight.map((row, index) => [index + 1, row.term, row.weight, row.count, row.rawSearchTerm, row.opportunity]),
    [],
    ["需要补充", "如要做趋势判断，再上传 TikTok Creative Center / Seller Center / Ads / Google Trends 的周度数据"],
  );
  return rows;
}

function confusionMatrixRowsMatrix() {
  const templateRows = buildTemplateRows(state.rows);
  const sourceLabels = Array.from(new Set(templateRows.map((row) => row.field || "未知信号"))).sort();
  const categoryLabels = Array.from(new Set(templateRows.map((row) => row.category || "未分类"))).sort();
  const matrix = new Map();
  for (const row of templateRows) {
    const source = row.field || "未知信号";
    const category = row.category || "未分类";
    const key = `${source}__${category}`;
    matrix.set(key, (matrix.get(key) || 0) + 1);
  }
  return [
    ["Confusion Matrix"],
    ["说明", "这里不是机器学习准确率；它是“来源信号/初始分类”与“最终模板分类”的交叉表，用来发现分类规则是否混淆。"],
    [],
    ["来源信号 \\ 最终分类", ...categoryLabels, "Total"],
    ...sourceLabels.map((source) => {
      const counts = categoryLabels.map((category) => matrix.get(`${source}__${category}`) || 0);
      return [source, ...counts, counts.reduce((sum, value) => sum + value, 0)];
    }),
  ];
}

function regionCoverageRowsMatrix() {
  const templateRows = buildTemplateRows(state.rows);
  const map = new Map();
  for (const row of templateRows) {
    const locale = row.locale || els.region.value || "未知";
    const entry = map.get(locale) || { rows: 0, count: 0, weight: 0, totalMetrics: 0, growthMetrics: 0, topTerm: "", topWeight: 0 };
    entry.rows += 1;
    entry.count += Number(row.count || 0);
    entry.weight += Number(row.weight || 0);
    if (parseMetricNumber(row.discussionTotal) !== null) entry.totalMetrics += 1;
    if (parseMetricNumber(row.growthSpeed) !== null) entry.growthMetrics += 1;
    if (Number(row.weight || 0) > entry.topWeight) {
      entry.topWeight = Number(row.weight || 0);
      entry.topTerm = row.term;
    }
    map.set(locale, entry);
  }
  const rows = Array.from(map.entries()).map(([locale, entry]) => [
    locale,
    entry.rows,
    entry.count,
    entry.rows ? Math.round(entry.weight / entry.rows) : "",
    entry.totalMetrics,
    entry.growthMetrics,
    entry.topTerm,
    entry.topWeight || "",
  ]);
  rows.sort((a, b) => Number(b[3] || 0) - Number(a[3] || 0));
  return [["地区/语种", "词条数", "总出现次数", "平均Weight", "真实总量词条", "真实增速词条", "最高Weight词", "最高Weight"], ...rows];
}

function scoringModelRowsMatrix() {
  return [
    ["Weight Scoring Model"],
    ["说明", "Weight 是本工具内部排序分，只用于选词优先级；它不是 Amazon/TikTok 官方搜索量，也不是 Google Trends 热度。"],
    ["组件", "最高分", "数据来源", "空白/无数据处理"],
    ["出现次数", 45, "公开采集文本、上传文本、真实报告中观察到的词频", "无词频则为 0"],
    ["来源查询覆盖", 15, "采集时保留的原始搜索 query 数", "无 query 元数据则为 0"],
    ["来源类型覆盖", 10, "标题、评论、报告、趋势等来源类型数量", "无来源类型则为 0"],
    ["真实趋势热度", 15, "上传 Google Trends / TikTok / 趋势报告里的讨论热度", "无真实热度则为 0，不估算"],
    ["讨论总量", "展示字段", "上传报告里的 volume/views/posts/comments/讨论总量", "无真实总量则留空，不估算"],
    ["上升速度", "展示字段", "上传报告里的 growth/growth rate/WoW/MoM/环比/增量", "无真实增速则留空，不估算"],
    ["机会判断", "规则结论", "优先使用讨论总量 + 上升速度；否则只基于公开词频给候选方向", "缺真实增速时不会写成确定预测"],
    ["意图强度", 10, "最终分类：核心词、痛点词、功能词、内容场景词等", "按规则给固定权重"],
    ["长尾具体度", 8, "词组长度和具体度", "单词较低，多词长尾较高"],
    ["排序规则", "Weight desc", "同分时按出现次数 desc，再按词典顺序", ""],
  ];
}

async function downloadXlsx() {
  const response = await fetch("/api/export-keyword-xlsx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sheets: [
        { name: "TK模板", rows: templateRowsMatrix() },
        { name: "汇总表", rows: summaryRowsMatrix() },
        { name: "agent analysis", rows: agentAnalysisRowsMatrix() },
        { name: "google trends", rows: googleTrendsRowsMatrix() },
      ],
    }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || "xlsx export failed");
  }
  const blob = await response.blob();
  downloadBlob(`${state.platform}_keyword_library_template.xlsx`, blob);
}

async function copyPackage() {
  await navigator.clipboard.writeText(state.packageText);
  els.copy.textContent = "已复制";
  setTimeout(() => {
    els.copy.textContent = "复制";
  }, 1200);
}

function downloadTxt() {
  downloadFile(`${state.platform}_keyword_source_audit.txt`, state.packageText, "text/plain;charset=utf-8");
}

function toCsv(rows) {
  return rows
    .map((row) =>
      row
        .map((cell) => {
          const text = String(cell ?? "");
          return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
        })
        .join(","),
    )
    .join("\n");
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
  downloadBlob(filename, blob);
}

function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function loadSample() {
  state.platform = "amazon";
  els.platformButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.platform === "amazon"));
  els.keyword.value = "yoga mat";
  els.region.value = "US";
  els.buyer.value = "home workout buyers, beginners, pilates buyers";
  els.price.value = "$19.99-$49.99";
  els.productText.value = "";
  els.reviewText.value = "";
  els.reportText.value = "";
  setProgress("示例已填入。点击采集词库。");
  refreshVideoPrompts();
}

function clearAll() {
  state.uploads = [];
  state.collection = null;
  state.autoProductText = "";
  state.autoReviewText = "";
  state.trendLookup = new Map();
  state.rows = [];
  state.packageText = "";
  els.keyword.value = "";
  els.buyer.value = "";
  els.price.value = "";
  els.productText.value = "";
  els.reviewText.value = "";
  els.reportText.value = "";
  els.uploadList.innerHTML = "";
  els.packageOutput.textContent = "采集后生成。没有真实数据的字段保持空白，不会模拟。";
  els.table.innerHTML = `<tr><td colspan="${templateHeaders.length}" class="empty-cell">等待采集</td></tr>`;
  els.sourceCount.textContent = "0";
  els.keywordCount.textContent = "0";
  els.reportCount.textContent = "0";
  els.downloadCsv.disabled = true;
  els.downloadXlsx.disabled = true;
  els.copy.disabled = true;
  els.downloadTxt.disabled = true;
  resetVideoStudio();
  setProgress("准备采集。不会生成模拟 ABA、模拟 Google Trends 热度或假销量。");
}

function updateConnectionLabel() {
  els.connectionStatus.textContent = els.localMode.checked ? "localhost mode" : "Vercel mode";
}

function platformLabel() {
  return state.platform === "amazon" ? "Amazon" : "TikTok Shop";
}

function setProgress(text, type = "") {
  els.progress.textContent = text;
  els.progress.classList.toggle("is-working", type === "working");
  els.progress.classList.toggle("is-error", type === "error");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
