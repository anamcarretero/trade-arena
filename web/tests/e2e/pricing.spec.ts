import {expect, test} from "@playwright/test";

test("pricing is public, bilingual and reachable from public navigation", async ({page}) => {
  await page.goto("/es");
  await page.getByRole("link", {name: "Planes"}).click();
  await expect(page).toHaveURL(/\/es\/pricing$/);
  await expect(page.getByRole("heading", {level: 1})).toContainText("Empieza gratis");
  await expect(page.getByRole("listitem").filter({hasText: "Una liga activa"})).toBeVisible();
  await expect(page.getByRole("listitem").filter({hasText: "Dos plazas"})).toBeVisible();
  await expect(page.getByRole("listitem").filter({hasText: "3.000 USD de capital virtual inicial por competición"})).toBeVisible();
  await expect(page.getByRole("listitem").filter({hasText: "Hasta cinco jugadores"})).toBeVisible();
  await expect(page.getByRole("listitem").filter({hasText: "Competiciones de hasta un año"})).toBeVisible();
  await expect(page.getByRole("listitem").filter({hasText: "Capital virtual inicial configurable"})).toBeVisible();
  await expect(page.getByRole("listitem").filter({hasText: "Hasta 20 jugadores"})).toBeVisible();
  await expect(page.getByRole("listitem").filter({hasText: "Hasta cinco ligas activas"})).toBeVisible();
  await expect(page.getByText("Próximamente", {exact: true})).toHaveCount(2);
  await expect(page.getByRole("link", {name: /Empezar con Free/})).toHaveAttribute(
    "href", "/auth/login?locale=es&returnTo=/es/app"
  );

  await page.getByRole("link", {name: "EN", exact: true}).click();
  await expect(page).toHaveURL(/\/en\/pricing$/);
  await expect(page.getByRole("heading", {level: 1})).toContainText("Start for free");
  await expect(page.getByRole("listitem").filter({hasText: "USD 3,000 starting virtual capital per competition"})).toBeVisible();
  await expect(page.getByText("Coming soon", {exact: true})).toHaveCount(2);
});

test("pricing exposes accessible landmarks and keyboard focus", async ({page}) => {
  await page.goto("/en/pricing");
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("navigation", {name: "Primary navigation"})).toBeVisible();
  await expect(page.getByRole("navigation", {name: "Language"})).toBeVisible();
  await expect(page.getByRole("heading", {level: 1})).toHaveCount(1);
  await expect(page.getByRole("heading", {level: 2})).toHaveCount(3);
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus-visible")).toBeVisible();
});

for (const width of [375, 414]) {
  test(`pricing has no horizontal scroll at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 844});
    await page.goto("/es/pricing");
    const dimensions = await page.evaluate(() => ({
      documentClientWidth: document.documentElement.clientWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth
    }));
    expect(dimensions.documentScrollWidth).toBe(dimensions.documentClientWidth);
    expect(dimensions.bodyScrollWidth).toBeLessThanOrEqual(dimensions.documentClientWidth);
    await expect(page.getByRole("heading", {name: "Free"})).toBeVisible();
    await expect(page.getByRole("link", {name: /Empezar con Free/})).toBeVisible();
  });
}
