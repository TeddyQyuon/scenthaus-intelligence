import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from app.catalog import ACCORDS


def scale(values):
    v = np.asarray(values, dtype=float)
    return v / v.max() if v.max() > 0 else v


def quiz_weights(a):
    w = dict.fromkeys(ACCORDS, 0.1)
    for key, value in {
        "fresh": {"citrus": 1, "fresh": 0.9, "aquatic": 0.8},
        "warm": {"amber": 1, "sweet": 0.8, "spicy": 0.7},
        "floral": {"floral": 1, "fresh": 0.5, "sweet": 0.4},
        "woody": {"woody": 1, "spicy": 0.5, "fresh": 0.4},
    }[a["mood"]].items():
        w[key] += value
    if a["occasion"] == "office":
        w["fresh"] += 0.35
        w["citrus"] += 0.2
    if a["occasion"] == "evening":
        w["amber"] += 0.3
        w["spicy"] += 0.2
    w["fresh" if a["intensity"] == "soft" else "amber"] += 0.2
    return w


def fit(products, orders, wishes, events, cutoff=None):
    from mlxtend.frequent_patterns import apriori, association_rules

    products = products.sort_values("id").reset_index(drop=True)
    ids = products.id.tolist()
    index = {pid: i for i, pid in enumerate(ids)}
    texts = [
        " ".join(p.accords + sum(p.notes.values(), []) + p.occasions + [p.category])
        for p in products.itertuples()
    ]
    active = (
        np.ones(len(ids), bool)
        if cutoff is None
        else pd.to_datetime(products.launch_date).values <= np.datetime64(cutoff)
    )
    tf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    tf.fit([t for t, a in zip(texts, active) if a])
    x = tf.transform(texts)
    content = cosine_similarity(x)
    svd = TruncatedSVD(n_components=min(16, x.shape[0] - 1), random_state=42).fit(
        x[active]
    )
    embeddings = normalize(svd.transform(x))
    if cutoff is not None:
        orders = orders[orders.created_at < cutoff]
        wishes = wishes[wishes.created_at < cutoff]
        events = events[events.created_at < cutoff]
    users = sorted(set(orders.user_id) | set(wishes.user_id) | set(events.user_id))
    ui = {u: i for i, u in enumerate(users)}
    matrix = np.zeros((len(users), len(ids)))
    for r in orders.itertuples():
        matrix[ui[r.user_id], index[r.product_id]] += r.quantity * 3
    for r in wishes.itertuples():
        matrix[ui[r.user_id], index[r.product_id]] += 1.5
    for r in events.itertuples():
        if r.product_id in index:
            matrix[ui[r.user_id], index[r.product_id]] += {
                "view": 0.08,
                "add_to_cart": 0.7,
                "wishlist_add": 0.1,
            }.get(r.event_type, 0)
    cf = cosine_similarity(matrix.T)
    np.fill_diagonal(cf, 0)
    popularity = scale(
        orders.groupby("product_id").quantity.sum().reindex(ids, fill_value=0).values
    )
    rules = []
    if not orders.empty:
        baskets = (
            pd.crosstab(orders.order_id, orders.product_id)
            .reindex(columns=ids, fill_value=0)
            .astype(bool)
        )
        frequent = apriori(baskets, min_support=0.004, use_colnames=True, max_len=3)
        if not frequent.empty:
            ar = association_rules(
                frequent,
                metric="confidence",
                min_threshold=0.08,
                num_itemsets=len(baskets),
            )
            for r in ar[ar.lift >= 1.05].itertuples():
                rules.append(
                    {
                        "antecedents": list(r.antecedents),
                        "consequents": list(r.consequents),
                        "support": float(r.support),
                        "confidence": float(r.confidence),
                        "lift": float(r.lift),
                    }
                )
    return (
        {
            "ids": ids,
            "index": index,
            "content": content,
            "cf": cf,
            "popularity": popularity,
            "new": matrix.sum(axis=0) == 0,
            "tfidf": tf,
            "svd": svd,
            "embeddings": embeddings,
            "accords": np.array(
                [[int(a in p.accords) for a in ACCORDS] for p in products.itertuples()]
            ),
            "rules": rules,
            "weights": (0.4, 0.5, 0.1),
        },
        matrix,
        users,
    )


def scores(model, history=None, weights=None, quiz=None):
    history = history or {}
    vector = np.zeros(len(model["ids"]))
    for pid, value in history.items():
        if pid in model["index"]:
            vector[model["index"][pid]] = value
    content = (
        scale(vector @ model["content"]) if vector.sum() else model["popularity"].copy()
    )
    if quiz:
        q = np.array([quiz.get(a, 0) for a in ACCORDS])
        content = scale(cosine_similarity([q], model["accords"])[0])
    cf = scale(vector @ model["cf"])
    w = weights or model["weights"]
    hybrid = w[0] * content + w[1] * cf + w[2] * model["popularity"]
    if not vector.sum() and not quiz:
        hybrid = model["popularity"].copy()
    hybrid[model["new"]] = content[model["new"]]
    return content, cf, hybrid


def mmr(model, relevance, candidates, brands, k=8, pinned=None):
    remaining = list(candidates)
    selected = []
    pinned = pinned or []
    for i in pinned[:2]:
        if i in remaining:
            selected.append(i)
            remaining.remove(i)
    while remaining and len(selected) < k:

        def value(i):
            redundancy = max(
                [
                    model["content"][i, j] + (0.15 if brands[i] == brands[j] else 0)
                    for j in selected
                ],
                default=0,
            )
            return 0.72 * relevance[i] - 0.28 * redundancy

        best = max(remaining, key=value)
        selected.append(best)
        remaining.remove(best)
    return selected


def ranking_metrics(ranked, relevant, k=5):
    hits = [int(p in relevant) for p in ranked[:k]]
    dcg = sum(h / np.log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1 / np.log2(i + 2) for i in range(min(k, len(relevant))))
    return sum(hits) / k, sum(hits) / len(relevant), dcg / ideal if ideal else 0


def evaluate(products, orders, wishes, events):
    last = pd.to_datetime(orders.created_at).max().normalize()
    test = last - pd.Timedelta(weeks=8)
    val = test - pd.Timedelta(weeks=8)

    def run(cut, finish, weights):
        model, matrix, users = fit(products, orders, wishes, events, cut)
        ui = {u: i for i, u in enumerate(users)}
        eligible = [
            i
            for i, p in enumerate(products.sort_values("id").itertuples())
            if pd.Timestamp(p.launch_date) < cut
        ]
        history = orders[orders.created_at < cut]
        truths = orders[(orders.created_at >= cut) & (orders.created_at < finish)]
        result = {key: [] for key in ["popularity", "content", "cf", "hybrid"]}
        coverage = {key: set() for key in result}
        diversity = {key: [] for key in result}
        for u, g in truths.groupby("user_id"):
            past = set(history[history.user_id == u].product_id)
            relevant = set(g.product_id) - past
            relevant &= {model["ids"][i] for i in eligible}
            if not relevant:
                continue
            signal = (
                {model["ids"][i]: v for i, v in enumerate(matrix[ui[u]]) if v}
                if u in ui
                else {}
            )
            c, f, h = scores(model, signal, weights)
            choices = [i for i in eligible if model["ids"][i] not in past]
            for key, s in [
                ("popularity", model["popularity"]),
                ("content", c),
                ("cf", f),
                ("hybrid", h),
            ]:
                rank = sorted(choices, key=lambda i: s[i], reverse=True)[:5]
                pids = [model["ids"][i] for i in rank]
                result[key].append(ranking_metrics(pids, relevant))
                coverage[key].update(pids)
                diversity[key].append(
                    float(
                        np.mean(
                            [
                                1 - model["content"][a, b]
                                for n, a in enumerate(rank)
                                for b in rank[n + 1 :]
                            ]
                        )
                    )
                    if len(rank) > 1
                    else 0
                )
        return {
            key: dict(
                zip(
                    ["precision_at_5", "recall_at_5", "ndcg_at_5"],
                    np.mean(values, axis=0).tolist(),
                )
            )
            | {
                "coverage": len(coverage[key]) / len(eligible),
                "diversity": float(np.mean(diversity[key])),
                "users": len(values),
            }
            for key, values in result.items()
        }

    grid = [
        (0.2, 0.7, 0.1),
        (0.4, 0.5, 0.1),
        (0.6, 0.3, 0.1),
        (0.8, 0.1, 0.1),
        (0.3, 0.5, 0.2),
    ]
    # One fit per grid is intentionally simple and deterministic; only validation chooses weights.
    best = max(grid, key=lambda w: run(val, test, w)["hybrid"]["ndcg_at_5"])
    return {
        "split": {
            "validation_start": str(val.date()),
            "test_start": str(test.date()),
            "test_end": str(last.date()),
            "k": 5,
        },
        "weights": best,
        "metrics": run(test, last + pd.Timedelta(days=1), best),
    }
