import { test, expect } from "@playwright/test";

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`secure checkout layout and saved bag at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/cart");
    const session = await page.request.get("/api/auth/session").then((r) => r.json());
    const catalog = await page.request.get("/api/products").then((r) => r.json());
    const product = catalog.products.find((p) => p.variants.some((v) => v.stock >= 2));
    const variant = product.variants.find((v) => v.stock >= 2);
    const response = await page.request.put("/api/cart", {
      headers: { "X-CSRF-Token": session.csrf, Origin: new URL(page.url()).origin },
      data: { variant_id: variant.id, quantity: 2 },
    });
    expect(response.ok()).toBeTruthy();
    await page.goto("/checkout");
    await expect(page.getByRole("heading", { name: "A scent worth coming home to." })).toBeVisible();
    await expect(page.getByLabel("Email address", { exact: true })).toBeVisible();
    await page.getByLabel("Email address", { exact: true }).fill("test@example.com");
    await page.getByLabel("Full name", { exact: true }).fill("Test Customer");
    await page.getByLabel("Address line 1", { exact: true }).fill("1 Test Street");
    await page.getByLabel("Postal code", { exact: true }).fill("123456");
    await expect(page.getByLabel("City", { exact: true })).toHaveValue("Singapore");
    await expect(page.getByRole("complementary", { name: "Order summary" })).toContainText(`${variant.size_ml}ml · Quantity 2`);
    const form = await page.locator(".checkout-form").boundingBox();
    const summary = await page.locator(".checkout-summary").boundingBox();
    if (viewport.width > 760) expect(summary.x).toBeGreaterThan(form.x + form.width - 1);
    else expect(summary.y).toBeGreaterThan(form.y + form.height - 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.getByRole("button", { name: /Pay now/ })).toBeDisabled();
    await page.goto("/checkout/success?order_id=unpaid-or-nonexistent");
    await expect(page.getByRole("alert")).toContainText("Order not found");
    await expect(page.getByRole("heading", { name: "Thank you for your order." })).toHaveCount(0);
    const cart = await page.request.get("/api/cart").then((r) => r.json());
    expect(cart.items[0].quantity).toBe(2);
  });
}
