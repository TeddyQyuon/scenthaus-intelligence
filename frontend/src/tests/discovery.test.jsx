import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "../App";
import { api } from "../api";
import { clearCatalogue } from "../catalogue";
import { productImageSources } from "../ProductImage";
vi.mock("../api", () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() }, setCsrf: vi.fn(), message: () => "Connection failed", money: (n) => `$${n}`, download: vi.fn() }));
const products = Array.from({ length: 60 }, (_, index) => ({
  id: index + 1, slug: `scent-${index}`, name: `Scent ${index}`, brand: index % 2 ? "Chanel" : "Dior",
  image: "/images/product.png", category: index % 2 ? "Floral" : "Woody", concentration: "EDP",
  notes: { top: ["rose"], heart: [], base: [] }, in_stock: true, price_from: 90 + index,
  variants: [{ id: `v${index}`, size_ml: 50, price: 90 + index, stock: 3 }],
  accords: [], seasons: [], occasions: [],
}));
beforeEach(() => {
  vi.clearAllMocks(); clearCatalogue(); window.history.replaceState({}, "", "/");
  window.scrollTo = vi.fn();
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); };
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  api.get.mockImplementation(async (path) => ({ data: path === "/auth/session" ? { user: { role: "guest", consent: false }, csrf: "test" }
    : path === "/cart" ? { items: [], total: 0 } : path === "/products" ? { products, brands: ["Dior", "Chanel"] }
    : path.startsWith("/products/scent-") ? products.find((p) => path.endsWith(p.slug)) : { products: [] } }));
});
afterEach(cleanup);

describe("fragrance discovery", () => {
  it("opens search, focuses the input, finds a fragrance and opens its product", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Search scents" }));
    const dialog = await screen.findByRole("dialog");
    const input = within(dialog).getByRole("searchbox");
    expect(document.activeElement).toBe(input);
    fireEvent.change(input, { target: { value: "Scent 23" } });
    const result = await within(dialog).findByRole("link", { name: /Scent 23/ });
    fireEvent.click(result);
    await screen.findByRole("heading", { name: "Scent 23" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("returns focus to search when the dialog closes", async () => {
    render(<App />);
    const opener = screen.getByRole("button", { name: "Search scents" });
    opener.focus(); fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Close search" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(opener);
  });
  it("applies search and scent-family deep links immediately", async () => {
    window.history.replaceState({}, "", "/shop?category=Woody&q=Scent%202");
    render(<App />);
    await screen.findByText("Showing 6 of 6 scents");
    expect(screen.getByRole("textbox", { name: "Search the collection" }).value).toBe("Scent 2");
    expect(screen.getByRole("button", { name: "Woody", exact: true }).getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelectorAll(".product-card")).toHaveLength(6);
  });
  it("starts with 24 cards, loads more and resets the limit after filtering", async () => {
    window.history.replaceState({}, "", "/shop"); render(<App />);
    await screen.findByText("Showing 24 of 60 scents");
    expect(document.querySelectorAll(".product-card")).toHaveLength(24);
    fireEvent.click(screen.getByRole("button", { name: "Discover more scents" }));
    expect(document.querySelectorAll(".product-card")).toHaveLength(48);
    fireEvent.click(screen.getByRole("button", { name: "Woody", exact: true }));
    await screen.findByText("Showing 24 of 30 scents");
    expect(window.location.search).toBe("?category=Woody");
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    await screen.findByText("Showing 24 of 60 scents");
  });
  it("submits search to the filtered collection without a document reload", async () => {
    render(<App />); fireEvent.click(screen.getByRole("button", { name: "Search scents" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "Scent 59" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "View all search results" }));
    await screen.findByText("Showing 1 of 1 scents");
    expect(window.location.search).toBe("?q=Scent%2059");
  });
  it("keeps a natural-language example selected when URL filters synchronize", async () => {
    window.history.replaceState({}, "", "/shop"); render(<App />);
    await screen.findByText("Showing 24 of 60 scents");
    fireEvent.click(screen.getByRole("checkbox", { name: "Describe your scent in natural language" }));
    fireEvent.click(screen.getByRole("button", { name: "Fresh office scent under $150" }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Search the collection" }).value).toBe("Fresh office scent under $150"));
    expect(new URLSearchParams(window.location.search).get("q")).toBe("Fresh office scent under $150");
  });
  it("uses responsive local images and leaves remote image URLs intact", () => {
    expect(productImageSources("/images/products/001-demo.png")).toEqual({ src: "/images/products/001-demo-640.webp", srcSet: "/images/products/001-demo-320.webp 320w, /images/products/001-demo-640.webp 640w" });
    expect(productImageSources("https://example.com/perfume.jpg")).toEqual({ src: "https://example.com/perfume.jpg" });
  });
});
