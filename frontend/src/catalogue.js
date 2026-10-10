import { api } from "./api";

// Public browsing data only. Quick Add and checkout revalidate with the API.
const TTL = 30_000;
let cached;
let expires = 0;
let pending;
export function clearCatalogue() {
  cached = undefined;
  expires = 0;
}
export function peekCatalogue() {
  return Date.now() < expires ? cached : undefined;
}
export function loadCatalogue() {
  const current = peekCatalogue();
  if (current) return Promise.resolve(current);
  if (!pending) {
    pending = api.get("/products").then(({ data }) => {
      cached = data;
      expires = Date.now() + TTL;
      return data;
    }).finally(() => { pending = undefined; });
  }
  return pending;
}

export function filterCatalogue(data, filters) {
  const query = filters.q.trim().toLowerCase();
  const products = data.products.filter((p) => {
    if (filters.brand && p.brand !== filters.brand ||
        filters.category && p.category !== filters.category ||
        filters.gender && p.gender !== filters.gender ||
        filters.season && !p.seasons?.includes(filters.season)) return false;
    if (query && ![p.name, p.brand, p.category, ...(p.accords || []),
      ...Object.values(p.notes || {}).flat()].join(" ").toLowerCase().includes(query)) return false;
    return p.variants.some((v) =>
      (!filters.budget || v.price <= Number(filters.budget)) &&
      (!filters.size || v.size_ml === Number(filters.size)) &&
      (!filters.in_stock || v.stock > 0));
  });
  products.sort(filters.sort === "price-low" ? (a, b) => a.price_from - b.price_from :
    filters.sort === "price-high" ? (a, b) => b.price_from - a.price_from :
    (a, b) => Number(!!b.pinned) - Number(!!a.pinned) || a.id - b.id);
  return { ...data, products };
}
