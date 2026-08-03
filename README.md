Delayed-Feedback Contextual Bandit Platform with Fairness Constraints and Counterfactual Evaluation

Batch: C2C-19  |  Domain: AI for Computational Intelligence  |  Guide: Mr. Jevin J A (Emp. ID 8591) Team: 2300030970 · 2300030055 · 2300032727 · 2300033058

This repository contains the full In-Term Review (CP1 + CP2) documentation package for the capstone project: an integrated contextual bandit platform that handles delayed reward feedback, enforces fairness constraints across user groups, and validates every candidate policy offline via counterfactual (doubly robust) evaluation before it is ever exposed to live users.

1. What's in This Repository
File	What it is	Deliverable
Review1_DelayedFairBandit.md	Full CP1 research document — problem statement, 18+ paper literature survey, comparative & critical analysis, research gap, positioning/novelty statements, initial architecture, methodology, datasets, metrics, math formulation	CP1
index.html	Browsable website version of the CP1 document (sidebar navigation, milestone tracker, rendered equations)	CP1 (presentation form)
build_site.py	Python script that generates index.html from Review1_DelayedFairBandit.md	Tooling
CP2_Package.md	Finalized methodology, finalized system architecture (module interfaces, sequence diagram, schema), and the full implementation plan (roles, 12-week timeline, tools, risk register)	CP2
Abstract_Proforma_C2C-19.docx	Filled official abstract submission form (KLEF proforma)	Institutional submission
CP1_CP2_Review.pptx	14-slide presentation deck covering both checkpoints, for the live review	Presentation

Everything traces back to the same 18+-paper literature survey and the same research gap — the documents are different views of one underlying research package, not independent write-ups.

2. How the Pieces Fit Together
Review1_DelayedFairBandit.md  ──(build_site.py)──►  index.html
        │
        ├──► CP2_Package.md          (extends §11 architecture, §13 methodology)
        ├──► Abstract_Proforma.docx  (condensed abstract, official submission)
        └──► CP1_CP2_Review.pptx     (both checkpoints, presentation form)

The literature survey, comparative table, and research gap identified in Review1_DelayedFairBandit.md are the single source of truth. If the guide requests a change to a paper, a claim, or the gap statement, update it there first, then propagate the change into CP2_Package.md, the abstract, and the slides.

3. Project Summary

Recommendation and decision-making systems built on contextual bandits assume rewards arrive immediately, that reward-maximizing policies are automatically acceptable, and that a new policy is safe to deploy directly. All three assumptions fail in production:

Delayed feedback — conversions/outcomes resolve minutes to weeks after the decision.
Fairness — unconstrained reward maximization can systematically under-serve protected user groups.
Safe deployment — a new policy must be validated offline against historical logs before it ever reaches live users.

A systematic review of 18+ papers (ICML, NeurIPS, UAI, KDD, JMLR, IEEE, WWW, AISTATS) shows each sub-problem is well studied in isolation, but no prior work solves all three together. This project proposes an integrated platform combining a delay-aware credit-assignment module, a fairness-constrained exploration policy, and a doubly robust counterfactual evaluator, gated by a safety/fallback layer with continuous monitoring — validated on the Open Bandit Dataset with injected delay and fairness structure.

Closest prior art: Group-Sensitive Offline Contextual Bandits (Guo et al., 2024) — fairness + doubly robust evaluation, but offline-only, no delay handling. Neural Contextual Bandits Under Delayed Feedback Constraints (Moghimi et al., 2025) — delay-aware, but no fairness or counterfactual evaluation.

4. Working with Each File
Review1_DelayedFairBandit.md / index.html

Plain Markdown — open and edit directly, or regenerate the website after any edit:

bash
pip install markdown
python3 build_site.py Review1_DelayedFairBandit.md .

This overwrites index.html. Open it directly in any browser (no server needed).

CP2_Package.md

Plain Markdown, same editing workflow. Covers the finalized methodology (Section 1), finalized architecture with concrete module interfaces and a sequence diagram (Section 2), and the implementation plan — role split, 12-week timeline, tools, risk register (Section 3).

Abstract_Proforma_C2C-19.docx

The official KLEF submission form, pre-filled with batch number, domain, guide details, project title, abstract, keywords, and all 4 student IDs. Open in Word; only the guide-facing fields (Attendance, Understanding Level, Remarks, Signature) are left blank intentionally.

CP1_CP2_Review.pptx

Open directly in PowerPoint. 14 slides covering the roadmap, problem statement, literature clusters, research-gap Venn diagram, positioning/novelty, finalized methodology and architecture, tech stack, 12-week timeline, team roles, and a milestone checklist.

5. Research Snapshot
	
Papers reviewed	18+ across three clusters — Delayed Feedback, Fairness in Bandits, Counterfactual/Off-Policy Evaluation
Primary dataset	Open Bandit Dataset (Saito et al., 2020), with synthetic delay injection calibrated to Criteo delay statistics and synthetic protected-attribute injection
Core estimator	Doubly Robust (Dudík et al., 2011), extended with a delay-corrected reward term for censored logs
Fairness formulation	Lagrangian-constrained group parity (exposure- or outcome-based), following Guo et al. (2024)
Baselines	LinUCB (Li et al., 2010), Delayed NeuralUCB/TS (Moghimi et al., 2025), GC-PG (Guo et al., 2024, adapted online)
Key metrics	Cumulative regret, exposure/demographic-parity fairness violation, IPS/SNIPS/DM/DR/DR-shrinkage estimator MSE, coverage, delay-distribution fit

Full citations are in Review1_DelayedFairBandit.md, Section 17 (IEEE-style reference list).

6. Milestone Status
 CP1 — Problem statement, literature survey, research gap, objectives, methodology
 CP2 — Revised literature survey, finalized methodology, finalized architecture, implementation plan
 Implementation — simulator, delay-aware fairness-constrained learner, counterfactual evaluation, safety layer (next phase — see CP2_Package.md, Section 3.2 for the week-by-week plan)
 Review 2 — consolidated report, live demo, updated comparative-analysis table with results
7. Team
Member ID	Suggested Role (see CP2_Package.md §3.1 to reassign)
2300030970	Data & Simulation Engineer
2300030055	Bandit Algorithms Engineer
2300032727	Fairness & Evaluation Engineer
2300033058	Platform, Safety & Documentation Lead

Guide: Mr. Jevin J A, Emp. ID 8591
