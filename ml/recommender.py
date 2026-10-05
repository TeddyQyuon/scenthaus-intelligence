"""Weighted PyTorch two towers; honest comparisons against Phase 2 baselines."""

from copy import deepcopy
from collections import deque
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F
from app.catalog import ACCORDS
from .core import ARTIFACTS, config, snapshot, write_report, save_json
from .embeddings import product_embeddings
from .baselines import evaluate_rec, rec_baseline, scorer_for


class TwoTower(nn.Module):
    def __init__(
        self, users: int, item_features: np.ndarray, c: dict, ablation: str = "full"
    ):
        super().__init__()
        self.c = c
        self.ablation = ablation
        self.user_id = nn.Embedding(users + 1, c["id_dim"], padding_idx=0)
        self.item_id = nn.Embedding(len(item_features) + 1, c["id_dim"], padding_idx=0)
        self.register_buffer(
            "features",
            torch.tensor(
                np.vstack(
                    [np.zeros((1, item_features.shape[1]), np.float32), item_features]
                )
            ),
        )
        self.user_net = nn.Sequential(
            nn.Linear(c["id_dim"] * 2 + 8, c["hidden"]),
            nn.ReLU(),
            nn.Linear(c["hidden"], c["embedding_dim"]),
        )
        self.item_net = nn.Sequential(
            nn.Linear(c["id_dim"] + item_features.shape[1], c["hidden"]),
            nn.ReLU(),
            nn.Linear(c["hidden"], c["embedding_dim"]),
        )

    def items(self, ids, known=None):
        lookup = (
            ids if known is None else torch.where(known, ids, torch.zeros_like(ids))
        )
        if self.training:
            lookup = torch.where(
                torch.rand_like(lookup.float()) < self.c["id_dropout"], 0, lookup
            )
        content = self.features[ids]
        content = (
            torch.zeros_like(content) if self.ablation == "no_content" else content
        )
        return F.normalize(
            self.item_net(torch.cat([self.item_id(lookup), content], -1)), dim=-1
        )

    def users(self, ids, recent, quiz):
        if self.training:
            ids = torch.where(
                torch.rand_like(ids.float()) < self.c["id_dropout"], 0, ids
            )
        history = self.item_id(recent).sum(1) / (recent > 0).sum(
            1, keepdim=True
        ).clamp_min(1)
        if self.ablation == "no_history":
            history = torch.zeros_like(history)
        if self.ablation == "no_quiz":
            quiz = torch.zeros_like(quiz)
        return F.normalize(
            self.user_net(torch.cat([self.user_id(ids), history, quiz], -1)), dim=-1
        )


def inputs(data: dict, cut: pd.Timestamp, c: dict) -> dict:
    weights = c["event_weights"]
    e = data["events"]
    e = e[(e.created_at < cut) & e.product_id.notna()]
    orders = data["orders"]
    orders = orders[orders.created_at < cut]
    events = pd.concat(
        [
            e[e.event_type != "purchase"][
                ["user_id", "product_id", "created_at", "event_type"]
            ],
            orders[["user_id", "product_id", "created_at"]].assign(
                event_type="purchase"
            ),
        ],
        ignore_index=True,
    )
    events = events[events.event_type.isin(weights)].sort_values(
        ["created_at", "user_id", "product_id"]
    )
    users = sorted(events.user_id.unique())
    ui = {u: i + 1 for i, u in enumerate(users)}
    ids = data["products"].id.tolist()
    ix = {pid: i + 1 for i, pid in enumerate(ids)}
    recent = np.zeros((len(users) + 1, c["recent_items"]), np.int64)
    quiz = np.zeros((len(users) + 1, 8), np.float32)
    seen = [set() for _ in range(len(users) + 1)]
    for uid, group in events.groupby("user_id"):
        values = [ix[pid] for pid in group.product_id.tolist()[-c["recent_items"] :]]
        recent[ui[uid], -len(values) :] = values
        seen[ui[uid]] = set(ix[x] for x in group.product_id)
    for row in data["quiz"][data["quiz"].created_at < cut].itertuples():
        if row.user_id in ui:
            quiz[ui[row.user_id]] = [row.weights.get(a, 0) for a in ACCORDS]
    pairs = np.array(
        [
            [ui[r.user_id], ix[r.product_id], weights[r.event_type]]
            for r in events.itertuples()
        ],
        np.float32,
    )
    pair_recent = np.zeros((len(events), c["recent_items"]), np.int64)
    histories = {}
    pending = []
    last = None
    for j, row in enumerate(events.itertuples()):
        if last is not None and row.created_at != last:
            for uid, pid in pending:
                histories.setdefault(uid, deque(maxlen=c["recent_items"])).append(pid)
            pending = []
        past = list(histories.get(row.user_id, []))
        if past:
            pair_recent[j, -len(past) :] = past
        pending.append((row.user_id, ix[row.product_id]))
        last = row.created_at

    return {
        "users": users,
        "ui": ui,
        "ids": ids,
        "recent": recent,
        "quiz": quiz,
        "seen": seen,
        "pairs": pairs,
        "pair_recent": pair_recent,
        "known": np.array([any(i + 1 in s for s in seen) for i in range(len(ids))]),
    }


def item_features(data: dict) -> np.ndarray:
    p = data["products"]
    v = data["variants"]
    prices = v.groupby("product_id").price.min().reindex(p.id).astype(float).values
    bands = np.eye(5, dtype=np.float32)[np.digitize(prices, [100, 150, 250, 400])]
    accords = np.array(
        [[float(a in r.accords) for a in ACCORDS] for r in p.itertuples()], np.float32
    )
    return np.concatenate([product_embeddings(p), accords, bands], 1)


def cached(model: TwoTower, x: dict) -> tuple:
    model.eval()
    with torch.no_grad():
        item = model.items(
            torch.arange(1, len(x["ids"]) + 1), torch.tensor(x["known"])
        ).numpy()
        user = model.users(
            torch.arange(len(x["users"]) + 1),
            torch.tensor(x["recent"]),
            torch.tensor(x["quiz"]),
        ).numpy()
    return item, user


def learn(
    data: dict, cut, until, features: np.ndarray, c: dict, ablation: str, epochs=None
):
    torch.manual_seed(c["seed"])
    np.random.seed(c["seed"])
    torch.set_num_threads(c["threads"])
    torch.use_deterministic_algorithms(True)
    rng = np.random.default_rng(c["seed"])
    x = inputs(data, cut, c)
    model = TwoTower(len(x["users"]), features, c, ablation)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=c["learning_rate"], weight_decay=c["weight_decay"]
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=c["epochs"])
    recent = torch.tensor(x["recent"])
    quiz = torch.tensor(x["quiz"])
    known = torch.tensor(x["known"])
    population = (
        np.bincount(x["pairs"][:, 1].astype(int), minlength=len(x["ids"]) + 1)[
            1:
        ].astype(float)
        + 1
    )
    population /= population.sum()
    similarity = features[:, :384] @ features[:, :384].T
    allowed = {
        uid: np.array(
            [
                i
                for i in range(1, len(x["ids"]) + 1)
                if i not in seen and x["known"][i - 1]
            ]
        )
        for uid, seen in enumerate(x["seen"])
    }
    max_pool = len(x["ids"])
    pools = np.zeros((len(x["users"]) + 1, max_pool), np.int64)
    lengths = np.zeros(len(pools), np.int64)
    cdfs = np.ones((len(pools), max_pool))
    hard = np.zeros((len(pools), max_pool, 10), np.int64)
    for uid, pool in allowed.items():
        if not len(pool):
            pool = np.arange(1, max_pool + 1)[x["known"]]
        pools[uid, : len(pool)] = pool
        lengths[uid] = len(pool)
        probability = population[pool - 1]
        probability /= probability.sum()
        cdfs[uid, : len(pool)] = np.cumsum(probability)
        for pid in range(1, max_pool + 1):
            closest = pool[
                np.argsort(similarity[pid - 1, pool - 1])[-min(10, len(pool)) :]
            ]
            hard[uid, pid - 1] = np.resize(closest, 10)
    pair_recent = torch.tensor(x["pair_recent"])
    best = -1.0
    patience = 0
    best_state = None
    best_epoch = 1
    losses = []
    for epoch in range(epochs or c["epochs"]):
        model.train()
        total = []
        permutation = rng.permutation(len(x["pairs"]))
        for start in range(0, len(permutation), c["batch_size"]):
            batch = x["pairs"][permutation[start : start + c["batch_size"]]]
            uids = batch[:, 0].astype(int)
            positive = batch[:, 1].astype(int)
            negatives = np.empty((len(uids), c["negatives"]), np.int64)
            for j in range(c["negatives"]):
                mode = rng.choice(3, len(uids), p=c["negative_mixture"])
                r = rng.random(len(uids))
                random_neg = pools[
                    uids, np.minimum((r * lengths[uids]).astype(int), lengths[uids] - 1)
                ]
                popular_neg = pools[
                    uids,
                    np.minimum((r[:, None] > cdfs[uids]).sum(1), lengths[uids] - 1),
                ]
                hard_neg = hard[uids, positive - 1, np.minimum((r * 10).astype(int), 9)]
                negatives[:, j] = np.where(
                    mode == 0, random_neg, np.where(mode == 1, popular_neg, hard_neg)
                )
            u = model.users(
                torch.tensor(uids),
                pair_recent[permutation[start : start + c["batch_size"]]],
                quiz[uids],
            )
            p = model.items(torch.tensor(positive), known[positive - 1])
            if ablation == "bpr":
                neg = torch.tensor(negatives)
                n = model.items(neg, known[neg - 1])
                loss = (
                    -F.logsigmoid((u * p).sum(1)[:, None] - (u[:, None, :] * n).sum(2))
                ).mean(1)
            else:
                candidates = np.concatenate([positive, np.array(negatives).ravel()])
                emb = model.items(torch.tensor(candidates), known[candidates - 1])
                logits = u @ emb.T / c["temperature"]
                mask = np.array(
                    [[item in x["seen"][uid] for item in candidates] for uid in uids]
                )
                mask[np.arange(len(uids)), np.arange(len(uids))] = False
                logits = logits.masked_fill(torch.tensor(mask), -1e9)
                loss = F.cross_entropy(
                    logits, torch.arange(len(uids)), reduction="none"
                )
            loss = (loss * torch.tensor(batch[:, 2])).sum() / torch.tensor(
                batch[:, 2]
            ).sum()
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
            total.append(float(loss.detach()))
        scheduler.step()
        losses.append(float(np.mean(total)))
        if epochs is not None:
            continue
        items, users = cached(model, x)
        result = evaluate_rec(
            data,
            cut,
            until,
            lambda uid: items @ users[x["ui"].get(uid, 0)],
            config("baselines")["k"],
        )
        if result["ndcg"] > best + 1e-6:
            best = result["ndcg"]
            best_state = deepcopy(model.state_dict())
            best_epoch = epoch + 1
            patience = 0
        else:
            patience += 1
        if patience >= c["patience"]:
            break
    if epochs is None:
        model.load_state_dict(best_state)
    return (
        model,
        x,
        {
            "best_epoch": best_epoch if epochs is None else epochs,
            "loss": losses,
            "validation_ndcg": best,
        },
    )


def train() -> dict:
    data = snapshot()
    c = config("recommender")
    features = item_features(data)
    rows = []
    results = {}
    baselines = json.loads((ARTIFACTS / "baselines.json").read_text())
    rows += [{"Model": name, **r} for name, r in baselines["recommender"].items()]
    folder = ARTIFACTS / "recommender"
    folder.mkdir(parents=True, exist_ok=True)
    for ablation in c["ablations"]:
        _, _, selection = learn(
            data, data["train_end"], data["val_end"], features, c, ablation
        )
        model, x, refit = learn(
            data,
            data["val_end"],
            data["end"],
            features,
            c,
            ablation,
            selection["best_epoch"],
        )
        items, users = cached(model, x)
        score = evaluate_rec(
            data,
            data["val_end"],
            data["end"],
            lambda uid: items @ users[x["ui"].get(uid, 0)],
            baselines["k"],
        )
        results[ablation] = score | {
            "epochs": selection["best_epoch"],
            "validation_ndcg": selection["validation_ndcg"],
        }
        rows.append({"Model": "two_tower:" + ablation, **score})
        if ablation == "full":
            torch.save(model.state_dict(), folder / "two_tower.pt")
        print("Two tower", ablation, score["ndcg"], flush=True)
    # Full serving model refit on the complete observed history using validation-selected epochs.
    full, x, _ = learn(
        data, data["end"], data["end"], features, c, "full", results["full"]["epochs"]
    )
    items, users = cached(full, x)
    np.savez(
        folder / "cached.npz",
        items=items,
        users=users,
        features=features,
        known=x["known"],
        user_ids=np.array(x["users"]),
        product_ids=np.array(x["ids"]),
        recent=x["recent"],
        quiz=x["quiz"],
    )
    # Export only the small user network/ID weights for NumPy cold-start inference.
    state = {
        k: v.detach().numpy() for k, v in full.state_dict().items() if k != "features"
    }
    np.savez(folder / "weights.npz", **state)
    torch.save(full.state_dict(), folder / "two_tower.pt")
    output = {
        "data_hash": data["data_hash"],
        "models": results,
        "simulated": True,
        "config": c,
    }
    save_json(folder / "metrics.json", output)
    write_report(
        "recommender",
        rows,
        f"Same exclusive 52/13/13-week split, K={baselines['k']}, novel purchase targets and eligible catalog as baselines. Actual PyTorch two towers with frozen MiniLM revision `{c['revision']}`, ID/recent item/quiz features; purchase > cart > wishlist > view weights. Random/popular/content-hard negatives exclude known positives; duplicate in-batch positives masked. Validation NDCG selects early-stopped epoch count, refit through validation before untouched test. Ablations remove the indicated inputs; BPR is a loss ablation. Final serving cache refits through all observed data. Cosine match is an alignment score, not calibrated preference probability. One recommender seed; small catalog and coarse curated accords limit validity. No commercial uplift claim. Results include baselines even if the neural model loses.",
    )
    return output


if __name__ == "__main__":
    train()
