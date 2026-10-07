import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { Check, ShoppingBag, X } from "lucide-react";
import { useShop } from "./context";
import { money, message } from "./api";

export default function QuickAdd({ product, onClose }) {
  const { add } = useShop();
  const dialog = useRef(null);
  const pending = useRef(false);
  const titleId = useId();
  const [selected, setSelected] = useState(product.variants.find((v) => v.stock > 0));
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const opener = document.activeElement;
    dialog.current.showModal();
    return () => { opener?.focus(); };
  }, []);
  async function addSelected() {
    if (pending.current || !selected?.stock) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await add(selected);
      setAdded(true);
    } catch (e) {
      setError(message(e));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  return createPortal(
    <dialog className="quick-dialog" ref={dialog} aria-labelledby={titleId}
      onCancel={(e) => { e.preventDefault(); if (!pending.current) onClose(); }}
      onClick={(e) => { if (e.target === dialog.current && !pending.current) onClose(); }}>
      <div className="quick-content">
        <div className="quick-heading"><span className="eyebrow">QUICK ADD</span><button className="icon" aria-label="Close quick add" disabled={busy} onClick={onClose} autoFocus><X size={22} /></button></div>
        <div className="quick-product"><img src={product.image} alt={`${product.name} by ${product.brand}`} /><div><p className="eyebrow">{product.brand}</p><h2 id={titleId}>{product.name}</h2><p className="metadata">{product.concentration} · {product.category}</p></div></div>
        {added ? <div className="quick-success" role="status"><Check size={24} /><h3>In your bag.</h3><p>{selected.size_ml} ml · {money(selected.price)}</p><Link className="button wide" to="/cart" onClick={onClose}>View bag <ShoppingBag size={17} /></Link><button className="outline wide" onClick={onClose}>Keep exploring</button></div> : <>
          <fieldset className="quick-variants" disabled={busy}><legend>Choose your size</legend>{product.variants.map((v) => <button type="button" key={v.id} className={selected?.id === v.id ? "selected" : "outline"} disabled={!v.stock || busy} aria-pressed={selected?.id === v.id} onClick={() => { setSelected(v); setError(""); }}><span>{v.size_ml} ml</span><span>{money(v.price)}</span>{!v.stock && <small>Sold out</small>}</button>)}</fieldset>
          <div className="quick-total"><span>{selected?.size_ml} ml · {selected?.stock ? "In stock" : "Sold out"}</span><strong>{money(selected?.price)}</strong></div>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="wide" disabled={busy || !selected?.stock} onClick={addSelected}>{busy ? "Adding to bag…" : "Add to bag"}<ShoppingBag size={17} /></button>
          <Link className="quick-details" to={`/product/${product.slug}`} onClick={onClose}>View fragrance details</Link>
        </>}
        <p className="quick-demo">Portfolio demo · prices and stock are simulated.</p>
      </div>
    </dialog>, document.body,
  );
}
