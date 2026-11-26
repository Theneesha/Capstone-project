import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const GLYPHS = ["✦", "◈", "◉", "✧", "▣", "✺"];
const hue = (id) => (id * 47) % 360;

function Poster({ id, label }) {
  return (
    <div className="poster" style={{ "--h": hue(id) }} aria-hidden="true">
      <span className="glyph">{GLYPHS[id % GLYPHS.length]}</span>
      <span className="poster-id">{label}</span>
    </div>
  );
}

function Stars({ onRate, disabled, value }) {
  return (
    <div className="stars" role="group" aria-label="Your star rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} className={value === n ? "on" : ""} disabled={disabled} onClick={() => onRate(n)}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}>
          {n}★
        </button>
      ))}
    </div>
  );
}

function MovieCard({ m, rated, onRate, pick }) {
  const done = rated != null;
  return (
    <article className="card movie">
      <Poster id={m.movie_id} label={pick || `#${m.movie_id}`} />
      <div className="movie-body">
        <h3>{m.title}</h3>
        <p className="genres">{m.genres.join(" · ") || "No genres listed"}</p>
        {m.score !== undefined && (
          <p className="score">
            Recommendation score <b>{m.score}</b>
            <span className="parts">
              estimate {m.estimate} + exploration {m.exploration_bonus}
              {m.fairness_bonus > 0 && ` + fairness ${m.fairness_bonus}`}
            </span>
          </p>
        )}
        <div className="rate-row">
          <span>{done ? "Rating sent to the learning queue" : "How many stars?"}</span>
          <Stars onRate={onRate} disabled={done} value={rated} />
        </div>
      </div>
    </article>
  );
}

function Counter({ label, value, hint }) {
  return (
    <div className="card counter">
      <span className="label">{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("discover");
  const [userId, setUserId] = useState(1);
  const [draftId, setDraftId] = useState("1");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dash, setDash] = useState(null);
  const [recs, setRecs] = useState([]);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [catalog, setCatalog] = useState({ items: [], total: 0, genres: [] });
  const [q, setQ] = useState("");
  const [genre, setGenre] = useState("");
  const [online, setOnline] = useState(null);
  const recRef = useRef(null);

  const guard = useCallback(async (fn) => {
    try { setError(""); return await fn(); } catch (e) { setError(e.message); }
  }, []);

  const refreshDash = useCallback(() => guard(async () => setDash(await api.dashboard(userId))), [userId, guard]);
  const searchCatalog = useCallback(() => guard(async () => setCatalog(await api.catalog(q, genre))), [q, genre, guard]);

  useEffect(() => { refreshDash(); }, [refreshDash]);
  useEffect(() => { searchCatalog(); }, []); // eslint-disable-line
  useEffect(() => {
    const ping = () => api.health().then(() => setOnline(true)).catch(() => setOnline(false));
    ping(); const t = setInterval(() => { ping(); refreshDash(); }, 5000);
    return () => clearInterval(t);
  }, [refreshDash]);

  const ratedMap = Object.fromEntries((dash?.recent || []).map((r) => [r.movie_id, r.rating]));

  const getRecs = () => guard(async () => {
    setLoadingRecs(true);
    try { const r = await api.recommend(userId, 8); setRecs(r.items); setNotice(""); recRef.current?.scrollIntoView({ behavior: "smooth" }); }
    finally { setLoadingRecs(false); }
  });

  const rate = (movie_id, n) => guard(async () => {
    const r = await api.rate(userId, movie_id, n);
    setNotice(r.message); await refreshDash();
  });

  const switchUser = (e) => {
    e.preventDefault();
    const n = parseInt(draftId, 10);
    if (!Number.isInteger(n) || n < 1) return setError("Enter a user ID of 1 or higher.");
    setError(""); setRecs([]); setNotice(""); setUserId(n);
  };

  const nav = [["discover", "Discover", "◈"], ["activity", "My Activity", "◷"], ["research", "Research", "⌘"]];

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><span className="logo">M</span><div><b>MovieMind</b><small>Research Studio</small></div></div>
        <nav aria-label="Workspace">
          {nav.map(([id, name, ic]) => (
            <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}><span>{ic}</span>{name}</button>
          ))}
        </nav>
        <div className="status"><i className={online === false ? "off" : online ? "on" : ""} />
          <div><b>Research engine</b><small>{online === false ? "API not reachable" : online ? "API connected" : "Connecting…"}</small></div>
        </div>
      </aside>

      <main>
        <header className="top">
          <div><small className="crumb">{nav.find((n) => n[0] === view)[1]}</small><h1>
            {view === "discover" ? "Discover your next favorite" : view === "activity" ? "Your ratings and rewards" : "Research dashboard"}</h1></div>
          <form className="user" onSubmit={switchUser}>
            <label htmlFor="uid">Demo user</label>
            <input id="uid" value={draftId} onChange={(e) => setDraftId(e.target.value)} inputMode="numeric" />
            <button className="avatar" title="Switch user">Go</button>
          </form>
        </header>

        {error && <div className="banner error" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss">×</button></div>}
        {notice && <div className="banner" role="status">{notice}</div>}

        <section className="counters">
          <Counter label="Your points" value={dash?.points ?? 0} hint="+10 per valid rating" />
          <Counter label="Ratings given" value={dash?.ratings_given ?? 0} hint="One rating per movie" />
          <Counter label="Feedback in queue" value={dash?.feedback_in_queue ?? 0} hint="Awaiting delayed update" />
          <Counter label="LinUCB updates" value={dash?.linucb_updates ?? 0} hint="Applied reward updates" />
        </section>

        {view === "discover" && (
          <>
            <section className="hero">
              <div>
                <h2>Rate movies you know.<br />The engine learns after a delay.</h2>
                <p>Recommendations come from a contextual bandit with a fairness guardrail. Each rating is queued, then applied to the model once its delay has passed.</p>
                <button className="primary" onClick={getRecs} disabled={loadingRecs}>{loadingRecs ? "Finding movies…" : "Get recommendations"}</button>
              </div>
            </section>

            <section ref={recRef}>
              <h2 className="sec">Recommended for you</h2>
              {recs.length === 0 ? (
                <div className="empty">Your next movie is waiting. Choose “Get recommendations” to load picks for user {userId}.</div>
              ) : (
                <div className="grid">
                  {recs.map((m, i) => (
                    <MovieCard key={m.interaction_id} m={m} pick={`Pick ${i + 1}`} rated={ratedMap[m.movie_id]} onRate={(n) => rate(m.movie_id, n)} />
                  ))}
                </div>
              )}
            </section>

            <section>
              <div className="sec-row">
                <h2 className="sec">Browse the catalogue</h2>
                <form className="filters" onSubmit={(e) => { e.preventDefault(); searchCatalog(); }}>
                  <input placeholder="Search titles…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search titles" />
                  <select value={genre} onChange={(e) => setGenre(e.target.value)} aria-label="Genre">
                    <option value="">All genres</option>{catalog.genres.map((g) => <option key={g}>{g}</option>)}
                  </select>
                  <button className="ghost">Search</button>
                </form>
              </div>
              <p className="muted">{catalog.total} movies match. Rate any movie to send feedback to the learning pipeline.</p>
              <div className="grid">
                {catalog.items.map((m) => (
                  <MovieCard key={m.movie_id} m={m} rated={ratedMap[m.movie_id]} onRate={(n) => rate(m.movie_id, n)} />
                ))}
              </div>
            </section>
          </>
        )}

        {view === "activity" && <Activity dash={dash} />}
        {view === "research" && <Research guard={guard} setNotice={setNotice} refreshDash={refreshDash} />}
      </main>
    </div>
  );
}

function Activity({ dash }) {
  if (!dash) return <div className="empty">Loading…</div>;
  const label = { feedback_received_waiting: "Waiting for delay", delivered: "Applied to model", pending: "Pending" };
  return (
    <>
      <h2 className="sec">Badges earned</h2>
      <div className="badges">
        {dash.badges.map((b) => (
          <div key={b.id} className={"card badge " + (b.earned ? "earned" : "locked")}>
            <b>{b.name}</b><small>{b.description}</small><em>{b.earned ? "Earned" : "Locked"}</em>
          </div>
        ))}
      </div>
      <h2 className="sec">Rating history</h2>
      {dash.recent.length === 0 ? <div className="empty">No ratings yet. Rate a movie on the Discover page.</div> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Movie</th><th>Rating</th><th>Learning status</th><th>Applies in</th></tr></thead>
          <tbody>{dash.recent.map((r, i) => (
            <tr key={i}><td>{r.title}</td><td>{"★".repeat(r.rating)}</td><td>{label[r.state] || r.state}</td>
              <td>{r.state === "delivered" ? "—" : `${r.due_in_seconds}s`}</td></tr>))}</tbody>
        </table></div>
      )}
    </>
  );
}

function Research({ guard, setNotice, refreshDash }) {
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [ev, setEv] = useState(null);
  const [events, setEvents] = useState([]);

  const load = useCallback(() => guard(async () => {
    const [h, m, e, evs] = await Promise.all([api.health(), api.metrics(), api.evaluate(), api.events()]);
    setHealth(h); setMetrics(m); setEv(e); setEvents(evs);
  }), [guard]);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const process = () => guard(async () => {
    const r = await api.processDue();
    setNotice(`Processed ${r.processed} feedback item(s); ${r.still_waiting} still waiting; ${r.linucb_updates} LinUCB updates in total.`);
    await load(); await refreshDash();
  });
  const reset = () => { if (window.confirm("Clear all interactions and the learned model?")) guard(async () => { await api.reset(); setNotice("Model and logs cleared."); await load(); await refreshDash(); }); };

  if (!health || !metrics) return <div className="empty">Loading research data…</div>;
  const max = Math.max(...metrics.exposure.map((e) => e.share), 0.01);
  const f = (v, d = 3) => (v == null ? "—" : Number(v).toFixed(d));
  return (
    <>
      <div className="actions">
        <button className="primary" onClick={process}>Process due feedback now</button>
        <button className="ghost" onClick={load}>Refresh</button>
        <button className="ghost danger" onClick={reset}>Reset model and logs</button>
      </div>

      <div className="two">
        <div className="card pad">
          <h3>System state</h3>
          <dl>
            <dt>Dataset</dt><dd>{health.movies.toLocaleString()} movies · {health.ratings.toLocaleString()} ratings · {health.users} users</dd>
            <dt>Interactions</dt><dd>{health.pending} pending · {health.feedback_waiting} waiting · {health.delivered} delivered</dd>
            <dt>LinUCB updates</dt><dd>{health.linucb_updates}</dd>
            <dt>Configuration</dt><dd>α = {health.config.alpha} · d = {health.config.feature_dim} · delay = {health.config.delay_seconds}s · fairness floor {health.config.fairness_min_share} (+{health.config.fairness_bonus}) · IPS cap {health.config.ips_cap}</dd>
          </dl>
        </div>
        <div className="card pad">
          <h3>Counterfactual evaluation</h3>
          {ev && ev.n > 0 ? (
            <dl>
              <dt>Logged rated recommendations</dt><dd>{ev.n}</dd>
              <dt>IPS</dt><dd>{f(ev.ips)}</dd><dt>DR-style</dt><dd>{f(ev.dr)}</dd>
              <dt>Self-normalised IPS</dt><dd>{f(ev.snips)}</dd><dt>Mean reward</dt><dd>{f(ev.mean_reward)}</dd>
              <dt>Effective sample size</dt><dd>{f(ev.effective_sample_size, 1)}</dd>
            </dl>
          ) : <p className="muted">Rate some recommended movies to see IPS and DR-style estimates.</p>}
          <p className="muted small">{ev?.note}</p>
        </div>
      </div>

      <div className="card pad">
        <h3>Genre exposure</h3>
        <p className="muted small">{metrics.recommendations} recommendations logged · min share {f(metrics.min_share)} · Gini {f(metrics.exposure_gini)}. Genres under {metrics.fairness_min_share} get a fairness bonus.</p>
        <div className="bars">
          {metrics.exposure.map((e) => (
            <div key={e.genre} className="bar-row">
              <span>{e.genre}</span>
              <div className="track"><div className={"fill" + (e.below_threshold ? " low" : "")} style={{ width: `${(e.share / max) * 100}%` }} /></div>
              <span className="pct">{(e.share * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card pad">
        <h3>Event log</h3>
        {events.length === 0 ? <p className="muted">No events yet.</p> : (
          <ul className="events">{events.map((e) => (
            <li key={e.id}><time>{new Date(e.ts * 1000).toLocaleTimeString()}</time><b>{e.kind}</b>
              <code>{JSON.stringify(e.payload)}</code></li>))}</ul>
        )}
      </div>
    </>
  );
}
