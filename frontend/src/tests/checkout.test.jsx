import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CheckoutPage, CheckoutSuccess, CheckoutCancelled } from "../Checkout";
import { api } from "../api";
const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("../api", () => ({ api: { get: vi.fn(), post: vi.fn() }, message: (e) => e.response?.data?.detail || "Please try again." }));
vi.mock("../context", () => ({ useShop: () => ({ user: { email: "" }, refresh }) }));
const quote = { items: [{ product_id: 1, variant_id: 2, size_ml: 50, quantity: 2, brand: "Dior", name: "Test scent", unit_price_minor: 12990, item_total_minor: 25980 }], subtotal_minor: 25980, shipping_minor: 0, tax_minor: 0, discount_minor: 0, total_minor: 25980, currency: "SGD", quote_token: "a".repeat(64), payment_mode: "test", payments_available: true };
const pending = { ...quote, id: "order-one", order_number: "SCENT-2026-000001", payment_status: "pending", status: "pending", customer_name: "Test Customer", customer_email: "test@example.com", delivery_address: { line1: "1 Test Street", city: "Singapore", postal_code: "123456" } };
function show(Component, path = "/checkout") { return render(<MemoryRouter initialEntries={[path]}><Component /></MemoryRouter>); }
beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); refresh.mockResolvedValue(); api.get.mockResolvedValue({ data: quote }); });
afterEach(cleanup);

it("shows server totals, size, unit price and Singapore delivery defaults", async () => {
  show(CheckoutPage);
  await screen.findByRole("button", { name: /Pay now.*S\$259.80/ });
  expect(screen.getByText("50ml · Quantity 2")).toBeTruthy();
  expect(screen.getByText("S$129.90 each")).toBeTruthy();
  expect(screen.getByLabelText("City").value).toBe("Singapore");
  expect(screen.getByText(/Stripe test mode/)).toBeTruthy();
});

it("guards rapid Pay now submissions and sends identities without client prices", async () => {
  let reject;
  api.post.mockImplementation(() => new Promise((_, r) => { reject = r; }));
  show(CheckoutPage);
  const button = await screen.findByRole("button", { name: /Pay now/ });
  fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "test@example.com" } });
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Test Customer" } });
  fireEvent.change(screen.getByLabelText("Address line 1"), { target: { value: "1 Test Street" } });
  fireEvent.change(screen.getByLabelText("Postal code"), { target: { value: "123456" } });
  fireEvent.submit(button.closest("form")); fireEvent.submit(button.closest("form"));
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(button.disabled).toBe(true);
  const sent = api.post.mock.calls[0][1];
  expect(sent.items).toEqual([{ product_id: 1, variant_id: 2, size_ml: 50, quantity: 2 }]);
  expect(sent).not.toHaveProperty("total");
  const requestKey = sent.idempotency_key;
  await act(async () => reject(new Error("Network Error")));
  expect(screen.getByRole("alert").textContent).toContain("Your bag is saved");
  fireEvent.submit(button.closest("form"));
  expect(api.post.mock.calls[1][1].idempotency_key).toBe(requestKey);
  await act(async () => reject(new Error("Network Error")));
});

it("blocks payments when backend keys or webhook are unconfigured", async () => {
  api.get.mockResolvedValue({ data: { ...quote, payments_available: false } });
  show(CheckoutPage);
  expect((await screen.findByRole("button", { name: /Pay now/ })).disabled).toBe(true);
  expect(screen.getByRole("alert").textContent).toContain("temporarily unavailable");
  expect(api.post).not.toHaveBeenCalled();
});

it("direct success navigation does not claim payment or clear the bag", async () => {
  api.get.mockResolvedValue({ data: pending });
  show(CheckoutSuccess, "/checkout/success?order_id=order-one");
  await screen.findByText(/haven’t received a completed payment/);
  expect(refresh).not.toHaveBeenCalled();
  expect(api.post).not.toHaveBeenCalled();
  expect(screen.queryByText("Thank you for your order.")).toBeNull();
});

it("refreshing confirmed success only reads the existing order", async () => {
  api.get.mockResolvedValue({ data: { ...pending, payment_status: "paid", status: "confirmed" } });
  const first = show(CheckoutSuccess, "/checkout/success?order_id=order-one");
  await screen.findByRole("heading", { name: "Thank you for your order." });
  await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  first.unmount();
  show(CheckoutSuccess, "/checkout/success?order_id=order-one");
  await screen.findByRole("heading", { name: "Thank you for your order." });
  expect(api.post).not.toHaveBeenCalled();
  expect(screen.getByText(/will not be dispatched/)).toBeTruthy();
});

it("cancel page waits for explicit cancellation and preserves the bag", async () => {
  api.get.mockResolvedValue({ data: pending });
  api.post.mockResolvedValue({ data: { ...pending, status: "cancelled", payment_status: "failed" } });
  show(CheckoutCancelled, "/checkout/cancelled?order_id=order-one");
  const button = await screen.findByRole("button", { name: "Cancel payment and keep my bag" });
  expect(api.post).not.toHaveBeenCalled();
  fireEvent.click(button);
  await screen.findByText(/No completed payment is recorded/);
  expect(api.post).toHaveBeenCalledWith("/checkout/order-one/cancel");
  expect(refresh).not.toHaveBeenCalled();
});

it("refund confirmation does not say that payment never completed", async () => {
  api.get.mockResolvedValue({ data: { ...pending, payment_status: "refunded", status: "cancelled", refunded_minor: 25980 } });
  show(CheckoutSuccess, "/checkout/success?order_id=order-one");
  await screen.findByRole("heading", { name: "Your refund is recorded." });
  expect(screen.queryByText(/No completed payment is recorded/)).toBeNull();
});
