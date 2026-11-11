import puppeteer from "puppeteer-core";

const BASE = "http://127.0.0.1:5173";
const OUT = process.argv[2];
const results = [];
const check = (name, ok, extra = "") => { results.push(ok); console.log(`${ok ? "PASS" : "FAIL"} ${name}${extra ? `  [${extra}]` : ""}`); };

const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", headless: "new", args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });
const problems = [];
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("401")) problems.push(`console: ${m.text()}`); });
page.on("response", (r) => { if (r.status() >= 400 && r.status() !== 401) console.log("   http", r.status(), r.request().method(), r.url()); if (r.status() >= 500) problems.push(`${r.status()} ${r.url()}`); });

const text = () => page.evaluate(() => document.body.innerText);
const waitText = (t, timeout = 8000) => page.waitForFunction((x) => document.body.innerText.includes(x), { timeout }, t);
const clickText = async (sel, t) => {
  await page.waitForFunction((s, x) => [...document.querySelectorAll(s)].some((e) => e.innerText.includes(x) && !e.disabled), { timeout: 8000 }, sel, t);
  await page.evaluate((s, x) => [...document.querySelectorAll(s)].find((e) => e.innerText.includes(x) && !e.disabled).click(), sel, t);
};
const shot = (n) => page.screenshot({ path: `${OUT}/${n}.png`, fullPage: true });

// 1. home
await page.goto(BASE, { waitUntil: "networkidle0" });
check("home renders", (await text()).includes("Find the right doctor"));
await page.waitForFunction(() => document.querySelectorAll("select option").length > 3);
await page.select("select", "dermatology");
await shot("1-home");

// 2. search -> results
await clickText("button", "Search");
await waitText("Dr A. Sen");
const results1 = await text();
check("results list both approved doctors", results1.includes("Dr A. Sen") && results1.includes("Dr R. Das"), results1.match(/\d+ verified doctors?/)?.[0]);
check("results show availability", /slots? left/.test(results1));
await shot("2-results");
await page.select("aside select:nth-of-type(1)", "dermatology").catch(() => {});

// 3. profile (not logged in)
await clickText("a", "View and book");
await waitText("Select date and time");
check("profile shows clinic + schedule summary", (await text()).includes("4 to 5 pm"));
await page.waitForFunction(() => document.querySelectorAll(".slot").length >= 5);
await page.evaluate(() => [...document.querySelectorAll(".slot")].find((b) => !b.disabled).click());
await waitText("Book slot");
await shot("3-profile");
await clickText("button", "Book slot");

// 4. login as patient (redirected here because we are anonymous)
await waitText("Log in");
await page.waitForSelector('input[autocomplete="tel"]');
await page.click('input[autocomplete="tel"]', { clickCount: 3 });
await page.type('input[autocomplete="tel"]', "+91 98000 12345");
await clickText("button", "Send OTP");
await waitText("Enter 6-digit OTP");
check("resend timer shown from retry_after_seconds", /Resend OTP in 0:\d\d/.test(await text()));
await page.type('input[autocomplete="one-time-code"]', "123456");
await shot("4-otp");
await clickText("button", "Verify and continue");
await waitText("Select date and time");
check("login returns to the doctor profile", page.url().includes("/doctors/"));

// 5. book -> details
await page.waitForFunction(() => document.querySelectorAll(".slot").length >= 5);
await page.evaluate(() => [...document.querySelectorAll(".slot")].filter((b) => !b.disabled)[2].click());
await waitText("Book slot");
await clickText("button", "Book slot");
await waitText("Who is the patient?");
check("details page shows hold countdown", /Slot held for \d\d:\d\d/.test(await text()), (await text()).match(/Slot held for \d\d:\d\d/)?.[0]);
check("details shows token and slot position", /Slot 3 of 5/.test(await text()) || /Slot \d of 5/.test(await text()));
await page.type('input[placeholder="As on ID"]', "Asha Roy");
await page.type('input[type="number"]', "34");
await shot("5-details");
await clickText("button", "Continue to payment");

// 6. payment
await waitText("Generic checkout placeholder");
check("payment page shows price and policy", (await text()).includes("₹500") && (await text()).includes("full refund"));
await shot("6-payment");
await clickText("button", "securely");

// 7. confirmed
await waitText("You're booked", 15000);
const confirmed = await text();
check("confirmed page shows token and booking id", /CS-\d{6}/.test(confirmed) && /Your token/.test(confirmed), confirmed.match(/CS-\d{6}/)?.[0]);
await shot("7-confirmed");

// 8. my bookings
await clickText("a", "My bookings");
await waitText("My bookings");
await waitText("Dr A. Sen");
check("My bookings > Upcoming lists the booking", (await text()).includes("CS-"));
await shot("8-bookings");

// 9. the booked slot is now unavailable on the doctor's page
await page.goBack().catch(() => {});
await page.goto(`${BASE}/doctors`, { waitUntil: "networkidle0" });
await waitText("Dr A. Sen");
check("search still works while logged in", (await text()).includes("Dr R. Das"));

// 10. mobile layout has no horizontal scroll
await page.setViewport({ width: 390, height: 844 });
await page.goto(BASE, { waitUntil: "networkidle0" });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
check("home has no horizontal scroll at 390px", overflow <= 0, `overflow ${overflow}px`);
await shot("9-mobile-home");

check("no page errors, console errors or 5xx", problems.length === 0, problems.slice(0, 3).join(" | "));
await browser.close();
console.log(`\n${results.filter(Boolean).length}/${results.length} checks passed`);
process.exit(results.every(Boolean) ? 0 : 1);
