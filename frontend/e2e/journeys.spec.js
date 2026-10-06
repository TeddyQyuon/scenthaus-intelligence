import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const reports = path.resolve("../reports");

async function realProduct(page) {
  const response = await page.request.get("/api/products?in_stock=false");
  expect(response.ok()).toBeTruthy();
  const catalog = await response.json();
  expect(catalog.products).toHaveLength(150);
  expect(catalog.brands).toHaveLength(35);
  return catalog.products.find(
    (product) =>
      product.brand === "Dior" && product.variants.some((variant) => variant.stock > 0),
  );
}

async function adminCredentials() {
  if (process.env.ADMIN_PASSWORD) {
    return {
      email: process.env.ADMIN_EMAIL || "admin@scenthaus.demo",
      password: process.env.ADMIN_PASSWORD,
    };
  }
  const env = fs.readFileSync("../backend/.env", "utf8");
  return {
    email: env.match(/^ADMIN_EMAIL=(.+)$/m)?.[1] || "admin@scenthaus.demo",
    password: env.match(/^ADMIN_PASSWORD=(.+)$/m)?.[1],
  };
}

test("real catalog, discovery, consent, wishlist, quiz and demo order", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const product = await realProduct(page);
  expect(product).toBeTruthy();

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Less ordinary.*More you/ }),
  ).toBeVisible();
  await expect(page.locator(".product-image img").first()).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator(".product-image img")
        .first()
        .evaluate((image) => image.complete && image.naturalWidth > 0),
    )
    .toBeTruthy();
  await fs.promises.mkdir(reports, { recursive: true });
  await page.screenshot({
    path: path.join(reports, "home-desktop.png"),
    fullPage: true,
  });

  await page.getByRole("link", { name: "Explore the collection" }).click();
  await expect(
    page.getByRole("heading", { name: "The collection." }),
  ).toBeVisible();
  await expect(page.locator(".product-card")).toHaveCount(150);
  await page.getByLabel("House").selectOption("Dior");
  await expect(page.locator(".product-card").first()).toContainText("Dior");
  await page.getByLabel("House").selectOption("");

  await page
    .getByRole("checkbox", { name: "Describe your scent in natural language" })
    .check();
  await page
    .getByRole("button", { name: "Fresh office scent under $150" })
    .click();
  await expect(page.locator(".product-card").first()).toBeVisible();
  await expect(page.locator(".results-count")).toContainText("Budget");

  await page.goto("/privacy");
  const personalization = page.getByRole("checkbox", {
    name: "Personalize my recommendations",
  });
  await personalization.check();
  await page.reload();
  await expect(
    page.getByRole("checkbox", { name: "Personalize my recommendations" }),
  ).toBeChecked();

  await page.goto("/shop");
  await page.getByRole("button", { name: `Save ${product.name}` }).click();
  await expect(
    page.getByRole("button", { name: `Remove ${product.name}` }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: `Remove ${product.name}` }),
  ).toBeVisible();
  await page.goto("/wishlist");
  await expect(page.locator(".product-card")).toHaveCount(1);

  await page.goto("/quiz");
  for (let step = 0; step < 3; step += 1) {
    await page.getByRole("button", { name: "Continue" }).click();
  }
  await page.getByRole("button", { name: "See my matches" }).click();
  await expect(
    page.getByRole("heading", { name: "These feel like you." }),
  ).toBeVisible();
  await expect(page.locator(".match").first()).toContainText("% match");
  await expect(page.locator(".reason-chips").first()).toBeVisible();

  await page.goto(`/product/${product.slug}`);
  await expect(
    page.getByRole("heading", { name: product.name, exact: true }),
  ).toBeVisible();
  const variant = product.variants.find((entry) => entry.stock > 0);
  await page
    .getByRole("button", { name: new RegExp(`${variant.size_ml}ml`) })
    .click();
  await page.getByRole("button", { name: "Add to bag" }).click();
  await page.goto("/cart");
  await expect(page.locator(".cart-item")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".cart-item")).toHaveCount(1);
  await page.getByRole("button", { name: "Place demo order" }).click();
  await expect(
    page.getByRole("heading", { name: "A new scent chapter." }),
  ).toBeVisible();
  await expect(page.getByText("No payment was taken.")).toBeVisible();

  await expect
    .poll(async () => {
      const result = await page.request.get("/api/privacy/export");
      const exported = await result.json();
      return exported.events.map((event) => event.type);
    })
    .toEqual(expect.arrayContaining(["view", "wishlist_add", "add_to_cart", "purchase"]));
  await page.goto("/privacy");
  await page
    .getByRole("checkbox", { name: "Personalize my recommendations" })
    .uncheck();
  const exported = await page.request.get("/api/privacy/export").then((r) => r.json());
  expect(exported.events).toEqual([]);
  expect(exported.orders.length).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

test("forecast dashboard is protected and compares serving models", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/admin/forecast");
  await expect(
    page.getByRole("heading", { name: "Admin access required." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Go to sign in" }).click();
  const credentials = await adminCredentials();
  await page.getByLabel("Email", { exact: true }).fill(credentials.email);
  await page
    .getByLabel("Password", { exact: true })
    .fill(credentials.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("link", { name: "Open admin dashboard", exact: true }),
  ).toBeVisible();

  await page.goto("/admin/forecast");
  await expect(
    page.getByRole("heading", { name: "Forecasts.", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Forecast model").selectOption("lstm");
  await expect(
    page.getByRole("img", { name: /P10–P90 learned band/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Forecast accuracy by model" }),
  ).toBeVisible();
  await expect(page.getByText("N-BEATS", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "About this model" }).click();
  await expect(page.getByRole("dialog")).toContainText("SIMULATED DATA");
  await page.getByRole("button", { name: "Close model information" }).click();

  await page.getByLabel("Forecast level").selectOption("sku");
  await page.getByLabel("Forecast model").selectOption("nbeats");
  await page.getByLabel("Forecast horizon").selectOption("12");
  await expect(page.getByRole("img", { name: /P10–P90 learned band/ })).toBeVisible();
  await expect(page.locator(".table-wrap tbody tr").first()).toBeVisible();
  await page.screenshot({
    path: path.join(reports, "admin-forecast.png"),
    fullPage: true,
  });

  for (const tab of [
    "Overview",
    "Inventory",
    "Customers",
    "Recommendations",
    "Experiments",
    "Product controls",
    "Model health",
  ]) {
    await page.getByRole("button", { name: tab, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: `${tab}.`, exact: true }),
    ).toBeVisible();
    await expect(page.locator(".error")).toHaveCount(0);
  }
  await expect(
    page.getByText("SIMULATED DATA", { exact: true }).first(),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile catalogue and search controls fit the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "The collection", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "The collection." }),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: "Describe your scent in natural language" })
    .check();
  await expect(
    page.getByRole("button", { name: "Fresh office scent under $150" }),
  ).toBeVisible();
  const width = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(width).toBeLessThanOrEqual(1);
});
