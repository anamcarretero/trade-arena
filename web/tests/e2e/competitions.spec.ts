import {expect, test} from "@playwright/test";
import {EncryptJWT} from "jose";

async function sessionCookie() {
  const key = Buffer.from("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "base64url");
  return new EncryptJWT({token: "e2e-session"})
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
  await expect(page.getByText("3000.00 USD")).toBeVisible();
  await expect(page.getByText("XNYS · America/New_York")).toBeVisible();
  await page.getByRole("link", {name: "EN", exact: true}).click();
  await expect(page.getByText("Calendar and rules copied immutably")).toBeVisible();
  await expect(page.getByText("This competition will not change when the general rules are updated.")).toBeVisible();
});
