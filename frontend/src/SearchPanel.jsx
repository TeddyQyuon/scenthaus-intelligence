import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Search, X } from "lucide-react";
import { filterCatalogue, loadCatalogue, peekCatalogue } from "./catalogue";
import { money } from "./api";
import ProductImage from "./ProductImage";

export default function SearchPanel({ onClose }) {
  const dialog = useRef(null);
  const input = useRef(null);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [catalogue, setCatalogue] = useState(peekCatalogue);
  const [failed, setFailed] = useState(false);
  const results = query.trim() && catalogue
    ? filterCatalogue(catalogue, { q: query }).products : [];
  useEffect(() => {
    const opener = document.activeElement;
    dialog.current.showModal();
    input.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    let active = true;
    loadCatalogue().then((data) => active && setCatalogue(data))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
      document.body.style.overflow = overflow;
      opener?.focus();
    };
  }, []);
  return createPortal(
    <dialog ref={dialog} className="search-dialog" aria-labelledby="search-title" onClose={onClose}
      onClick={(e) => e.target === e.currentTarget && dialog.current.close()}>
      <div className="search-panel">
        <div className="search-panel-heading"><p className="eyebrow">FOLLOW YOUR CURIOSITY</p>
          <button className="icon" aria-label="Close search" onClick={() => dialog.current.close()}><X size={22} /></button></div>
        <h2 id="search-title">What draws you in?</h2>
        <form className="search-panel-field" onSubmit={(event) => { event.preventDefault(); navigate(`/shop?q=${encodeURIComponent(query.trim())}`); onClose(); }}>
          <Search size={22} aria-hidden="true" />
          <input ref={input} aria-label="Search fragrances, houses or notes" name="q" type="search"
            autoComplete="off" placeholder="A fragrance, a house, a favourite note…" value={query}
            onChange={(e) => setQuery(e.target.value)} />
          <button className="icon" aria-label="View all search results"><ArrowRight size={22} /></button>
        </form>
        {query.trim() ? <>
          <p className="metadata" role="status">{!catalogue ? failed ? "Search is taking a moment. Try the full collection." : "Opening the collection…" : `${results.length} scents found`}</p>
          <div className="search-results">
            {results.slice(0, 6).map((p) => <Link key={p.id} to={`/product/${p.slug}`} onClick={onClose}>
              <ProductImage src={p.image} alt="" width="64" height="76" sizes="64px" />
              <span><small>{p.brand}</small><strong>{p.name}</strong><span>From {money(p.price_from)}</span></span>
              <ArrowRight size={17} />
            </Link>)}
          </div>
          {catalogue && !results.length && <p>Try another note or house, such as “rose” or “Dior”.</p>}
          <Link className="text-link" to={`/shop?q=${encodeURIComponent(query)}`} onClick={onClose}>Explore all results <ArrowRight size={16} /></Link>
        </> : <div className="search-discover"><p className="eyebrow">START WITH A FEELING</p>
          <div className="discovery-chips">{["Fresh", "Woody", "Floral", "Amber"].map((family) =>
            <Link key={family} to={`/shop?category=${family}`} onClick={onClose}>{family} <ArrowRight size={14} /></Link>)}</div>
          <p className="metadata">Or explore a house</p><div className="search-house-links">{["Dior", "Chanel", "Tom Ford", "Diptyque"].map((brand) =>
            <Link key={brand} to={`/shop?brand=${encodeURIComponent(brand)}`} onClick={onClose}>{brand}</Link>)}</div>
        </div>}
      </div>
    </dialog>, document.body,
  );
}
