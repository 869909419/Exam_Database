import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const authState = process.env.FENBI_AUTH_STATE;
const paperId = process.env.FENBI_PAPER_ID;
const routecs = process.env.FENBI_ROUTECS || "xingce";
const prefix = process.env.FENBI_PREFIX || "xingce";
const categories = process.env.FENBI_CATEGORIES || "xingce";
const fontExerId = process.env.FENBI_FONT_EXER_ID || "3";
const outputFile = process.env.FENBI_OUTPUT_FILE;
const headless = process.env.FENBI_HEADLESS !== "0";
const timeoutMs = Number(process.env.FENBI_TIMEOUT_MS || 180000);
const delayMs = Number(process.env.FENBI_DELAY_MS || 1500);

if (!authState || !paperId || !outputFile) {
  console.error("missing FENBI_AUTH_STATE, FENBI_PAPER_ID, or FENBI_OUTPUT_FILE");
  process.exit(2);
}

const browser = await chromium.launch({ headless });
const context = await browser.newContext({ storageState: authState });
const page = await context.newPage();

try {
  const createUrl = new URL("https://www.fenbi.com/spa/tiku/exam/create");
  createUrl.searchParams.set("paperId", paperId);
  createUrl.searchParams.set("type", "1");
  createUrl.searchParams.set("prefix", prefix);
  createUrl.searchParams.set("fontExerId", fontExerId);
  createUrl.searchParams.set("categories", categories);

  await page.goto(createUrl.toString(), { waitUntil: "domcontentloaded", timeout: timeoutMs });
  await page.waitForURL(/\/ti\/exam\/exercise\//, { timeout: timeoutMs }).catch(() => {});
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  if (!(await isExercisePage(page))) {
    if (await isLoginPage(page)) {
      throw new Error("login state expired; run auth fenbi-login again");
    }
    throw new Error("exercise page was not opened");
  }

  const exerciseKey = exerciseKeyFromUrl(page.url());
  await page.waitForTimeout(delayMs);
  await clickSubmit(page);
  await page.waitForTimeout(Math.max(500, Math.floor(delayMs / 2)));

  const solutionResponsePromise = page.waitForResponse(
    response => response.url().includes("/combine/static/solution") && response.status() === 200,
    { timeout: timeoutMs },
  );
  await confirmSubmit(page);
  const solutionResponse = await solutionResponsePromise;
  const body = await solutionResponse.text();
  JSON.parse(body);

  await fs.mkdir(path.dirname(outputFile), { recursive: true });
  await fs.writeFile(outputFile, body, "utf8");
  await context.storageState({ path: authState });

  const finalExerciseKey = exerciseKey || exerciseKeyFromUrl(page.url());
  const sourceUrl = `https://spa.fenbi.com/ti/exam/solution/${finalExerciseKey}?routecs=${routecs}`;
  console.log(JSON.stringify({
    status: "downloaded",
    paperId,
    exerciseKey: finalExerciseKey,
    sourceUrl,
    path: outputFile,
  }));
} catch (error) {
  console.error(String(error && error.message ? error.message : error));
  process.exit(1);
} finally {
  await browser.close();
}

async function isExercisePage(page) {
  const url = page.url();
  if (url.includes("/ti/exam/exercise/")) {
    return true;
  }
  return await page.locator("text=交卷").first().isVisible().catch(() => false);
}

async function isLoginPage(page) {
  return await page.locator("text=/登录|登录\\/注册|验证码|手机号/").first().isVisible().catch(() => false);
}

function exerciseKeyFromUrl(url) {
  const match = url.match(/\/(?:exercise|solution)\/([^?/#]+)/);
  return match ? match[1] : "";
}

async function clickSubmit(page) {
  const selectors = [
    "text=交卷",
    "button:has-text('交卷')",
  ];
  for (const selector of selectors) {
    const target = page.locator(selector).first();
    if (await target.isVisible().catch(() => false)) {
      await target.click();
      return;
    }
  }
  throw new Error("submit button was not found");
}

async function confirmSubmit(page) {
  const selectors = [
    "button:has-text('确认')",
    "button:has-text('确定')",
  ];
  for (const selector of selectors) {
    const target = page.locator(selector).first();
    if (await target.isVisible().catch(() => false)) {
      await target.click();
      return;
    }
  }
  throw new Error("confirm submit button was not found");
}
