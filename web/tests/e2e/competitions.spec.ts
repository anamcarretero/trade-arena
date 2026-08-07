import {expect, test, type BrowserContext, type Page} from "@playwright/test";
import {EncryptJWT} from "jose";

async function sessionCookie(token = "e2e-session") {
  const key = Buffer.from("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "base64url");
  return new EncryptJWT({token}).setProtectedHeader({alg: "dir", enc: "A256GCM"})
    .setIssuedAt().setExpirationTime("10m").encrypt(key);
}

async function authenticate(context: BrowserContext, token: string) {
  await context.addCookies([{
    name: "tradearena_session", value: await sessionCookie(token),
    domain: "localhost", path: "/", httpOnly: true, sameSite: "Lax"
  }]);
}

async function reset(request: {post: (url: string, options: {data: unknown}) => Promise<unknown>}, seed = false) {
  await request.post("http://127.0.0.1:18080/__e2e/reset", {data: {seed}});
}

test("two participants complete the critical private competition flow", async ({browser, request}) => {
  await reset(request);
  const ownerContext = await browser.newContext();
  const memberContext = await browser.newContext();
  await authenticate(ownerContext, "e2e-session");
  await authenticate(memberContext, "e2e-session-member");
  const owner = await ownerContext.newPage();
  const member = await memberContext.newPage();

  await owner.goto("/es/app");
  await owner.getByLabel("Nombre de la liga").fill("Liga WCAG");
  await owner.getByRole("button", {name: "Crear liga"}).click();
  await expect(owner.getByRole("heading", {name: "Liga WCAG"})).toBeVisible();
  await owner.getByLabel("Email de la persona invitada").fill("member@example.com");
  await owner.getByRole("button", {name: "Generar enlace"}).click();
  await expect(owner.getByRole("status").filter({hasText: "Enlace creado"})).toBeVisible();

  await member.goto("/en/app");
  await expect(member.getByRole("heading", {name: "Invitations received"})).toBeVisible();
  await expect(member.getByText("Liga WCAG")).toBeVisible();
  await member.getByRole("button", {name: "Accept invitation"}).click();
  await expect(member.getByRole("heading", {name: "Liga WCAG"})).toBeVisible();
  await expect(member.getByText("Member E2E")).toBeVisible();
  await expect(member.getByRole("button", {name: "Generate link"})).toHaveCount(0);

  await owner.reload();
  await owner.getByLabel("Nombre de la competición").fill("Otoño E2E");
  await owner.getByLabel("Empieza").fill("2026-09-01");
  await owner.getByLabel("Termina").fill("2026-09-30");
  await owner.getByRole("button", {name: /Crear borrador/}).click();
  await expect(owner.getByRole("status").filter({hasText: "Borrador de competición creado"})).toBeVisible();
  await owner.getByRole("link", {name: "Abrir dashboard"}).click();
  await expect(owner.getByText("La competición todavía no tiene jornadas valorables.")).toBeVisible();
  await owner.getByRole("link", {name: "Volver a la liga"}).click();
  await owner.getByRole("button", {name: /Iniciar competición/}).click();
  await expect(owner.getByText("Calendario y reglas copiados de forma inmutable")).toBeVisible();
  await owner.getByRole("link", {name: "Abrir dashboard"}).click();

  const ownerOrder = owner.getByRole("heading", {name: "Nueva orden"}).locator("..");
  await ownerOrder.getByLabel("Símbolo").fill("AAPL");
  await ownerOrder.getByLabel("Cantidad (hasta 8 decimales)").fill("2");
  await ownerOrder.getByLabel("Comisión (opcional)").fill("0,75");
  await ownerOrder.getByRole("button", {name: /Enviar orden/}).click();
  await expect(owner.getByRole("status").filter({hasText: "Orden enviada"})).toBeVisible();
  await expect(owner.getByText("2799.25 USD")).toBeVisible();

  await member.goto("/en/app/leagues/league-e2e/competitions/competition-1");
  const reported = member.getByRole("heading", {name: "Record a completed trade"}).locator("..");
  await reported.getByLabel("Date and time").fill("2026-09-03T15:00");
  await reported.getByLabel("Symbol").fill("MU");
  await reported.getByLabel("Quantity (up to 8 decimals)").fill("1");
  await reported.getByLabel("Price per share (USD)").fill("855.70");
  await reported.getByLabel("Total amount (USD)").fill("856.85");
  await reported.getByRole("button", {name: /Record trade/}).click();
  await expect(member.getByRole("status").filter({hasText: "Reported trade recorded"})).toBeVisible();
  await expect(member.getByText("2143.15 USD")).toBeVisible();

  const portfolioUrl = "http://127.0.0.1:18080/api/v1/leagues/league-e2e/competitions/competition-1/portfolio";
  const ownerPortfolio = await (await request.get(portfolioUrl, {headers: {Authorization: "Bearer e2e-session"}})).json();
  const memberPortfolio = await (await request.get(portfolioUrl, {headers: {Authorization: "Bearer e2e-session-member"}})).json();
  expect(ownerPortfolio.user_id).toBe("owner-e2e");
  expect(memberPortfolio.user_id).toBe("member-e2e");
  expect(JSON.stringify(ownerPortfolio)).not.toContain("2143.15");
  expect(JSON.stringify(memberPortfolio)).not.toContain("2799.25");
  const memberOrderId = memberPortfolio.orders[0].id;
  const crossOrder = await request.delete(`http://127.0.0.1:18080/api/v1/leagues/league-e2e/competitions/competition-1/orders/${memberOrderId}`, {headers: {Authorization: "Bearer e2e-session"}});
  expect(crossOrder.status()).toBe(404);

  const sharedDashboard = await (await request.get("http://127.0.0.1:18080/api/v1/leagues/league-e2e/competitions/competition-1/dashboard", {headers: {Authorization: "Bearer e2e-session"}})).json();
  const sharedPayload = JSON.stringify(sharedDashboard);
  for (const forbidden of ["quantity", "price", "total_amount", "commission", "cash", "equity", "orders", "ledger", "client_order_id", "client_trade_id"]) {
    expect(sharedPayload).not.toContain(`"${forbidden}"`);
  }

  await owner.reload();
  await expect(owner.getByText("Dashboard de competición", {exact: false})).toBeVisible();
  await expect(owner.getByRole("heading", {level: 3, name: "Ranking"})).toBeVisible();
  await expect(owner.getByRole("heading", {name: "Portfolios por jugador"})).toBeVisible();
  await expect(owner.getByRole("heading", {name: "Últimas operaciones"}).locator("..").getByText("Member E2E · MU")).toBeVisible();
  await expect(owner.locator("body")).not.toContainText("2143.15");
  await expect(owner.locator("body")).not.toContainText("856.85");
  await expect(owner.locator("body")).not.toContainText("855.70");
  await expect(owner.locator("body")).not.toContainText("1.15");
  await expect(owner.locator("body")).not.toContainText(memberOrderId);
  await expect(member.locator("body")).not.toContainText("2799.25");
  await expect(member.locator("body")).not.toContainText("0.75");

  for (const page of [owner, member]) await expectNoHorizontalScroll(page);
  await ownerContext.close();
  await memberContext.close();
});

test("loading, error, missing quotes and inaccessible routes are understandable", async ({browser, request}) => {
  await reset(request, true);
  const context = await browser.newContext();
  await authenticate(context, "e2e-session");
  const page = await context.newPage();
  await request.post("http://127.0.0.1:18080/__e2e/dashboard", {data: {mode: "complete", delay: 3000}});
  await page.goto("/es/app/leagues/league-e2e/competitions/competition-1", {waitUntil: "commit"});
  await expect(page.getByRole("status").filter({hasText: "Cargando / Loading"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Otoño E2E"})).toBeVisible();

  await request.post("http://127.0.0.1:18080/__e2e/dashboard", {data: {mode: "incomplete", delay: 0}});
  await page.reload();
  await expect(page.getByRole("status")).toContainText("Faltan cotizaciones");
  await page.getByText("Cotizaciones ausentes").click();
  await expect(page.getByRole("listitem").filter({hasText: "AAPL"})).toBeVisible();

  await request.post("http://127.0.0.1:18080/__e2e/dashboard", {data: {mode: "error", delay: 0}});
  await page.reload();
  await expect(page.getByRole("alert").filter({hasText: "No hemos podido cargar esta pantalla"})).toBeVisible();

  const outsider = await browser.newContext();
  await authenticate(outsider, "e2e-session-outsider");
  const outsiderPage = await outsider.newPage();
  await outsiderPage.goto("/en/app/leagues/league-e2e");
  await expect(outsiderPage.getByRole("heading", {name: "Private league"})).toBeVisible();
  await expect(outsiderPage.getByText("You do not have access")).toBeVisible();
  await outsiderPage.goto("/en/invite/invitation-e2e");
  await expect(outsiderPage.getByRole("alert").filter({hasText: "You cannot access this league"})).toBeVisible();
  await outsider.close();
  await context.close();
});

test("private notifications, export and confirmed deletion remain scoped", async ({browser, request}) => {
  await reset(request, true);
  const ownerContext = await browser.newContext();
  await authenticate(ownerContext, "e2e-session");
  const owner = await ownerContext.newPage();
  await owner.goto("/es/app/notifications");
  await expect(owner.getByText("Temporada preparada")).toBeVisible();
  await owner.getByRole("button", {name: "Marcar como leída"}).click();
  await expect(owner.getByRole("status")).toContainText("Notificación marcada como leída");
  await owner.goto("/en/app/account");
  const downloadPromise = owner.waitForEvent("download");
  await owner.getByRole("link", {name: "Download export"}).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  let exported = "";
  for await (const chunk of stream) exported += chunk.toString();
  expect(exported).toContain("owner@example.com");
  expect(exported).toContain("portfolio-owner-e2e");
  expect(exported).not.toContain("member@example.com");
  expect(exported).not.toContain("portfolio-member-e2e");
  expect(exported).not.toContain("e2e-session");
  await ownerContext.close();

  const memberContext = await browser.newContext();
  await authenticate(memberContext, "e2e-session-member");
  const member = await memberContext.newPage();
  await member.goto("/en/app/account");
  const deleteButton = member.getByRole("button", {name: "Permanently delete account"});
  await deleteButton.click();
  await expect(member).toHaveURL(/\/en\/app\/account$/);
  await member.getByRole("checkbox").check();
  await deleteButton.click();
  await expect(member).toHaveURL(/\/en\?account_deleted=1$/);
  await member.goto("/en/app/notifications");
  await expect(member).toHaveURL(/^https:\/\/test\.eu\.auth0\.com\/authorize/);
  await memberContext.close();
});

async function expectNoHorizontalScroll(page: Page) {
  await page.setViewportSize({width: 375, height: 812});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}
