import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const reports = path.resolve("../reports");
test("storefront, persistent wishlist, quiz, bag and demo order", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => {
    errors.push(e.message);
    console.log("BROWSER_ERROR", e.stack);
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Less ordinary. More you." }),
  ).toBeVisible();
  await expect(page.locator(".product-image img").first()).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator(".product-image img")
        .first()
        .evaluate((i) => i.complete && i.naturalWidth > 0),
    )
    .toBeTruthy();
  await page.screenshot({
    path: path.join(reports, "home-desktop.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Explore the collection", exact: true })
    .first()
    .click();
  console.log("NAV_URL", page.url());
  await expect(
    page.getByRole("heading", { name: "The collection." }),
  ).toBeVisible();
  await expect(page.locator(".product-card")).toHaveCount(36);
  await page
    .getByRole("button", { name: "Save Citrus Theory", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Remove Citrus Theory", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Remove Citrus Theory", exact: true }),
  ).toBeVisible();
  await page.goto("/wishlist");
  await expect(page.locator(".product-card")).toHaveCount(1);
  await page.goto("/quiz");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page
    .getByRole("button", { name: "See my matches", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "These feel like you." }),
  ).toBeVisible();
  await expect(page.locator(".match").first()).toContainText("% match");
  await page.goto("/product/citrus-theory");
  await expect(
    page.getByRole("heading", { name: "Citrus Theory", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add to bag", exact: true }).click();
  await page.goto("/cart");
  await expect(page.locator(".cart-item")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".cart-item")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Place demo order", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "A new scent chapter." }),
  ).toBeVisible();
  await expect(
    page.getByText("No payment was taken.", { exact: false }),
  ).toBeVisible();
  await page.goto("/privacy");
  await page
    .getByRole("checkbox", {
      name: "Personalize my recommendations",
      exact: true,
    })
    .check();
  await page.reload();
  await expect(
    page.getByRole("checkbox", {
      name: "Personalize my recommendations",
      exact: true,
    }),
  ).toBeChecked();
  await page
    .getByRole("checkbox", {
      name: "Personalize my recommendations",
      exact: true,
    })
    .uncheck();
  await page.goto("/intelligence");
  await expect(
    page.getByRole("heading", { name: "Measured, openly." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
test("protected admin and all intelligence panels", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => {
    errors.push(e.message);
    console.log("BROWSER_ERROR", e.stack);
  });
  await page.goto("/admin");
  await expect(
    page.getByRole("heading", { name: "Admin access required." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Go to sign in", exact: true }).click();
  let password = process.env.ADMIN_PASSWORD;
  if (!password) {
    const env = fs.readFileSync("../backend/.env", "utf8");
    password = env.match(/^ADMIN_PASSWORD=(.+)$/m)?.[1];
  }
  await page
    .getByLabel("Email", { exact: true })
    .fill(process.env.ADMIN_EMAIL || "admin@scenthaus.demo");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page
    .getByRole("link", { name: "Open admin dashboard", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Revenue outlook & uncertainty" }),
  ).toBeVisible();
  await expect(page.locator(".kpi-grid strong").first()).not.toHaveText("");
  await page.screenshot({
    path: path.join(reports, "admin-overview.png"),
    fullPage: true,
  });
  for (const tab of [
    "Forecasts",
    "Inventory",
    "Customers",
    "Recommendations",
    "Experiments",
    "Product controls",
    "Model health",
  ]) {
    await page.getByRole("button", { name: tab, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: tab + ".", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".error")).toHaveCount(0);
    if (tab === "Forecasts") {
      await page
        .getByLabel("Forecast level", { exact: true })
        .selectOption("sku");
      await page
        .getByLabel("Forecast horizon", { exact: true })
        .selectOption("12");
      await expect(
        page.getByRole("heading", {
          name: "Weekly demand · SH-001-30",
          exact: true,
        }),
      ).toBeVisible();
      await page.screenshot({
        path: path.join(reports, "admin-forecast.png"),
        fullPage: true,
      });
    }
    if (tab === "Experiments") {
      await page
        .getByRole("button", { name: "Run simulation", exact: true })
        .click();
      await expect(page.getByText("p =", { exact: false })).toBeVisible();
    }
  }
  expect(errors).toEqual([]);
});
test("mobile collection, menu, product and quiz fit the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of [
    "/",
    "/shop",
    "/product/after-hours",
    "/quiz",
    "/cart",
    "/privacy",
  ]) {
    await page.goto(route);
    await expect(page.locator("h1").first()).toBeVisible();
    await expect(page.locator(".error")).toHaveCount(0);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 2,
    );
    expect(overflow, route + " horizontal overflow").toBeFalsy();
    if (route === "/")
      await page.screenshot({
        path: path.join(reports, "home-mobile.png"),
        fullPage: true,
      });
  }
  await page
    .getByRole("button", { name: "Toggle navigation", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Find your scent", exact: true }),
  ).toBeVisible();
});
