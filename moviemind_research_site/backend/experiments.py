"""Offline policy comparison on the historical ratings (reward oracle = logged rating / 5).

Policies:  random | linucb_immediate | linucb_delayed | moviemind (delayed + fairness)
Each user's ratings are split 50/50: the first half builds the user-history features, the second half
supplies the candidate movies and their true rewards (no leakage). Feedback arrives DELAY rounds late.

Run:  python experiments.py --rounds 2000 --seeds 5 --delay 20
Output: results/experiments.json, results/experiments.csv, results/*.png
"""
import argparse, json, os
from collections import deque
import numpy as np
import pandas as pd

from core import GENRES, Data, LinUCB, exposure_shares, fairness_bonus, gini, load_movies, load_ratings

POLICIES = ["random", "linucb_immediate", "linucb_delayed", "moviemind"]


def split(ratings, rng):
    hist, test = [], []
    for u, g in ratings.groupby("userId"):
        g = g.sample(frac=1, random_state=int(rng.integers(1e9)))
        h = len(g) // 2
        hist.append(g.iloc[:h]); test.append(g.iloc[h:])
    return pd.concat(hist), pd.concat(test)


def run(policy, movies, hist, test, rounds, delay, k_cand, alpha, seed):
    rng = np.random.default_rng(seed)
    data = Data(movies, hist)
    users = [u for u, g in test.groupby("userId") if len(g) >= k_cand and u in data.user_stats]
    tg = {u: g for u, g in test.groupby("userId")}
    model = LinUCB(alpha=alpha)
    counts = np.zeros(len(GENRES)); queue = deque(); cum, curve = 0.0, []
    for t in range(rounds):
        while queue and queue[0][0] <= t:                         # deliver due feedback
            _, x, r = queue.popleft(); model.update(x, r)
        u = users[rng.integers(len(users))]
        g = tg[u].sample(k_cand, random_state=int(rng.integers(1e9)))
        midx = g.movieId.map(data.mid2idx).values; rew = g.rating.values / 5.0
        X = data.context(u, midx)
        if policy == "random":
            j = int(rng.integers(len(midx)))
        else:
            est, bonus = model.score(X); s = est + bonus
            if policy == "moviemind":
                s = s + fairness_bonus(data.G[midx], exposure_shares(counts))
            j = int(np.argmax(s))
        counts += data.G[midx[j]]; cum += rew[j]; curve.append(cum)
        if policy != "random":
            queue.append((t + (0 if policy == "linucb_immediate" else delay), X[j], rew[j]))
            if policy == "linucb_immediate":
                _, x, r = queue.popleft(); model.update(x, r)
    sh = exposure_shares(counts)
    return dict(cum_reward=cum, avg_reward=cum / rounds, min_genre_share=float(sh.min()),
                genres_below_5pct=int((sh < 0.05).sum()), exposure_gini=gini(counts), curve=curve)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "data"))
    ap.add_argument("--rounds", type=int, default=2000); ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--delay", type=int, default=20); ap.add_argument("--candidates", type=int, default=20)
    ap.add_argument("--alpha", type=float, default=0.7); ap.add_argument("--out", default="results")
    a = ap.parse_args()
    movies = load_movies(os.path.join(a.data, "movies.csv")); ratings = load_ratings(os.path.join(a.data, "ratings.txt"))
    os.makedirs(a.out, exist_ok=True)
    res = {p: [] for p in POLICIES}
    for s in range(a.seeds):
        hist, test = split(ratings, np.random.default_rng(1000 + s))
        for p in POLICIES:
            r = run(p, movies, hist, test, a.rounds, a.delay, a.candidates, a.alpha, seed=s)
            res[p].append(r); print(f"seed {s} {p:17s} avg_reward={r['avg_reward']:.4f} min_share={r['min_genre_share']:.4f}")
    rows = []
    for p in POLICIES:
        d = {"policy": p}
        for m in ["cum_reward", "avg_reward", "min_genre_share", "genres_below_5pct", "exposure_gini"]:
            v = np.array([r[m] for r in res[p]]); d[m + "_mean"] = float(v.mean()); d[m + "_std"] = float(v.std())
        rows.append(d)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(a.out, "experiments.csv"), index=False)
    json.dump({"args": vars(a), "summary": rows}, open(os.path.join(a.out, "experiments.json"), "w"), indent=2)
    print("\n" + df.round(4).to_string(index=False))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        plt.figure(figsize=(7, 4))
        for p in POLICIES:
            c = np.mean([r["curve"] for r in res[p]], axis=0); plt.plot(c, label=p)
        plt.xlabel("round"); plt.ylabel("cumulative reward"); plt.legend(); plt.title("Cumulative reward (mean over seeds)")
        plt.tight_layout(); plt.savefig(os.path.join(a.out, "cumulative_reward.png"), dpi=160); plt.close()
        plt.figure(figsize=(7, 4)); xs = np.arange(len(POLICIES))
        plt.bar(xs, df.min_genre_share_mean, yerr=df.min_genre_share_std); plt.xticks(xs, POLICIES, rotation=15)
        plt.ylabel("minimum genre exposure share"); plt.title("Exposure floor by policy")
        plt.tight_layout(); plt.savefig(os.path.join(a.out, "min_genre_share.png"), dpi=160); plt.close()
    except Exception as e:
        print("plots skipped:", e)


if __name__ == "__main__":
    main()
