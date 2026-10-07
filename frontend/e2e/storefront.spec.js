import { test, expect } from "@playwright/test";

const product = {
  id: "test-perfume", slug: "test-perfume", name: "Test fragrance", brand: "Dior",
  category: "Fresh", concentration: "EDP", image: "/images/product.png",
  notes: { top: ["Bergamot"], heart: [], base: [] }, in_stock: true, price_from: 90,
  variants: [
    { id: "size-30", size_ml: 30, price: 90, stock: 3 },
    { id: "size-50", size_ml: 50, price: 130, stock: 0 },
    { id: "size-100", size_ml: 100, price: 180, stock: 5 },
  ],
};
const session = { user: { id: "guest-fixture", role: "guest", consent: false }, csrf: "fixture-csrf" };
async function fixture(page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let body = {};
    if (url.pathname === "/api/products") body = { products: [product], brands: ["Dior"] };
    if (url.pathname === "/api/products/test-perfume") body = product;
    if (url.pathname === "/api/auth/session") body = session;
    if (url.pathname === "/api/cart") body = { items: [], total: 0 };
    if (url.pathname === "/api/wishlist" || url.pathname === "/api/recommend/user") body = { products: [] };
    await route.fulfill({ json: body });
  });
}

test("homepage and catalogue stay visible while session and recommendations wait", async ({ page }) => {
  await fixture(page);
  let release;
  const hold = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/auth/session", async (route) => { await hold; await route.fulfill({ json: session }); });
  await page.route("**/api/recommend/user", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Less ordinary.*More you/ })).toBeVisible();
  await expect(page.locator(".product-card").first()).toContainText(product.name);
  await expect(page.getByText("Opening your scent collection…")).toHaveCount(0);
  release();
  await expect(page.locator(".product-card").first()).toContainText(product.name);
});

test("session failure keeps browsing available and reconnect recovers the bag", async ({ page }) => {
  await fixture(page);
  let attempts = 0;
  await page.route("**/api/auth/session", async (route) => {
    attempts += 1;
    await route.fulfill(attempts === 1 ? { status: 503, json: { detail: "Service waking up" } } : { json: session });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Less ordinary.*More you/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reconnect" })).toBeVisible();
  await page.getByRole("button", { name: "Reconnect" }).click();
  await expect(page.getByRole("button", { name: "Reconnect" })).toHaveCount(0);
  await page.getByRole("link", { name: "Shopping bag, 0 items" }).click();
  await expect(page.getByRole("heading", { name: "Your bag." })).toBeVisible();
});

test("quick add uses the chosen size and prevents duplicate submission on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fixture(page);
  const writes = [];
  let release;
  const hold = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/cart/add", async (route) => {
    if (route.request().method() === "POST") {
      writes.push(route.request().postDataJSON());
      expect(route.request().headers()["x-csrf-token"]).toBe("fixture-csrf");
      await hold;
    }
    await route.fulfill({ json: { items: [], total: 0 } });
  });
  await page.goto("/");
  const opener = page.getByRole("button", { name: "Quick add Test fragrance" }).first();
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Test fragrance" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("radio", { name: /50ml/ })).toBeDisabled();
  await dialog.getByRole("radio", { name: /100ml/ }).check();
  await expect(dialog.getByRole("radio", { name: /100ml/ })).toBeChecked();
  await dialog.getByRole("button", { name: "Add to bag", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Adding…" })).toBeDisabled();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes).toEqual([{ variant_id: "size-100", quantity: 1 }]);
  release();
  await expect(dialog).toContainText("Added 1 × 100ml");
  await expect(dialog).toContainText("100ml");
  await dialog.getByRole("button", { name: "Continue shopping" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await opener.click();
  await page.getByRole("button", { name: "Close quick add" }).press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("quick add waits for the session and increments the existing bag atomically", async ({ page }) => {
  await fixture(page);
  let release;
  const hold = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/auth/session", async (route) => { await hold; await route.fulfill({ json: session }); });
  const writes = [];
  await page.route("**/api/cart/add", async (route) => {
    if (route.request().method() === "POST") writes.push(route.request().postDataJSON());
    await route.fulfill({ json: { items: [{ variant_id: "size-30", quantity: 2 }], total: 180 } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Quick add Test fragrance" }).first().click();
  await page.getByRole("dialog").getByRole("radio", { name: /30ml/ }).check();
  await page.getByRole("dialog").getByRole("button", { name: "Add to bag", exact: true }).click();
  expect(writes).toEqual([]);
  release();
  await expect(page.getByRole("dialog")).toContainText("Added 1 × 30ml");
  expect(writes).toEqual([{ variant_id: "size-30", quantity: 1 }]);
});
