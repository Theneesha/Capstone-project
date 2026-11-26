"""MovieMind core: data loading, feature construction, LinUCB, fairness helpers."""
import os
import numpy as np
import pandas as pd

GENRES = ["Action", "Adventure", "Animation", "Children", "Comedy", "Crime", "Documentary", "Drama",
          "Fantasy", "Film-Noir", "Horror", "IMAX", "Musical", "Mystery", "Romance", "Sci-Fi",
          "Thriller", "War", "Western"]                      # 19 genre features
G_IDX = {g: i for i, g in enumerate(GENRES)}
N_USER_FEATS = 8
FEATURE_DIM = 1 + len(GENRES) + N_USER_FEATS              # 1 + 19 + 8 = 28


def _sep_of(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        head = f.readline()
    if "::" in head:
        return "::", head
    if "\t" in head:
        return "\t", head
    return ",", head


def load_ratings(path):
    """Accepts CSV / TSV / '::' files, with or without header: userId, movieId, rating, timestamp."""
    sep, head = _sep_of(path)
    has_header = any(c.isalpha() for c in head)
    df = pd.read_csv(path, sep=sep, engine="python" if sep == "::" else "c",
                     header=0 if has_header else None)
    df = df.iloc[:, :4].copy()
    df.columns = ["userId", "movieId", "rating", "timestamp"][:df.shape[1]]
    if "timestamp" not in df:
        df["timestamp"] = 0
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["userId", "movieId", "rating"])
    df["userId"] = df.userId.astype(int)
    df["movieId"] = df.movieId.astype(int)
    return df.reset_index(drop=True)


def load_movies(path):
    sep, head = _sep_of(path)
    has_header = "movieId" in head or "title" in head.lower()
    df = pd.read_csv(path, sep=sep, engine="python" if sep == "::" else "c",
                     header=0 if has_header else None)
    df = df.iloc[:, :3].copy()
    df.columns = ["movieId", "title", "genres"]
    df["movieId"] = df.movieId.astype(int)
    df["genres"] = df.genres.fillna("").astype(str)
    return df.drop_duplicates("movieId").reset_index(drop=True)


class Data:
    """Movie metadata + historical ratings -> 28-d feature vectors for (user, movie)."""

    def __init__(self, movies, ratings):
        self.movies = movies.reset_index(drop=True)
        self.ratings = ratings[ratings.movieId.isin(set(self.movies.movieId))].reset_index(drop=True)
        self.mid2idx = {m: i for i, m in enumerate(self.movies.movieId)}
        n = len(self.movies)
        self.G = np.zeros((n, len(GENRES)))
        self.genre_lists = []
        for i, g in enumerate(self.movies.genres):
            lst = [x for x in g.split("|") if x in G_IDX]
            self.genre_lists.append(lst)
            for x in lst:
                self.G[i, G_IDX[x]] = 1.0
        self.gsum = self.G.sum(1)
        ridx = self.ratings.movieId.map(self.mid2idx).values
        cnt = np.bincount(ridx, minlength=n).astype(float)
        tot = np.bincount(ridx, weights=self.ratings.rating.values, minlength=n)
        self.pop = np.log1p(cnt) / max(np.log1p(cnt.max()), 1e-9)
        self.avg = ((tot + 3.5 * 5) / (cnt + 5)) / 5.0           # smoothed mean rating / 5
        self.user_stats = {}
        for u, grp in self.ratings.groupby("userId"):
            idx = grp.movieId.map(self.mid2idx).values
            r = grp.rating.values
            gc = self.G[idx].sum(0)
            gs = (self.G[idx] * r[:, None]).sum(0)
            mean = r.mean()
            gmean = np.where(gc > 0, gs / np.maximum(gc, 1), mean)
            top = np.zeros(len(GENRES))
            order = np.argsort(gc)[-3:]
            top[order[gc[order] > 0]] = 1
            self.user_stats[int(u)] = dict(n=len(r), mean=mean, std=r.std(), gmean=gmean,
                                           gshare=gc / len(r), top=top, seen=set(idx.tolist()))
        self.max_n = max([s["n"] for s in self.user_stats.values()] + [1])
        self.default_stats = dict(n=0, mean=3.5, std=1.0, gmean=np.full(len(GENRES), 3.5),
                                  gshare=np.zeros(len(GENRES)), top=np.zeros(len(GENRES)), seen=set())

    @classmethod
    def from_dir(cls, d):
        return cls(load_movies(os.path.join(d, "movies.csv")),
                   load_ratings(os.path.join(d, "ratings.txt")))

    def stats(self, uid):
        return self.user_stats.get(int(uid), self.default_stats)

    def context(self, uid, midx):
        """x = [1, genre one-hot (19), 8 user-history features] for each candidate in midx."""
        s = self.stats(uid)
        midx = np.asarray(midx)
        G = self.G[midx]
        gs = np.maximum(self.gsum[midx], 1)
        f = np.stack([
            np.full(len(midx), s["mean"] / 5.0),                               # f1 user mean rating
            np.full(len(midx), min(s["std"] / 2.0, 1.0)),                      # f2 rating spread
            np.full(len(midx), np.log1p(s["n"]) / np.log1p(self.max_n)),       # f3 activity level
            np.where(self.gsum[midx] > 0, (G @ s["gmean"]) / gs, s["mean"]) / 5.0,  # f4 user avg for these genres
            (G @ s["gshare"]) / gs,                                            # f5 share of history in these genres
            self.pop[midx],                                                    # f6 movie popularity
            self.avg[midx],                                                    # f7 movie smoothed mean rating
            (G @ s["top"]) / gs,                                               # f8 overlap with user's top genres
        ], axis=1)
        return np.hstack([np.ones((len(midx), 1)), G, f])


class LinUCB:
    """Shared-parameter LinUCB: UCB(x) = x^T theta + alpha * sqrt(x^T A^-1 x)."""

    def __init__(self, d=FEATURE_DIM, alpha=0.7, lam=1.0):
        self.d, self.alpha = d, alpha
        self.A = lam * np.eye(d)
        self.b = np.zeros(d)
        self.updates = 0
        self._refresh()

    def _refresh(self):
        self.Ainv = np.linalg.inv(self.A)
        self.theta = self.Ainv @ self.b

    def score(self, X):
        est = X @ self.theta
        bonus = self.alpha * np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", X, self.Ainv, X), 0))
        return est, bonus

    def update(self, x, r):
        x = np.asarray(x, float)
        self.A += np.outer(x, x)          # A = A + x x^T
        self.b += r * x                   # b = b + r x
        self.updates += 1
        self._refresh()                   # theta = A^-1 b

    def save(self, path):
        np.savez(path, A=self.A, b=self.b, updates=self.updates, alpha=self.alpha)

    @classmethod
    def load(cls, path, alpha=0.7):
        m = cls(alpha=alpha)
        if os.path.exists(path):
            z = np.load(path)
            if z["A"].shape == m.A.shape:
                m.A, m.b, m.updates = z["A"], z["b"], int(z["updates"])
                m._refresh()
        return m


def exposure_shares(counts):
    tot = counts.sum()
    return counts / tot if tot > 0 else np.zeros_like(counts, dtype=float)


def fairness_bonus(G, shares, min_share=0.05, bonus=0.25):
    """+bonus when the least-exposed genre of a movie has share < min_share (heuristic guardrail)."""
    low = np.where(G > 0, shares[None, :], np.inf).min(1)
    return np.where(low < min_share, bonus, 0.0)


def gini(x):
    x = np.sort(np.asarray(x, float))
    if x.sum() == 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def softmax_select(scores, k, rng, temp=0.15):
    """Stochastic selection from the top pool; returns (indices, propensities)."""
    avail = list(np.argsort(-scores)[:max(k * 3, 15)])
    chosen, props = [], []
    for _ in range(min(k, len(avail))):
        s = scores[avail] / temp
        s = np.exp(s - s.max())
        p = s / s.sum()
        j = rng.choice(len(avail), p=p)
        chosen.append(avail[j])
        props.append(float(p[j]))
        avail.pop(j)
    return chosen, props
