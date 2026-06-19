import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const authState = process.env.FENBI_AUTH_STATE;
const labelId = process.env.FENBI_LABEL_ID || "1";
const paperKind = process.env.FENBI_PAPER_KIND || "xingce";
const pageSize = parseIntegerEnv("FENBI_PAGE_SIZE", 50, { min: 1 });
const outputFile = process.env.FENBI_OUTPUT_FILE || "";
const headless = parseHeadless(process.env.FENBI_HEADLESS);
const timeoutMs = parseIntegerEnv("FENBI_TIMEOUT_MS", 180000, { min: 1 });
const networkIdleTimeout = parseIntegerEnv("FENBI_NETWORK_IDLE_MS", 15000, { min: 1 });
const scrollDelayMs = parseIntegerEnv("FENBI_SCROLL_DELAY_MS", 800, { min: 0 });
const maxPages = parseIntegerEnv("FENBI_MAX_PAGES", 20, { min: 1 });

if (!["xingce", "shenlun"].includes(paperKind)) {
  console.error("FENBI_PAPER_KIND must be xingce or shenlun");
  process.exit(2);
}

if (authState) {
  try {
    await fs.access(authState);
  } catch {
    console.error("auth state not found at:", authState);
    process.exit(2);
  }
}

const browser = await chromium.launch({ headless });
const context = await browser.newContext(authState ? { storageState: authState } : {});
const page = await context.newPage();

try {
  let papers = [];
  try {
    papers = await fetchPaperListFromApi(page);
  } catch (error) {
    console.error(`paper list API failed, falling back to page capture: ${error.message}`);
    papers = [];
  }

  if (papers.length === 0) {
    const listUrl = paperKind === "shenlun"
      ? `https://www.fenbi.com/spa/tiku/guide/realTest/shenlun/shenlun?labelId=${labelId}`
      : `https://www.fenbi.com/spa/tiku/guide/realTest/xingce/xingce?labelId=${labelId}`;
    const captured = [];
    const pendingResponses = new Set();
    page.on("response", async (response) => {
      const pending = capturePaperResponse(response, captured);
      if (!pending) {
        return;
      }
      pendingResponses.add(pending);
      pending.finally(() => pendingResponses.delete(pending));
    });
    await page.goto(listUrl, { waitUntil: "domcontentloaded", timeout: timeoutMs });
    await page.waitForLoadState("networkidle", { timeout: networkIdleTimeout }).catch(() => {});
    for (let index = 0; index < 5; index += 1) {
      await page.evaluate(() => window.scrollBy(0, 800));
      await page.waitForTimeout(scrollDelayMs);
    }
    await page.waitForLoadState("networkidle", { timeout: networkIdleTimeout }).catch(() => {});
    await Promise.allSettled(Array.from(pendingResponses));
    papers = normalizePapers(captured);
    if (papers.length === 0) {
      throw new Error("no papers discovered from API or fallback page capture");
    }
  }

  const result = {
    status: "discovered",
    labelId,
    paperKind,
    count: papers.length,
    papers,
  };
  const text = JSON.stringify(result, null, 2);
  console.log(text);
  if (outputFile) {
    await fs.mkdir(path.dirname(outputFile), { recursive: true });
    await fs.writeFile(outputFile, text, "utf8");
  }
} catch (error) {
  console.error(String(error && error.message ? error.message : error));
  process.exit(1);
} finally {
  await browser.close();
}

async function fetchPaperListFromApi(page) {
  const items = [];
  for (let toPage = 0; toPage < maxPages; toPage += 1) {
    const apiUrl = `https://tiku.fenbi.com/api/${paperKind}/comptroller/papers?toPage=${toPage}&pageSize=${pageSize}&labelId=${labelId}`;
    const payload = await fetchJson(page, apiUrl, `paper list API page ${toPage}`);
    const pageItems = extractPaperList(payload);
    items.push(...pageItems);
    if (pageItems.length < pageSize) {
      return normalizePapers(items);
    }
  }
  throw new Error(`paper list API reached FENBI_MAX_PAGES=${maxPages}; increase it to continue discovery`);
}

function capturePaperResponse(response, captured) {
  const url = response.url();
  if (!url.includes("comptroller/papers") && !url.includes(`api/${paperKind}/papers`)) {
    return null;
  }
  return (async () => {
    try {
      const body = await response.text();
      const data = JSON.parse(body);
      captured.push(...extractPaperList(data));
    } catch {
      // Ignore non-JSON responses from unrelated endpoints.
    }
  })();
}

function parseIntegerEnv(name, defaultValue, { min } = {}) {
  const raw = process.env[name];
  if (raw === undefined || raw === "") {
    return defaultValue;
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || (min !== undefined && value < min)) {
    const suffix = min === undefined ? "" : ` >= ${min}`;
    throw new Error(`${name} must be an integer${suffix}`);
  }
  return value;
}

function parseHeadless(value) {
  if (value === undefined || value === "") {
    return true;
  }
  return !["0", "false", "no"].includes(value.toLowerCase());
}

function normalizePapers(items) {
  const seen = new Set();
  const papers = [];
  for (const item of items) {
    const paperId = String(item.id || "");
    const name = item.name || item.title || "";
    if (!paperId || !name || seen.has(paperId)) {
      continue;
    }
    seen.add(paperId);
    papers.push({
      paperId,
      name,
      date: item.date || "",
      difficulty: item.paperMeta?.difficulty || "",
      exerciseCount: item.paperMeta?.exerciseCount ?? null,
      combineKey: item.combineKey || "",
    });
  }
  return papers;
}

function extractPaperList(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.list)) {
    return payload.list;
  }
  if (Array.isArray(payload?.data?.list)) {
    return payload.data.list;
  }
  if (Array.isArray(payload?.data)) {
    return payload.data;
  }
  return [];
}

async function fetchJson(page, url, description) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
  const text = await page.evaluate(() => document.body.innerText);
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${description} returned non-JSON: ${text.substring(0, 300)}`);
  }
}
