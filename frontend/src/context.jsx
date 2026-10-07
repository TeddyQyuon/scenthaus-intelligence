import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, setCsrf, message } from "./api";
const Context = createContext(null);
export function ShopProvider({ children }) {
  const [user, setUser] = useState({ role: "guest", consent: false }),
    [cart, setCart] = useState({ items: [], total: 0 }),
    [wishlist, setWishlist] = useState([]),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [consentBusy, setConsentBusy] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const connection = useRef(null);
  const mutations = useRef(new Set());
  const cartRef = useRef(cart);
  const wishlistRef = useRef(wishlist);
  async function refresh() {
    const [c, w] = await Promise.all([api.get("/cart"), api.get("/wishlist")]);
    cartRef.current = c.data;
    wishlistRef.current = w.data.products;
    setCart(c.data);
    setWishlist(w.data.products);
  }
  async function accept(data) {
    setUser(data.user);
    setCsrf(data.csrf);
    await refresh();
    setSessionReady(true);
  }
  function init() {
    if (connection.current) return connection.current;
    setError("");
    connection.current = api.get("/auth/session")
      .then((r) => accept(r.data))
      .catch((e) => { setError(message(e)); throw e; })
      .finally(() => { connection.current = null; });
    return connection.current;
  }
  async function ensureSession() {
    if (!sessionReady) await init();
  }
  useEffect(() => {
    init().catch(() => {});
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(timer);
  }, [toast]);
  async function add(v, quantity = 1) {
    if (mutations.current.has(v.id)) return;
    mutations.current.add(v.id);
    try {
      await ensureSession();
      await api.put("/cart", {
        variant_id: v.id,
        quantity: Math.min(
          10,
          (cartRef.current.items.find((i) => i.variant_id === v.id)?.quantity || 0) +
            quantity,
        ),
      });
      await refresh();
      setToast(`${v.size_ml} ml added to your bag`);
    } finally { mutations.current.delete(v.id); }
  }
  async function wish(p) {
    await ensureSession();
    if (wishlistRef.current.some((w) => w.id === p.id))
      await api.delete(`/wishlist/${p.id}`);
    else await api.put(`/wishlist/${p.id}`);
    await refresh();
  }
  async function consent(value) {
    if (consentBusy) return;
    await ensureSession();
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
        sessionReady,
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
      {children}
      {error && (
        <div className="connection-notice" role="status">
          <span>Your bag and account could not connect. You can still browse.</span>
          <button onClick={() => init().catch(() => {})}>Reconnect</button>
        </div>
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

export function SessionBoundary({ children }) {
  const { sessionReady } = useShop();
  return sessionReady ? children : (
    <section className="section" role="status">
      <h1>Connecting your scent space.</h1>
      <p>Your bag, wishlist and account will be ready shortly.</p>
    </section>
  );
}
