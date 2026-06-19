import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const authState = process.env.FENBI_AUTH_STATE;
const paperId = process.env.FENBI_PAPER_ID;
const outputFile = process.env.FENBI_OUTPUT_FILE;
const headless = process.env.FENBI_HEADLESS !== "0";
const timeoutMs = Number(process.env.FENBI_TIMEOUT_MS || 180000);

if (!authState || !paperId || !outputFile) {
  console.error("missing FENBI_AUTH_STATE, FENBI_PAPER_ID, or FENBI_OUTPUT_FILE");
  process.exit(2);
}

try {
  await fs.access(authState);
} catch {
  console.error("auth state not found at:", authState);
  process.exit(2);
}

const browser = await chromium.launch({ headless });
const context = await browser.newContext({ storageState: authState });
const page = await context.newPage();

try {
  const paperMeta = await fetchJson(page, `https://tiku.fenbi.com/api/shenlun/papers/${paperId}`, "paper metadata");
  const combineKey = paperMeta.combineKey;
  const checkId = paperMeta.encodeCheckInfo;
  const title = paperMeta.name || `paper-${paperId}`;

  if (!combineKey) {
    throw new Error("no combineKey in paper metadata");
  }

  const solutionMetaUrl =
    `https://tiku.fenbi.com/combine/exercise/getPaperSolution?format=html` +
    `&key=${combineKey}&routecs=shenlun&paperId=${paperId}&checkId=${checkId}`;
  const solutionMeta = await fetchJson(page, solutionMetaUrl, "solution metadata");
  if (solutionMeta.code !== 1) {
    throw new Error(`getPaperSolution failed: ${solutionMeta.msg || "unknown error"}`);
  }

  const staticUrls = solutionMeta.data?.staticUrl?.urls || [];
  if (staticUrls.length === 0) {
    throw new Error("no static URLs in solution metadata");
  }

  let solutionData = null;
  for (const cdnUrl of staticUrls) {
    try {
      solutionData = await fetchJson(page, cdnUrl, "CDN solution");
      break;
    } catch {
      // Try the next CDN URL.
    }
  }
  if (!solutionData) {
    throw new Error("all CDN URLs failed");
  }

  const questionCount = solutionData.solutions?.length || 0;
  const materialCount = solutionData.materials?.length || 0;
  if (questionCount === 0) {
    throw new Error("solution data has no solutions");
  }

  await fs.mkdir(path.dirname(outputFile), { recursive: true });
  await fs.writeFile(outputFile, JSON.stringify(solutionData, null, 2), "utf8");
  await context.storageState({ path: authState });

  const sourceUrl =
    `https://spa.fenbi.com/ti/view/paper/${combineKey}?routecs=shenlun&checkId=${checkId}&paperId=${paperId}`;
  console.log(JSON.stringify({
    status: "downloaded",
    paperId,
    title,
    questionCount,
    materialCount,
    combineKey,
    checkId,
    sourceUrl,
    path: outputFile,
  }));
} catch (error) {
  console.error(String(error && error.message ? error.message : error));
  process.exit(1);
} finally {
  await browser.close();
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
