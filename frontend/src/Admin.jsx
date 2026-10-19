import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
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
import ModelInfo from "./ModelInfo";
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
const tabPaths = {
  Overview: "/admin",
  Forecasts: "/admin/forecast",
  Inventory: "/admin/inventory",
  Customers: "/admin/customers",
  Recommendations: "/admin/recommendations",
  Experiments: "/admin/experiments",
  "Product controls": "/admin/product-controls",
  "Model health": "/admin/model-health",
};
const modelLabels = {
  seasonal_naive: "Seasonal naive",
  lightgbm: "LightGBM",
  lstm: "LSTM",
  nbeats: "N-BEATS",
};
const percent = (value) =>
  Number.isFinite(value) ? `${value.toFixed(2)}%` : "—";
const decimal = (value) => (Number.isFinite(value) ? value.toFixed(3) : "—");
const coverage = (value) =>
  Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
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
function ForecastChart({ data, revenue = false, model = "lightgbm" }) {
  if (!data) return null;
  const innerBandLabel = ["lstm", "nbeats"].includes(model)
    ? "P10–P90 learned band"
    : "80% validation interval";
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
      aria-label={`Weekly history, ${modelLabels[model] || model} forecast, ${innerBandLabel} and approximate 95 percent interval`}
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
            name="Approximate 95% interval"
            stroke="none"
            fill="#abb79d"
            fillOpacity={0.2}
          />
          <Area
            isAnimationActive={false}
            dataKey="band80"
            name={innerBandLabel}
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
    location = useLocation(),
    navigate = useNavigate(),
    [data, setData] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [dates, setDates] = useState({ start: "2024-09-30", end: "2026-10-03" }),
    [forecast, setForecast] = useState(null),
    [choice, setChoice] = useState({
      group: "all",
      key: "",
      horizon: 8,
      model: "lightgbm",
    }),
    [revenue, setRevenue] = useState(false),
    [risk, setRisk] = useState(""),
    [ab, setAb] = useState({
      visitors: 10000,
      baseline_rate: 0.04,
      relative_lift: 0.1,
      seed: 42,
    }),
    [abResult, setAbResult] = useState(null);
  const tab =
    Object.entries(tabPaths).find(([, path]) => path === location.pathname)?.[0] ||
    "Overview";
  function setTab(label) {
    navigate(tabPaths[label] || "/admin");
    setError("");
  }
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
            ? {
                sku: choice.key,
                horizon: choice.horizon,
                model: choice.model,
              }
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
          <div className="admin-actions">
            <button className="outline" disabled={loading} onClick={load}>
              <RefreshCw size={16} />
              {loading ? "Refreshing…" : "Refresh"}
            </button>
            <ModelInfo
              version={data?.monitor?.model_version}
              model={modelLabels[choice.model] || choice.model}
            />
          </div>
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
                  <ForecastChart data={forecast} revenue model={choice.model} />
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
                    Model
                    <select
                      aria-label="Forecast model"
                      value={choice.model}
                      onChange={(e) =>
                        setChoice((c) => ({ ...c, model: e.target.value }))
                      }
                    >
                      {Object.keys(evalData.forecast.comparison || {}).map(
                        (model) => (
                          <option key={model} value={model}>
                            {modelLabels[model] || model}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
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
                    {choice.key || "All SKUs"} · {modelLabels[choice.model] || choice.model}
                  </h3>
                  <ForecastChart
                    data={forecast}
                    revenue={revenue}
                    model={choice.model}
                  />
                  <p className="metadata">
                    {forecast?.interval_note || evalData.forecast.interval_note}
                  </p>
                  <Table
                    rows={forecast?.forecast}
                    columns={[
                      ["week", "Week"],
                      [
                        "lower80",
                        ["lstm", "nbeats"].includes(choice.model)
                          ? "P10"
                          : "80% lower",
                        (n) => Number(n).toFixed(1),
                      ],
                      [
                        "prediction",
                        ["lstm", "nbeats"].includes(choice.model)
                          ? "P50 / median"
                          : "Forecast",
                        (n) => Number(n).toFixed(1),
                      ],
                      [
                        "upper80",
                        ["lstm", "nbeats"].includes(choice.model)
                          ? "P90"
                          : "80% upper",
                        (n) => Number(n).toFixed(1),
                      ],
                      ["lower95", "Approx. 95% lower", (n) => Number(n).toFixed(1)],
                      ["upper95", "Approx. 95% upper", (n) => Number(n).toFixed(1)],
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
                  <h3>Forecast accuracy by model</h3>
                  <Table
                    rows={Object.entries(evalData.forecast.comparison || {}).map(
                      ([model, groups]) => ({
                        model,
                        skuWape: groups.sku?.mean?.wape,
                        categoryWape: groups.category?.mean?.wape,
                        skuSmape: groups.sku?.mean?.smape,
                        categorySmape: groups.category?.mean?.smape,
                        skuMase: groups.sku?.mean?.mase,
                        categoryMase: groups.category?.mean?.mase,
                        skuCoverage: groups.sku?.mean?.coverage80,
                        categoryCoverage: groups.category?.mean?.coverage80,
                        seeds: groups.sku?.seeds,
                      }),
                    )}
                    columns={[
                      ["model", "Model", (v) => modelLabels[v] || v],
                      ["skuWape", "SKU WAPE", percent],
                      ["categoryWape", "Category WAPE", percent],
                      ["skuSmape", "SKU sMAPE", percent],
                      ["categorySmape", "Category sMAPE", percent],
                      ["skuMase", "SKU MASE", decimal],
                      ["categoryMase", "Category MASE", decimal],
                      ["skuCoverage", "SKU interval coverage", coverage],
                      ["categoryCoverage", "Category interval coverage", coverage],
                      ["seeds", "Seeds"],
                    ]}
                  />
                  <p className="metadata">
                    WAPE and sMAPE are percentages; MASE is scale-free. SKU
                    and category scores are separate. Interval coverage refers
                    to the 80% validation interval for baselines and the
                    learned P10–P90 band for neural models. All models use the
                    same time-based test origins; the baseline remains visible
                    even when a neural model performs better.
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
                  <h3>Offline evaluation · K = 10</h3>
                  <MetricsTable metrics={evalData.recommender.metrics} />
                  <p className="metadata">
                    Exclusive cutoffs: training ends{" "}
                    {evalData.recommender.split.train_end}; validation ends{" "}
                    {evalData.recommender.split.val_end}; test ends{" "}
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
                  <h3>Two-tower ablations · K = 10</h3>
                  <MetricsTable metrics={evalData.two_tower.models} />
                  <p className="metadata">
                    Same chronological split and novel-purchase targets as the
                    baselines. One seed on simulated activity; full is the neural
                    serving model and BPR is a loss ablation. These comparisons
                    do not establish real customer preference or commercial uplift.
                  </p>
                </section>
                <section className="panel">
                  <h3>Validation-selected training</h3>
                  <Table
                    rows={Object.entries(evalData.two_tower.models).map(
                      ([name, metrics]) => ({ name, ...metrics }),
                    )}
                    columns={[
                      ["name", "Variant"],
                      ["epochs", "Selected epochs"],
                      ["validation_ndcg", "Validation NDCG@10", decimal],
                      ["users", "Test users"],
                    ]}
                  />
                  <p className="metadata">
                    Validation chooses the early-stopped epoch count. The test
                    window stays untouched by model selection; final serving
                    arrays are refitted through all observed history.
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
                    <span>LightGBM SKU WAPE</span>
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
                    Active version {data.monitor.model_version}. The optional
                    GitHub workflow produces reviewable simulated-data
                    candidates; it does not update Production. Daily retention
                    and forecast reconciliation run at 04:00 Singapore time.
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
                    Measured LightGBM SKU coverage of the nominal 80% band:{" "}
                    {(evalData.forecast.coverage80 * 100).toFixed(1)}%.
                  </p>
                  <p>{data.monitor.drift.note}</p>
                  <p className="metadata">{evalData.forecast.interval_note}</p>
                </section>
              </>
            )}
          </>
        )}
        <MerchantSaaSConsole notify={notify} />
      </main>
    </div>
  );
}
function Shield() {
  return <Activity size={36} />;
}

function MerchantSaaSConsole({ notify }) {
  const [isOpen, setIsOpen] = useState(true);
  const [subTab, setSubTab] = useState("catalog");
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [consoleError, setConsoleError] = useState("");
  const [consoleSuccess, setConsoleSuccess] = useState("");

  const [newProduct, setNewProduct] = useState({
    name: "",
    brand: "SCENTHAUS",
    category: "Woody",
    concentration: "EDP",
    gender: "Unisex",
    description: "",
    sku: "",
    sizeMl: 50,
    price: 120,
    stock: 20,
  });
  const [submittingProduct, setSubmittingProduct] = useState(false);

  const [addVariantProduct, setAddVariantProduct] = useState(null);
  const [variantForm, setVariantForm] = useState({
    sku: "",
    sizeMl: 100,
    price: 180,
    stock: 15,
  });

  const [includeSimulated, setIncludeSimulated] = useState(true);
  const [orderStatusFilter, setOrderStatusFilter] = useState("");
  const [shippingModalOrder, setShippingModalOrder] = useState(null);
  const [shippingCarrier, setShippingCarrier] = useState("SingPost");
  const [shippingTracking, setShippingTracking] = useState("");
  const [refundModalOrder, setRefundModalOrder] = useState(null);
  const [refundReason, setRefundReason] = useState("Customer requested return");
  const [refundRestock, setRefundRestock] = useState(true);

  async function fetchProducts() {
    setLoadingProducts(true);
    try {
      const res = await api.get("/tenant/catalog/products", {
        params: { include_hidden: true },
      });
      setProducts(res.data?.products || []);
    } catch {
      // In dev / unmocked test environments, keep graceful fallback
    } finally {
      setLoadingProducts(false);
    }
  }

  async function fetchOrders() {
    setLoadingOrders(true);
    try {
      const params = { include_simulated: includeSimulated };
      if (orderStatusFilter) params.status = orderStatusFilter;
      const res = await api.get("/tenant/orders", { params });
      setOrders(res.data?.orders || []);
    } catch {
      // In dev / unmocked test environments, keep graceful fallback
    } finally {
      setLoadingOrders(false);
    }
  }

  useEffect(() => {
    fetchProducts();
    fetchOrders();
  }, [includeSimulated, orderStatusFilter]);

  async function handleCreateProduct(e) {
    e.preventDefault();
    setSubmittingProduct(true);
    setConsoleError("");
    setConsoleSuccess("");
    try {
      const payload = {
        name: newProduct.name.trim(),
        brand: newProduct.brand.trim(),
        category: newProduct.category,
        concentration: newProduct.concentration,
        gender: newProduct.gender,
        description: newProduct.description.trim(),
        variants: [
          {
            sku: newProduct.sku.trim(),
            size_ml: parseInt(newProduct.sizeMl, 10),
            price: parseFloat(newProduct.price),
            stock: parseInt(newProduct.stock, 10),
            lead_time_weeks: 2,
          },
        ],
      };
      await api.post("/tenant/catalog/products", payload);
      setConsoleSuccess(`Product "${payload.name}" created successfully`);
      notify?.(`Product "${payload.name}" created successfully`);
      setNewProduct({
        name: "",
        brand: "SCENTHAUS",
        category: "Woody",
        concentration: "EDP",
        gender: "Unisex",
        description: "",
        sku: "",
        sizeMl: 50,
        price: 120,
        stock: 20,
      });
      fetchProducts();
    } catch (err) {
      setConsoleError(message(err));
    } finally {
      setSubmittingProduct(false);
    }
  }

  async function handleAddVariant(e) {
    e.preventDefault();
    if (!addVariantProduct) return;
    setConsoleError("");
    setConsoleSuccess("");
    try {
      const payload = {
        sku: variantForm.sku.trim(),
        size_ml: parseInt(variantForm.sizeMl, 10),
        price: parseFloat(variantForm.price),
        stock: parseInt(variantForm.stock, 10),
        lead_time_weeks: 2,
      };
      await api.post(
        `/tenant/catalog/products/${addVariantProduct.id}/variants`,
        payload
      );
      setConsoleSuccess(
        `Variant ${payload.sku} added to ${addVariantProduct.name}`
      );
      notify?.(`Variant ${payload.sku} added to ${addVariantProduct.name}`);
      setAddVariantProduct(null);
      fetchProducts();
    } catch (err) {
      setConsoleError(message(err));
    }
  }

  async function handleTransition(orderId, targetStatus, extras = {}) {
    setConsoleError("");
    setConsoleSuccess("");
    try {
      const payload = {
        target_status: targetStatus,
        ...extras,
      };
      await api.post(`/tenant/orders/${orderId}/transition`, payload);
      setConsoleSuccess(`Order transitioned to ${targetStatus}`);
      notify?.(`Order transitioned to ${targetStatus}`);
      fetchOrders();
      setShippingModalOrder(null);
      setRefundModalOrder(null);
    } catch (err) {
      setConsoleError(message(err));
    }
  }

  function getAvailableTransitions(status) {
    const transitions = {
      pending_payment: ["paid", "cancelled"],
      confirmed: ["fulfilling", "shipped", "refunded", "cancelled"],
      paid: ["fulfilling", "shipped", "refunded", "cancelled"],
      fulfilling: ["shipped", "refunded", "cancelled"],
      shipped: ["delivered", "refunded"],
      delivered: ["refunded"],
      partially_refunded: ["refunded"],
    };
    return transitions[status] || [];
  }

  return (
    <section className="panel merchant-console" aria-label="Merchant SaaS Console">
      <div className="merchant-console-header">
        <div>
          <p className="eyebrow">MULTI-TENANT STOREFRONT OPERATIONS</p>
          <h2 style={{ margin: "4px 0" }}>Merchant SaaS Console</h2>
          <p className="metadata">Manage your tenant catalog, SKU variants, and order fulfillment lifecycle.</p>
        </div>
        <button
          type="button"
          className="outline"
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? "Collapse Console" : "Expand Console"}
        </button>
      </div>

      {consoleError && (
        <div className="connection-notice" role="alert" style={{ margin: "16px 0" }}>
          <span>{consoleError}</span>
          <button type="button" onClick={() => setConsoleError("")}>Dismiss</button>
        </div>
      )}
      {consoleSuccess && (
        <div className="explanation" style={{ margin: "16px 0", background: "#e8efe1", color: "#364e24" }}>
          {consoleSuccess}
        </div>
      )}

      {isOpen && (
        <>
          <div className="merchant-nav" role="tablist">
            <button
              type="button"
              className={subTab === "catalog" ? "active" : ""}
              onClick={() => setSubTab("catalog")}
            >
              Catalog & Products ({products.length})
            </button>
            <button
              type="button"
              className={subTab === "orders" ? "active" : ""}
              onClick={() => setSubTab("orders")}
            >
              Orders & Fulfilment ({orders.length})
            </button>
          </div>

          {subTab === "catalog" && (
            <div>
              <div className="panel" style={{ background: "#fbfbfa", marginBottom: "28px" }}>
                <h3>Create New Tenant Product</h3>
                <p className="metadata" style={{ marginBottom: "18px" }}>
                  Add a fragrance to your store catalog via <code>POST /tenant/catalog/products</code>.
                </p>
                <form onSubmit={handleCreateProduct}>
                  <div className="merchant-form-grid">
                    <label>
                      Product Name *
                      <input
                        type="text"
                        required
                        minLength={2}
                        maxLength={100}
                        value={newProduct.name}
                        onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                        placeholder="e.g. Amber Reverie"
                      />
                    </label>
                    <label>
                      Brand *
                      <input
                        type="text"
                        required
                        minLength={2}
                        maxLength={100}
                        value={newProduct.brand}
                        onChange={(e) => setNewProduct({ ...newProduct, brand: e.target.value })}
                        placeholder="e.g. SCENTHAUS"
                      />
                    </label>
                    <label>
                      Category
                      <select
                        value={newProduct.category}
                        onChange={(e) => setNewProduct({ ...newProduct, category: e.target.value })}
                      >
                        <option value="Woody">Woody</option>
                        <option value="Fresh">Fresh</option>
                        <option value="Floral">Floral</option>
                        <option value="Amber">Amber</option>
                        <option value="Oriental">Oriental</option>
                      </select>
                    </label>
                    <label>
                      Concentration
                      <select
                        value={newProduct.concentration}
                        onChange={(e) => setNewProduct({ ...newProduct, concentration: e.target.value })}
                      >
                        <option value="EDP">EDP</option>
                        <option value="EDT">EDT</option>
                        <option value="Parfum">Parfum</option>
                        <option value="Cologne">Cologne</option>
                        <option value="Unverified">Unverified</option>
                      </select>
                    </label>
                    <label>
                      Gender
                      <select
                        value={newProduct.gender}
                        onChange={(e) => setNewProduct({ ...newProduct, gender: e.target.value })}
                      >
                        <option value="Unisex">Unisex</option>
                        <option value="Feminine">Feminine</option>
                        <option value="Masculine">Masculine</option>
                      </select>
                    </label>
                  </div>

                  <label style={{ display: "block", marginBottom: "16px", fontSize: "13px", fontWeight: 500 }}>
                    Description * (min 10 characters)
                    <textarea
                      required
                      minLength={10}
                      maxLength={1000}
                      rows={3}
                      style={{ width: "100%", padding: "12px", border: "1px solid #d0d3c7", marginTop: "6px", fontFamily: "inherit" }}
                      value={newProduct.description}
                      onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
                      placeholder="Sensual warm notes of golden amber, labdanum, and soft Bourbon vanilla..."
                    />
                  </label>

                  <div style={{ background: "#f2f3ee", padding: "16px", marginBottom: "18px" }}>
                    <p className="eyebrow" style={{ marginBottom: "10px" }}>INITIAL SKU VARIANT</p>
                    <div className="merchant-form-grid" style={{ marginBottom: 0 }}>
                      <label>
                        SKU Code *
                        <input
                          type="text"
                          required
                          minLength={2}
                          maxLength={40}
                          value={newProduct.sku}
                          onChange={(e) => setNewProduct({ ...newProduct, sku: e.target.value })}
                          placeholder="e.g. SCH-AMB-50"
                        />
                      </label>
                      <label>
                        Size (ml) *
                        <input
                          type="number"
                          min={1}
                          max={1000}
                          required
                          value={newProduct.sizeMl}
                          onChange={(e) => setNewProduct({ ...newProduct, sizeMl: e.target.value })}
                        />
                      </label>
                      <label>
                        Price (SGD) *
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          required
                          value={newProduct.price}
                          onChange={(e) => setNewProduct({ ...newProduct, price: e.target.value })}
                        />
                      </label>
                      <label>
                        Stock *
                        <input
                          type="number"
                          min={0}
                          required
                          value={newProduct.stock}
                          onChange={(e) => setNewProduct({ ...newProduct, stock: e.target.value })}
                        />
                      </label>
                    </div>
                  </div>

                  <button type="submit" disabled={submittingProduct}>
                    {submittingProduct ? "Creating Product…" : "Create Product"}
                  </button>
                </form>
              </div>

              <div>
                <div className="section-heading">
                  <h3>Tenant Catalog ({products.length} products)</h3>
                  <button type="button" className="outline" onClick={fetchProducts} disabled={loadingProducts}>
                    {loadingProducts ? "Loading…" : "Refresh Catalog"}
                  </button>
                </div>
                {products.length === 0 ? (
                  <p className="metadata">No products in tenant catalog.</p>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Product</th>
                          <th>Category</th>
                          <th>Concentration</th>
                          <th>Variants / Sizes</th>
                          <th>Price range</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {products.map((p) => (
                          <tr key={p.id}>
                            <td>
                              <strong>{p.name}</strong>
                              <p className="metadata">{p.brand}</p>
                            </td>
                            <td>{p.category}</td>
                            <td>{p.concentration}</td>
                            <td>
                              {p.variants?.map((v) => (
                                <span key={v.id || v.sku} style={{ display: "inline-block", background: "#f0f1ea", padding: "2px 6px", margin: "2px", fontSize: "11px" }}>
                                  {v.size_ml}ml ({v.sku}) · {money(v.price)} · Stock: {v.stock}
                                </span>
                              ))}
                            </td>
                            <td>{money(p.price_from)}</td>
                            <td>
                              <button
                                type="button"
                                className="outline"
                                style={{ minHeight: "32px", padding: "6px 12px", fontSize: "12px" }}
                                onClick={() => {
                                  setAddVariantProduct(p);
                                  setVariantForm({
                                    sku: `${p.slug || "prod"}-100`,
                                    sizeMl: 100,
                                    price: (p.price_from * 1.5).toFixed(2),
                                    stock: 15,
                                  });
                                }}
                              >
                                + Add Variant
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {subTab === "orders" && (
            <div>
              <div className="section-heading">
                <div>
                  <h3>Tenant Orders</h3>
                  <p className="metadata">Manage fulfillment, shipping dispatch, delivery confirmation, and refunds.</p>
                </div>
                <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                  <label className="check-row" style={{ fontSize: "12px" }}>
                    <input
                      type="checkbox"
                      checked={includeSimulated}
                      onChange={(e) => setIncludeSimulated(e.target.checked)}
                    />
                    Include simulated orders
                  </label>
                  <select
                    value={orderStatusFilter}
                    onChange={(e) => setOrderStatusFilter(e.target.value)}
                    style={{ minHeight: "38px", padding: "6px 12px", fontSize: "12px" }}
                  >
                    <option value="">All statuses</option>
                    <option value="pending_payment">Pending payment</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="paid">Paid</option>
                    <option value="fulfilling">Fulfilling</option>
                    <option value="shipped">Shipped</option>
                    <option value="delivered">Delivered</option>
                    <option value="refunded">Refunded</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                  <button type="button" className="outline" onClick={fetchOrders} disabled={loadingOrders}>
                    {loadingOrders ? "Loading…" : "Refresh Orders"}
                  </button>
                </div>
              </div>

              {orders.length === 0 ? (
                <p className="metadata">No orders found.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Order #</th>
                        <th>Date</th>
                        <th>Customer</th>
                        <th>Status</th>
                        <th>Total</th>
                        <th>Fulfillment</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((order) => {
                        const available = getAvailableTransitions(order.status);
                        const fulfilment = order.delivery_address?.fulfilment;
                        return (
                          <tr key={order.id}>
                            <td>
                              <strong>{order.order_number}</strong>
                              <p className="metadata" style={{ fontSize: "10px" }}>{order.id.slice(0, 8)}</p>
                            </td>
                            <td>
                              <span className="metadata">
                                {order.created_at ? new Date(order.created_at).toLocaleDateString() : "—"}
                              </span>
                            </td>
                            <td>
                              <div>{order.customer_name || "Guest"}</div>
                              <div className="metadata">{order.customer_email || "—"}</div>
                            </td>
                            <td>
                              <span className={`status-badge ${order.status}`}>
                                {order.status}
                              </span>
                              <div className="metadata" style={{ marginTop: "4px" }}>
                                Pay: {order.payment_status}
                              </div>
                            </td>
                            <td>
                              <strong>{money(order.total)}</strong>
                              <p className="metadata">{order.currency}</p>
                            </td>
                            <td>
                              {fulfilment ? (
                                <div style={{ fontSize: "11px" }}>
                                  <div><strong>{fulfilment.carrier}</strong></div>
                                  <div className="metadata">{fulfilment.tracking_number}</div>
                                </div>
                              ) : (
                                <span className="metadata">—</span>
                              )}
                            </td>
                            <td>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                                {available.includes("fulfilling") && (
                                  <button
                                    type="button"
                                    className="outline"
                                    style={{ minHeight: "30px", padding: "4px 8px", fontSize: "11px" }}
                                    onClick={() => handleTransition(order.id, "fulfilling")}
                                  >
                                    Mark Fulfilling
                                  </button>
                                )}
                                {available.includes("shipped") && (
                                  <button
                                    type="button"
                                    className="outline"
                                    style={{ minHeight: "30px", padding: "4px 8px", fontSize: "11px" }}
                                    onClick={() => {
                                      setShippingModalOrder(order);
                                      setShippingCarrier("SingPost");
                                      setShippingTracking("");
                                    }}
                                  >
                                    Ship…
                                  </button>
                                )}
                                {available.includes("delivered") && (
                                  <button
                                    type="button"
                                    className="outline"
                                    style={{ minHeight: "30px", padding: "4px 8px", fontSize: "11px" }}
                                    onClick={() => handleTransition(order.id, "delivered")}
                                  >
                                    Mark Delivered
                                  </button>
                                )}
                                {available.includes("refunded") && (
                                  <button
                                    type="button"
                                    className="outline"
                                    style={{ minHeight: "30px", padding: "4px 8px", fontSize: "11px" }}
                                    onClick={() => {
                                      setRefundModalOrder(order);
                                      setRefundReason("Customer return");
                                      setRefundRestock(true);
                                    }}
                                  >
                                    Refund…
                                  </button>
                                )}
                                {available.includes("cancelled") && (
                                  <button
                                    type="button"
                                    className="outline"
                                    style={{ minHeight: "30px", padding: "4px 8px", fontSize: "11px" }}
                                    onClick={() => handleTransition(order.id, "cancelled", { reason: "Merchant cancelled" })}
                                  >
                                    Cancel
                                  </button>
                                )}
                                {available.includes("paid") && (
                                  <button
                                    type="button"
                                    className="outline"
                                    style={{ minHeight: "30px", padding: "4px 8px", fontSize: "11px" }}
                                    onClick={() => handleTransition(order.id, "paid")}
                                  >
                                    Mark Paid
                                  </button>
                                )}
                                {available.length === 0 && (
                                  <span className="metadata">Completed</span>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Shipping Modal */}
          {shippingModalOrder && (
            <div className="merchant-modal" role="dialog" aria-modal="true">
              <div className="merchant-modal-box">
                <h3>Ship Order {shippingModalOrder.order_number}</h3>
                <p className="metadata" style={{ margin: "8px 0 16px" }}>
                  Provide shipping carrier and tracking number to notify customer and mark order shipped.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleTransition(shippingModalOrder.id, "shipped", {
                      carrier: shippingCarrier,
                      tracking_number: shippingTracking,
                    });
                  }}
                >
                  <label style={{ display: "block", marginBottom: "12px", fontSize: "13px", fontWeight: 500 }}>
                    Carrier *
                    <input
                      type="text"
                      required
                      value={shippingCarrier}
                      onChange={(e) => setShippingCarrier(e.target.value)}
                      placeholder="e.g. SingPost, DHL, FedEx"
                      style={{ width: "100%", marginTop: "4px" }}
                    />
                  </label>
                  <label style={{ display: "block", marginBottom: "20px", fontSize: "13px", fontWeight: 500 }}>
                    Tracking Number *
                    <input
                      type="text"
                      required
                      value={shippingTracking}
                      onChange={(e) => setShippingTracking(e.target.value)}
                      placeholder="e.g. SG123456789"
                      style={{ width: "100%", marginTop: "4px" }}
                    />
                  </label>
                  <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      className="outline"
                      onClick={() => setShippingModalOrder(null)}
                    >
                      Cancel
                    </button>
                    <button type="submit">Confirm Dispatch</button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Refund Modal */}
          {refundModalOrder && (
            <div className="merchant-modal" role="dialog" aria-modal="true">
              <div className="merchant-modal-box">
                <h3>Refund Order {refundModalOrder.order_number}</h3>
                <p className="metadata" style={{ margin: "8px 0 16px" }}>
                  Record refund and optionally return inventory items back to stock.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleTransition(refundModalOrder.id, "refunded", {
                      reason: refundReason,
                      restock: refundRestock,
                    });
                  }}
                >
                  <label style={{ display: "block", marginBottom: "12px", fontSize: "13px", fontWeight: 500 }}>
                    Refund Reason
                    <input
                      type="text"
                      value={refundReason}
                      onChange={(e) => setRefundReason(e.target.value)}
                      placeholder="e.g. Customer return"
                      style={{ width: "100%", marginTop: "4px" }}
                    />
                  </label>
                  <label className="check-row" style={{ display: "flex", alignItems: "center", margin: "14px 0 20px" }}>
                    <input
                      type="checkbox"
                      checked={refundRestock}
                      onChange={(e) => setRefundRestock(e.target.checked)}
                    />
                    Restock order items back into inventory
                  </label>
                  <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      className="outline"
                      onClick={() => setRefundModalOrder(null)}
                    >
                      Cancel
                    </button>
                    <button type="submit">Process Refund</button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Add Variant Modal */}
          {addVariantProduct && (
            <div className="merchant-modal" role="dialog" aria-modal="true">
              <div className="merchant-modal-box">
                <h3>Add Variant to {addVariantProduct.name}</h3>
                <p className="metadata" style={{ margin: "8px 0 16px" }}>
                  Create an additional SKU size and price for this fragrance.
                </p>
                <form onSubmit={handleAddVariant}>
                  <label style={{ display: "block", marginBottom: "12px", fontSize: "13px", fontWeight: 500 }}>
                    SKU Code *
                    <input
                      type="text"
                      required
                      minLength={2}
                      maxLength={40}
                      value={variantForm.sku}
                      onChange={(e) => setVariantForm({ ...variantForm, sku: e.target.value })}
                      placeholder="e.g. SCH-PROD-100"
                      style={{ width: "100%", marginTop: "4px" }}
                    />
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px", marginBottom: "20px" }}>
                    <label style={{ fontSize: "13px", fontWeight: 500 }}>
                      Size (ml) *
                      <input
                        type="number"
                        min={1}
                        max={1000}
                        required
                        value={variantForm.sizeMl}
                        onChange={(e) => setVariantForm({ ...variantForm, sizeMl: e.target.value })}
                        style={{ width: "100%", marginTop: "4px" }}
                      />
                    </label>
                    <label style={{ fontSize: "13px", fontWeight: 500 }}>
                      Price (SGD) *
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        required
                        value={variantForm.price}
                        onChange={(e) => setVariantForm({ ...variantForm, price: e.target.value })}
                        style={{ width: "100%", marginTop: "4px" }}
                      />
                    </label>
                    <label style={{ fontSize: "13px", fontWeight: 500 }}>
                      Stock *
                      <input
                        type="number"
                        min={0}
                        required
                        value={variantForm.stock}
                        onChange={(e) => setVariantForm({ ...variantForm, stock: e.target.value })}
                        style={{ width: "100%", marginTop: "4px" }}
                      />
                    </label>
                  </div>
                  <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      className="outline"
                      onClick={() => setAddVariantProduct(null)}
                    >
                      Cancel
                    </button>
                    <button type="submit">Add Variant</button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
