import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Download,
  RefreshCw,
  LayoutDashboard,
  TrendingUp,
  Boxes,
  Users,
  Sparkles,
  FlaskConical,
  SlidersHorizontal,
  Activity,
} from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { useShop } from "./context";
import { api, money, message, download } from "./api";
import { ErrorBox, MetricsTable } from "./App";
const tabs = [
  ["Overview", LayoutDashboard],
  ["Forecasts", TrendingUp],
  ["Inventory", Boxes],
  ["Customers", Users],
  ["Recommendations", Sparkles],
  ["Experiments", FlaskConical],
  ["Product controls", SlidersHorizontal],
  ["Model health", Activity],
];
function Table({ rows, columns }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(([key, label]) => (
              <th key={key}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows?.map((row, i) => (
            <tr key={row.sku || row.id || row.name || i}>
              {columns.map(([key, label, render]) => (
                <td key={key}>{render ? render(row[key], row) : row[key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows?.length && <p className="metadata">No records in this range.</p>}
    </div>
  );
}
function ForecastChart({ data, revenue = false }) {
  if (!data) return null;
  const rows = [
    ...data.history
      .slice(-26)
      .map((r) => ({ week: r.week, actual: revenue ? r.revenue : r.actual })),
    ...data.forecast.map((r) => {
      const ratio = revenue ? r.revenue / Math.max(r.prediction, 0.0001) : 1;
      return {
        week: r.week,
        prediction: revenue ? r.revenue : r.prediction,
        band80: [r.lower80 * ratio, r.upper80 * ratio],
        band95: [r.lower95 * ratio, r.upper95 * ratio],
      };
    }),
  ];
  return (
    <div
      className="chart"
      role="img"
      aria-label="Weekly history, forecast and 80 and 95 percent uncertainty bands"
    >
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart
          data={rows}
          margin={{ top: 15, right: 16, left: 0, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="week"
            tickFormatter={(s) => s.slice(5)}
            minTickGap={38}
          />
          <YAxis
            width={65}
            tickFormatter={(n) =>
              revenue ? `$${Math.round(n / 1000)}k` : Math.round(n)
            }
          />
          <Tooltip
            formatter={(v) =>
              Array.isArray(v)
                ? v.map((n) => Math.round(n)).join(" – ")
                : revenue
                  ? money(v)
                  : Number(v).toFixed(1)
            }
          />
          <Legend />
          <Area
            isAnimationActive={false}
            dataKey="band95"
            name="95% interval"
            stroke="none"
            fill="#abb79d"
            fillOpacity={0.2}
          />
          <Area
            isAnimationActive={false}
            dataKey="band80"
            name="80% interval"
            stroke="none"
            fill="#7f946c"
            fillOpacity={0.35}
          />
          <Line
            isAnimationActive={false}
            dataKey="actual"
            name="Actual"
            stroke="#272d22"
            strokeWidth={2}
            dot={false}
          />
          <Line
            isAnimationActive={false}
            dataKey="prediction"
            name="Forecast"
            stroke="#a06a35"
            strokeDasharray="5 4"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
function SalesChart({ rows }) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="week"
            tickFormatter={(s) => s.slice(0, 7)}
            minTickGap={50}
          />
          <YAxis
            width={65}
            tickFormatter={(n) => `$${Math.round(n / 1000)}k`}
          />
          <Tooltip formatter={(v) => money(v)} />
          <Area
            isAnimationActive={false}
            dataKey="revenue"
            stroke="#566444"
            fill="#aab69b"
            fillOpacity={0.35}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
export default function Admin() {
  const { user, notify } = useShop(),
    [tab, setTab] = useState("Overview"),
    [data, setData] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [dates, setDates] = useState({ start: "2024-09-30", end: "2026-10-03" }),
    [forecast, setForecast] = useState(null),
    [choice, setChoice] = useState({ group: "all", key: "", horizon: 8 }),
    [revenue, setRevenue] = useState(false),
    [risk, setRisk] = useState(""),
    [ab, setAb] = useState({
      visitors: 10000,
      baseline_rate: 0.04,
      relative_lift: 0.1,
      seed: 42,
    }),
    [abResult, setAbResult] = useState(null),
    [experiment, setExperiment] = useState("two_tower");
  async function load() {
    if (user.role !== "admin") return;
    setLoading(true);
    setError("");
    try {
      const names = [
        "overview",
        "inventory",
        "segments",
        "evaluation",
        "monitor",
        "models",
        "products",
        "tracking",
      ];
      const values = await Promise.all(
        names.map((n) =>
          api.get(`/admin/${n}`, { params: n === "overview" ? dates : {} }),
        ),
      );
      setData(Object.fromEntries(names.map((n, i) => [n, values[i].data])));
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, [user.id]);
  useEffect(() => {
    if (user.role !== "admin") return;
    let active = true;
    const url = choice.group === "sku" ? "/forecast/sku" : "/forecast/summary";
    api
      .get(url, {
        params:
          choice.group === "sku"
            ? { sku: choice.key, horizon: choice.horizon }
            : choice,
      })
      .then((r) => active && setForecast(r.data))
      .catch((e) => active && setError(message(e)));
    return () => {
      active = false;
    };
  }, [choice, user.role]);
  async function exportCsv(kind) {
    try {
      const r = await api.get("/admin/export", {
        params: { kind, ...dates },
        responseType: "text",
      });
      download(r.data, `scenthaus-${kind}.csv`, "text/csv");
    } catch (e) {
      setError(message(e));
    }
  }
  async function control(p, key, value) {
    try {
      await api.put(`/admin/products/${p.id}`, {
        pinned:
          key === "pinned"
            ? value
            : key === "hidden" && value
              ? false
              : p.pinned,
        hidden:
          key === "hidden"
            ? value
            : key === "pinned" && value
              ? false
              : p.hidden,
      });
      await load();
      notify("Recommendation control saved");
    } catch (e) {
      setError(message(e));
    }
  }
  if (user.role !== "admin")
    return (
      <div className="full-state">
        <Shield />
        <h1>Admin access required.</h1>
        <p>
          Sign in with your administrator account to view business intelligence.
        </p>
        <Link className="button" to="/account">
          Go to sign in
        </Link>
        <Link to="/">Return to storefront</Link>
      </div>
    );
  const k = data?.overview.kpis,
    evalData = data?.evaluation;
  const groupOptions =
    choice.group === "brand"
      ? [...new Set(data?.products.map((p) => p.brand))]
      : choice.group === "category"
        ? ["Fresh", "Woody", "Floral", "Amber"]
        : choice.group === "sku"
          ? data?.inventory.map((i) => i.sku)
          : [];
  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <Link className="wordmark" to="/">
          SCENTHAUS
        </Link>
        <p className="eyebrow">INTELLIGENCE STUDIO</p>
        <nav>
          {tabs.map(([label, Icon]) => (
            <button
              className={tab === label ? "active" : ""}
              key={label}
              onClick={() => {
                setTab(label);
                setError("");
              }}
            >
              <Icon size={17} />
              {label}
            </button>
          ))}
        </nav>
        <Link className="back-shop" to="/">
          Back to storefront <ArrowUpRight size={15} />
        </Link>
        <span className="demo-badge">SIMULATED DATA</span>
      </aside>
      <main className="admin-main">
        <div className="admin-heading">
          <div>
            <p className="eyebrow">SCENTHAUS / INTELLIGENCE</p>
            <h1>{tab}.</h1>
            <p className="metadata">
              A portfolio demonstration · SGD · No real customer history
            </p>
          </div>
          <button className="outline" disabled={loading} onClick={load}>
            <RefreshCw size={16} />
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        <ErrorBox error={error} />
        {!data ? (
          <p>Loading intelligence…</p>
        ) : (
          <>
            {tab === "Overview" && (
              <>
                <div className="admin-filters">
                  <label>
                    From
                    <input
                      aria-label="From date"
                      type="date"
                      value={dates.start}
                      onChange={(e) =>
                        setDates((d) => ({ ...d, start: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    To
                    <input
                      aria-label="To date"
                      type="date"
                      value={dates.end}
                      onChange={(e) =>
                        setDates((d) => ({ ...d, end: e.target.value }))
                      }
                    />
                  </label>
                  <button onClick={load}>Apply dates</button>
                  <button
                    className="outline"
                    onClick={() => exportCsv("sales")}
                  >
                    <Download size={16} /> Export sales
                  </button>
                </div>
                <div className="kpi-grid">
                  {[
                    [
                      "Revenue",
                      new Intl.NumberFormat("en-SG", {
                        style: "currency",
                        currency: "SGD",
                        notation: "compact",
                        maximumFractionDigits: 2,
                      }).format(k.revenue),
                    ],
                    ["Orders", k.orders.toLocaleString()],
                    ["Average order", money(k.aov)],
                    ["Conversion", `${(k.conversion * 100).toFixed(1)}%`],
                    ["Repeat rate", `${(k.repeat_rate * 100).toFixed(1)}%`],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
                <section className="panel">
                  <h3>Sales over time</h3>
                  <SalesChart rows={data.overview.weekly} />
                  <p className="metadata">
                    Revenue at transaction prices. Conversion uses observed
                    consented view users; simulated views follow the generator’s
                    patterns.
                  </p>
                </section>
                <section className="panel">
                  <h3>Revenue outlook & uncertainty</h3>
                  <ForecastChart data={forecast} revenue />
                  <p className="metadata">
                    Forecasts use current prices. Aggregate bands sum SKU
                    intervals and are conservative.
                  </p>
                </section>
                <div className="admin-columns">
                  <section className="panel">
                    <h3>Top products</h3>
                    <Table
                      rows={data.overview.top_products}
                      columns={[
                        ["name", "Scent"],
                        ["units", "Units"],
                        ["revenue", "Revenue", money],
                      ]}
                    />
                  </section>
                  <section className="panel">
                    <h3>Houses & size mix</h3>
                    <Table
                      rows={data.overview.brands}
                      columns={[
                        ["brand", "House"],
                        ["revenue", "Revenue", money],
                      ]}
                    />
                    <Table
                      rows={data.overview.size_mix}
                      columns={[
                        ["size_ml", "Size (ml)"],
                        ["units", "Units"],
                      ]}
                    />
                  </section>
                </div>
              </>
            )}
            {tab === "Forecasts" && (
              <>
                <div className="admin-filters">
                  <label>
                    Level
                    <select
                      aria-label="Forecast level"
                      value={choice.group}
                      onChange={(e) => {
                        const g = e.target.value;
                        setChoice((c) => ({
                          ...c,
                          group: g,
                          key:
                            g === "brand"
                              ? data.products[0].brand
                              : g === "category"
                                ? "Fresh"
                                : g === "sku"
                                  ? data.inventory[0].sku
                                  : "",
                        }));
                      }}
                    >
                      {["all", "brand", "category", "sku"].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </label>
                  {choice.group !== "all" && (
                    <label>
                      Group
                      <select
                        aria-label="Forecast group"
                        value={choice.key}
                        onChange={(e) =>
                          setChoice((c) => ({ ...c, key: e.target.value }))
                        }
                      >
                        {groupOptions?.map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label>
                    Horizon
                    <select
                      aria-label="Forecast horizon"
                      value={choice.horizon}
                      onChange={(e) =>
                        setChoice((c) => ({
                          ...c,
                          horizon: Number(e.target.value),
                        }))
                      }
                    >
                      {[4, 8, 12].map((v) => (
                        <option key={v} value={v}>
                          {v} weeks
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="check-row">
                    <input
                      type="checkbox"
                      checked={revenue}
                      onChange={(e) => setRevenue(e.target.checked)}
                    />{" "}
                    Revenue
                  </label>
                </div>
                <section className="panel">
                  <h3>
                    Weekly {revenue ? "revenue" : "demand"} ·{" "}
                    {choice.key || "All SKUs"}
                  </h3>
                  <ForecastChart data={forecast} revenue={revenue} />
                  <p className="metadata">
                    {forecast?.interval_note || evalData.forecast.interval_note}
                  </p>
                  <Table
                    rows={forecast?.forecast}
                    columns={[
                      ["week", "Week"],
                      ["prediction", "Units", (n) => n.toFixed(1)],
                      ["lower80", "80% lower", (n) => n.toFixed(1)],
                      ["upper80", "80% upper", (n) => n.toFixed(1)],
                      ["lower95", "95% lower", (n) => n.toFixed(1)],
                      ["upper95", "95% upper", (n) => n.toFixed(1)],
                      ["revenue", "Revenue", money],
                    ]}
                  />
                </section>
                <section className="panel">
                  <h3>Untouched holdout: forecast vs actual</h3>
                  <p className="metadata">
                    Origin {evalData.forecast.test_origin} · Live snapshots are
                    reconciled by the daily worker when complete weeks arrive.
                  </p>
                  <Table
                    rows={data.tracking.holdout
                      .filter(
                        (r) => choice.group !== "sku" || r.sku === choice.key,
                      )
                      .slice(0, 16)}
                    columns={[
                      ["sku", "SKU"],
                      ["week", "Week"],
                      ["actual", "Actual"],
                      ["prediction", "Forecast", (v) => v.toFixed(1)],
                    ]}
                  />
                  <button
                    className="outline"
                    onClick={() => exportCsv("tracking")}
                  >
                    Export full tracking CSV
                  </button>
                </section>
                <section className="panel">
                  <h3>Saved forecasts & arriving actuals</h3>
                  <Table rows={data.tracking.live.filter(r=>choice.group!=="sku"||r.sku===choice.key).slice(0,24)} columns={[
                    ["sku","SKU"],["week","Week"],["prediction","Saved forecast",v=>v.toFixed(1)],
                    ["actual","Actual",v=>v==null?"Awaiting completed week":v],
                    ["version","Model version"]
                  ]}/>
                  <p className="metadata">Forecasts are saved before outcomes arrive. Refresh after the daily worker reconciles completed weeks.</p>
                </section>
                <section className="panel">
                  <h3>Model ladder</h3>
                  <Table
                    rows={Object.entries(
                      evalData.forecast.model_macro_sku_wape,
                    ).map(([model, wape]) => ({
                      model,
                      wape,
                      count: evalData.forecast.selection_counts[model],
                    }))}
                    columns={[
                      ["model", "Model"],
                      ["wape", "Macro SKU WAPE", (n) => `${n.toFixed(1)}%`],
                      ["count", "Selected SKUs"],
                    ]}
                  />
                  <p className="metadata">
                    Macro SKU scores are not directly comparable to
                    volume-weighted selected-model WAPE. Model selection uses
                    three expanding validation origins.
                  </p>
                </section>
              </>
            )}
            {tab === "Inventory" && (
              <>
                <div className="admin-filters">
                  <select
                    aria-label="Inventory risk"
                    value={risk}
                    onChange={(e) => setRisk(e.target.value)}
                  >
                    <option value="">All risks</option>
                    {["stockout", "reorder", "overstock", "healthy"].map(
                      (v) => (
                        <option key={v}>{v}</option>
                      ),
                    )}
                  </select>
                  <button
                    className="outline"
                    onClick={() => exportCsv("inventory")}
                  >
                    <Download size={16} /> Export inventory
                  </button>
                </div>
                <section className="panel">
                  <h3>Replenishment decisions</h3>
                  <p className="metadata">
                    Suggested quantities are decision support. An administrator
                    reviews each purchase order.
                  </p>
                  <Table
                    rows={data.inventory.filter(
                      (i) => !risk || i.risk === risk,
                    )}
                    columns={[
                      [
                        "sku",
                        "SKU",
                        (v, r) => (
                          <button
                            className="why"
                            onClick={() => {
                              setChoice({ group: "sku", key: v, horizon: 8 });
                              setTab("Forecasts");
                            }}
                          >
                            {v}
                          </button>
                        ),
                      ],
                      ["name", "Scent"],
                      ["stock", "On hand"],
                      [
                        "risk",
                        "Risk",
                        (v) => <span className={`risk ${v}`}>{v}</span>,
                      ],
                      ["safety_stock", "Safety"],
                      ["reorder_point", "Reorder point"],
                      ["suggested_reorder", "Suggested qty"],
                      [
                        "trend",
                        "Recent trend",
                        (n) => `${(n * 100).toFixed(0)}%`,
                      ],
                    ]}
                  />
                </section>
              </>
            )}
            {tab === "Customers" && (
              <>
                <div className="kpi-grid">
                  {data.segments.segments.map((s) => (
                    <div key={s.cluster}>
                      <span>{s.label}</span>
                      <strong>{s.customers}</strong>
                      <p>
                        {s.orders.toFixed(1)} orders · {money(s.aov)} AOV
                      </p>
                    </div>
                  ))}
                </div>
                <section className="panel">
                  <h3>RFM + K-Means</h3>
                  <Table
                    rows={data.segments.segments}
                    columns={[
                      ["label", "Segment"],
                      ["recency_days", "Recency (days)", (n) => n.toFixed(1)],
                      ["orders", "Frequency", (n) => n.toFixed(1)],
                      ["spend", "Lifetime spend", money],
                      ["aov", "AOV", money],
                    ]}
                  />
                  <p>{data.segments.note}</p>
                </section>
              </>
            )}
            {tab === "Recommendations" && (
              <>
                <section className="panel">
                  <h3>Offline evaluation · K = 5</h3>
                  <MetricsTable metrics={evalData.recommender.metrics} />
                  <p className="metadata">
                    Time split: validation{" "}
                    {evalData.recommender.split.validation_start}; test{" "}
                    {evalData.recommender.split.test_start} to{" "}
                    {evalData.recommender.split.test_end}. Tuned weights{" "}
                    {evalData.recommender.weights.join(" / ")} for content / CF
                    / popularity. Serving additionally applies filters and MMR;
                    this table measures the underlying rankers.
                  </p>
                </section>
                <section className="panel">
                  <h3>Performance by placement</h3>
                  <Table
                    rows={data.overview.performance}
                    columns={[
                      ["slot", "Placement"],
                      ["impressions", "Impressions"],
                      ["clicks", "Clicks"],
                      ["ctr", "CTR", (n) => `${(n * 100).toFixed(1)}%`],
                      [
                        "add_to_cart_rate",
                        "Add-to-cart rate",
                        (n) => `${(n * 100).toFixed(1)}%`,
                      ],
                      ["attributed_revenue", "Revenue", money],
                    ]}
                  />
                  <p className="metadata">
                    {data.overview.attribution} Synthetic historical browsing
                    has no minted recommendation references, so attributed
                    performance begins with interactions in this application.
                  </p>
                </section>
              </>
            )}
            {tab === "Experiments" && (
              <>
                <section className="panel">
                  <h3>A/B test simulator</h3>
                  <p>
                    Random assignment, simulated conversions, two-sided
                    proportion test and 95% difference interval.
                  </p>
                  <form
                    className="admin-filters"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      try {
                        setAbResult(
                          (await api.post("/admin/ab-simulate", ab)).data,
                        );
                      } catch (er) {
                        setError(message(er));
                      }
                    }}
                  >
                    {[
                      ["visitors", "Visitors", 100, 200000, 100],
                      ["baseline_rate", "Baseline rate", 0.001, 0.49, 0.001],
                      ["relative_lift", "Assumed lift", -0.9, 1, 0.01],
                      ["seed", "Seed", 0, 999999, 1],
                    ].map(([key, label, min, max, step]) => (
                      <label key={key}>
                        {label}
                        <input
                          aria-label={label}
                          type="number"
                          min={min}
                          max={max}
                          step={step}
                          required
                          value={ab[key]}
                          onChange={(e) =>
                            setAb((a) => ({
                              ...a,
                              [key]: Number(e.target.value),
                            }))
                          }
                        />
                      </label>
                    ))}
                    <button>Run simulation</button>
                  </form>
                  {abResult && (
                    <div className="notice">
                      <p>
                        Control {(abResult.rates[0] * 100).toFixed(2)}% ·
                        Treatment {(abResult.rates[1] * 100).toFixed(2)}% ·
                        Observed lift{" "}
                        {abResult.relative_lift == null
                          ? "undefined"
                          : `${(abResult.relative_lift * 100).toFixed(1)}%`}
                      </p>
                      <p>
                        p = {abResult.p_value.toFixed(4)} · Difference CI:{" "}
                        {abResult.difference_95_ci
                          .map((v) => `${(v * 100).toFixed(2)}pp`)
                          .join(" to ")}
                      </p>
                      <p>{abResult.note}</p>
                    </div>
                  )}
                </section>
                <section className="panel">
                  <h3>Neural recommendation experiments</h3>
                  <select
                    aria-label="Neural experiment"
                    value={experiment}
                    onChange={(e) => setExperiment(e.target.value)}
                  >
                    <option value="two_tower">Two-tower</option>
                    <option value="item2vec">Session skip-gram</option>
                  </select>
                  <div className="chart">
                    <ResponsiveContainer width="100%" height={240}>
                      <ComposedChart
                        data={evalData.experiments[
                          experiment === "two_tower"
                            ? "two_tower_loss"
                            : "item2vec_loss"
                        ].map((loss, i) => ({ epoch: i + 1, loss }))}
                      >
                        <XAxis dataKey="epoch" />
                        <YAxis domain={["auto", "auto"]} />
                        <Tooltip />
                        <Line dataKey="loss" stroke="#60704c" dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                  <p>{evalData.experiments.note}</p>
                  <p className="metadata">
                    Opt-in serving: /recommend/user?experiment=two_tower or
                    item2vec. Neural training loss is not offline recommendation
                    quality.
                  </p>
                </section>
                <section className="panel">
                  <h3>Price response by size</h3>
                  <Table
                    rows={evalData.experiments.elasticity.slice(0, 24)}
                    columns={[
                      ["sku", "SKU"],
                      [
                        "coefficient",
                        "Log-price coefficient",
                        (v) => v.toFixed(3),
                      ],
                      ["weeks", "Weeks"],
                      ["r_squared", "Training R²", (v) => v.toFixed(3)],
                    ]}
                  />
                  <p className="metadata">
                    Associations from synthetic promotion prices. These
                    coefficients are not causal elasticity or an automated
                    pricing recommendation.
                  </p>
                </section>
              </>
            )}
            {tab === "Product controls" && (
              <section className="panel">
                <div className="section-heading">
                  <h3>Human recommendation overrides</h3>
                  <button
                    className="outline"
                    onClick={() => exportCsv("products")}
                  >
                    Export controls
                  </button>
                </div>
                <p className="metadata">
                  Pin up to two eligible products at the top of a placement.
                  Hidden products are removed from storefront results. All edits
                  are recorded in the audit log.
                </p>
                {data.products.map((p) => (
                  <div className="control-row" key={p.id}>
                    <div>
                      <strong>{p.name}</strong>
                      <p className="metadata">{p.brand}</p>
                    </div>
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={p.pinned}
                        onChange={(e) => control(p, "pinned", e.target.checked)}
                      />{" "}
                      Pin
                    </label>
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={p.hidden}
                        onChange={(e) => control(p, "hidden", e.target.checked)}
                      />{" "}
                      Hide
                    </label>
                    <div className="stock-forms">
                      {p.variants.map((v) => (
                        <form
                          key={v.id}
                          onSubmit={async (e) => {
                            e.preventDefault();
                            try {
                              await api.put(`/admin/stock/${v.id}`, {
                                stock: Number(
                                  new FormData(e.currentTarget).get("stock"),
                                ),
                              });
                              await load();
                              notify("Stock updated");
                            } catch (er) {
                              setError(message(er));
                            }
                          }}
                        >
                          <label>
                            {v.size_ml}ml
                            <input
                              aria-label={`${p.name} ${v.size_ml}ml stock`}
                              name="stock"
                              type="number"
                              min="0"
                              max="100000"
                              defaultValue={v.stock}
                            />
                          </label>
                          <button className="outline">Save</button>
                        </form>
                      ))}
                    </div>
                  </div>
                ))}
              </section>
            )}
            {tab === "Model health" && (
              <>
                <div className="kpi-grid">
                  <div>
                    <span>API latency p95</span>
                    <strong>
                      {data.monitor.latency.p95_ms?.toFixed(0) || "—"} ms
                    </strong>
                    <p>{data.monitor.latency.samples} samples · process only</p>
                  </div>
                  <div>
                    <span>Forecast WAPE</span>
                    <strong>{evalData.forecast.wape.toFixed(1)}%</strong>
                    <p>
                      sMAPE {evalData.forecast.smape.toFixed(1)}% · MASE{" "}
                      {evalData.forecast.mase.toFixed(3)}
                    </p>
                  </div>
                  <div>
                    <span>Distribution drift PSI</span>
                    <strong>{data.monitor.drift.psi.toFixed(3)}</strong>
                    <p>
                      {data.monitor.drift.alert
                        ? "Review drift alert"
                        : "No active alert"}{" "}
                      · {data.monitor.drift.events} events
                    </p>
                  </div>
                </div>
                <section className="panel">
                  <h3>Live forecast error</h3>
                  <p>{data.monitor.live_forecast_error.observations} reconciled observations · WAPE {data.monitor.live_forecast_error.wape==null?'awaiting actuals':`${data.monitor.live_forecast_error.wape.toFixed(1)}%`}.</p>
                  <p className="metadata">Current model only. Holdout error remains visible separately.</p>
                </section>
                <section className="panel">
                  <h3>Model registry</h3>
                  <Table
                    rows={data.models}
                    columns={[
                      ["version", "Version"],
                      ["created_at", "Trained"],
                      ["data_hash", "Data fingerprint", (v) => v.slice(0, 12)],
                      ["mlflow_run_id", "MLflow run", (v) => v?.slice(0, 12)],
                    ]}
                  />
                  <p className="metadata">
                    Active version {data.monitor.model_version}. Weekly Sunday
                    retraining at 03:00 Singapore time; validation gates
                    activation. Daily retention and forecast reconciliation at
                    04:00.
                  </p>
                </section>
                <section className="panel">
                  <h3>Validation & uncertainty</h3>
                  <p>
                    Data validation{" "}
                    {evalData.validation.passed ? "passed" : "failed"} ·{" "}
                    {evalData.validation.order_lines.toLocaleString()} order
                    lines · {evalData.validation.warnings.length} price
                    warnings.
                  </p>
                  <p>
                    Measured interval coverage: 80% band{" "}
                    {(evalData.forecast.coverage80 * 100).toFixed(1)}%; 95% band{" "}
                    {(evalData.forecast.coverage95 * 100).toFixed(1)}%.
                  </p>
                  <p>{data.monitor.drift.note}</p>
                  <p className="metadata">{evalData.forecast.interval_note}</p>
                </section>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
function Shield() {
  return <Activity size={36} />;
}
