import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Link,
  NavLink,
  Outlet,
  useLocation,
  useParams,
} from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Heart,
  ShoppingBag,
  UserRound,
  Search,
  Menu,
  X,
  Sparkles,
  Leaf,
  SlidersHorizontal,
  Plus,
  Minus,
  Check,
  ShieldCheck,
} from "lucide-react";
import { ShopProvider, useShop } from "./context";
import { api, money, message, download } from "./api";
const Admin = lazy(() => import("./Admin"));
function Scroll() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
export function ErrorBox({ error }) {
  return error ? (
    <p className="error" role="alert">
      {error}
    </p>
  ) : null;
}
export function ProductCard({ product: p, rec }) {
  const { wishlist, wish, add, track, notify } = useShop(),
    ref = useRef(null);
  const [why, setWhy] = useState(false),
    [busy, setBusy] = useState(false);
  const saved = wishlist.some((w) => w.id === p.id),
    variant = p.variants.find((v) => v.stock > 0);
  useEffect(() => {
    if (!rec?.recommendation_id) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          track(p.id, "impression", rec.recommendation_id);
          observer.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [p.id, rec?.recommendation_id]);
  async function action(fn) {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      notify(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="product-card" ref={ref}>
      <div className={`product-image tone-${p.category.toLowerCase()}`}>
        <Link
          to={`/product/${p.slug}`}
          onClick={() =>
            rec?.recommendation_id &&
            track(p.id, "click", rec.recommendation_id)
          }
        >
          <img
            src={p.image}
            alt={`${p.name} — illustrative fragrance bottle`}
            loading="lazy"
          />
        </Link>
        <button
          className={`icon heart ${saved ? "saved" : ""}`}
          aria-label={`${saved ? "Remove" : "Save"} ${p.name}`}
          onClick={() => action(() => wish(p))}
        >
          <Heart size={19} fill={saved ? "currentColor" : "none"} />
        </button>
        {p.match != null && <span className="match">{p.match}% match</span>}
        {!p.in_stock && <span className="match">Sold out</span>}
      </div>
      <p className="eyebrow">{p.brand}</p>
      <div className="card-title">
        <Link to={`/product/${p.slug}`} onClick={()=>rec?.recommendation_id&&track(p.id,"click",rec.recommendation_id)}>{p.name}</Link>
        <button
          className="icon"
          disabled={!variant || busy}
          aria-label={`Add ${p.name} to bag`}
          onClick={() => action(() => add(variant))}
        >
          <Plus size={19} />
        </button>
      </div>
      <p className="metadata">
        {p.category} · {p.concentration} · {p.notes.top.join(", ")}
      </p>
      <p className="price">From {money(p.price_from)}</p>
      {p.why && (
        <>
          <button className="why" onClick={() => setWhy(!why)}>
            <Sparkles size={13} /> Why this scent?
          </button>
          {why && (
            <p className="explanation">
              {p.why}
              {p.rule &&
                ` · Lift ${p.rule.lift.toFixed(2)}, confidence ${(p.rule.confidence * 100).toFixed(0)}%`}
            </p>
          )}
        </>
      )}
    </article>
  );
}
export function Grid({ products, rec, limit }) {
  return (
    <div className="product-grid">
      {products?.slice(0, limit || products.length).map((p) => (
        <ProductCard key={p.id} product={p} rec={rec} />
      ))}
    </div>
  );
}
function Layout() {
  const { cart, wishlist } = useShop();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => {
    setOpen(false);
  }, [loc.pathname]);
  return (
    <>
      <div className="announcement">
        A scent for every version of you.{" "}
        <Link to="/quiz">
          Find yours <ArrowRight size={12} />
        </Link>
      </div>
      <header className="site-header">
        <Link className="brand" to="/">
          <span className="wordmark">SCENTHAUS</span>
          <span className="brand-caption">THE ART OF FINDING YOU</span>
        </Link>
        <nav className={open ? "open" : ""}>
          <NavLink to="/shop">The collection</NavLink>
          <NavLink to="/quiz">Find your scent</NavLink>
          <NavLink to="/intelligence">The intelligence</NavLink>
        </nav>
        <div className="header-icons">
          <Link to="/shop" aria-label="Search scents">
            <Search size={20} />
          </Link>
          <Link
            to="/wishlist"
            aria-label={`Wishlist, ${wishlist.length} scents`}
          >
            <Heart size={20} />
            {wishlist.length > 0 && <i>{wishlist.length}</i>}
          </Link>
          <Link to="/account" aria-label="Your account">
            <UserRound size={20} />
          </Link>
          <Link
            to="/cart"
            aria-label={`Shopping bag, ${cart.items.length} items`}
          >
            <ShoppingBag size={20} />
            {cart.items.length > 0 && <i>{cart.items.length}</i>}
          </Link>
          <button
            className="icon mobile-menu"
            aria-label="Toggle navigation"
            onClick={() => setOpen(!open)}
          >
            {open ? <X /> : <Menu />}
          </button>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer>
        <div>
          <Link className="wordmark" to="/">
            SCENTHAUS
          </Link>
          <p>Fragrance, with a little more feeling.</p>
          <p className="metadata">
            A portfolio demonstration. Fictional scents,
            <br />
            illustrative bottles and simulated sales.
          </p>
        </div>
        <div>
          <p className="eyebrow">Explore</p>
          <Link to="/shop">The collection</Link>
          <Link to="/quiz">Your scent profile</Link>
          <Link to="/wishlist">Your wishlist</Link>
        </div>
        <div>
          <p className="eyebrow">Behind the scent</p>
          <Link to="/intelligence">Our methods</Link>
          <Link to="/privacy">Privacy & personalization</Link>
          <Link to="/account">Your account</Link>
          <Link to="/admin">Admin dashboard</Link>
        </div>
        <div>
          <p className="eyebrow">Made for you, on your terms.</p>
          <p>
            Personalization is optional.
            <br />
            Your preferences stay in your control.
          </p>
          <Link className="text-link" to="/privacy">
            Manage preferences <ArrowUpRight size={14} />
          </Link>
        </div>
        <div className="footer-bottom">
          © 2026 SCENTHAUS · Built as a pipeline + method showcase{" "}
          <span>Singapore · SGD</span>
        </div>
      </footer>
    </>
  );
}
function Home() {
  const { user } = useShop();
  const [featured, setFeatured] = useState([]),
    [rec, setRec] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api.get("/products"), api.get("/recommend/user")])
      .then(([a, b]) => {
        if (active) {
          setFeatured(a.data.products.slice(0, 4));
          setRec(b.data);
        }
      })
      .catch((e) => active && setError(message(e)));
    return () => {
      active = false;
    };
  }, [user.consent]);
  return (
    <>
      <section className="hero">
        <img
          src="/images/hero.png"
          alt="Amber fragrance bottles on dark sculptural stone"
          fetchPriority="high"
        />
        <div className="hero-content">
          <p className="eyebrow">A PERSONAL APPROACH TO PERFUME</p>
          <h1>
            Less ordinary.
            <br />
            <em>More you.</em>
          </h1>
          <p>
            Some scents make an impression.
            <br />
            The right one feels like an extension of you.
          </p>
          <div className="button-row">
            <Link className="button light" to="/shop">
              Explore the collection <ArrowRight size={16} />
            </Link>
            <Link className="hero-link" to="/quiz">
              Find your signature <ArrowUpRight size={16} />
            </Link>
          </div>
          <span className="hero-footnote">
            Thoughtfully curated. Intelligently discovered.
          </span>
        </div>
        <span className="hero-index">01 / A SCENT OF SELF</span>
      </section>
      <div className="houses">
        <span className="eyebrow">IN GOOD COMPANY</span>
        {[
          "ATELIER 08",
          "MAISON OBLIQUE",
          "STUDIO SILLAGE",
          "BOTANIQUE",
          "NOCTURNE",
          "COASTLINE",
        ].map((h) => (
          <span key={h}>{h}</span>
        ))}
      </div>
      <section className="section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">THE EDIT</p>
            <h2>Worth getting close to.</h2>
          </div>
          <Link className="text-link" to="/shop">
            View all scents <ArrowRight size={16} />
          </Link>
        </div>
        <ErrorBox error={error} />
        <Grid products={featured} />
      </section>
      <section className="quiz-banner">
        <div className="orb">
          <Sparkles size={64} strokeWidth={0.7} />
        </div>
        <div>
          <p className="eyebrow">LESS GUESSWORK. MORE CONNECTION.</p>
          <h2>
            Your signature isn’t chosen.
            <br />
            <em>It’s recognized.</em>
          </h2>
          <p>
            A few questions about what you love.
            <br />A collection of scents that speaks your language.
          </p>
          <Link className="button" to="/quiz">
            Discover your scent profile <ArrowRight size={16} />
          </Link>
        </div>
        <span className="vertical-note">A LITTLE SCIENCE. A LOT OF YOU.</span>
      </section>
      <section className="section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">
              {user.consent ? "YOUR PERSONAL EDIT" : "COMMUNITY FAVOURITES"}
            </p>
            <h2>
              {user.consent ? "Picked for you." : "A good place to begin."}
            </h2>
          </div>
          <Link className="text-link" to="/privacy">
            Your preferences <ArrowUpRight size={16} />
          </Link>
        </div>
        <Grid products={rec?.products} rec={rec} limit={4} />
        <p className="metadata">
          {user.consent
            ? "Your quiz, wishlist and browsing help shape this edit."
            : "Turn on personalization to shape this edit around your preferences."}
        </p>
      </section>
      <section className="values">
        <div>
          <Leaf size={25} />
          <h3>Beyond the bottle.</h3>
          <p>Explore every note, accord and impression.</p>
        </div>
        <div>
          <Sparkles size={25} />
          <h3>A thoughtful match.</h3>
          <p>Discover the connection behind each suggestion.</p>
        </div>
        <div>
          <ShieldCheck size={25} />
          <h3>Always your choice.</h3>
          <p>Personalization with consent, control and clarity.</p>
        </div>
      </section>
    </>
  );
}
function Shop() {
  const [data, setData] = useState({ products: [], brands: [] }),
    [filters, setFilters] = useState({
      q: "",
      category: "",
      brand: "",
      budget: "",
      size: "",
      gender: "",
      season: "",
      in_stock: false,
      sort: "featured",
    }),
    [natural, setNatural] = useState(false),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      const params = Object.fromEntries(
        Object.entries(filters).filter(([k, v]) => v !== ""),
      );
      api
        .get(natural && filters.q ? "/search" : "/products", {
          params: natural && filters.q ? { q: filters.q } : params,
        })
        .then(
          (r) =>
            active &&
            setData((d) => ({ ...r.data, brands: r.data.brands || d.brands })),
        )
        .catch((e) => active && setError(message(e)))
        .finally(() => active && setLoading(false));
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [filters, natural]);
  function change(key, value) {
    setFilters((f) => ({ ...f, [key]: value }));
    setError("");
  }
  return (
    <section className="section shop">
      <p className="eyebrow">36 SCENTS. COUNTLESS POSSIBILITIES.</p>
      <h1>The collection.</h1>
      <p className="intro">Follow a note. Find a feeling. Make it yours.</p>
      <div className="search-field">
        <Search size={19} />
        <input
          aria-label="Search the collection"
          placeholder={
            natural
              ? "Try “fresh office scent under $150”"
              : "Search a scent, note or house…"
          }
          value={filters.q}
          onChange={(e) => change("q", e.target.value)}
        />
      </div>
      <label className="check-row">
        <input
          type="checkbox"
          checked={natural}
          onChange={(e) => setNatural(e.target.checked)}
        />{" "}
        Describe your scent in natural language
      </label>
      <div className="filter-bar">
        <SlidersHorizontal size={18} />
        {[
          ["category", "Family", ["Fresh", "Woody", "Floral", "Amber"]],
          ["brand", "House", data.brands],
          ["size", "Size", ["30", "50", "100"]],
          ["gender", "Gender label", ["Unisex", "Feminine", "Masculine"]],
          ["season", "Season", ["Summer", "Spring", "Autumn", "Winter"]],
          ["budget", "Budget", ["100", "150", "200", "300"]],
        ].map(([key, label, opts]) => (
          <select
            key={key}
            aria-label={label}
            value={filters[key]}
            onChange={(e) => change(key, e.target.value)}
            disabled={natural && !!filters.q}
          >
            <option value="">{label}</option>
            {opts.map((v) => (
              <option key={v} value={v}>
                {key === "budget"
                  ? `Under $${v}`
                  : key === "size"
                    ? `${v}ml`
                    : v}
              </option>
            ))}
          </select>
        ))}
        <label className="check-row">
          <input
            type="checkbox"
            checked={filters.in_stock}
            onChange={(e) => change("in_stock", e.target.checked)}
            disabled={natural && !!filters.q}
          />{" "}
          In stock
        </label>
        <select
          aria-label="Sort"
          value={filters.sort}
          onChange={(e) => change("sort", e.target.value)}
        >
          <option value="featured">Featured</option>
          <option value="price-low">Price: low to high</option>
          <option value="price-high">Price: high to low</option>
        </select>
      </div>
      <div className="results-count">
        {loading ? "Finding your scents…" : `${data.products.length} scents`}
        {data.parsed && (
          <span>
            {" "}
            · Budget {data.parsed.budget ? money(data.parsed.budget) : "any"} ·
            Available scents
          </span>
        )}
      </div>
      <ErrorBox error={error} />
      <Grid products={data.products} />
      {!loading && !data.products.length && (
        <div className="empty">
          <h2>No scents in this edit.</h2>
          <p>Try a wider budget or another note.</p>
          <button
            onClick={() =>
              setFilters({
                q: "",
                category: "",
                brand: "",
                budget: "",
                size: "",
                gender: "",
                season: "",
                in_stock: false,
                sort: "featured",
              })
            }
          >
            Reset filters
          </button>
        </div>
      )}
      <p className="metadata">
        Bottle images are illustrative. Gender labels are catalogue descriptors;
        every scent is for anyone.
      </p>
    </section>
  );
}
function Product() {
  const { slug } = useParams(),
    { add, wish, wishlist, track, notify } = useShop();
  const [p, setP] = useState(null),
    [selected, setSelected] = useState(null),
    [sections, setSections] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    setP(null);
    api
      .get(`/products/${slug}`)
      .then(async (r) => {
        if (!active) return;
        setP(r.data);
        setSelected(
          r.data.variants.find((v) => v.stock > 0) || r.data.variants[0],
        );
        track(r.data.id);
        const types = [
          "similar",
          "also-bought",
          ...(!r.data.in_stock ? ["substitutes"] : []),
        ];
        const values = await Promise.all(
          types.map((type) =>
            api
              .get(`/recommend/${type}`, { params: { product_id: r.data.id } })
              .then((v) => ({ type, ...v.data })),
          ),
        );
        if (active) setSections(values);
      })
      .catch((e) => active && setError(message(e)));
    return () => {
      active = false;
    };
  }, [slug]);
  if (error)
    return (
      <section className="section">
        <ErrorBox error={error} />
      </section>
    );
  if (!p) return <div className="section">Finding your scent…</div>;
  async function addBag() {
    setBusy(true);
    try {
      await add(selected);
    } catch (e) {
      notify(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="breadcrumb">
        <Link to="/shop">The collection</Link> / {p.name}
      </div>
      <section className="product-detail">
        <div className={`detail-image tone-${p.category.toLowerCase()}`}>
          <img src={p.image} alt={`${p.name}, illustrative bottle`} />
          <span>SCENTHAUS · {p.category.toUpperCase()} COLLECTION</span>
        </div>
        <div className="detail-copy">
          <p className="eyebrow">{p.brand}</p>
          <h1>{p.name}</h1>
          <p className="metadata">
            {p.concentration} · {p.gender} · {p.category}
          </p>
          <p className="detail-description">{p.description}</p>
          <div className="accords">
            {p.accords.map((a) => (
              <span key={a}>{a}</span>
            ))}
          </div>
          <p className="detail-price">{money(selected?.price)}</p>
          <div className="sizes">
            {p.variants.map((v) => (
              <button
                key={v.id}
                className={v.id === selected?.id ? "selected" : "outline"}
                onClick={() => setSelected(v)}
              >
                {v.size_ml}ml{v.stock === 0 ? " · Sold out" : ""}
              </button>
            ))}
          </div>
          <p className="metadata">
            {selected?.stock > 0
              ? `${selected.stock} available · SGD`
              : "This size is out of stock"}
          </p>
          <div className="button-row">
            <button
              className="wide"
              disabled={!selected?.stock || busy}
              onClick={addBag}
            >
              Add to bag <ShoppingBag size={17} />
            </button>
            <button
              className="outline"
              aria-label="Save scent"
              onClick={() => wish(p).catch((e) => notify(message(e)))}
            >
              <Heart
                size={20}
                fill={
                  wishlist.some((w) => w.id === p.id) ? "currentColor" : "none"
                }
              />
            </button>
          </div>
          <div className="note-pyramid">
            {Object.entries(p.notes).map(([level, notes]) => (
              <div key={level}>
                <span className="eyebrow">{level} notes</span>
                <p>{notes.join(" · ")}</p>
              </div>
            ))}
          </div>
          <div className="detail-stats">
            <span>
              Longevity <strong>{p.longevity} hours</strong>
            </span>
            <span>
              Sillage <strong>{p.sillage}</strong>
            </span>
            <span>
              Made for <strong>{p.occasions.join(" / ")}</strong>
            </span>
          </div>
          <p className="metadata">
            Fictional catalogue. Illustrative bottle. Demo orders only.
          </p>
        </div>
      </section>
      {sections.map((s) => (
        <section className="section" key={s.type}>
          <p className="eyebrow">DISCOVER THE CONNECTION</p>
          <h2>
            {s.type === "similar"
              ? "A familiar feeling."
              : s.type === "also-bought"
                ? "Customers also explored."
                : "Available alternatives."}
          </h2>
          <Grid products={s.products} rec={s} limit={4} />
        </section>
      ))}
    </>
  );
}
function Quiz() {
  const { user, consent, consentBusy } = useShop(),
    [answers, setAnswers] = useState({
      mood: "fresh",
      occasion: "office",
      intensity: "balanced",
      budget: 150,
      size: null,
    }),
    [step, setStep] = useState(0),
    [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const questions = [
    [
      "mood",
      "What feels most like you?",
      [
        ["fresh", "Fresh & bright", "Citrus, ocean air, clean beginnings."],
        ["woody", "Grounded & quiet", "Woods, texture, a little stillness."],
        ["floral", "Soft & expressive", "Petals, light, gentle confidence."],
        ["warm", "Warm & magnetic", "Amber, spice, after-dark energy."],
      ],
    ],
    [
      "occasion",
      "Where will it take you?",
      [
        ["office", "The working day", "An easy presence, never too much."],
        ["everyday", "Everywhere", "Your signature, on repeat."],
        ["evening", "After hours", "A little intrigue when the light changes."],
        ["gift", "A thoughtful gift", "Something memorable for someone else."],
      ],
    ],
    [
      "intensity",
      "How close should it stay?",
      [
        ["soft", "A quiet whisper", "Intimate and subtle."],
        [
          "balanced",
          "A comfortable presence",
          "Noticeable, without taking over.",
        ],
        ["bold", "A lasting impression", "Expressive and unapologetic."],
      ],
    ],
  ];
  async function submit() {
    setBusy(true);
    setError("");
    try {
      setResult((await api.post("/recommend/quiz", answers)).data);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  if (result)
    return (
      <section className="section">
        <p className="eyebrow">YOUR PERSONAL SCENT EDIT</p>
        <h1>These feel like you.</h1>
        <p className="intro">A starting point for your next signature.</p>
        <p className="metadata">
          {result.match_note} Your quiz is saved to your account.
        </p>
        <Grid products={result.products} rec={result} />
        <button
          className="outline"
          onClick={() => {
            setStep(0);
            setResult(null);
          }}
        >
          Retake your quiz
        </button>
      </section>
    );
  return (
    <section className="quiz-page">
      <p className="eyebrow">A LITTLE SCIENCE. A LOT OF YOU.</p>
      <div className="quiz-progress">
        {[0, 1, 2, 3].map((n) => (
          <span key={n} className={n <= step ? "done" : ""} />
        ))}
      </div>
      <p className="metadata">QUESTION {step + 1} OF 4</p>
      <h1>{step < 3 ? questions[step][1] : "Find your comfortable range."}</h1>
      <p className="intro">
        There are no wrong answers. Just your preferences.
      </p>
      {step < 3 ? (
        <div className="quiz-options">
          {questions[step][2].map(([value, title, copy]) => (
            <button
              key={value}
              className={answers[questions[step][0]] === value ? "chosen" : ""}
              onClick={() =>
                setAnswers((a) => ({ ...a, [questions[step][0]]: value }))
              }
            >
              <span>{title}</span>
              <small>{copy}</small>
              {answers[questions[step][0]] === value && <Check size={19} />}
            </button>
          ))}
        </div>
      ) : (
        <div className="quiz-budget">
          <label>
            Your budget <strong>{money(answers.budget)}</strong>
            <input
              aria-label="Your budget"
              type="range"
              min="60"
              max="350"
              step="10"
              value={answers.budget}
              onChange={(e) =>
                setAnswers((a) => ({ ...a, budget: Number(e.target.value) }))
              }
            />
          </label>
          <label>
            Preferred size
            <select
              aria-label="Preferred size"
              value={answers.size || ""}
              onChange={(e) =>
                setAnswers((a) => ({
                  ...a,
                  size: e.target.value ? Number(e.target.value) : null,
                }))
              }
            >
              <option value="">Any size</option>
              {[30, 50, 100].map((v) => (
                <option key={v} value={v}>
                  {v}ml
                </option>
              ))}
            </select>
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={user.consent}
              disabled={consentBusy}
              onChange={(e) =>
                consent(e.target.checked).catch((er) => setError(message(er)))
              }
            />{" "}
            Use my activity to personalize future suggestions
          </label>
          <p className="metadata">
            Optional. Your quiz works with personalization off.
          </p>
        </div>
      )}
      <ErrorBox error={error} />
      <div className="button-row">
        {step > 0 && (
          <button className="outline" onClick={() => setStep(step - 1)}>
            Back
          </button>
        )}
        <button
          disabled={busy}
          onClick={() => (step < 3 ? setStep(step + 1) : submit())}
        >
          {step < 3
            ? "Continue"
            : busy
              ? "Finding your scents…"
              : "See my matches"}{" "}
          <ArrowRight size={16} />
        </button>
      </div>
    </section>
  );
}
function Wishlist() {
  const { wishlist } = useShop();
  return (
    <section className="section">
      <p className="eyebrow">KEEP A LITTLE INSPIRATION CLOSE</p>
      <h1>Your wishlist.</h1>
      {wishlist.length ? (
        <Grid products={wishlist} />
      ) : (
        <div className="empty">
          <Heart size={36} />
          <h2>A space for your favourites.</h2>
          <p>Save scents as you explore. They’ll be here when you return.</p>
          <Link className="button" to="/shop">
            Explore scents <ArrowRight size={16} />
          </Link>
        </div>
      )}
    </section>
  );
}
function Cart() {
  const { cart, refresh, notify } = useShop(),
    [recs, setRecs] = useState(null),
    [order, setOrder] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const key = useRef(crypto.randomUUID().replaceAll("-", ""));
  useEffect(() => {
    api
      .get("/recommend/cart")
      .then((r) => setRecs(r.data))
      .catch(() => {});
  }, [cart.items.length]);
  async function update(v, q) {
    try {
      if (q < 1) await api.delete(`/cart/${v}`);
      else await api.put("/cart", { variant_id: v, quantity: q });
      await refresh();
      key.current = crypto.randomUUID().replaceAll("-", "");
    } catch (e) {
      notify(message(e));
    }
  }
  async function checkout() {
    setBusy(true);
    setError("");
    try {
      setOrder(
        (await api.post("/checkout", { idempotency_key: key.current })).data,
      );
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  if (order)
    return (
      <section className="section centered">
        <Check size={48} />
        <p className="eyebrow">YOUR DEMO ORDER IS COMPLETE</p>
        <h1>A new scent chapter.</h1>
        <p>No payment was taken. Your order was saved and inventory updated.</p>
        <p className="metadata">
          Order {order.id} · {money(order.total)}
        </p>
        <Link className="button" to="/shop">
          Keep exploring
        </Link>
      </section>
    );
  return (
    <section className="section">
      <p className="eyebrow">A LITTLE SOMETHING FOR YOU</p>
      <h1>Your bag.</h1>
      {cart.items.length ? (
        <div className="cart-layout">
          <div>
            {cart.items.map((i) => (
              <div className="cart-item" key={i.variant_id}>
                <Link to={`/product/${i.product.slug}`}>
                  <img src={i.product.image} alt={i.product.name} />
                </Link>
                <div>
                  <p className="eyebrow">{i.product.brand}</p>
                  <Link to={`/product/${i.product.slug}`}>
                    <h3>{i.product.name}</h3>
                  </Link>
                  <p className="metadata">
                    {i.size_ml}ml · {i.product.concentration}
                  </p>
                  <div className="quantity">
                    <button
                      className="icon"
                      aria-label={`Reduce ${i.product.name} quantity`}
                      onClick={() => update(i.variant_id, i.quantity - 1)}
                    >
                      <Minus size={14} />
                    </button>
                    <span>{i.quantity}</span>
                    <button
                      className="icon"
                      disabled={i.quantity >= 10 || i.quantity >= i.stock}
                      aria-label={`Increase ${i.product.name} quantity`}
                      onClick={() => update(i.variant_id, i.quantity + 1)}
                    >
                      <Plus size={14} />
                    </button>
                  </div>
                </div>
                <div className="cart-price">
                  <strong>{money(i.price * i.quantity)}</strong>
                  <button
                    className="why"
                    onClick={() => update(i.variant_id, 0)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
          <aside className="order-summary">
            <h3>Your order</h3>
            <div>
              <span>Subtotal</span>
              <strong>{money(cart.total)}</strong>
            </div>
            <div>
              <span>Delivery</span>
              <span>Demo only</span>
            </div>
            <div className="total">
              <span>Total</span>
              <strong>{money(cart.total)}</strong>
            </div>
            <ErrorBox error={error} />
            <button className="wide" disabled={busy} onClick={checkout}>
              {busy ? "Saving order…" : "Place demo order"}{" "}
              <ArrowRight size={16} />
            </button>
            <p className="metadata">
              No payment is collected. Prices and inventory are checked by the
              server when you place your order.
            </p>
          </aside>
        </div>
      ) : (
        <div className="empty">
          <ShoppingBag size={36} />
          <h2>Room for something you love.</h2>
          <Link className="button" to="/shop">
            Explore the collection
          </Link>
        </div>
      )}
      {cart.items.length > 0 && recs?.products.length > 0 && (
        <div className="cart-recs">
          <p className="eyebrow">A GOOD PAIRING</p>
          <h2>Better together.</h2>
          <Grid products={recs.products} rec={recs} limit={4} />
        </div>
      )}
    </section>
  );
}
function Account() {
  const { user, accept, consent, consentBusy } = useShop(),
    [mode, setMode] = useState("login"),
    [credentials, setCredentials] = useState({ email: "", password: "" }),
    [orders, setOrders] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!user.guest)
      api
        .get("/orders")
        .then((r) => setOrders(r.data))
        .catch(() => {});
  }, [user.id]);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await accept((await api.post(`/auth/${mode}`, credentials)).data);
    } catch (er) {
      setError(message(er));
    } finally {
      setBusy(false);
    }
  }
  if (user.guest)
    return (
      <section className="account-page">
        <p className="eyebrow">YOUR SCENT SPACE</p>
        <h1>{mode === "login" ? "Welcome back." : "Make it yours."}</h1>
        <p>Your bag and wishlist will stay with you.</p>
        <form onSubmit={submit}>
          <label>
            Email
            <input
              required
              type="email"
              autoComplete="email"
              value={credentials.email}
              onChange={(e) =>
                setCredentials((c) => ({ ...c, email: e.target.value }))
              }
            />
          </label>
          <label>
            Password
            <input
              required
              type="password"
              minLength={10}
              maxLength={128}
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              value={credentials.password}
              onChange={(e) =>
                setCredentials((c) => ({ ...c, password: e.target.value }))
              }
            />
          </label>
          <p className="metadata">At least 10 characters.</p>
          <ErrorBox error={error} />
          <button disabled={busy}>
            {busy
              ? "Please wait…"
              : mode === "login"
                ? "Sign in"
                : "Create account"}{" "}
            <ArrowRight size={16} />
          </button>
        </form>
        <button
          className="why"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login"
            ? "New here? Create an account"
            : "Already have an account? Sign in"}
        </button>
        <p className="metadata">
          Browse, take the quiz and shop in guest mode any time.
        </p>
      </section>
    );
  return (
    <section className="section">
      <p className="eyebrow">YOUR SCENT SPACE</p>
      <h1>Welcome back.</h1>
      <p>{user.email}</p>
      <div className="button-row">
        {user.role === "admin" && (
          <Link className="button" to="/admin">
            Open admin dashboard <ArrowUpRight size={17} />
          </Link>
        )}
        <button
          className="outline"
          onClick={async () => {
            try {
              await accept((await api.post("/auth/logout")).data);
            } catch (e) {
              setError(message(e));
            }
          }}
        >
          Sign out
        </button>
      </div>
      <ErrorBox error={error} />
      <div className="preferences">
        <h3>Your preferences</h3>
        <label className="check-row">
          <input
            type="checkbox"
            checked={user.consent}
            disabled={consentBusy}
            onChange={(e) =>
              consent(e.target.checked).catch((er) => setError(message(er)))
            }
          />{" "}
          Personalize my recommendations
        </label>
        <button
          className="outline"
          onClick={async () => {
            try {
              download(
                (await api.get("/privacy/export")).data,
                "scenthaus-my-data.json",
              );
            } catch (e) {
              setError(message(e));
            }
          }}
        >
          Download my data
        </button>
      </div>
      <h2>Your orders.</h2>
      {orders.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Date</th>
                <th>Total</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.id.slice(0, 8)}</td>
                  <td>{o.created_at.slice(0, 10)}</td>
                  <td>{money(o.total)}</td>
                  <td>{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>No orders yet.</p>
      )}
    </section>
  );
}
function Privacy() {
  const { user, consent, consentBusy } = useShop(),
    [error, setError] = useState("");
  return (
    <section className="reading section">
      <p className="eyebrow">ON YOUR TERMS</p>
      <h1>Personal, by choice.</h1>
      <p className="intro">
        You decide how your activity shapes your recommendations.
      </p>
      <div className="preferences">
        <label className="check-row">
          <input
            type="checkbox"
            checked={user.consent}
            disabled={consentBusy}
            onChange={(e) =>
              consent(e.target.checked).catch((er) => setError(message(er)))
            }
          />{" "}
          Personalize my recommendations
        </label>
        <ErrorBox error={error} />
        <p>
          With your consent, we use views, wishlist activity, your quiz and
          purchases to build your scent profile. With it off, you can still take
          the quiz and explore community favourites.
        </p>
      </div>
      <h2>What we keep</h2>
      <p>
        Your bag, wishlist, quiz and orders are stored in the database to
        provide these features. Account email and password hashes stay separate
        from model features. We never ask for card details in this
        demonstration.
      </p>
      <h2>When you opt out</h2>
      <p>
        We delete your tracking events, recommendation references and quiz
        profile. Functional cart, wishlist and orders remain available. Your
        records are excluded from future training; aggregate contributions
        already learned by a model clear on retraining, rather than instantly.
      </p>
      <h2>Retention & access</h2>
      <p>
        The daily maintenance worker expires tracking events and recommendation
        references after 180 days. Download your personal data from your
        account. This is a PDPA-aware demonstration, not a legal compliance
        certification.
      </p>
      <h2>Human control</h2>
      <p>
        Administrators can pin or hide products and review uncertain forecasts.
        Recommendations never make consequential decisions about you.
      </p>
    </section>
  );
}
export function MetricsTable({ metrics }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Precision@5</th>
            <th>Recall@5</th>
            <th>NDCG@5</th>
            <th>Coverage</th>
            <th>Diversity</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(metrics || {}).map(([name, m]) => (
            <tr key={name}>
              <td>{name}</td>
              {[
                "precision_at_5",
                "recall_at_5",
                "ndcg_at_5",
                "coverage",
                "diversity",
              ].map((k) => (
                <td key={k}>{m[k].toFixed(3)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Intelligence() {
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    api
      .get("/intelligence")
      .then((r) => setData(r.data))
      .catch((e) => setError(message(e)));
  }, []);
  return (
    <section className="section">
      <p className="eyebrow">A LITTLE SCIENCE BEHIND THE SCENT</p>
      <h1>Thoughtful discovery.</h1>
      <p className="intro">A transparent pipeline built on simulated data.</p>
      <ErrorBox error={error} />
      <div className="method-grid">
        {[
          [
            "A familiar feeling",
            "Notes and accords become TF-IDF vectors. Cosine similarity finds scents with a shared character.",
          ],
          [
            "A personal connection",
            "A validation-tuned hybrid combines content, collaborative signals and popularity. Brand diversity helps widen your edit.",
          ],
          [
            "A view of what’s next",
            "Weekly demand models compare seasonal naive, ETS, SARIMA, LightGBM and Croston through expanding time windows.",
          ],
        ].map(([title, copy]) => (
          <article key={title}>
            <Sparkles size={23} />
            <h3>{title}</h3>
            <p>{copy}</p>
          </article>
        ))}
      </div>
      {data && (
        <>
          <h2>Measured, openly.</h2>
          <p>
            Eight weeks held out by time. Hyperparameters use the preceding
            validation window.
          </p>
          <MetricsTable metrics={data.recommender.metrics} />
          <div className="notice">
            <strong>Simulated orders, not real commercial evidence.</strong>
            <p>
              We generated 2,000 hidden customer profiles and 104 weeks of
              orders. These results validate pipeline mechanics and methods.
              They do not prove effectiveness on real customers. Content may
              outperform the hybrid in this particular simulation.
            </p>
          </div>
          <div className="kpi-grid">
            <div>
              <span>Forecast WAPE</span>
              <strong>{data.forecast.wape.toFixed(1)}%</strong>
            </div>
            <div>
              <span>80% interval coverage</span>
              <strong>{(data.forecast.coverage80 * 100).toFixed(1)}%</strong>
            </div>
            <div>
              <span>95% interval coverage</span>
              <strong>{(data.forecast.coverage95 * 100).toFixed(1)}%</strong>
            </div>
          </div>
          <p className="metadata">
            Sparse, noisy SKU demand creates substantial error. Interval
            coverage is measured, not guaranteed. Aggregate bounds are
            conservative.
          </p>
          <h2>Model cards.</h2>
          <div className="method-grid">
            {[
              [
                "Discovery",
                "Purpose: help shoppers explore. Data: product metadata and consented pseudonymous activity. Limits: simulated behaviour, popularity bias, no certainty of preference.",
              ],
              [
                "Forecasting",
                "Purpose: support replenishment planning. Data: weekly SKU sales and Singapore calendar features. Limits: 24 months, synthetic shocks, uncertain low-volume demand. Humans review every reorder.",
              ],
              [
                "Experiments",
                "Two-tower and skip-gram session models are implemented as optional experiments. Learning curves are training diagnostics. Elasticity is observational and promotion-confounded; A/B outcomes are simulated.",
              ],
            ].map(([title, copy]) => (
              <article key={title}>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
          <p className="metadata">Model version: {data.version}</p>
        </>
      )}
    </section>
  );
}
export default function App() {
  return (
    <BrowserRouter>
      <ShopProvider>
        <Scroll />
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="shop" element={<Shop />} />
            <Route path="product/:slug" element={<Product />} />
            <Route path="quiz" element={<Quiz />} />
            <Route path="wishlist" element={<Wishlist />} />
            <Route path="cart" element={<Cart />} />
            <Route path="account" element={<Account />} />
            <Route path="privacy" element={<Privacy />} />
            <Route path="intelligence" element={<Intelligence />} />
            <Route
              path="*"
              element={
                <section className="section">
                  <h1>This scent trail ends here.</h1>
                  <Link className="button" to="/shop">
                    Back to the collection
                  </Link>
                </section>
              }
            />
          </Route>
          <Route
            path="admin"
            element={
              <Suspense
                fallback={
                  <div className="section">Opening your dashboard…</div>
                }
              >
                <Admin />
              </Suspense>
            }
          />
        </Routes>
      </ShopProvider>
    </BrowserRouter>
  );
}
