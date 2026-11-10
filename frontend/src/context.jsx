import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
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

  const refresh = useCallback(async () => {
    const [c, w] = await Promise.all([api.get("/cart"), api.get("/wishlist")]);
    cartRef.current = c.data;
    wishlistRef.current = w.data.products;
    setCart(c.data);
    setWishlist(w.data.products);
  }, []);

  const accept = useCallback(async (data) => {
    setUser(data.user);
    setCsrf(data.csrf);
    await refresh();
    setSessionReady(true);
  }, [refresh]);

  const init = useCallback(() => {
    if (connection.current) return connection.current;
    setError("");
    connection.current = api
      .get("/auth/session")
      .then((r) => accept(r.data))
      .catch((e) => {
        setError(message(e));
        throw e;
      })
      .finally(() => {
        connection.current = null;
      });
    return connection.current;
  }, [accept]);

  const ensureSession = useCallback(async () => {
    if (!sessionReady) await init();
  }, [sessionReady, init]);

  useEffect(() => {
    init().catch(() => {});
  }, [init]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(timer);
  }, [toast]);

  const add = useCallback(async (v, quantity = 1) => {
    if (mutations.current.has(v.id)) return;
    mutations.current.add(v.id);
    try {
      await ensureSession();
      const response = await api.post("/cart/add", {
        variant_id: v.id,
        quantity,
      });
      cartRef.current = response.data;
      setCart(response.data);
      setToast(`${v.size_ml} ml added to your bag`);
    } finally {
      mutations.current.delete(v.id);
    }
  }, [ensureSession]);

  const wish = useCallback(async (p) => {
    await ensureSession();
    if (wishlistRef.current.some((w) => w.id === p.id))
      await api.delete(`/wishlist/${p.id}`);
    else await api.put(`/wishlist/${p.id}`);
    await refresh();
  }, [ensureSession, refresh]);

  const consent = useCallback(async (value) => {
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
  }, [consentBusy, ensureSession, user.consent]);

  const track = useCallback((product_id, event_type = "view", recommendation_id) => {
    if (user?.consent)
      api
        .post("/events", { product_id, event_type, recommendation_id })
        .catch(() => {});
  }, [user?.consent]);

  const wishlistIds = useMemo(() => new Set(wishlist.map((w) => w.id)), [wishlist]);

  const value = useMemo(
    () => ({
      user,
      sessionReady,
      cart,
      wishlist,
      wishlistIds,
      refresh,
      accept,
      ensureSession,
      add,
      wish,
      consent,
      consentBusy,
      track,
      notify: setToast,
    }),
    [user, sessionReady, cart, wishlist, wishlistIds, refresh, accept, ensureSession, add, wish, consent, consentBusy, track],
  );

  return (
    <Context.Provider value={value}>
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
  return sessionReady ? (
    children
  ) : (
    <section className="section session-boundary" role="status">
      <h1>Connecting your scent space.</h1>
      <p>Your bag, wishlist and account will be ready shortly.</p>
    </section>
  );
}
