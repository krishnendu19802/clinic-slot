// Doctor journey. Phase "onboarding": sign up, fill profile, upload documents, submit.
// Phase "schedule" (after the runner approves the doctor): clinic, weekly hours, block a day and a slot.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import puppeteer from "puppeteer-core";

const BASE = "http://127.0.0.1:5173";
const [OUT, PHASE] = [process.argv[2], process.argv[3]];
const PHONE = "+91 97000 00099";
const results = [];
const check = (name, ok, extra = "") => { results.push(ok); console.log(`${ok ? "PASS" : "FAIL"} [${PHASE}] ${name}${extra ? `  [${extra}]` : ""}`); };

const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", headless: "new", args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 1000 });
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
/** Set a controlled React input (date/time/number) the way a user edit would. */
const setValue = (el, value) => el.evaluate((node, v) => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(node, v);
  node.dispatchEvent(new Event("input", { bubbles: true }));
}, value);
const labelInput = async (label) => (await page.$$(`xpath/.//label[contains(., "${label}")]//input`))[0];
const type = async (label, value) => { const el = await labelInput(label); await el.click({ clickCount: 3 }); await el.type(value); };
const shot = (n) => page.screenshot({ path: `${OUT}/${n}.png`, fullPage: true });

async function login() {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle0" });
  await clickText("button", "Doctor");
  await page.waitForSelector('input[autocomplete="tel"]');
  await page.click('input[autocomplete="tel"]', { clickCount: 3 });
  await page.type('input[autocomplete="tel"]', PHONE);
  await clickText("button", "Send OTP");
  await waitText("Enter 6-digit OTP");
  await page.type('input[autocomplete="one-time-code"]', "123456");
  await clickText("button", "Verify and continue");
}

if (PHASE === "onboarding") {
  await login();
  await waitText("Complete your profile");
  check("new doctor lands on onboarding with 'Not submitted'", (await text()).includes("Not submitted"));

  await type("Full name", "Dr N. Onboard");
  await type("Registration number", "WBMC-E2E1");
  await page.select("xpath/.//label[contains(., 'Issuing council')]//select", "1").catch(async () => {
    const sel = (await page.$$(`xpath/.//label[contains(., "Issuing council")]//select`))[0];
    await sel.select(await sel.evaluate((s) => s.options[1].value));
  });
  await type("Degrees", "MBBS, MD");
  const gender = (await page.$$(`xpath/.//label[contains(., "Gender")]//select`))[0];
  await gender.select("male");
  await type("Experience", "9");
  await type("Consultation fee", "600");
  await clickText("label", "Dermatology");
  await clickText("label", "English");
  await type("Remarks", "Skin and hair.");
  await clickText("button", "Save draft");
  await waitText("Draft saved.");
  await page.reload({ waitUntil: "networkidle0" });
  await waitText("Complete your profile");
  const kept = await (await labelInput("Full name")).evaluate((n) => n.value);
  check("draft survives a reload (partial save works)", kept === "Dr N. Onboard", kept);

  await clickText("button", "Submit for verification");
  await waitText("Still needed");
  problems.splice(0, problems.length, ...problems.filter((p) => !p.includes("status of 400"))); // that 400 is the case under test
  const need = await text();
  check("submit without documents lists what is missing", /Registration certificate/.test(need) && /Government ID/.test(need));

  const files = {};
  for (const [k, label] of [["registration", "Registration certificate"], ["degree", "Degree certificate"], ["id", "Government ID"]]) {
    const f = path.join(os.tmpdir(), `e2e-${k}.pdf`);
    fs.writeFileSync(f, "%PDF-1.4 e2e");
    files[label] = f;
  }
  for (const [label, f] of Object.entries(files)) {
    const input = (await page.$$(`input[aria-label="Upload ${label}"]`))[0];
    await input.uploadFile(f);
    await page.waitForFunction((l) => !document.querySelector(`input[aria-label="Upload ${l}"]`), { timeout: 8000 }, label);
  }
  check("three documents uploaded", (await page.$$('button[aria-label^="Remove"]')).length === 3);
  await shot("d1-onboarding");
  await clickText("button", "Submit for verification");
  await waitText("Under review");
  const nameDisabled = await (await labelInput("Full name")).evaluate((n) => n.matches(":disabled")); // fieldset-disabled inputs keep .disabled === false
  check("submitted profile is read-only", nameDisabled && (await text()).includes("You cannot edit while it is under review"));
  await shot("d2-submitted");
} else {
  await login();
  await waitText("Clinic and schedule");
  check("approved doctor lands on the schedule page", page.url().endsWith("/doctor/schedule") && !(await text()).includes("not approved yet"));

  await type("Clinic name", "E2E Clinic");
  await type("Address", "1 Test Road");
  await type("Area", "City Centre");
  await type("Pincode", "713201");
  await clickText("button", "Add clinic");
  await waitText("Weekly hours");
  for (let i = 0; i < 7; i++) {
    await clickText("button", "+ Add window");
    const sel = (await page.$$(`xpath/.//label[contains(., "Day")]//select`))[i];
    await sel.select(String(i + 1));
  }
  const body = await text();
  check("each window shows its slot count", (body.match(/5 slots of 12 min/g) ?? []).length === 7);
  check("preview lists slot times like the design", body.includes("4:00 pm") && body.includes("4:48 pm"));
  await shot("d3-schedule");

  // a bad window is caught before the server is called
  const to = (await page.$$(`xpath/.//label[contains(., "To")]//input`))[0];
  await setValue(to, "17:05");
  check("non-divisible window is flagged and Save is disabled", (await text()).includes("do not divide")
    && await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText === "Save schedule").disabled));
  await setValue(to, "17:00");

  await clickText("button", "Save schedule");
  await waitText("are now bookable");
  check("saving generates slots for an approved doctor", /\d+ new slots are now bookable/.test(await text()), (await text()).match(/\d+ new slots are now bookable/)?.[0]);

  const day = (n) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
  const date = (await page.$$(`xpath/.//label[contains(., "Date")]//input`))[0];
  await setValue(date, day(3));
  await page.waitForFunction(() => [...document.querySelectorAll("button.slot")].length >= 5, { timeout: 8000 });
  const first = await page.evaluate(() => { const b = document.querySelector("button.slot"); b.click(); return b.innerText; });
  await page.waitForFunction(() => document.querySelector("button.slot")?.classList.contains("gone"), { timeout: 8000 });
  check("a slot can be blocked", true, first);
  await page.evaluate(() => document.querySelector("button.slot").click());
  await page.waitForFunction(() => !document.querySelector("button.slot")?.classList.contains("gone"), { timeout: 8000 });
  check("and unblocked again", true);

  await setValue(date, day(4));
  await clickText("button", "Block day");
  await waitText("day off");
  check("a whole day can be blocked and is listed", (await text()).includes("day off"));
  await page.evaluate(() => document.querySelector('button[aria-label^="Remove 20"]').click());
  await page.waitForFunction(() => !document.body.innerText.includes("day off"), { timeout: 8000 });
  check("and the day off can be removed", true);
  await shot("d4-blocked");
}

check("no page errors, console errors or 5xx", problems.length === 0, problems.slice(0, 3).join(" | "));
await browser.close();
console.log(`\n[${PHASE}] ${results.filter(Boolean).length}/${results.length} checks passed`);
process.exit(results.every(Boolean) ? 0 : 1);
