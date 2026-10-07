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
  cart = { items: [], total: 0 };
  api.get.mockImplementation(async (path) => ({ data: path === "/auth/session" ? session : path === "/cart" ? cart : path === "/products" ? { products: [product] } : { products: [] } }));
  api.put.mockResolvedValue({ data: {} });
  window.scrollTo = vi.fn();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
});
afterEach(cleanup);
function Ready() { const { sessionReady } = useShop(); return <span>{sessionReady ? "Ready" : "Connecting"}</span>; }
function quick() { render(<MemoryRouter><ShopProvider><Ready /><QuickAdd product={product} onClose={vi.fn()} /></ShopProvider></MemoryRouter>); }

describe("nonblocking storefront and safe quick add", () => {
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
    api.put.mockReturnValue(held.promise);
    quick();
    await screen.findByText("Ready");
    expect(screen.getByRole("button", { name: /50 ml/ }).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /100 ml/ }));
    const add = screen.getByRole("button", { name: "Add to bag" });
    fireEvent.click(add);
    fireEvent.click(add);
    await waitFor(() => expect(api.put).toHaveBeenCalledTimes(1));
    expect(api.put).toHaveBeenCalledWith("/cart", { variant_id: "v100", quantity: 1 });
    expect(screen.getByRole("button", { name: "Adding to bag…" }).disabled).toBe(true);
    await act(async () => { held.resolve({ data: {} }); });
    expect(screen.getByRole("heading", { name: "In your bag." })).toBeTruthy();
    expect(screen.getByText("100 ml · $180")).toBeTruthy();
  });
  it("waits for the session and preserves the existing quantity", async () => {
    const held = deferred();
    const original = api.get.getMockImplementation();
    cart = { items: [{ variant_id: "v30", quantity: 2 }], total: 180 };
    api.get.mockImplementation((path) => path === "/auth/session" ? held.promise : original(path));
    quick();
    fireEvent.click(screen.getByRole("button", { name: "Add to bag" }));
    expect(api.put).not.toHaveBeenCalled();
    await act(async () => { held.resolve({ data: session }); });
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/cart", { variant_id: "v30", quantity: 3 }));
  });
  it("keeps size selection open after a rejected add and allows retry", async () => {
    api.put.mockRejectedValueOnce(new Error("stock changed"));
    quick();
    await screen.findByText("Ready");
    fireEvent.click(screen.getByRole("button", { name: "Add to bag" }));
    await screen.findByRole("alert");
    expect(screen.queryByRole("heading", { name: "In your bag." })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Add to bag" }));
    await screen.findByRole("heading", { name: "In your bag." });
    expect(api.put).toHaveBeenCalledTimes(2);
  });
});
