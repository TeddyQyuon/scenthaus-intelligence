import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { createPortal } from "react-dom";
import { Check, Minus, Plus, X } from "lucide-react";
import { api, money, message } from "./api";
import { useShop } from "./context";

export default function QuickAdd({ product, onClose, recommendationId }) {
  const { add, cart, track } = useShop();
  const dialog = useRef(null);
  const pending = useRef(false);
  const titleId = useId();
  const [current, setCurrent] = useState(product);
  const [selected, setSelected] = useState(
    product.variants.length === 1 ? product.variants[0].id : null,
  );
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState(false);
  const variant = current.variants.find((v) => v.id === selected);
  const existing =
    cart.items.find((item) => item.variant_id === selected)?.quantity || 0;
  const maximum = variant
    ? Math.max(0, Math.min(10, variant.stock) - existing)
    : 0;

  useEffect(() => {
    const opener = document.activeElement;
    dialog.current.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      opener?.focus();
    };
  }, []);

  useEffect(() => {
    let active = true;
    api
      .get(`/products/${product.slug}`)
      .then((r) => {
        if (active) {
          setCurrent(r.data);
          setAvailable(true);
        }
      })
      .catch((e) => {
        if (active) setError(message(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [product.slug]);

  async function submit(e) {
    e.preventDefault();
    if (pending.current || !variant || maximum < quantity) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await add(variant, quantity);
      if (recommendationId) track(product.id, "click", recommendationId);
      setAdded(true);
    } catch (e) {
      setError(message(e));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return createPortal(
    <dialog
      ref={dialog}
      className="quick-add-dialog"
      aria-labelledby={titleId}
      onCancel={(e) => {
        if (pending.current) e.preventDefault();
      }}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget && !pending.current) dialog.current.close();
      }}
    >
      <div className="quick-add-content">
        <button
          className="icon dialog-close"
          aria-label="Close quick add"
          disabled={busy}
          onClick={() => dialog.current.close()}
        >
          <X size={22} />
        </button>
        <p className="eyebrow">{added ? "IN YOUR BAG" : "QUICK ADD"}</p>
        <div className="quick-add-product">
          <img src={current.image} alt={current.name} />
          <div>
            <p className="eyebrow">{current.brand}</p>
            <h2 id={titleId}>{current.name}</h2>
            <p className="metadata">
              {current.category} · {current.concentration}
            </p>
          </div>
        </div>
        {added ? (
          <div className="quick-add-success" role="status">
            <p>
              <Check size={20} /> Added {quantity} × {variant.size_ml}ml to your
              bag.
            </p>
            <Link className="button wide" to="/cart" onClick={onClose}>
              View bag
            </Link>
            <button
              className="outline wide"
              onClick={() => dialog.current.close()}
            >
              Continue shopping
            </button>
          </div>
        ) : (
          <form onSubmit={submit}>
            <fieldset className="quick-add-sizes" disabled={busy || loading}>
              <legend>Choose a size</legend>
              {current.variants.map((v) => (
                <label
                  key={v.id}
                  className={`${selected === v.id ? "selected" : ""} ${v.stock < 1 ? "unavailable" : ""}`}
                >
                  <input
                    type="radio"
                    name={titleId}
                    required
                    value={v.id}
                    checked={selected === v.id}
                    disabled={v.stock < 1}
                    onChange={() => {
                      setSelected(v.id);
                      setQuantity(1);
                    }}
                  />
                  <span>{v.size_ml}ml</span>
                  <small>{v.stock > 0 ? money(v.price) : "Sold out"}</small>
                </label>
              ))}
            </fieldset>
            <div className="quick-add-quantity">
              <span>Quantity</span>
              <div className="quantity">
                <button
                  type="button"
                  aria-label="Decrease quick-add quantity"
                  disabled={busy || quantity <= 1}
                  onClick={() => setQuantity((q) => q - 1)}
                >
                  <Minus size={16} />
                </button>
                <output aria-label="Quick-add quantity">{quantity}</output>
                <button
                  type="button"
                  aria-label="Increase quick-add quantity"
                  disabled={busy || loading || quantity >= maximum}
                  onClick={() => setQuantity((q) => q + 1)}
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
            {existing > 0 && (
              <p className="metadata">
                {existing} already in your bag for this size.
              </p>
            )}
            {variant && maximum < 1 && (
              <p className="metadata">
                Your bag has the maximum available quantity for this size.
              </p>
            )}
            <p className="quick-add-total">
              <span>{variant ? "Total" : "From"}</span>
              <strong>
                {money(variant ? variant.price * quantity : current.price_from)}
              </strong>
            </p>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <button
              className="wide"
              disabled={
                !available || loading || busy || !variant || quantity > maximum
              }
            >
              {loading
                ? "Checking availability…"
                : busy
                  ? "Adding…"
                  : "Add to bag"}
              <Plus size={17} />
            </button>
            <Link
              className="why"
              to={`/product/${product.slug}`}
              onClick={onClose}
            >
              View full product details
            </Link>
            <p className="metadata">
              Demo prices and stock. No payment is taken.
            </p>
          </form>
        )}
      </div>
    </dialog>, document.body,
  );
}
