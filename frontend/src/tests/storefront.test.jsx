import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ShopProvider, useShop } from "../context";
import QuickAdd from "../QuickAdd";
import App from "../App";
import { api } from "../api";
vi.mock("../api", () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() }, setCsrf: vi.fn(), message: () => "Connection failed", money: (n) => `$${n}`, download: vi.fn() }));
const session = { user: { role: "guest", consent: false }, csrf: "token" };
const product = { id: "scent", slug: "scent", name: "Test scent", brand: "Dior", image: "/images/product.png", category: "Fresh", concentration: "EDP", notes: { top: [], heart: [], base: [] }, in_stock: true, price_from: 90, variants: [{ id: "v30", size_ml: 30, price: 90, stock: 3 }, { id: "v50", size_ml: 50, price: 130, stock: 0 }, { id: "v100", size_ml: 100, price: 180, stock: 4 }] };
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r; }); return { promise, resolve }; };
let cart;
beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/");
  cart = { items: [], total: 0 };
  api.get.mockImplementation(async (path) => ({ data: path === "/auth/session" ? session : path === "/cart" ? cart : path === "/products/scent" ? product : path === "/products" ? { products: [product] } : { products: [] } }));
  api.post.mockReset();
  api.post.mockResolvedValue({ data: cart });
  window.scrollTo = vi.fn();
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); };
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
});
afterEach(cleanup);
function Ready() { const { sessionReady } = useShop(); return <span>{sessionReady ? "Ready" : "Connecting"}</span>; }
function quick() { render(<MemoryRouter><ShopProvider><Ready /><QuickAdd product={product} onClose={vi.fn()} /></ShopProvider></MemoryRouter>); }

describe("nonblocking storefront and safe quick add", () => {
  it("records a consented product view when the session arrives after the product", async () => {
    const held = deferred();
    const original = api.get.getMockImplementation();
    api.get.mockImplementation((path) => path === "/auth/session" ? held.promise : path === "/products/scent" ? Promise.resolve({ data: { ...product, accords: [], seasons: [], occasions: [], source: null } }) : original(path));
    window.history.replaceState({}, "", "/product/scent");
    render(<App />);
    await screen.findByRole("heading", { name: "Test scent" });
    expect(api.post).not.toHaveBeenCalledWith("/events", expect.anything());
    await act(async () => { held.resolve({ data: { ...session, user: { ...session.user, consent: true } } }); });
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/events", { product_id: "scent", event_type: "view", recommendation_id: undefined }));
    expect(api.post.mock.calls.filter(([path]) => path === "/events")).toHaveLength(1);
  });
  it("renders home and products while the session has not responded", async () => {
    const held = deferred();
    const original = api.get.getMockImplementation();
    api.get.mockImplementation((path) => path === "/auth/session" ? held.promise : original(path));
    render(<App />);
    expect(screen.getByRole("heading", { name: /Less ordinary.*More you/ })).toBeTruthy();
    await waitFor(() => expect(screen.getAllByText("Test scent").length).toBeGreaterThan(0));
    expect(api.get).not.toHaveBeenCalledWith("/recommend/user");
    expect(screen.queryByText("Opening your scent collection…")).toBeNull();
    await act(async () => { held.resolve({ data: session }); });
  });
  it("shows catalogue even when optional recommendations fail", async () => {
    const original = api.get.getMockImplementation();
    api.get.mockImplementation((path) => path === "/recommend/user" ? Promise.reject(new Error("offline")) : original(path));
    render(<App />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/recommend/user"));
    expect(screen.getAllByText("Test scent").length).toBeGreaterThan(0);
    expect(screen.queryByRole("alert")).toBeNull();
  });
  it("keeps browsing usable when session fails and reconnects", async () => {
    const original = api.get.getMockImplementation();
    let fail = true;
    api.get.mockImplementation((path) => path === "/auth/session" && fail ? Promise.reject(new Error("offline")) : original(path));
    render(<App />);
    await screen.findByRole("button", { name: "Reconnect" });
    expect(screen.getByRole("heading", { name: /Less ordinary.*More you/ })).toBeTruthy();
    expect(screen.getAllByText("Test scent").length).toBeGreaterThan(0);
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Reconnect" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Reconnect" })).toBeNull());
  });
  it("submits the selected size once, disables unavailable sizes, and confirms the size", async () => {
    const held = deferred();
    api.post.mockReturnValue(held.promise);
    quick();
    await screen.findByText("Ready");
    await waitFor(() => expect(screen.getByRole("radio", { name: /30ml/ }).disabled).toBe(false));
    expect(screen.getByRole("radio", { name: /50ml/ }).disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: /100ml/ }));
    const add = screen.getByRole("button", { name: "Add to bag" });
    fireEvent.click(add);
    fireEvent.click(add);
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith("/cart/add", { variant_id: "v100", quantity: 1 });
    expect(screen.getByRole("button", { name: "Adding…" }).disabled).toBe(true);
    await act(async () => { held.resolve({ data: cart }); });
    expect(screen.getByText(/Added 1 × 100ml/)).toBeTruthy();
    expect(screen.getByText(/Added 1 × 100ml/)).toBeTruthy();
  });
  it("waits for the session and preserves the existing quantity", async () => {
    const held = deferred();
    const original = api.get.getMockImplementation();
    cart = { items: [{ variant_id: "v30", quantity: 2 }], total: 180 };
    api.get.mockImplementation((path) => path === "/auth/session" ? held.promise : original(path));
    quick();
    await waitFor(() => expect(screen.getByRole("radio", { name: /30ml/ }).disabled).toBe(false));
    fireEvent.click(screen.getByRole("radio", { name: /30ml/ }));
    fireEvent.click(screen.getByRole("button", { name: "Add to bag" }));
    expect(api.post).not.toHaveBeenCalled();
    await act(async () => { held.resolve({ data: session }); });
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/cart/add", { variant_id: "v30", quantity: 1 }));
  });
  it("keeps size selection open after a rejected add and allows retry", async () => {
    api.post.mockRejectedValueOnce(new Error("stock changed"));
    quick();
    await screen.findByText("Ready");
    await waitFor(() => expect(screen.getByRole("radio", { name: /30ml/ }).disabled).toBe(false));
    fireEvent.click(screen.getByRole("radio", { name: /30ml/ }));
    fireEvent.click(screen.getByRole("button", { name: "Add to bag" }));
    await screen.findByRole("alert");
    expect(screen.queryByText(/Added 1 ×/)).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: /30ml/ }));
    fireEvent.click(screen.getByRole("button", { name: "Add to bag" }));
    await screen.findByText(/Added 1 × 30ml/);
    expect(api.post).toHaveBeenCalledTimes(2);
  });
});
