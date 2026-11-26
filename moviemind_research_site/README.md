# MovieMind – Delayed-Feedback Contextual Bandit Platform

LinUCB recommender + delayed-feedback queue + genre-exposure fairness controller + IPS / DR-style
counterfactual evaluation. FastAPI + SQLite backend, React + Vite frontend.

## 1. Run it (Windows PowerShell)

Terminal 1 – backend (http://127.0.0.1:8000, API docs at /docs):
```
cd moviemind_research_site\backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
Terminal 2 – frontend (http://localhost:5173):
```
cd moviemind_research_site\frontend
npm.cmd install
npm.cmd run dev
```
(or double-click `run_backend.bat` and `run_frontend.bat`). Open http://localhost:5173.

**No CORS errors:** the Vite dev server proxies `/api` to port 8000, so the browser never makes a
cross-origin call. The backend also allows CORS, so you can set `VITE_API=http://127.0.0.1:8000` if you prefer.

## 2. Use your real dataset
`backend/data/` ships with a small **demo dataset** (240 movies, 200 users) so the app runs immediately.
Replace both files with your own and restart the backend:
- `movies.csv` – `movieId,title,genres` (genres separated by `|`)
- `ratings.txt` – `userId,movieId,rating,timestamp` (CSV, tab or `::` separated, header optional)

With your files the health check should show 10,329 movies / 105,339 ratings / 668 users.
Delete `backend/moviemind.db` and `backend/linucb_state.npz` after switching datasets for a clean start.

## 3. Demo flow
1. **Discover** → *Get recommendations* (the user ID box top-right switches users).
2. Rate a movie → "Rating saved… reward signal 0.8… queued". *Feedback in queue* goes up.
3. After `DELAY_SECONDS` (default 60) the item is applied to LinUCB automatically (background check every 5 s),
   or immediately via **Research → Process due feedback now** / `POST /api/process-due-feedback`.
   *LinUCB updates* goes up; each interaction is applied only once.
4. **Research** shows state counts, configuration, genre exposure (fairness), IPS / DR-style estimates and the event log.
   **My Activity** shows rating history, queue status and badges (1 / 5 / 10 ratings).

For a quick demo use a short delay: `$env:DELAY_SECONDS=5; python -m uvicorn main:app --port 8000`.

## 4. What is implemented (matches the report)
| Item | Value |
|---|---|
| Model | shared-parameter LinUCB, `UCB = xᵀθ + α·√(xᵀA⁻¹x)`, α = 0.7 |
| Context | 28-d = 1 bias + 19 genres + 8 user-history features (see `core.py`) |
| Reward | rating / 5 |
| Update | `A += xxᵀ`, `b += r·x`, `θ = A⁻¹b`; saved to `linucb_state.npz` |
| Delay | `DELAY_SECONDS = 60`; states `pending → feedback_received_waiting → delivered` |
| Fairness | genre share < 0.05 → +0.25 score (heuristic guardrail, not a formal guarantee) |
| Selection | stochastic (softmax over the top pool); propensity logged |
| IPS / DR | IPS = mean(r·min(1/p, 20)); DR-style with global-mean baseline (exploratory); SNIPS also reported |

Environment variables: `ALPHA`, `DELAY_SECONDS`, `FAIRNESS_MIN_SHARE`, `AUTO_PROCESS_SECONDS` (0 = manual only),
`DATA_DIR`, `DB_PATH`, `MODEL_PATH`.

API: `GET /api/health`, `GET /api/catalog`, `GET /api/dashboard/{user_id}`, `POST /api/recommendations`,
`POST /api/feedback`, `POST /api/process-due-feedback`, `GET /api/metrics`, `GET /api/evaluate`,
`GET /api/events`, `POST /api/admin/reset` (clears logs and model).

## 5. Experiments for the research paper
```
cd backend
python experiments.py --rounds 2000 --seeds 5 --delay 20
```
Compares **random**, **LinUCB (immediate feedback)**, **LinUCB (delayed)** and **MovieMind (delayed + fairness)**
on your ratings file. Each user's ratings are split 50/50 (history features vs. candidate pool, so no leakage), the
logged rating / 5 is the reward, and feedback arrives `--delay` rounds late. Output: `results/experiments.csv|json`
and plots (`cumulative_reward.png`, `min_genre_share.png`) with mean ± std over seeds.

**Run it on your real data before quoting any numbers.** Results on the bundled demo data are not meaningful.
This is a replay-style simulation using historical ratings as the reward oracle, not a live user study.

## 6. Troubleshooting
- **"Can't reach the MovieMind backend"** – the backend is not running on port 8000; start Terminal 1.
- **Port 5173 busy** – Vite picks the next port automatically; the proxy still works.
- **Counts look stale after changing data** – delete `moviemind.db` and `linucb_state.npz`, restart.
- **`python` not found** – use `py -m pip …` and `py -m uvicorn …`.
