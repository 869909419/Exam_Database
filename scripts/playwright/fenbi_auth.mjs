import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const username = process.env.FENBI_USERNAME || "";
const password = process.env.FENBI_PASSWORD || "";
const authDir = process.env.FENBI_AUTH_DIR;
const headless = process.env.FENBI_HEADLESS !== "0";
const manual = process.env.FENBI_MANUAL_LOGIN === "1";
const timeoutMs = Number(process.env.FENBI_TIMEOUT_MS || 180000);
const loginUrl = process.env.FENBI_LOGIN_URL || "https://www.fenbi.com/spa/tiku/guide/realTest/xingce/xingce?redirect=true";

if (!authDir) {
  console.error("missing FENBI_AUTH_DIR");
  process.exit(2);
}
if (!manual && (!username || !password)) {
  console.error("missing FENBI_USERNAME or FENBI_PASSWORD");
  process.exit(2);
}

const browser = await chromium.launch({ headless });
const context = await browser.newContext();
const page = await context.newPage();

try {
  await fs.mkdir(authDir, { recursive: true });
  await page.goto(loginUrl, { waitUntil: "domcontentloaded", timeout: timeoutMs });
  if (!(await isLoggedIn(page))) {
    if (manual) {
      await waitForManualLogin(page, timeoutMs);
    } else {
      await loginWithPassword(page, username, password, timeoutMs);
    }
  }
  if (!(await isLoggedIn(page))) {
    throw new Error("login was not confirmed");
  }
  const statePath = path.join(authDir, "storage-state.json");
  await context.storageState({ path: statePath });
  console.log(JSON.stringify({ status: "authenticated", path: statePath }));
} catch (error) {
  console.error(String(error && error.message ? error.message : error));
  process.exit(1);
} finally {
  await browser.close();
}

async function loginWithPassword(page, user, pass, timeout) {
  await clickIfVisible(page, [
    "button:has-text('登录')",
    "text=登录/注册",
    "text=登录",
  ]);
  await page.waitForTimeout(1000);
  await clickIfVisible(page, [
    "button:has-text('账号密码登录')",
    "text=账号密码登录",
    "text=密码登录",
  ]);
  await page.waitForTimeout(500);

  const userInput = await firstVisible(page, [
    "input[type='tel']",
    "input[type='text']",
    "input[placeholder*='手机']",
    "input[placeholder*='账号']",
    "input[name*='phone']",
    "input[name*='user']",
  ]);
  const passInput = await firstVisible(page, [
    "input[type='password']",
    "input[placeholder*='密码']",
  ]);
  if (!userInput || !passInput) {
    throw new Error("password login form was not found");
  }
  await userInput.fill(user);
  await passInput.fill(pass);
  await clickIfVisible(page, [
    "text=/我已阅读并同意/",
    "label:has-text('我已阅读')",
    "input[type='checkbox']",
  ]);
  const submit = await firstVisible(page, [
    "button:has-text('登录')",
    "button[type='submit']",
    "text=登录",
  ]);
  if (!submit) {
    throw new Error("login submit button was not found");
  }
  await submit.click();

  const blocked = page.locator("text=/验证码|短信|扫码|安全验证|人机验证|获取验证码/").first();
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await isLoggedIn(page)) {
      return;
    }
    if (await blocked.isVisible().catch(() => false)) {
      throw new Error("login blocked by captcha, sms, qr, or risk verification; rerun with --manual");
    }
    await page.waitForTimeout(1000);
  }
  throw new Error("login timed out");
}

async function waitForManualLogin(page, timeout) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await isLoggedIn(page)) {
      return;
    }
    await page.waitForTimeout(1000);
  }
  throw new Error("manual login timed out");
}

async function isLoggedIn(page) {
  if (await page.locator("img[alt='用户头像']").first().isVisible().catch(() => false)) {
    return true;
  }
  const current = await page.evaluate(async () => {
    try {
      const response = await fetch("https://login.fenbi.com/api/users/current?app=web&kav=125&av=127&hav=125&gav=2", {
        credentials: "include",
      });
      return response.ok;
    } catch {
      return false;
    }
  }).catch(() => false);
  return Boolean(current);
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

async function clickIfVisible(page, selectors) {
  const target = await firstVisible(page, selectors);
  if (!target) {
    return false;
  }
  await target.click().catch(() => {});
  return true;
}
