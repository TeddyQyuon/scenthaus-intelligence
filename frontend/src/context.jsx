import { createContext, useContext, useEffect, useState } from "react";
import { api, setCsrf, message } from "./api";
const Context = createContext(null);
export function ShopProvider({ children }) {
  const [user, setUser] = useState(null),
    [cart, setCart] = useState({ items: [], total: 0 }),
    [wishlist, setWishlist] = useState([]),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [consentBusy, setConsentBusy] = useState(false);
  async function refresh() {
    const [c, w] = await Promise.all([api.get("/cart"), api.get("/wishlist")]);
    setCart(c.data);
    setWishlist(w.data.products);
  }
  async function accept(data) {
    setUser(data.user);
    setCsrf(data.csrf);
    await refresh();
  }
  async function init() {
    setError("");
    try {
      await accept((await api.get("/auth/session")).data);
    } catch (e) {
      setError(message(e));
    }
  }
  useEffect(() => {
    init();
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(timer);
  }, [toast]);
  async function add(v, quantity = 1) {
    await api.put("/cart", {
      variant_id: v.id,
      quantity: Math.min(
        10,
        (cart.items.find((i) => i.variant_id === v.id)?.quantity || 0) +
          quantity,
      ),
    });
    await refresh();
    setToast("Added to your bag");
  }
  async function wish(p) {
    if (wishlist.some((w) => w.id === p.id))
      await api.delete(`/wishlist/${p.id}`);
    else await api.put(`/wishlist/${p.id}`);
    await refresh();
  }
  async function consent(value) {
    if (consentBusy) return;
    const previous = user.consent;
    setConsentBusy(true);
    setUser((u) => ({ ...u, consent: value }));
    try {
      await api.put("/privacy/consent", { consent: value });
      setToast(value ? "Personalization enabled" : "Personalization is off");
    } catch (e) {
      setUser((u) => ({ ...u, consent: previous }));
      throw e;
    } finally {
      setConsentBusy(false);
    }
  }
  function track(product_id, event_type = "view", recommendation_id) {
    if (user?.consent)
      api
        .post("/events", { product_id, event_type, recommendation_id })
        .catch(() => {});
  }
  return (
    <Context.Provider
      value={{
        user,
        cart,
        wishlist,
        refresh,
        accept,
        add,
        wish,
        consent,
        consentBusy,
        track,
        notify: setToast,
      }}
    >
      {error ? (
        <div className="full-state">
          <h1>Let’s reconnect.</h1>
          <p>The storefront needs its Python service to continue.</p>
          <p>{error}</p>
          <button onClick={init}>Try again</button>
        </div>
      ) : !user ? (
        <div className="full-state">
          <p className="wordmark">SCENTHAUS</p>
          <p>Opening your scent collection…</p>
        </div>
      ) : (
        children
      )}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </Context.Provider>
  );
}
export const useShop = () => useContext(Context);
