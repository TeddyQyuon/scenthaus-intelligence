import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, LockKeyhole, Package, ShieldCheck } from "lucide-react";
import { api, message } from "./api";
import { useShop } from "./context";

export const paymentMoney = (minor) => `S$${new Intl.NumberFormat("en-SG", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
}).format((minor || 0) / 100)}`;

const blankDelivery = { email: "", phone: "", full_name: "", line1: "", line2: "",
  postal_code: "", city: "Singapore", country: "SG" };

function ErrorNotice({ error }) {
  return error ? <p className="error" role="alert">{error}</p> : null;
}

export function OrderSummary({ order, title = "Your selection" }) {
  return <aside className="checkout-summary" aria-label="Order summary">
    <h2>{title}</h2>
    <div className="checkout-items">
      {order.items.map((item) => <div className="checkout-line" key={item.variant_id}>
        <img src={item.image || "/images/product.png"} alt={item.name} width="80" height="96" />
        <div>
          <p className="eyebrow">{item.brand}</p>
          <strong>{item.name}</strong>
          <p className="metadata">{item.size_ml}ml · Quantity {item.quantity}</p>
          <p className="metadata">{paymentMoney(item.unit_price_minor)} each</p>
        </div>
        <strong>{paymentMoney(item.item_total_minor)}</strong>
      </div>)}
    </div>
    <dl className="checkout-totals">
      <div><dt>Subtotal</dt><dd>{paymentMoney(order.subtotal_minor)}</dd></div>
      <div><dt>Standard delivery</dt><dd>{order.shipping_minor ? paymentMoney(order.shipping_minor) : "Complimentary"}</dd></div>
      <div><dt>Discount</dt><dd>{order.discount_minor ? `−${paymentMoney(order.discount_minor)}` : paymentMoney(0)}</dd></div>
      <div><dt>Additional tax</dt><dd>{paymentMoney(order.tax_minor)}</dd></div>
      <div className="checkout-total"><dt>Total <small>SGD</small></dt><dd>{paymentMoney(order.total_minor)}</dd></div>
    </dl>
    <p className="checkout-trust"><ShieldCheck size={18} /> Prices and availability verified by SCENTHAUS.</p>
  </aside>;
}

function DeliveryForm({ delivery, setDelivery, busy }) {
  function change(event) { setDelivery((previous) => ({ ...previous, [event.target.name]: event.target.value })); }
  return <>
    <fieldset disabled={busy} className="checkout-fieldset">
      <legend><span>01</span> Contact</legend>
      <p className="metadata">Your order details and delivery updates.</p>
      <label>Email address<input type="email" name="email" autoComplete="email" required maxLength={254} value={delivery.email} onChange={change} /></label>
      <label>Phone number <small>(optional)</small><input type="tel" name="phone" autoComplete="tel" maxLength={24} pattern="[+0-9 ()-]*" value={delivery.phone} onChange={change} /></label>
    </fieldset>
    <fieldset disabled={busy} className="checkout-fieldset">
      <legend><span>02</span> Delivery</legend>
      <p className="metadata">Complimentary standard delivery within Singapore.</p>
      <label>Full name<input name="full_name" autoComplete="name" required minLength={2} maxLength={120} value={delivery.full_name} onChange={change} /></label>
      <label>Address line 1<input name="line1" autoComplete="address-line1" required minLength={3} maxLength={200} value={delivery.line1} onChange={change} /></label>
      <label>Address line 2 <small>(optional)</small><input name="line2" autoComplete="address-line2" maxLength={200} value={delivery.line2} onChange={change} /></label>
      <div className="checkout-form-row">
        <label>Postal code<input name="postal_code" autoComplete="postal-code" inputMode="numeric" required pattern="[0-9]{6}" maxLength={6} title="Enter a 6-digit Singapore postal code" value={delivery.postal_code} onChange={change} /></label>
        <label>City<input name="city" autoComplete="address-level2" required minLength={2} maxLength={100} value={delivery.city} onChange={change} /></label>
      </div>
      <label>Country<select name="country" autoComplete="country" value={delivery.country} onChange={change}><option value="SG">Singapore</option></select></label>
    </fieldset>
  </>;
}

function checkoutKey() {
  const name = "scenthaus.checkout.request.v1";
  try {
    let key = sessionStorage.getItem(name);
    if (!key) { key = crypto.randomUUID(); sessionStorage.setItem(name, key); }
    return key;
  } catch { return crypto.randomUUID(); }
}

function resetCheckoutKey() {
  try { sessionStorage.removeItem("scenthaus.checkout.request.v1"); } catch { /* Storage can be disabled. */ }
}

function redirectToStripe(url) {
  const target = new URL(url);
  if (target.protocol !== "https:" || target.hostname !== "checkout.stripe.com") {
    throw new Error("The payment link could not be verified. Please retry.");
  }
  window.location.assign(target.href);
}

export function CheckoutPage() {
  const { user } = useShop();
  const [quote, setQuote] = useState(null);
  const [delivery, setDelivery] = useState(() => ({ ...blankDelivery, email: user.email || "" }));
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const [key, setKey] = useState(checkoutKey);

  async function loadQuote() {
    setLoading(true); setError("");
    try {
      const { data } = await api.get("/checkout/quote");
      setQuote(data);
      if (data.pending_order) setDelivery(data.pending_order.delivery);
      else { resetCheckoutKey(); setKey(checkoutKey()); }
    } catch (e) { setError(message(e)); }
    finally { setLoading(false); }
  }
  useEffect(() => { let active = true; api.get("/checkout/quote").then(({ data }) => {
    if (active) { setQuote(data); if (data.pending_order) setDelivery(data.pending_order.delivery); else { resetCheckoutKey(); setKey(checkoutKey()); } }
  }).catch((e) => { if (active) setError(message(e)); }).finally(() => { if (active) setLoading(false); });
  return () => { active = false; }; }, []);

  async function pay(event) {
    event.preventDefault();
    if (sending.current || !quote?.payments_available) return;
    sending.current = true; setBusy(true); setError("");
    try {
      const { data } = await api.post("/checkout/session", { delivery,
        items: quote.items.map(({ product_id, variant_id, size_ml, quantity }) => ({ product_id, variant_id, size_ml, quantity })),
        quote_token: quote.quote_token, idempotency_key: key });
      if (data.payment_status === "paid") window.location.assign(`/checkout/success?order_id=${encodeURIComponent(data.order_id)}`);
      else redirectToStripe(data.checkout_url);
    } catch (e) {
      setError(e.response ? message(e) : "Secure payment could not connect. Your bag is saved; please retry.");
    } finally { sending.current = false; setBusy(false); }
  }

  async function cancelPending() {
    if (sending.current) return;
    sending.current = true; setBusy(true); setError("");
    try {
      const { data } = await api.post(`/checkout/${quote.pending_order.order_id}/cancel`);
      if (data.payment_status === "paid") { window.location.assign(`/checkout/success?order_id=${encodeURIComponent(data.id)}`); return; }
      if (data.status !== "cancelled") { setError("Your payment is being checked. Please wait before starting another checkout."); return; }
      resetCheckoutKey(); setKey(checkoutKey()); await loadQuote();
    } catch (e) { setError(message(e)); }
    finally { sending.current = false; setBusy(false); }
  }

  return <section className="section checkout-page">
    <Link className="checkout-back" to="/cart"><ArrowLeft size={16} /> Back to bag</Link>
    <p className="eyebrow">THE FINISHING TOUCH</p>
    <h1>A scent worth coming home to.</h1>
    <p className="checkout-intro">Your selection, delivered with care.</p>
    {loading ? <div className="checkout-loading" role="status">Checking your selection and delivery total…</div> : !quote ?
      <div className="empty"><Package size={32} /><ErrorNotice error={error} /><Link className="button" to="/cart">Return to bag</Link><button className="outline" onClick={loadQuote}>Try again</button></div> : <>
      {quote.payment_mode === "test" && <p className="payment-mode-note" role="note">Stripe test mode — no real charge or delivery. Use test payment details.</p>}
      <div className="checkout-layout">
        <form onSubmit={pay} className="checkout-form" aria-busy={busy}>
          {quote.pending_order && <div className="checkout-reservation" role="status"><strong>Your secure checkout is saved.</strong><p>The selection and delivery details below are reserved for this checkout. Resume payment, or cancel it to edit your order.</p><button type="button" className="why" disabled={busy} onClick={cancelPending}>Cancel saved checkout and edit</button></div>}
          <DeliveryForm delivery={delivery} setDelivery={setDelivery} busy={busy || Boolean(quote.pending_order)} />
          <div className="checkout-payment">
            <h2><span>03</span> Secure payment</h2>
            <p>Continue to Stripe to pay by card or an eligible payment method. Your card details are handled securely by Stripe.</p>
            {!quote.payments_available && <p className="error" role="alert">Secure payments are temporarily unavailable. Your bag is saved.</p>}
            <ErrorNotice error={error} />
            {error && !busy && <button type="button" className="why" onClick={loadQuote}>Review the latest order and retry</button>}
            <button className="wide" disabled={busy || !quote.payments_available} type="submit"><LockKeyhole size={17} />{busy ? "Opening secure payment…" : `${quote.pending_order ? "Resume payment" : "Pay now"} · ${paymentMoney(quote.total_minor)}`}<ArrowRight size={16} /></button>
            <p className="metadata">You’ll review this amount again on Stripe before confirming payment.</p>
          </div>
        </form>
        <OrderSummary order={quote} />
      </div>
    </>}
  </section>;
}

function DeliveryDetails({ order }) {
  const address = order.delivery_address;
  return <div className="order-delivery"><h2>Delivery details</h2><p>{order.customer_name}<br />{address?.line1}<br />{address?.line2 ? <>{address.line2}<br /></> : null}{address?.city} {address?.postal_code}<br />Singapore</p><p className="metadata">{order.customer_email}</p></div>;
}

function OrderView({ id, cancelled = false, detail = false }) {
  const { refresh } = useShop();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [poll, setPoll] = useState(0);
  const notified = useRef(false);
  useEffect(() => {
    if (!id) { setLoading(false); return; }
    let active = true;
    let timer;
    const load = async () => {
      try {
        const { data } = await api.get(`/orders/${encodeURIComponent(id)}`);
        if (!active) return;
        setOrder(data); setError(""); setLoading(false);
        if (data.payment_status === "paid" && !notified.current) { notified.current = true; resetCheckoutKey(); refresh().catch(() => {}); }
        if (!cancelled && !["paid", "refunded"].includes(data.payment_status) && data.status !== "cancelled" && poll < 20) timer = setTimeout(() => setPoll((n) => n + 1), 1500);
      } catch (e) { if (active) { setError(message(e)); setLoading(false); } }
    };
    load();
    return () => { active = false; clearTimeout(timer); };
  }, [id, poll, cancelled]);

  async function confirmCancel() {
    setLoading(true); setError("");
    try {
      const { data } = await api.post(`/checkout/${encodeURIComponent(id)}/cancel`);
      setOrder(data);
      if (data.status === "cancelled") resetCheckoutKey();
    } catch (e) { setError(message(e)); }
    finally { setLoading(false); }
  }
  const paid = order?.payment_status === "paid";
  const ended = order?.status === "cancelled";
  const refunded = order?.payment_status === "refunded";
  return <section className="section checkout-page order-confirmation">
    <p className="eyebrow">{detail ? "YOUR SCENTHAUS ORDER" : paid ? "A NEW SCENT CHAPTER" : "YOUR CHECKOUT"}</p>
    <h1>{loading ? "Checking your order." : paid ? "Thank you for your order." : refunded ? "Your refund is recorded." : ended ? "Your payment wasn’t completed." : cancelled ? "Return to your selection." : "We’re checking your payment."}</h1>
    <ErrorNotice error={error} />
    {!id && <p>No order was selected. Payment is confirmed only after Stripe verifies it.</p>}
    {order && <>
      <p className="order-number">Order #{order.order_number}</p>
      {order.payment_mode === "test" && <p className="payment-mode-note">Stripe test payment — no real charge or delivery.</p>}
      {paid ? <p className="order-status"><Check size={20} /> Your payment was successful. Order status: {order.status}.</p> : refunded ? <p>This order has been refunded.</p> : ended ? <p>No completed payment is recorded for this order. Your bag is saved.</p> : <p>We haven’t received a completed payment confirmation yet. Your bag stays saved while we verify the payment.</p>}
      {order.refunded_minor > 0 && <p>Refund recorded: {paymentMoney(order.refunded_minor)}. Your bank determines when the funds appear.</p>}
      {paid && <p>{order.payment_mode === "test" ? "This test order is confirmed. It will not be dispatched." : "Next, your selection will be reviewed for packing. Keep your order number for reference."}</p>}
      {cancelled && !paid && !ended && <button className="outline" disabled={loading} onClick={confirmCancel}>Cancel payment and keep my bag</button>}
      <div className="checkout-layout"><DeliveryDetails order={order} /><OrderSummary order={order} title={paid ? "Your purchase" : "Your selection"} /></div>
    </>}
    <div className="order-actions"><Link className="button" to="/shop">Continue shopping <ArrowRight size={16} /></Link>{order && !detail && <Link className="outline button" to={`/orders/${order.id}`}>View order</Link>}{!paid && <Link className="outline button" to="/checkout">Return to checkout</Link>}{id && <button className="outline" disabled={loading} onClick={() => { setLoading(true); setPoll((n) => n + 1); }}>Check payment status</button>}</div>
  </section>;
}

export function CheckoutSuccess() { const [params] = useSearchParams(); return <OrderView id={params.get("order_id")} />; }
export function CheckoutCancelled() { const [params] = useSearchParams(); return <OrderView id={params.get("order_id")} cancelled />; }
export function OrderDetail() { const { orderId } = useParams(); return <OrderView id={orderId} detail />; }
