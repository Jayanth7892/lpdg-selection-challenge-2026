# System Limitations & Two-Week Roadmap

In accordance with Section Part 1, Item 4 of the challenge brief (*"What it cannot do — where your thing falls over, and what another two weeks would fix"*), this document transparently states the boundary conditions of the current implementation and outlines future enhancements.

---

## 1. Where the Current System Falls Over

### A. Cold-Start on Recently Commissioned Gateways
* **Failure Mode**: The engine computes rolling 28-day baselines to establish normal LoRa packet throughput and reporting cadence. Gateways installed less than 28 days prior lack sufficient historical depth.
* **Operational Risk**: A new gateway experiencing early-life infant mortality might be misclassified as "low historical volume" rather than an active defect, delaying field dispatch.

### B. Fleet-Wide Uniform Financial Weighting
* **Failure Mode**: The current ranker prioritizes failure severity uniformly across all active gateways. However, `gateway_master.csv` indicates that gateways serve anywhere from **40 to 900+ meters**.
* **Operational Risk**: A failing gateway relaying 900 meters causes $22.5\times$ more unread meters than one serving 40 meters. Under a hard 15-visit budget, failing to weight by `n_meters_installed` risks resolving minor isolated faults while leaving hundreds of customer bills unread.

### C. Carrier Tower Outages vs. Physical Hardware Defects
* **Failure Mode**: When a regional telecommunications tower experiences an outage (e.g., O2DE tower maintenance in Nordrhein-Westfalen), multiple nearby gateways drop connection simultaneously.
* **Operational Risk**: The engine may interpret high `no_conn_importance` as physical gateway damage and dispatch technicians who arrive on site only to find the hardware functioning normally (*Kein Fehler gefunden*).

### D. Post-Visit Baseline Contamination
* **Failure Mode**: If a technician attends a site midweek and replaces a power supply (*Netzteil*), the gateway's trailing 7-day window still contains the pre-repair failure telemetry.
* **Operational Risk**: The gateway could be erroneously re-flagged the following Monday despite having been repaired.

---

## 2. What Another Two Weeks Would Fix

| Enhancement | Operational Impact | Implementation Approach |
|---|---|---|
| **Hierarchical Fleet Priors for Cold-Start** | Accurate assessment of new gateways from Day 1 | Replace missing 28-day baselines with empirical Bayesian priors grouped by `hw_model` and `site_type`. |
| **Meter-Weighted Expected Loss Optimization** | Maximizes business ROI per technician visit | Scale gateway risk scores by $\text{Expected Loss} = P(\text{Failure}) \times n\_meters\_installed \times €/meter$, transforming the ranking into a direct revenue protection function. |
| **Geographic Spatial Clustering** | Eliminates carrier-induced false dispatches | Group concurrent outages by `region` and `operator_*`. If $>3$ gateways on the same carrier fail synchronously, classify as carrier network incident and suppress field dispatch. |
| **Closed-Loop Work Order Integration** | Prevents redundant repeat visits | Ingest `field_visits.csv` to register completed repairs and apply a temporary 14-day observation cooldown window. |
