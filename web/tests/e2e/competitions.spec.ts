import {expect, test} from "@playwright/test";
import {EncryptJWT} from "jose";

async function sessionCookie(token = "e2e-session") {
  const key = Buffer.from("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "base64url");
  return new EncryptJWT({token})
    .setProtectedHeader({alg: "dir", enc: "A256GCM"})
    .setIssuedAt()
    .setExpirationTime("10m")
    .encrypt(key);
}

test("an owner creates and starts a competition with immutable ES/EN confirmation", async ({context, page}) => {
  await context.addCookies([{
    name: "tradearena_session", value: await sessionCookie(),
    domain: "localhost", path: "/", httpOnly: true, sameSite: "Lax"
  }]);
  await page.goto("/es/app/leagues/league-e2e");
  await expect(page.getByRole("heading", {name: "Competiciones"})).toBeVisible();

  await page.getByLabel("Nombre de la competición").fill("Otoño E2E");
  await page.getByLabel("Empieza").fill("2026-09-01");
  await page.getByLabel("Termina").fill("2026-09-30");
  await page.getByRole("button", {name: /Crear borrador/}).click();
  await expect(page.getByText("Borrador de competición creado.")).toBeVisible();
  await page.getByRole("button", {name: /Iniciar competición/}).click();

  await expect(page.getByText("Calendario y reglas copiados de forma inmutable")).toBeVisible();
  await expect(page.getByRole("definition").filter({hasText: "3000.00 USD"})).toBeVisible();
  await expect(page.getByText("XNYS · America/New_York")).toBeVisible();
  await page.getByRole("link", {name: "Abrir dashboard"}).click();
  await expect(page.getByText("Dashboard de competición", {exact: false})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Rentabilidad acumulada"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Insights de liga"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Portfolio agregado"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Cartera y órdenes"})).toBeVisible();
  const orderForm = page.getByRole("heading", {name: "Nueva orden"}).locator("..");
  await orderForm.getByLabel("Símbolo").fill("AAPL");
  await orderForm.getByLabel("Cantidad (hasta 8 decimales)").fill("2");
  await orderForm.getByLabel("Comisión (opcional)").fill("0,75");
  await page.getByRole("button", {name: /Enviar orden/}).click();
  await expect(page.getByText("Orden enviada.")).toBeVisible();
  await expect(page.getByText("2799.25 USD")).toBeVisible();
  await expect(page.getByText("Ejecutada", {exact: true})).toBeVisible();
  await expect(page.getByText("Ejecutada por fixture de mercado")).toBeVisible();

  const reportedForm = page.getByRole("heading", {name: "Registrar operación ya realizada"}).locator("..");
  await reportedForm.getByLabel("Fecha y hora").fill("2026-09-03T15:00");
  await expect(reportedForm.getByLabel("Zona horaria")).toHaveValue("Europe/Madrid");
  await reportedForm.getByLabel("Símbolo").fill("MU");
  await reportedForm.getByLabel("Cantidad (hasta 8 decimales)").fill("1");
  await reportedForm.getByLabel("Precio por acción (USD)").fill("855,70");
  await reportedForm.getByLabel("Importe total (USD)").fill("856,85");
  await expect(reportedForm.getByLabel("Comisión (opcional)")).toHaveValue("1.15");
  await reportedForm.getByRole("button", {name: /Registrar operación/}).click();
  await expect(page.getByText("Operación declarada registrada")).toBeVisible();
  await expect(page.getByText("Declarada por el usuario")).toBeVisible();
  await expect(page.getByRole("heading", {name: "Últimas operaciones"}).locator("..").getByText("MU")).toBeVisible();
  await expect(page.getByText("1942.00 USD")).toBeVisible();
  await expect(page.getByRole("strong").filter({hasText: "Member E2E"}).first()).toBeVisible();
  await expect(page.getByText("Incorporación tardía", {exact: true})).toBeVisible();
  await page.getByRole("link", {name: "EN", exact: true}).click();
  await expect(page.getByText("Competition dashboard", {exact: false})).toBeVisible();
  await expect(page.getByRole("heading", {name: "League insights"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Portfolio and orders"})).toBeVisible();
  await expect(page.getByText("Reported by the user")).toBeVisible();
  await expect(page.getByText("Late entry", {exact: true})).toBeVisible();
  await page.setViewportSize({width: 375, height: 812});
  const noHorizontalScroll = await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth
  );
  expect(noHorizontalScroll).toBe(true);
});

test("two participants use private notifications, export and confirmed deletion", async ({browser}) => {
  const ownerContext = await browser.newContext();
  await ownerContext.addCookies([{
    name: "tradearena_session", value: await sessionCookie(),
    domain: "localhost", path: "/", httpOnly: true, sameSite: "Lax"
  }]);
  const ownerPage = await ownerContext.newPage();
  await ownerPage.goto("/es/app/notifications");
  await expect(ownerPage.getByText("Temporada preparada")).toBeVisible();
  await expect(ownerPage.getByText("No leída")).toBeVisible();
  await ownerPage.getByRole("button", {name: "Marcar como leída"}).click();
  await expect(ownerPage.getByText("Notificación marcada como leída.")).toBeVisible();
  await expect(ownerPage.getByText("Leída", {exact: true})).toBeVisible();
  await ownerPage.setViewportSize({width: 375, height: 812});
  expect(await ownerPage.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth
  )).toBe(true);

  await ownerPage.goto("/en/app/account");
  const downloadPromise = ownerPage.waitForEvent("download");
  await ownerPage.getByRole("link", {name: "Download export"}).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  let exported = "";
  for await (const chunk of stream) exported += chunk.toString();
  expect(exported).toContain("owner@example.com");
  expect(exported).toContain("portfolio-owner-e2e");
  expect(exported).not.toContain("member@example.com");
  expect(exported).not.toContain("e2e-session");
  expect(exported).not.toContain("secret");
  await ownerContext.close();

  const memberContext = await browser.newContext();
  await memberContext.addCookies([{
    name: "tradearena_session", value: await sessionCookie("e2e-session-member"),
    domain: "localhost", path: "/", httpOnly: true, sameSite: "Lax"
  }]);
  const memberPage = await memberContext.newPage();
  await memberPage.goto("/en/app/account");
  const deleteButton = memberPage.getByRole("button", {name: "Permanently delete account"});
  await deleteButton.click();
  await expect(memberPage).toHaveURL(/\/en\/app\/account$/);
  await memberPage.getByRole("checkbox").check();
  await deleteButton.click();
  await expect(memberPage).toHaveURL(/\/en\?account_deleted=1$/);
  await memberPage.goto("/en/app/notifications");
  await expect(memberPage).toHaveURL(/^https:\/\/test\.eu\.auth0\.com\/authorize/);
  await memberContext.close();
});
