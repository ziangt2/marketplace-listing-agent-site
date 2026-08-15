const MAX_ITEMS = 2200;
const MAX_SOURCE_TEXT_CHARS = 240000;
const CONCURRENCY = 8;
const FETCH_TIMEOUT_MS = 4500;
const MAX_GENERAL_SEARCH_QUERIES = 12;
const MAX_TIKTOK_SEARCH_QUERIES = 0;
const MAX_GENERAL_SUGGESTION_QUERIES = 90;
const MAX_TIKTOK_SUGGESTION_QUERIES = 120;
const MAX_GENERAL_PAGE_QUERIES = 2;
const MAX_TIKTOK_PAGE_QUERIES = 0;

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, error: "Method not allowed" });
    return;
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    const platform = body.platform === "tiktok_shop" ? "tiktok_shop" : "amazon";
    const keyword = String(body.keyword || "").trim();
    const region = String(body.region || "US").trim();

    if (!keyword) {
      res.status(400).json({ ok: false, error: "keyword is required" });
      return;
    }

    const result = await collectMarketplace({ platform, keyword, region });
    res.status(200).json(result);
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message || "collect failed" });
  }
};

async function collectMarketplace({ platform, keyword, region }) {
  const markets = getMarketConfigs(region);
  const marketSummary = summarizeMarkets(region, markets);
  const queryPlan = limitQueryPlan({
    platform,
    queries: markets.flatMap((market) => buildQueries(platform, keyword, market)),
    suggestionQueries: markets.flatMap((market) => buildSuggestionQueries(platform, keyword, market)),
    pageQueries: markets.flatMap((market) => buildPublicPageQueries(platform, keyword, market)),
  });
  const collected = [];
  const errors = [];

  const searchTasks = queryPlan.queries.map((query) => async () => {
    try {
      const rows = await fetchDuckDuckGo(query.q);
      for (const row of rows) collected.push({ ...row, sourceType: query.sourceType, query: query.q, region: query.regionLabel, language: query.language });
    } catch (error) {
      errors.push({ query: query.q, error: error.message });
    }
  });

  const suggestionTasks = queryPlan.suggestionQueries.map((query) => async () => {
    try {
      const rows = await fetchSuggestions(query);
      for (const row of rows) collected.push({ ...row, sourceType: query.sourceType, query: query.q, region: query.regionLabel, language: query.language });
    } catch (error) {
      errors.push({ query: query.q, error: error.message });
    }
  });

  const pageTasks = queryPlan.pageQueries.map((query) => async () => {
    try {
      const rows = await fetchPublicPageText(query);
      for (const row of rows) collected.push({ ...row, sourceType: query.sourceType, query: query.q, region: query.regionLabel, language: query.language });
    } catch (error) {
      errors.push({ query: query.url, error: error.message });
    }
  });

  await runLimited([...suggestionTasks, ...searchTasks, ...pageTasks], CONCURRENCY);

  const items = dedupe(collected).slice(0, MAX_ITEMS);
  return {
    ok: true,
    platform,
    keyword,
    region,
    market: marketSummary,
    markets,
    queries: [
      ...queryPlan.queries.map((query) => query.q),
      ...queryPlan.suggestionQueries.map((query) => query.q),
      ...queryPlan.pageQueries.map((query) => query.url),
    ],
    errors,
    items,
    sourceQueries: Array.from(new Set(items.map((item) => item.query).filter(Boolean))).slice(0, 500),
    sourceTexts: groupSourceTexts(items),
    stats: summarizeItems(items, errors, queryPlan),
    dataPolicy: "No simulated ABA, Ads, sales, search-volume, or trend data. Weight is derived only from observed source counts, source coverage, and uploaded real metrics.",
  };
}

function getMarketConfig(region) {
  const configs = {
    US: { label: "US", gl: "US", hl: "en", language: "en", searchLabel: "United States", spanish: false },
    UK: { label: "UK", gl: "GB", hl: "en", language: "en", searchLabel: "United Kingdom", spanish: false },
    CA: { label: "CA", gl: "CA", hl: "en", language: "en", searchLabel: "Canada", spanish: false },
    AU: { label: "AU", gl: "AU", hl: "en", language: "en", searchLabel: "Australia", spanish: false },
    DE: { label: "DE", gl: "DE", hl: "de", language: "de", searchLabel: "Germany", spanish: false },
    "US-ES": { label: "US Spanish", gl: "US", hl: "es", language: "es", searchLabel: "Estados Unidos español", spanish: true },
    ES: { label: "ES Spain", gl: "ES", hl: "es", language: "es", searchLabel: "España", spanish: true },
    MX: { label: "MX Mexico", gl: "MX", hl: "es", language: "es", searchLabel: "México", spanish: true },
    CO: { label: "CO Colombia", gl: "CO", hl: "es", language: "es", searchLabel: "Colombia", spanish: true },
    CL: { label: "CL Chile", gl: "CL", hl: "es", language: "es", searchLabel: "Chile", spanish: true },
    AR: { label: "AR Argentina", gl: "AR", hl: "es", language: "es", searchLabel: "Argentina", spanish: true },
    PE: { label: "PE Peru", gl: "PE", hl: "es", language: "es", searchLabel: "Perú", spanish: true },
    "LATAM-ES": { label: "LATAM Spanish", gl: "MX", hl: "es", language: "es", searchLabel: "Latinoamérica", spanish: true },
  };
  return configs[region] || configs.US;
}

function getMarketConfigs(region) {
  if (region === "ES-BUNDLE") {
    return ["US-ES", "ES", "MX"].map(getMarketConfig).map((market) => ({ ...market, bundle: true }));
  }
  return [getMarketConfig(region)];
}

function summarizeMarkets(region, markets) {
  if (markets.length === 1) return markets[0];
  return {
    label: region === "ES-BUNDLE" ? "Spanish Bundle" : markets.map((market) => market.label).join(" + "),
    gl: markets.map((market) => market.gl).join(","),
    hl: "es",
    language: "es",
    searchLabel: markets.map((market) => market.searchLabel).join(", "),
    spanish: markets.some((market) => market.spanish),
    markets: markets.map((market) => market.label),
  };
}

function withMarketMeta(query, market) {
  return {
    ...query,
    regionLabel: market.label,
    language: market.language,
    hl: query.hl || market.hl,
    gl: query.gl || market.gl,
  };
}

function limitQueryPlan({ platform, queries, suggestionQueries, pageQueries }) {
  const searchLimit = platform === "tiktok_shop" ? MAX_TIKTOK_SEARCH_QUERIES : MAX_GENERAL_SEARCH_QUERIES;
  const suggestionLimit = platform === "tiktok_shop" ? MAX_TIKTOK_SUGGESTION_QUERIES : MAX_GENERAL_SUGGESTION_QUERIES;
  const pageLimit = platform === "tiktok_shop" ? MAX_TIKTOK_PAGE_QUERIES : MAX_GENERAL_PAGE_QUERIES;
  return {
    queries: queries.slice(0, searchLimit),
    suggestionQueries: suggestionQueries.slice(0, suggestionLimit),
    pageQueries: pageQueries.slice(0, pageLimit),
    planned: {
      search: queries.length,
      suggestions: suggestionQueries.length,
      pages: pageQueries.length,
    },
    executed: {
      search: Math.min(queries.length, searchLimit),
      suggestions: Math.min(suggestionQueries.length, suggestionLimit),
      pages: Math.min(pageQueries.length, pageLimit),
    },
  };
}

function buildKeywordSeeds(keyword, market) {
  const baseTerms = String(keyword || "")
    .split(/[,;|]/)
    .map((term) => term.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  const seeds = new Set(baseTerms.length ? baseTerms : [String(keyword || "").replace(/\s+/g, " ").trim()].filter(Boolean));
  if (market.spanish) {
    for (const term of Array.from(seeds)) {
      for (const translated of spanishKeywordSeeds(term)) seeds.add(translated);
    }
  }
  return Array.from(seeds).slice(0, market.bundle ? 3 : 8);
}

function spanishKeywordSeeds(term) {
  const clean = String(term || "").toLowerCase().replace(/\s+/g, " ").trim();
  const phraseMap = new Map([
    ["yoga mat", ["tapete de yoga", "colchoneta de yoga", "esterilla de yoga", "mat de yoga", "alfombrilla de yoga"]],
    ["exercise mat", ["tapete de ejercicio", "colchoneta de ejercicio", "alfombrilla de ejercicio"]],
    ["fitness mat", ["tapete fitness", "colchoneta fitness", "tapete para ejercicio"]],
    ["pilates mat", ["tapete de pilates", "colchoneta de pilates", "esterilla de pilates"]],
  ]);
  if (phraseMap.has(clean)) return phraseMap.get(clean);
  if (/\byoga\b/.test(clean) && /\bmat\b/.test(clean)) return phraseMap.get("yoga mat");
  if (/\bexercise\b/.test(clean) && /\bmat\b/.test(clean)) return phraseMap.get("exercise mat");
  if (/\bfitness\b/.test(clean) && /\bmat\b/.test(clean)) return phraseMap.get("fitness mat");
  if (/\bpilates\b/.test(clean) && /\bmat\b/.test(clean)) return phraseMap.get("pilates mat");
  return [];
}

function buildQueries(platform, keyword, market) {
  const output = [];
  const seeds = buildKeywordSeeds(keyword, market);
  if (market.bundle) {
    return [];
  }
  for (const clean of seeds) {
    if (platform === "amazon") {
      output.push(
        { sourceType: "product_title", q: `${market.searchLabel} "${clean}" "Amazon" "review"` },
        { sourceType: "product_title", q: `"${clean}" "Amazon" "best"` },
        { sourceType: "review_text", q: `"${clean}" "Amazon" "problem" "review"` },
        { sourceType: "review_text", q: `"${clean}" "Amazon" "worth it" "review"` },
        { sourceType: "review_text", q: `"${clean}" "does it" "review"` },
      );
      if (market.spanish) {
        output.push(
          { sourceType: "product_title", q: `${market.searchLabel} "${clean}" "Amazon" "reseña"` },
          { sourceType: "product_title", q: `"${clean}" "Amazon" "opiniones"` },
          { sourceType: "review_text", q: `"${clean}" "vale la pena" "Amazon"` },
          { sourceType: "review_text", q: `"${clean}" "problema" "Amazon"` },
        );
      }
      continue;
    }

    const compact = clean.replace(/[^a-z0-9\u4e00-\u9fff]+/gi, "");
    output.push(
      { sourceType: "product_title", q: `${market.searchLabel} "${clean}" "TikTok Shop"` },
      { sourceType: "product_title", q: `"${clean}" "TikTok Shop" "review"` },
      { sourceType: "product_title", q: `"${clean}" "TikTok Shop" "best seller"` },
      { sourceType: "product_title", q: `"${clean}" "TikTok Shop" "viral"` },
      { sourceType: "product_title", q: `"${clean}" "TikTok Shop" "shop now"` },
      { sourceType: "product_title", q: `site:tiktok.com/view/product "${clean}"` },
      { sourceType: "product_title", q: `site:tiktok.com/shop "${clean}"` },
      { sourceType: "product_title", q: `site:tiktok.com "${clean}" "TikTok Shop"` },
      { sourceType: "review_text", q: `"${clean}" "TikTok" "review"` },
      { sourceType: "review_text", q: `"${clean}" "TikTok Shop" "reviews"` },
      { sourceType: "review_text", q: `"${clean}" "before you buy"` },
      { sourceType: "review_text", q: `"${clean}" "worth it" "TikTok"` },
      { sourceType: "review_text", q: `"${clean}" "unboxing" "TikTok"` },
      { sourceType: "review_text", q: `"${clean}" "demo" "TikTok"` },
      { sourceType: "review_text", q: `"${clean}" "honest review"` },
      { sourceType: "review_text", q: `"${clean}" "problem" "TikTok"` },
      { sourceType: "product_title", q: `#${compact} "${clean}"` },
    );
  }
  const modifiers = [
    "for beginners",
    "for home",
    "for women",
    "for men",
    "for kids",
    "gift",
    "deal",
    "coupon",
    "dupe",
    "comparison",
    "vs",
    "setup",
    "routine",
    "how to use",
    "does it work",
    "tiktok made me buy it",
  ];
  if (market.spanish) {
    modifiers.push(
      "reseña",
      "opiniones",
      "vale la pena",
      "antes de comprar",
      "cómo usar",
      "oferta",
      "cupón",
      "barato",
      "premium",
      "problema",
      "comparación",
      "viral en tiktok",
      "para casa",
      "para mujeres",
      "para principiantes",
    );
    for (const clean of seeds) {
      output.push(
        { sourceType: "product_title", q: `"${clean}" "TikTok Shop" "reseña"` },
        { sourceType: "product_title", q: `"${clean}" "TikTok Shop" "opiniones"` },
        { sourceType: "review_text", q: `"${clean}" "TikTok" "vale la pena"` },
        { sourceType: "review_text", q: `"${clean}" "TikTok" "antes de comprar"` },
        { sourceType: "review_text", q: `"${clean}" "TikTok" "problema"` },
      );
    }
  }
  const activeModifiers = market.bundle ? modifiers.slice(0, 18) : modifiers;
  for (const clean of seeds) {
    for (const modifier of activeModifiers) {
      output.push({ sourceType: "review_text", q: `"${clean}" "${modifier}" "TikTok"` });
    }
  }
  return output.map((query) => withMarketMeta(query, market));
}

function buildSuggestionQueries(platform, keyword, market) {
  const seeds = buildKeywordSeeds(keyword, market);
  const baseModifiers =
    platform === "amazon"
      ? ["", " best", " review", " for", " with", " size", " material", " problem", " alternative", " vs"]
      : [
          "",
          " best",
          " review",
          " reviews",
          " tiktok",
          " tiktok shop",
          " shop",
          " for",
          " with",
          " without",
          " vs",
          " dupe",
          " viral",
          " worth it",
          " problem",
          " before and after",
          " unboxing",
          " demo",
          " routine",
          " setup",
          " gift",
          " sale",
          " coupon",
          " cheap",
          " premium",
          " size",
          " color",
          " material",
          " thick",
          " non slip",
          " workout",
          " home",
        ];
  const questionModifiers =
    platform === "amazon"
      ? [" how", " what", " why", " which", " can", " does", " is"]
      : [" how to", " what is", " why is", " which", " can you", " does", " is it", " should i"];
  if (market.spanish) {
    baseModifiers.push(
      " reseña",
      " opiniones",
      " precio",
      " oferta",
      " cupón",
      " barato",
      " vale la pena",
      " antes de comprar",
      " comparación",
      " viral",
      " para casa",
      " para mujeres",
      " para principiantes",
    );
    questionModifiers.push(" cómo", " cuál", " dónde comprar", " vale la pena", " es bueno");
  }
  const alphabetModifiers = market.bundle ? [] : "abcdefghijklmnopqrstuvwxyz".split("").map((letter) => ` ${letter}`);
  const modifiers = market.bundle
    ? ["", " reseña", " opiniones", " precio", " vale la pena", " antes de comprar"]
    : [...baseModifiers, ...questionModifiers, ...alphabetModifiers];
  const queries = [];
  for (const clean of seeds) {
    for (const modifier of modifiers) {
      queries.push({ sourceType: "product_title", ds: "", q: `${clean}${modifier}`.trim(), keyword: clean, hl: market.hl, gl: market.gl });
      if (market.bundle) continue;
      if (!market.bundle) queries.push({ sourceType: "review_text", ds: "yt", q: `${clean}${modifier}`.trim(), keyword: clean, hl: market.hl, gl: market.gl });
      if (platform === "tiktok_shop" && modifier) {
        queries.push({ sourceType: "product_title", ds: "", q: `tiktok shop ${clean}${modifier}`.trim(), keyword: clean, hl: market.hl, gl: market.gl });
        if (!market.bundle) queries.push({ sourceType: "review_text", ds: "yt", q: `tiktok ${clean}${modifier}`.trim(), keyword: clean, hl: market.hl, gl: market.gl });
      }
    }
  }
  return queries.map((query) => withMarketMeta(query, market));
}

function buildPublicPageQueries(platform, keyword, market) {
  if (platform !== "tiktok_shop") return [];
  if (market.bundle) return [];
  const queries = [];
  for (const clean of buildKeywordSeeds(keyword, market).slice(0, market.bundle ? 2 : 4)) {
    const encoded = encodeURIComponent(clean);
    queries.push(
      {
        sourceType: "product_title",
        q: clean,
        url: `https://www.tiktok.com/search?q=${encoded}`,
        label: "TikTok public search page",
      },
      {
        sourceType: "product_title",
        q: clean,
        url: `https://www.tiktok.com/shop/s/${encoded}`,
        label: "TikTok Shop public search page",
      },
      {
        sourceType: "product_title",
        q: clean,
        url: `https://www.tiktok.com/shop/s/${encoded}?region=${encodeURIComponent(market.gl)}`,
        label: "TikTok Shop regional search page",
      },
    );
  }
  return queries.map((query) => withMarketMeta(query, market));
}

async function fetchDuckDuckGo(query) {
  const url = `https://duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
  const html = await fetchText(url, "text/html,application/xhtml+xml");
  return parseDuckDuckGo(html).slice(0, 20);
}

async function fetchSuggestions(query) {
  const providers = [fetchBingSuggestions, fetchGoogleSuggestions];
  let lastError = null;
  for (const provider of providers) {
    try {
      const rows = await provider(query);
      if (rows.length) return rows;
    } catch (error) {
      lastError = error;
    }
  }
  if (lastError) throw lastError;
  return [];
}

async function fetchBingSuggestions(query) {
  const url = `https://api.bing.com/osjson.aspx?query=${encodeURIComponent(query.q)}&cc=${encodeURIComponent(query.gl || "US")}&setlang=${encodeURIComponent(
    toBingLanguageTag(query),
  )}`;
  const text = await fetchText(url, "application/json,text/plain,*/*");
  const payload = JSON.parse(text);
  const suggestions = Array.isArray(payload?.[1]) ? payload[1] : [];
  return mapSuggestionRows(suggestions, query, "Bing public search suggestions", url);
}

async function fetchGoogleSuggestions(query) {
  const ds = query.ds ? `&ds=${encodeURIComponent(query.ds)}` : "";
  const locale = `${query.hl ? `&hl=${encodeURIComponent(query.hl)}` : ""}${query.gl ? `&gl=${encodeURIComponent(query.gl)}` : ""}`;
  const url = `https://suggestqueries.google.com/complete/search?client=firefox${ds}${locale}&q=${encodeURIComponent(query.q)}`;
  const text = await fetchText(url, "application/json,text/plain,*/*");
  const payload = JSON.parse(text);
  const suggestions = Array.isArray(payload?.[1]) ? payload[1] : [];
  return mapSuggestionRows(suggestions, query, "Google public search suggestions", "https://suggestqueries.google.com/complete/search");
}

function mapSuggestionRows(suggestions, query, provider, url) {
  return suggestions
    .filter((suggestion) => containsKeywordTokens(suggestion, query.keyword))
    .map((suggestion) => ({
      title: String(suggestion || "").trim(),
      snippet: "",
      provider,
      url,
    }));
}

function toBingLanguageTag(query) {
  const language = query.language || query.hl || "en";
  const region = query.gl || "US";
  return `${language}-${region}`;
}

async function fetchPublicPageText(query) {
  const html = await fetchText(query.url, "text/html,application/xhtml+xml");
  const rows = [];
  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const descriptionMatch =
    html.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["'][^>]*>/i) ||
    html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']description["'][^>]*>/i);
  const title = cleanHtml(titleMatch ? titleMatch[1] : query.label);
  const description = cleanHtml(descriptionMatch ? descriptionMatch[1] : "");
  if (containsKeywordTokens(`${title} ${description}`, query.q)) {
    rows.push({ title, snippet: description, url: query.url });
  }
  const jsonText = extractEmbeddedJsonText(html, query.q);
  for (const snippet of jsonText.slice(0, 40)) {
    rows.push({ title: query.label, snippet, url: query.url });
  }
  return rows;
}

async function fetchText(url, accept) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      headers: {
        accept,
        "accept-language": "en-US,en;q=0.9",
        "user-agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.text();
  } finally {
    clearTimeout(timeout);
  }
}

function parseDuckDuckGo(html) {
  const blocks = html.split(/<div class="result[\s"]/g).slice(1);
  const rows = [];
  for (const block of blocks) {
    const titleMatch = block.match(/class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/);
    const snippetMatch =
      block.match(/class="result__snippet"[^>]*>([\s\S]*?)<\/a>/) ||
      block.match(/class="result__snippet"[^>]*>([\s\S]*?)<\/div>/);
    if (!titleMatch) continue;
    const title = cleanHtml(titleMatch[2]);
    const snippet = cleanHtml(snippetMatch ? snippetMatch[1] : "");
    const url = unwrapDuckDuckGoUrl(decodeHtml(titleMatch[1]));
    if (url.includes("duckduckgo.com/y.js")) continue;
    if (title || snippet) rows.push({ title, snippet, url });
  }
  return rows;
}

function groupSourceTexts(items) {
  const groups = { product: [], review: [] };
  for (const item of items) {
    const line = `${item.title}. ${item.snippet}`.replace(/\s+/g, " ").trim();
    if (!line) continue;
    if (item.sourceType === "product_title") groups.product.push(line);
    else groups.review.push(line);
  }
  return {
    product: groups.product.join("\n").slice(0, MAX_SOURCE_TEXT_CHARS),
    review: groups.review.join("\n").slice(0, MAX_SOURCE_TEXT_CHARS),
  };
}

function dedupe(items) {
  const seen = new Set();
  const rows = [];
  for (const item of items) {
    const key = `${item.title} ${item.snippet}`.toLowerCase().replace(/\W+/g, " ").slice(0, 200);
    if (!item.title || seen.has(key)) continue;
    seen.add(key);
    rows.push(item);
  }
  return rows;
}

function summarizeItems(items, errors, queryPlan = null) {
  const byType = {};
  for (const item of items) byType[item.sourceType] = (byType[item.sourceType] || 0) + 1;
  return {
    items: items.length,
    sourceTypes: byType,
    errors: errors.length,
    plannedQueries: queryPlan?.planned || null,
    executedQueries: queryPlan?.executed || null,
    sourceTextLimitChars: MAX_SOURCE_TEXT_CHARS,
  };
}

function extractEmbeddedJsonText(html, keyword) {
  const output = [];
  const text = decodeHtml(String(html || ""))
    .replace(/\\u002F/g, "/")
    .replace(/\\u([\dA-Fa-f]{4})/g, (_, code) => String.fromCharCode(parseInt(code, 16)));
  const quotedStrings = text.match(/"([^"\\]*(?:\\.[^"\\]*)*)"/g) || [];
  for (const quoted of quotedStrings) {
    const cleaned = cleanHtml(quoted.slice(1, -1).replace(/\\"/g, '"').replace(/\\n/g, " "));
    if (cleaned.length < 12 || cleaned.length > 240) continue;
    if (!containsKeywordTokens(cleaned, keyword)) continue;
    output.push(cleaned);
  }
  return Array.from(new Set(output));
}

async function runLimited(tasks, limit) {
  let index = 0;
  const workers = Array.from({ length: Math.min(limit, tasks.length) }, async () => {
    while (index < tasks.length) {
      const current = tasks[index];
      index += 1;
      await current();
    }
  });
  await Promise.all(workers);
}

function containsKeywordTokens(text, keyword) {
  const normalized = String(text || "").toLowerCase();
  const tokens = String(keyword || "")
    .toLowerCase()
    .split(/\s+/)
    .filter((token) => token.length > 1);
  return tokens.every((token) => {
    if (/^[a-z0-9-]+$/.test(token)) {
      return new RegExp(`(^|[^a-z0-9])${escapeRegExp(token)}([^a-z0-9]|$)`).test(normalized);
    }
    return normalized.includes(token);
  });
}

function unwrapDuckDuckGoUrl(rawUrl) {
  try {
    const parsed = new URL(rawUrl, "https://duckduckgo.com");
    const wrapped = parsed.searchParams.get("uddg");
    return wrapped ? decodeURIComponent(wrapped) : parsed.href;
  } catch {
    return rawUrl;
  }
}

function cleanHtml(value) {
  return decodeHtml(String(value || "").replace(/<[^>]+>/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}

function decodeHtml(value) {
  return String(value || "")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)))
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ");
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
