import { api } from "./api";
import { FEATURED_PRODUCTS } from "./featured";

// Public browsing data only. Quick Add and checkout revalidate with the API.
const TTL = 60_000;
const STORAGE_KEY = "scenthaus_catalogue_swr";

function readStorage() {
  try {
    if (typeof window === "undefined" || !window.sessionStorage) return undefined;
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    if (parsed?.data?.products?.length && Date.now() - parsed.time < 3600_000) {
      return parsed.data;
    }
  } catch {}
  return undefined;
}

function writeStorage(data) {
  try {
    if (typeof window !== "undefined" && window.sessionStorage) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ time: Date.now(), data }));
    }
  } catch {}
}

let cached = readStorage();
let expires = cached ? Date.now() + TTL : 0;
let pending;

export function clearCatalogue() {
  cached = undefined;
  expires = 0;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {}
}

export function peekCatalogue() {
  return cached;
}

export function getFeaturedProducts() {
  if (cached?.products?.length) {
    const edit = ["Dior", "Yves Saint Laurent", "Tom Ford", "Creed"]
      .map((brand) => cached.products.find((p) => p.brand === brand))
      .filter(Boolean);
    if (edit.length >= 4) return edit;
    if (cached.products.length >= 4) return cached.products.slice(0, 4);
  }
  return FEATURED_PRODUCTS;
}

export function loadCatalogue(force = false) {
  if (!force && cached) {
    // If cache is nearing expiry, trigger quiet background revalidation without blocking
    if (Date.now() > expires && !pending) {
      pending = api
        .get("/products")
        .then(({ data }) => {
          cached = data;
          expires = Date.now() + TTL;
          writeStorage(data);
          return data;
        })
        .catch(() => cached)
        .finally(() => {
          pending = undefined;
        });
    }
    return Promise.resolve(cached);
  }

  if (!pending) {
    pending = api
      .get("/products")
      .then(({ data }) => {
        cached = data;
        expires = Date.now() + TTL;
        writeStorage(data);
        return data;
      })
      .finally(() => {
        pending = undefined;
      });
  }
  return pending;
}

export function filterCatalogue(data, filters) {
  if (!data?.products) return { products: [], brands: [] };
  const query = filters.q ? filters.q.trim().toLowerCase() : "";
  const products = data.products.filter((p) => {
    if (filters.brand && p.brand !== filters.brand) return false;
    if (filters.category && p.category !== filters.category) return false;
    if (filters.gender && p.gender !== filters.gender) return false;
    if (filters.season && !p.seasons?.includes(filters.season)) return false;
    if (
      query &&
      ![
        p.name,
        p.brand,
        p.category,
        ...(p.accords || []),
        ...Object.values(p.notes || {}).flat(),
      ]
        .join(" ")
        .toLowerCase()
        .includes(query)
    )
      return false;
    return p.variants.some(
      (v) =>
        (!filters.budget || v.price <= Number(filters.budget)) &&
        (!filters.size || v.size_ml === Number(filters.size)) &&
        (!filters.in_stock || v.stock > 0),
    );
  });
  products.sort(
    filters.sort === "price-low"
      ? (a, b) => a.price_from - b.price_from
      : filters.sort === "price-high"
      ? (a, b) => b.price_from - a.price_from
      : (a, b) => Number(!!b.pinned) - Number(!!a.pinned) || a.id - b.id,
  );
  return { ...data, products };
}
