import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const authState = process.env.FENBI_AUTH_STATE;
const labelId = process.env.FENBI_LABEL_ID || "1";
const paperKind = process.env.FENBI_PAPER_KIND || "xingce";
const pageSize = Number(process.env.FENBI_PAGE_SIZE || 50);
const outputFile = process.env.FENBI_OUTPUT_FILE || "";
const headless = process.env.FENBI_HEADLESS !== "0";
const timeoutMs = Number(process.env.FENBI_TIMEOUT_MS || 180000);

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
  const apiUrl = `https://tiku.fenbi.com/api/${paperKind}/comptroller/papers?toPage=0&pageSize=${pageSize}&labelId=${labelId}`;

  let papers = [];
  try {
    const payload = await fetchJson(page, apiUrl, "paper list API");
    papers = normalizePapers(extractPaperList(payload));
  } catch {
    papers = [];
  }

  if (papers.length === 0) {
    const listUrl = paperKind === "shenlun"
      ? `https://www.fenbi.com/spa/tiku/guide/realTest/shenlun/shenlun?labelId=${labelId}`
      : `https://www.fenbi.com/spa/tiku/guide/realTest/xingce/xingce?labelId=${labelId}`;
    const captured = [];
    page.on("response", async (response) => {
      const url = response.url();
      if (!url.includes("comptroller/papers") && !url.includes(`api/${paperKind}/papers`)) {
        return;
      }
      try {
        const body = await response.text();
        const data = JSON.parse(body);
        captured.push(...extractPaperList(data));
      } catch {
        // Ignore non-JSON responses from unrelated endpoints.
      }
    });
    await page.goto(listUrl, { waitUntil: "domcontentloaded", timeout: timeoutMs }).catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    for (let index = 0; index < 5; index += 1) {
      await page.evaluate(() => window.scrollBy(0, 800));
      await page.waitForTimeout(800);
    }
    papers = normalizePapers(captured);
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
      exerciseCount: item.paperMeta?.exerciseCount || 0,
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
