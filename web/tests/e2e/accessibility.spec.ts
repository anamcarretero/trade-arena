import AxeBuilder from "@axe-core/playwright";
import {expect, test, type BrowserContext, type Page} from "@playwright/test";
import {EncryptJWT} from "jose";

async function authenticate(context: BrowserContext, token = "e2e-session") {
  const key = Buffer.from("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "base64url");
  const value = await new EncryptJWT({token}).setProtectedHeader({alg: "dir", enc: "A256GCM"})
    .setIssuedAt().setExpirationTime("10m").encrypt(key);
  await context.addCookies([{
    name: "tradearena_session", value, domain: "localhost", path: "/",
    httpOnly: true, sameSite: "Lax"
  }]);
}

async function expectWcag22Aa(page: Page) {
  const results = await new AxeBuilder({page})
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations, results.violations.map(item =>
    `${item.id}: ${item.help}\n${item.nodes.map(node => node.target.join(" ")).join("\n")}`
  ).join("\n\n")).toEqual([]);
}

test("public ES/EN routes pass automated WCAG 2.2 AA checks", async ({page}) => {
  for (const route of ["/es", "/en", "/es/pricing", "/en/pricing"]) {
    const response = await page.goto(route);
    expect(await response?.text()).toContain(`<html lang="${route.startsWith("/en") ? "en" : "es"}"`);
    await expect(page.locator("html")).toHaveAttribute("lang", route.startsWith("/en") ? "en" : "es");
    await expectWcag22Aa(page);
  }
});

test("private critical routes and forms pass automated WCAG 2.2 AA checks", async ({browser, request}) => {
  await request.post("http://127.0.0.1:18080/__e2e/reset", {data: {seed: true}});
  const context = await browser.newContext();
  await authenticate(context);
  const page = await context.newPage();
  for (const route of [
    "/es/app", "/en/app/profile", "/es/app/leagues/league-e2e",
    "/en/app/leagues/league-e2e/competitions/competition-1",
    "/es/app/notifications", "/en/app/account"
  ]) {
    await page.goto(route);
    await expectWcag22Aa(page);
  }
  await context.close();
});

test("keyboard navigation, focus restoration, validation and reduced motion remain usable", async ({browser, request}) => {
  await request.post("http://127.0.0.1:18080/__e2e/reset", {data: {seed: true}});
  const context = await browser.newContext({reducedMotion: "reduce"});
  await authenticate(context);
  const page = await context.newPage();
  await page.goto("/es/app");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", {name: "Saltar al contenido principal"})).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();

  await page.getByRole("link", {name: "Abrir liga"}).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", {level: 1, name: "Liga E2E"})).toBeFocused();

  const form = page.getByRole("button", {name: "Crear borrador"}).locator("..");
  await form.getByRole("button", {name: "Crear borrador"}).click();
  await expect(form.getByLabel("Nombre de la competición")).toBeFocused();
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).toBe("auto");
  await context.close();
});
