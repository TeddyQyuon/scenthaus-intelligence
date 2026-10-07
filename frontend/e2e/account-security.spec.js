import { test, expect } from "@playwright/test";
import { createHmac, randomUUID } from "node:crypto";

// Independent RFC 6238 generator checks the authenticator setup end to end.
function authenticatorCode(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const character of secret)
    bits += alphabet.indexOf(character).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((part) => parseInt(part, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = createHmac("sha1", key).update(counter).digest();
  const offset = digest[digest.length - 1] & 15;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1000000).padStart(
    6,
    "0",
  );
}

test("mobile quick add chooses the exact size and quantity and keeps browsing position", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const response = await page.request.get("/api/products?in_stock=false");
  const { products } = await response.json();
  const product = products.find(
    (p) => p.variants.length > 1 && p.variants.some((v) => v.stock >= 3),
  );
  const variant = product.variants.find((v) => v.stock >= 3);
  await page.goto(`/shop?brand=${encodeURIComponent(product.brand)}`);
  const trigger = page.getByRole("button", {
    name: `Quick add ${product.name}`,
    exact: true,
  });
  await trigger.scrollIntoViewIfNeeded();
  const position = await page.evaluate(() => window.scrollY);
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: product.name });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Add to bag", exact: true }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("radio", { name: new RegExp(`^${variant.size_ml}ml`) }),
  ).toBeEnabled();
  await dialog
    .getByRole("radio", { name: new RegExp(`^${variant.size_ml}ml`) })
    .check();
  await dialog
    .getByRole("button", { name: "Increase quick-add quantity" })
    .click();
  await expect(
    dialog.getByLabel("Quick-add quantity", { exact: true }),
  ).toHaveText("2");
  await dialog.getByRole("button", { name: "Add to bag", exact: true }).click();
  await expect(dialog).toContainText(`Added 2 × ${variant.size_ml}ml`);
  await dialog.getByRole("button", { name: "Continue shopping" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  expect(await page.evaluate(() => window.scrollY)).toBe(position);
  await expect(
    page.getByRole("link", { name: "Shopping bag, 2 items" }),
  ).toBeVisible();
  await trigger.click();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page.goto("/cart");
  await expect(page.locator(".cart-item")).toHaveCount(1);
  await expect(page.locator(".cart-item")).toContainText(
    `${variant.size_ml}ml`,
  );
  const bag = await page.request.get("/api/cart").then((r) => r.json());
  expect(bag.items[0].variant_id).toBe(variant.id);
  expect(bag.items[0].quantity).toBe(2);
  await page.reload();
  await expect(page.locator(".cart-item")).toHaveCount(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("account setup, recovery sign-in, password change and device sessions work", async ({
  page,
}) => {
  const email = `browser-security-${randomUUID()}@example.test`;
  const password = "local-browser-test-password-1234";
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/account");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Security & sign-in." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Enable two-factor authentication" })
    .click();
  await page.getByLabel("Current password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Continue to authenticator setup" })
    .click();
  await expect(page.locator(".setup-key")).toBeVisible();
  const secret = await page.locator(".setup-key").innerText();
  await expect(page.locator(".authenticator-qr")).toBeVisible();
  await page
    .getByLabel("Six-digit authenticator code")
    .fill(authenticatorCode(secret));
  await page.getByRole("button", { name: "Verify & enable 2FA" }).click();
  await expect(page.locator(".recovery-codes code")).toHaveCount(10);
  const recovery = await page.locator(".recovery-codes code").allTextContents();
  await page.getByRole("button", { name: "I have saved my codes" }).click();
  await expect(page.locator(".recovery-codes code")).toHaveCount(0);
  await expect(page.getByText("10 recovery codes remaining.")).toBeVisible();
  await expect(page.locator(".session-item")).toHaveCount(1);
  await expect(page.locator(".session-item")).toContainText("This device");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "One more step." }),
  ).toBeVisible();
  await expect(page.locator(".account-security")).toHaveCount(0);
  await page.getByLabel("Verification code", { exact: true }).fill(recovery[0]);
  await page.getByRole("button", { name: "Verify & sign in" }).click();
  await expect(page.getByText("9 recovery codes remaining.")).toBeVisible();
  await page
    .getByRole("button", { name: "Change password", exact: true })
    .click();
  const form = page.locator(".security-form");
  await form.getByLabel("Current password", { exact: true }).fill(password);
  await form.getByLabel("Authenticator or recovery code").fill(recovery[1]);
  await form
    .getByLabel("New password", { exact: true })
    .fill(password + "-new");
  await form
    .getByLabel("Confirm new password", { exact: true })
    .fill(password + "-new");
  await form
    .getByRole("button", { name: "Change password", exact: true })
    .click();
  await expect(
    page.getByText("Password changed", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("8 recovery codes remaining.")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});
