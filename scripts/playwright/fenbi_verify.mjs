import { chromium } from "playwright";
import path from "node:path";

const username = process.env.FENBI_USERNAME;
const password = process.env.FENBI_PASSWORD;
const authDir = process.env.FENBI_AUTH_DIR;
const downloadDir = process.env.FENBI_DOWNLOAD_DIR;
const sampleUrl = process.env.FENBI_SAMPLE_URL || "https://www.fenbi.com/";

if (!username || !password || !authDir || !downloadDir) {
  console.error("missing required fenbi verification environment");
  process.exit(2);
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  acceptDownloads: true,
  storageState: undefined,
});
const page = await context.newPage();

try {
  await page.goto(sampleUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  await clickLoginIfVisible(page);
  await fillLoginForm(page, username, password);
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});

  const blocked = await page.locator("text=/验证码|短信|扫码|安全验证|人机验证|手机号/").first().isVisible().catch(() => false);
  if (blocked) {
    throw new Error("login blocked by captcha, sms, qr, or risk verification");
  }

  await context.storageState({ path: path.join(authDir, "storage-state.json") });

  const download = await capturePdfDownload(page);
  if (!download) {
    throw new Error("no PDF download was captured; provide FENBI_SAMPLE_URL for a concrete free paper page");
  }
  const suggested = sanitizeFilename(download.suggestedFilename() || "fenbi-verification.pdf");
  const target = path.join(downloadDir, suggested.endsWith(".pdf") ? suggested : `${suggested}.pdf`);
  await download.saveAs(target);
  console.log(JSON.stringify({ status: "downloaded", path: target }));
} catch (error) {
  console.error(String(error && error.message ? error.message : error));
  process.exit(1);
} finally {
  await browser.close();
}

async function clickLoginIfVisible(page) {
  const candidates = [
    "text=/登录/",
    "button:has-text('登录')",
    "a:has-text('登录')",
  ];
  for (const selector of candidates) {
    const target = page.locator(selector).first();
    if (await target.isVisible().catch(() => false)) {
      await target.click().catch(() => {});
      await page.waitForTimeout(1000);
      return;
    }
  }
}

async function fillLoginForm(page, user, pass) {
  const userSelectors = [
    "input[type='tel']",
    "input[type='text']",
    "input[name*='phone']",
    "input[name*='user']",
    "input[placeholder*='手机']",
    "input[placeholder*='账号']",
  ];
  const passSelectors = [
    "input[type='password']",
    "input[placeholder*='密码']",
  ];
  const userInput = await firstVisible(page, userSelectors);
  const passInput = await firstVisible(page, passSelectors);
  if (!userInput || !passInput) {
    throw new Error("login form was not found");
  }
  await userInput.fill(user);
  await passInput.fill(pass);
  const buttons = [
    "button:has-text('登录')",
    "text=/登录/",
    "button[type='submit']",
  ];
  const submit = await firstVisible(page, buttons);
  if (!submit) {
    throw new Error("login submit button was not found");
  }
  await submit.click();
}

async function capturePdfDownload(page) {
  const directPdf = await page.locator("a[href$='.pdf'], a[href*='.pdf?']").first();
  if (await directPdf.isVisible().catch(() => false)) {
    const downloadPromise = page.waitForEvent("download", { timeout: 30000 }).catch(() => null);
    await directPdf.click();
    return await downloadPromise;
  }

  const downloadButtons = [
    "text=/下载/",
    "button:has-text('下载')",
    "a:has-text('下载')",
    "text=/PDF/",
  ];
  for (const selector of downloadButtons) {
    const button = page.locator(selector).first();
    if (await button.isVisible().catch(() => false)) {
      const downloadPromise = page.waitForEvent("download", { timeout: 30000 }).catch(() => null);
      await button.click();
      const download = await downloadPromise;
      if (download) {
        return download;
      }
    }
  }
  return null;
}

async function firstVisible(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if (await locator.isVisible().catch(() => false)) {
      return locator;
    }
  }
  return null;
}

function sanitizeFilename(name) {
  return name.replace(/[\\/:*?"<>|#\[\]]+/g, "-").replace(/\s+/g, "-");
}
