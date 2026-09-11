import puppeteer from "puppeteer";

const APP_URL = "http://localhost:5173";
const unique = `reactuser${Date.now()}`;

const browser = await puppeteer.launch({ headless: true });
const page = await browser.newPage();
page.on("console", (msg) => {
  if (msg.type() === "error") console.log("BROWSER CONSOLE ERROR:", msg.text());
});
page.on("pageerror", (err) => console.log("PAGE ERROR:", err.message));

console.log("### 1. Landing page ###");
await page.goto(APP_URL, { waitUntil: "networkidle0" });
const heading = await page.$eval("h1", (el) => el.textContent);
console.log("H1:", heading);
const hasLoginLink = await page.$$eval("a", (as) => as.some((a) => a.textContent?.includes("Log in")));
const hasCreateLink = await page.$$eval("a", (as) => as.some((a) => a.textContent?.includes("Create account")));
console.log("has Log in link:", hasLoginLink, "| has Create account link:", hasCreateLink);
await page.screenshot({ path: "verify_1_landing.png" });

console.log("\n### 2. Click 'Create account' -> Registration page ###");
await page.click('a[href="/register"]');
await page.waitForFunction(() => location.pathname === "/register");
console.log("URL:", page.url());
await page.screenshot({ path: "verify_2_register.png" });

console.log("\n### 3. Fill and submit registration form (real backend call) ###");
const inputs = await page.$$("input");
await inputs[0].type("React User"); // Full name
await inputs[1].type(unique); // Username
await inputs[2].type(`${unique}@example.com`); // Email
await inputs[3].type("password123"); // Password
await inputs[4].type("password123"); // Confirm
await page.click('button[type="submit"]');
await page.waitForFunction(() => location.pathname === "/app/dashboard", { timeout: 15000 });
console.log("URL after submit:", page.url());

console.log("\n### 4. Dashboard should show REAL data for a fresh $250,000 account ###");
await page.waitForSelector("h1");
const dashboardH1 = await page.$eval("h1", (el) => el.textContent);
console.log("Dashboard H1:", dashboardH1);
await page.waitForFunction(
  () => document.body.textContent?.includes("$250,000") || document.body.textContent?.includes("Loading"),
  { timeout: 15000 },
);
// Wait for the loading state to resolve into real numbers
await page.waitForFunction(() => !document.body.textContent?.includes("Loading…"), { timeout: 20000 });
const bodyText = await page.$eval("body", (el) => el.textContent ?? "");
console.log("Contains $250,000 (fresh account portfolio value):", bodyText.includes("250,000"));
console.log("Contains 'No open positions':", bodyText.includes("No open positions"));
await page.screenshot({ path: "verify_3_dashboard.png", fullPage: true });

console.log("\n### 5. Log out -> back to landing page ###");
const logoutClicked = await page.evaluate(() => {
  const btn = Array.from(document.querySelectorAll("button")).find((b) => b.textContent?.includes("Log out"));
  if (btn) { btn.click(); return true; }
  return false;
});
console.log("logout button found and clicked:", logoutClicked);
await page.waitForFunction(() => location.pathname === "/", { timeout: 10000 });
console.log("URL after logout:", page.url());
await page.waitForSelector("h1", { timeout: 10000 });
const afterLogoutH1 = await page.$eval("h1", (el) => el.textContent);
console.log("H1 after logout (should be landing headline again):", afterLogoutH1);

console.log("\n### 6. Try to access /app/dashboard directly after logout (stale nav) ###");
await page.goto(`${APP_URL}/app/dashboard`, { waitUntil: "networkidle0" });
console.log("URL after direct nav attempt:", page.url());

console.log("\n### 7. Log back in ###");
await page.goto(`${APP_URL}/login`, { waitUntil: "networkidle0" });
const loginInputs = await page.$$("input");
await loginInputs[0].type(unique);
await loginInputs[1].type("password123");
await page.click('button[type="submit"]');
await page.waitForFunction(() => location.pathname === "/app/dashboard", { timeout: 15000 });
console.log("URL after re-login:", page.url());

console.log("\n### 8. Refresh the page (localStorage persistence check) ###");
await page.reload({ waitUntil: "networkidle0" });
await page.waitForFunction(() => !document.body.textContent?.includes("Loading…"), { timeout: 15000 });
console.log("URL after refresh:", page.url());
const stillLoggedIn = page.url().includes("/app/dashboard");
console.log("Still logged in after hard refresh (localStorage worked):", stillLoggedIn);

await browser.close();
console.log("\nDONE");
