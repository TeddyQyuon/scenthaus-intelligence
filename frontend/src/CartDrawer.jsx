import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Gift,
  LockKeyhole,
  Minus,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Truck,
  X,
} from "lucide-react";
import { api, money, message } from "./api";
import { useShop } from "./context";
import { getFeaturedProducts, peekCatalogue } from "./catalogue";

const FREE_DELIVERY_THRESHOLD = 80;
const FREE_SAMPLE_THRESHOLD = 180;

const COMPLIMENTARY_VIALS = [
  { id: "aventus-2ml", label: "Creed Aventus · 2ml Sample Vial" },
  { id: "oud-wood-2ml", label: "Tom Ford Oud Wood · 2ml Sample Vial" },
  { id: "sauvage-2ml", label: "Dior Sauvage EDP · 2ml Sample Vial" },
  { id: "libre-2ml", label: "YSL Libre · 2ml Sample Vial" },
  { id: "curators-pick", label: "Curator’s Mystery Niche 2ml Vial" },
];

export default function CartDrawer() {
  const {
    cart,
    bagOpen,
    closeBag,
    refresh,
    add,
    notify,
    freeSampleChoice,
    setFreeSampleChoice,
    giftWrap,
    setGiftWrap,
  } = useShop();

  const [upsells, setUpsells] = useState([]);
  const [busyId, setBusyId] = useState(null);

  const bagQuantity = cart.items.reduce((sum, item) => sum + item.quantity, 0);
  const subtotal = cart.total || 0;

  const deliveryRemaining = Math.max(0, FREE_DELIVERY_THRESHOLD - subtotal);
  const sampleRemaining = Math.max(0, FREE_SAMPLE_THRESHOLD - subtotal);
  const progressPercent = Math.min(
    100,
    Math.round((subtotal / FREE_SAMPLE_THRESHOLD) * 100),
  );

  useEffect(() => {
    if (!bagOpen) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") closeBag();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [bagOpen, closeBag]);

  useEffect(() => {
    if (!bagOpen) return;
    let active = true;
    const inCartProductIds = new Set(cart.items.map((i) => i.product?.id));

    api
      .get("/recommend/cart")
      .then((r) => {
        if (!active) return;
        const recs = (r.data?.products || []).filter(
          (p) => !inCartProductIds.has(p.id) && p.variants?.some((v) => v.stock > 0),
        );
        if (recs.length >= 2) {
          setUpsells(recs.slice(0, 3));
        } else {
          const pool =
            peekCatalogue()?.products || getFeaturedProducts() || [];
          const fallback = pool.filter(
            (p) =>
              !inCartProductIds.has(p.id) &&
              p.variants?.some((v) => v.stock > 0),
          );
          setUpsells([...recs, ...fallback].slice(0, 3));
        }
      })
      .catch(() => {
        if (!active) return;
        const pool = peekCatalogue()?.products || getFeaturedProducts() || [];
        const fallback = pool.filter(
          (p) =>
            !inCartProductIds.has(p.id) && p.variants?.some((v) => v.stock > 0),
        );
        setUpsells(fallback.slice(0, 3));
      });

    return () => {
      active = false;
    };
  }, [bagOpen, cart.items.length]);

  if (!bagOpen) return null;

  async function updateQty(variantId, nextQty) {
    setBusyId(variantId);
    try {
      if (nextQty < 1) {
        await api.delete(`/cart/${variantId}`);
      } else {
        await api.put("/cart", { variant_id: variantId, quantity: nextQty });
      }
      await refresh();
    } catch (e) {
      notify(message(e));
    } finally {
      setBusyId(null);
    }
  }

  async function quickAddUpsell(product) {
    const smallestAvailable = [...(product.variants || [])]
      .filter((v) => v.stock > 0)
      .sort((a, b) => a.size_ml - b.size_ml)[0];
    if (!smallestAvailable) return;
    setBusyId(`upsell-${product.id}`);
    try {
      await add(smallestAvailable, 1);
    } catch (e) {
      notify(message(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div
      className="bag-drawer-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) closeBag();
      }}
    >
      <aside
        className="bag-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Your shopping bag"
      >
        <header className="bag-drawer-header">
          <div>
            <p className="eyebrow">SCENTHAUS ATELIER BAG</p>
            <h2>
              Your selection{" "}
              {bagQuantity > 0 && (
                <span className="bag-count-pill">{bagQuantity}</span>
              )}
            </h2>
          </div>
          <button
            type="button"
            className="icon bag-close-btn"
            aria-label="Close shopping bag"
            onClick={closeBag}
          >
            <X size={20} />
          </button>
        </header>

        {/* Tiered Reward Progress Bar */}
        <div className="bag-rewards-bar" role="status">
          <div className="bag-rewards-copy">
            {deliveryRemaining > 0 ? (
              <p>
                <Truck size={15} /> Add{" "}
                <strong>{money(deliveryRemaining)}</strong> more for{" "}
                <strong>Complimentary Tracked Delivery</strong>
              </p>
            ) : sampleRemaining > 0 ? (
              <p>
                <Sparkles size={15} />{" "}
                <strong>Complimentary Delivery unlocked!</strong> Add{" "}
                <strong>{money(sampleRemaining)}</strong> for a{" "}
                <strong>Free 2ml Niche Sample Vial</strong>
              </p>
            ) : (
              <p className="bag-rewards-unlocked">
                <Check size={15} />{" "}
                <strong>
                  Complimentary Courier Delivery + Free 2ml Niche Sample Vial
                  unlocked
                </strong>
              </p>
            )}
          </div>
          <div className="bag-progress-track" aria-hidden="true">
            <div
              className="bag-progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="bag-tier-markers">
            <span className={subtotal >= FREE_DELIVERY_THRESHOLD ? "reached" : ""}>
              {subtotal >= FREE_DELIVERY_THRESHOLD ? "✓ " : ""}S$80 Free Delivery
            </span>
            <span className={subtotal >= FREE_SAMPLE_THRESHOLD ? "reached" : ""}>
              {subtotal >= FREE_SAMPLE_THRESHOLD ? "✓ " : ""}S$180 + Free 2ml
              Vial
            </span>
          </div>
        </div>

        {cart.items.length === 0 ? (
          <div className="bag-drawer-empty">
            <div className="bag-empty-orb">
              <ShoppingBag size={30} strokeWidth={1.3} />
            </div>
            <h3>Your scent wardrobe awaits.</h3>
            <p>
              Explore 150 iconic designer & niche fragrances—available in full
              factory-sealed flacons or discovery sizes.
            </p>
            <div className="bag-empty-actions">
              <Link className="button wide" to="/shop" onClick={closeBag}>
                Explore the collection <ArrowRight size={16} />
              </Link>
              <Link className="button outline wide" to="/quiz" onClick={closeBag}>
                Take the 60-second Scent Quiz <Sparkles size={15} />
              </Link>
            </div>
          </div>
        ) : (
          <div className="bag-drawer-body">
            <div className="bag-items-list">
              {cart.items.map((item) => (
                <div className="bag-line-item" key={item.variant_id}>
                  <Link
                    to={`/product/${item.product.slug}`}
                    className="bag-line-thumb"
                    onClick={closeBag}
                  >
                    <img src={item.product.image} alt={item.product.name} />
                  </Link>
                  <div className="bag-line-details">
                    <div className="bag-line-top">
                      <div>
                        <p className="eyebrow">{item.product.brand}</p>
                        <Link
                          to={`/product/${item.product.slug}`}
                          onClick={closeBag}
                        >
                          <h4>{item.product.name}</h4>
                        </Link>
                      </div>
                      <strong className="bag-line-price">
                        {money(item.price * item.quantity)}
                      </strong>
                    </div>
                    <p className="metadata">
                      {item.size_ml <= 10
                        ? `${item.size_ml}ml Travel Atomizer`
                        : `${item.size_ml}ml Full Flacon`}{" "}
                      ·{" "}
                      {item.product.concentration === "Unverified"
                        ? "EDP"
                        : item.product.concentration}
                    </p>
                    <div className="bag-line-controls">
                      <div className="quantity">
                        <button
                          type="button"
                          className="icon"
                          disabled={busyId === item.variant_id}
                          aria-label={`Reduce ${item.product.name} quantity`}
                          onClick={() =>
                            updateQty(item.variant_id, item.quantity - 1)
                          }
                        >
                          <Minus size={13} />
                        </button>
                        <span>{item.quantity}</span>
                        <button
                          type="button"
                          className="icon"
                          disabled={
                            busyId === item.variant_id ||
                            item.quantity >= 10 ||
                            item.quantity >= item.stock
                          }
                          aria-label={`Increase ${item.product.name} quantity`}
                          onClick={() =>
                            updateQty(item.variant_id, item.quantity + 1)
                          }
                        >
                          <Plus size={13} />
                        </button>
                      </div>
                      <button
                        type="button"
                        className="why bag-remove-btn"
                        disabled={busyId === item.variant_id}
                        onClick={() => updateQty(item.variant_id, 0)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Complimentary 2ml Sample Selector when unlocked */}
            <div className="bag-perks-box">
              <div className="bag-perk-row">
                <Sparkles size={16} />
                <div>
                  <strong>
                    {subtotal >= FREE_SAMPLE_THRESHOLD
                      ? "Select your complimentary 2ml Niche Sample Vial"
                      : "Complimentary Scent Blotter Card included"}
                  </strong>
                  <p className="metadata">
                    {subtotal >= FREE_SAMPLE_THRESHOLD
                      ? "Hand-decanted 2ml glass atomizer (~30 sprays) added free to your parcel."
                      : `Every order ships with a spritzed archival blotter card. Unlock a free 2ml vial at S$${FREE_SAMPLE_THRESHOLD}.`}
                  </p>
                </div>
              </div>
              {subtotal >= FREE_SAMPLE_THRESHOLD && (
                <select
                  aria-label="Complimentary 2ml sample choice"
                  className="bag-sample-select"
                  value={freeSampleChoice}
                  onChange={(e) => setFreeSampleChoice(e.target.value)}
                >
                  {COMPLIMENTARY_VIALS.map((vial) => (
                    <option key={vial.id} value={vial.id}>
                      {vial.label} (Complimentary)
                    </option>
                  ))}
                </select>
              )}
              <label className="check-row bag-gift-toggle">
                <input
                  type="checkbox"
                  checked={giftWrap}
                  onChange={(e) => setGiftWrap(e.target.checked)}
                />
                <Gift size={14} /> Complimentary linen pouch & gift presentation
              </label>
            </div>

            {/* Discovery & Layering Upsells */}
            {upsells.length > 0 && (
              <div className="bag-upsells">
                <p className="eyebrow">COMPLETE YOUR SCENT WARDROBE</p>
                <div className="bag-upsell-list">
                  {upsells.map((u) => {
                    const v = [...(u.variants || [])]
                      .filter((x) => x.stock > 0)
                      .sort((a, b) => a.size_ml - b.size_ml)[0];
                    if (!v) return null;
                    return (
                      <div className="bag-upsell-card" key={u.id}>
                        <Link
                          to={`/product/${u.slug}`}
                          onClick={closeBag}
                          className="bag-upsell-img"
                        >
                          <img src={u.image} alt={u.name} />
                        </Link>
                        <div className="bag-upsell-info">
                          <span className="eyebrow">{u.brand}</span>
                          <Link to={`/product/${u.slug}`} onClick={closeBag}>
                            <strong>{u.name}</strong>
                          </Link>
                          <span className="metadata">
                            {v.size_ml}ml · {money(v.price)}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="outline bag-upsell-add"
                          disabled={busyId === `upsell-${u.id}`}
                          onClick={() => quickAddUpsell(u)}
                        >
                          <Plus size={13} />{" "}
                          {busyId === `upsell-${u.id}` ? "Adding…" : "Add"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {cart.items.length > 0 && (
          <footer className="bag-drawer-footer">
            <div className="bag-summary-rows">
              <div>
                <span>Subtotal</span>
                <strong>{money(subtotal)}</strong>
              </div>
              <div>
                <span>Singapore Courier Delivery</span>
                <span className="bag-complimentary">Complimentary</span>
              </div>
              {subtotal >= FREE_SAMPLE_THRESHOLD && (
                <div>
                  <span>2ml Discovery Sample Vial</span>
                  <span className="bag-complimentary">Included Free</span>
                </div>
              )}
            </div>
            <Link
              className="button wide bag-checkout-btn"
              to="/checkout"
              onClick={closeBag}
            >
              <LockKeyhole size={16} /> Proceed to Checkout · {money(subtotal)}{" "}
              <ArrowRight size={16} />
            </Link>
            <div className="bag-drawer-sublinks">
              <Link to="/cart" onClick={closeBag}>
                View full shopping bag
              </Link>
              <span>
                <ShieldCheck size={13} /> 100% Authentic · Stripe Verified
              </span>
            </div>
          </footer>
        )}
      </aside>
    </div>
  );
}
