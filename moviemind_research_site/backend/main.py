"""MovieMind backend: LinUCB + delayed feedback + fairness controller + IPS/DR evaluation."""
import asyncio, json, os, sqlite3, threading, time
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core import (GENRES, FEATURE_DIM, Data, LinUCB, exposure_shares, fairness_bonus, gini,
                  softmax_select)

# ---------------- configuration (matches the project report) ----------------
ALPHA = float(os.getenv("ALPHA", 0.7))
DELAY_SECONDS = float(os.getenv("DELAY_SECONDS", 60))
FAIRNESS_MIN_SHARE = float(os.getenv("FAIRNESS_MIN_SHARE", 0.05))
FAIRNESS_BONUS = 0.25
IPS_CAP = 20.0
AUTO_PROCESS_SECONDS = float(os.getenv("AUTO_PROCESS_SECONDS", 5))   # 0 = manual only
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE, "data"))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE, "moviemind.db"))
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(BASE, "linucb_state.npz"))
POINTS_PER_RATING = 10

data = Data.from_dir(DATA_DIR)
model = LinUCB.load(MODEL_PATH, alpha=ALPHA)
rng = np.random.default_rng()
lock = threading.RLock()
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS interactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, movie_id INTEGER, source TEXT,
  context TEXT, score REAL, propensity REAL, state TEXT, rating INTEGER, reward REAL,
  created_at REAL, feedback_at REAL, due_at REAL, delivered_at REAL);
CREATE INDEX IF NOT EXISTS ix_user ON interactions(user_id, movie_id);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, payload TEXT);
""")
db.commit()


def log_event(kind, **payload):
    db.execute("INSERT INTO events(ts,kind,payload) VALUES(?,?,?)", (time.time(), kind, json.dumps(payload)))


def movie_dict(i):
    return {"movie_id": int(data.movies.movieId[i]), "title": data.movies.title[i],
            "genres": data.genre_lists[i]}


# ---------------- delayed feedback processing ----------------
def process_due():
    """Apply every rated interaction whose delay has elapsed to LinUCB, exactly once."""
    with lock:
        rows = db.execute("SELECT * FROM interactions WHERE state='feedback_received_waiting' "
                          "AND due_at<=? AND delivered_at IS NULL ORDER BY due_at", (time.time(),)).fetchall()
        for r in rows:
            model.update(np.array(json.loads(r["context"])), r["reward"])
            db.execute("UPDATE interactions SET state='delivered', delivered_at=? WHERE id=?",
                       (time.time(), r["id"]))
            log_event("model_update", interaction_id=r["id"], reward=r["reward"])
        if rows:
            model.save(MODEL_PATH)
        db.commit()
        waiting = db.execute("SELECT COUNT(*) FROM interactions WHERE state='feedback_received_waiting'").fetchone()[0]
        return {"processed": len(rows), "still_waiting": waiting, "linucb_updates": model.updates}


async def auto_loop():
    while True:
        await asyncio.sleep(AUTO_PROCESS_SECONDS)
        try:
            process_due()
        except Exception as e:  # keep the loop alive
            print("auto-process error:", e)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(auto_loop()) if AUTO_PROCESS_SECONDS > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="MovieMind API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------- exposure / fairness ----------------
def genre_counts():
    cnt = np.zeros(len(GENRES))
    for r in db.execute("SELECT movie_id FROM interactions WHERE source='recommendation'"):
        i = data.mid2idx.get(r["movie_id"])
        if i is not None:
            cnt += data.G[i]
    return cnt


# ---------------- API ----------------
@app.get("/api/health")
def health():
    st = {r["state"]: r["n"] for r in db.execute("SELECT state, COUNT(*) n FROM interactions GROUP BY state")}
    return {"status": "ok", "movies": len(data.movies), "ratings": len(data.ratings),
            "users": len(data.user_stats), "pending": st.get("pending", 0),
            "feedback_waiting": st.get("feedback_received_waiting", 0),
            "delivered": st.get("delivered", 0), "linucb_updates": model.updates,
            "modules": {"linucb": True, "delay_queue": True, "fairness_controller": True, "ips_dr_evaluator": True},
            "config": {"alpha": ALPHA, "feature_dim": FEATURE_DIM, "delay_seconds": DELAY_SECONDS,
                       "fairness_min_share": FAIRNESS_MIN_SHARE, "fairness_bonus": FAIRNESS_BONUS,
                       "ips_cap": IPS_CAP, "auto_process_seconds": AUTO_PROCESS_SECONDS}}


@app.get("/api/catalog")
def catalog(q: str = "", genre: str = "", limit: int = Query(24, le=100), offset: int = 0):
    m = data.movies
    mask = np.ones(len(m), bool)
    if q:
        mask &= m.title.str.contains(q, case=False, regex=False).values
    if genre and genre in GENRES:
        mask &= data.G[:, GENRES.index(genre)] > 0
    idx = np.where(mask)[0]
    idx = idx[np.argsort(-data.pop[idx], kind="stable")]
    page = idx[offset:offset + limit]
    return {"total": int(len(idx)), "genres": GENRES,
            "items": [dict(movie_dict(i), popularity=round(float(data.pop[i]), 3)) for i in page]}


class RecReq(BaseModel):
    user_id: int
    limit: int = Field(8, ge=1, le=30)


@app.post("/api/recommendations")
def recommend(req: RecReq):
    with lock:
        seen = set(data.stats(req.user_id)["seen"])
        for r in db.execute("SELECT movie_id FROM interactions WHERE user_id=?", (req.user_id,)):
            if r["movie_id"] in data.mid2idx:
                seen.add(data.mid2idx[r["movie_id"]])
        cand = np.array([i for i in range(len(data.movies)) if i not in seen])
        if len(cand) > 4000:
            cand = rng.choice(cand, 4000, replace=False)
        if len(cand) == 0:
            raise HTTPException(404, "No unseen movies left for this user")
        X = data.context(req.user_id, cand)
        est, bonus = model.score(X)
        shares = exposure_shares(genre_counts())
        fb = fairness_bonus(data.G[cand], shares, FAIRNESS_MIN_SHARE, FAIRNESS_BONUS)
        score = est + bonus + fb
        chosen, props = softmax_select(score, req.limit, rng)
        now, items = time.time(), []
        for j, p in zip(chosen, props):
            i = int(cand[j])
            cur = db.execute(
                "INSERT INTO interactions(user_id,movie_id,source,context,score,propensity,state,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (req.user_id, int(data.movies.movieId[i]), "recommendation", json.dumps(X[j].tolist()),
                 float(score[j]), p, "pending", now))
            items.append(dict(movie_dict(i), interaction_id=cur.lastrowid, score=round(float(score[j]), 4),
                              estimate=round(float(est[j]), 4), exploration_bonus=round(float(bonus[j]), 4),
                              fairness_bonus=float(fb[j]), propensity=round(p, 4)))
        log_event("recommendation", user_id=req.user_id, movies=[it["movie_id"] for it in items])
        db.commit()
        return {"user_id": req.user_id, "linucb_updates": model.updates, "items": items}


class FeedbackReq(BaseModel):
    user_id: int
    movie_id: int
    rating: int = Field(ge=1, le=5)


@app.post("/api/feedback")
def feedback(req: FeedbackReq):
    with lock:
        if req.movie_id not in data.mid2idx:
            raise HTTPException(404, "Unknown movie")
        row = db.execute("SELECT * FROM interactions WHERE user_id=? AND movie_id=? ORDER BY id DESC LIMIT 1",
                         (req.user_id, req.movie_id)).fetchone()
        now = time.time()
        reward = req.rating / 5.0
        if row and row["rating"] is not None:
            raise HTTPException(409, "This movie was already rated by this user")
        if row is None:     # rated straight from the catalogue: store context, propensity 1 (not used in IPS)
            i = data.mid2idx[req.movie_id]
            x = data.context(req.user_id, [i])[0]
            cur = db.execute("INSERT INTO interactions(user_id,movie_id,source,context,propensity,state,created_at) "
                             "VALUES(?,?,?,?,?,?,?)", (req.user_id, req.movie_id, "catalog",
                                                      json.dumps(x.tolist()), 1.0, "pending", now))
            iid = cur.lastrowid
        else:
            iid = row["id"]
        db.execute("UPDATE interactions SET rating=?, reward=?, state='feedback_received_waiting', "
                   "feedback_at=?, due_at=? WHERE id=?", (req.rating, reward, now, now + DELAY_SECONDS, iid))
        log_event("feedback", user_id=req.user_id, movie_id=req.movie_id, rating=req.rating, reward=reward)
        db.commit()
        return {"message": f"Rating saved. {POINTS_PER_RATING} points awarded. Model reward signal: {reward:.1f}. "
                           f"Learning status: queued.", "points_awarded": POINTS_PER_RATING,
                "reward": reward, "status": "queued", "due_in_seconds": DELAY_SECONDS}


@app.post("/api/process-due-feedback")
def process_endpoint():
    return process_due()


BADGES = [("first_rating", "First Rating", "Submit your first rating", 1),
          ("movie_explorer", "Movie Explorer", "Submit 5 ratings", 5),
          ("feedback_champion", "Feedback Champion", "Submit 10 ratings", 10)]


@app.get("/api/dashboard/{user_id}")
def dashboard(user_id: int):
    rows = db.execute("SELECT * FROM interactions WHERE user_id=? AND rating IS NOT NULL ORDER BY feedback_at DESC",
                      (user_id,)).fetchall()
    n = len(rows)
    waiting = sum(1 for r in rows if r["state"] == "feedback_received_waiting")
    now = time.time()
    recent = []
    for r in rows[:50]:
        i = data.mid2idx.get(r["movie_id"])
        recent.append({"movie_id": r["movie_id"], "title": data.movies.title[i] if i is not None else "?",
                       "rating": r["rating"], "state": r["state"], "source": r["source"],
                       "due_in_seconds": max(0, round(r["due_at"] - now)) if r["state"] != "delivered" else 0})
    return {"user_id": user_id, "points": n * POINTS_PER_RATING, "ratings_given": n, "feedback_in_queue": waiting,
            "linucb_updates": model.updates,
            "badges": [{"id": b, "name": nm, "description": d, "earned": n >= t} for b, nm, d, t in BADGES],
            "recent": recent, "rated_movie_ids": [r["movie_id"] for r in rows]}


@app.get("/api/metrics")
def metrics():
    cnt = genre_counts()
    sh = exposure_shares(cnt)
    st = {r["state"]: r["n"] for r in db.execute("SELECT state, COUNT(*) n FROM interactions GROUP BY state")}
    avg = db.execute("SELECT AVG(reward) FROM interactions WHERE reward IS NOT NULL").fetchone()[0]
    return {"states": st, "linucb_updates": model.updates, "mean_reward": avg,
            "recommendations": int(db.execute("SELECT COUNT(*) FROM interactions WHERE source='recommendation'").fetchone()[0]),
            "exposure": [{"genre": g, "count": int(c), "share": round(float(s), 4), "below_threshold": bool(s < FAIRNESS_MIN_SHARE)}
                         for g, c, s in zip(GENRES, cnt, sh)],
            "min_share": float(sh.min()), "exposure_gini": gini(cnt), "fairness_min_share": FAIRNESS_MIN_SHARE}


@app.get("/api/evaluate")
def evaluate():
    rows = db.execute("SELECT reward, propensity FROM interactions WHERE source='recommendation' "
                      "AND reward IS NOT NULL AND propensity>0").fetchall()
    if not rows:
        return {"n": 0, "ips": None, "dr": None, "note": "No rated recommendations logged yet."}
    r = np.array([x["reward"] for x in rows])
    w = np.minimum(1.0 / np.array([x["propensity"] for x in rows]), IPS_CAP)   # weights capped at 20
    q = r.mean()                                                              # global-mean reward model
    return {"n": len(r), "ips": float(np.mean(r * w)), "dr": float(np.mean(q + (r - q) * w)),
            "snips": float((r * w).sum() / w.sum()), "mean_reward": float(q), "effective_sample_size": float(w.sum() ** 2 / (w ** 2).sum()),
            "max_weight": float(w.max()), "ips_cap": IPS_CAP,
            "note": "IPS/DR follow the project formulas (not normalised, so values can exceed 1); SNIPS is the self-normalised variant. DR uses the global mean reward as baseline (exploratory)."}


@app.get("/api/events")
def events(limit: int = Query(50, le=500)):
    rows = db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r["id"], "ts": r["ts"], "kind": r["kind"], "payload": json.loads(r["payload"])} for r in rows]


@app.post("/api/admin/reset")
def reset():
    """Clear interactions, events and the learned model (for repeatable demos/experiments)."""
    global model
    with lock:
        db.execute("DELETE FROM interactions"); db.execute("DELETE FROM events"); db.commit()
        model = LinUCB(alpha=ALPHA)
        model.save(MODEL_PATH)
    return {"status": "reset"}
