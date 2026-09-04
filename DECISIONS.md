# Architectural & Methodological Decisions

This document details five key engineering choices made in developing the LPDG Gateway Prediction Service, including alternatives evaluated, trade-offs, and rationale.

---

### Decision 1: Active "Dead Gateway" Detection vs. Pure Telemetry Anomaly Detection
* **Choice**: Explicitly track fleet reporting completeness by cross-referencing active assets from `gateway_master.csv`. Any gateway with zero or critically depressed telemetry (<50% of expected 168 hours) in the trailing 7 days following an active 28-day baseline is immediately escalated to top-priority dispatch.
* **Alternatives Considered**: Naive 3-sigma anomaly scoring or isolation forests on telemetry rows alone (as done in `baseline_3sigma.py`).
* **Why Rejected**: When a gateway suffers a fatal hardware fault (e.g., power supply burnout), it stops transmitting entirely. A telemetry-only query (`window[window["ts"] >= recent_start].groupby("gateway_id")`) produces **zero rows** for that unit. The naive baseline completely ignores these dead gateways, assigning them zero flagged hours. In February 2026, 21 active gateways reported zero telemetry; engineer reviews revealed these were chronic outages with multiple customer complaints. Allowing them to linger incurs compounding penalties of **€600 per week**.

---

### Decision 2: Resilient Multi-Encoding Ingestion & Identifier Normalisation
* **Choice**: Ingest `gateway_master.csv` through an automated multi-encoding fallback (`latin1`, `cp1252`, `utf-8`) and enforce canonical 12-character uppercase hex identifiers across all relational joins.
* **Alternatives Considered**: Assuming standard UTF-8 and standardizing files via manual preprocessing scripts before execution.
* **Why Rejected**: The challenge specifies that solutions must execute in a clean environment against the raw, unzipped `data/` directory. German system exports contain byte `0xdf` (`ß` in *Außenmast*) and `0xe4` (`ä` in *Gebäude*), which crash Python's default UTF-8 parser with `UnicodeDecodeError`. Furthermore, `gateway_master.csv` formats MAC addresses with colons (`06:39:EA:56:02:C1`) whereas telemetry and metering use bare hex (`0639EA5602C1`). Ingesting without automatic normalization produces an empty relational join.

---

### Decision 3: LoRa Packet Collapse & Firmware Severity vs. Discrete Outlier Counts
* **Choice**: Score degradation based on packet throughput drop (`rx_nr_pkts` falling >70% below baseline) and system severity indicators (`no_conn_importance`, `r_dur_power_cycle`).
* **Alternatives Considered**: Counting the raw number of hours where disconnects or reboots exceeded gateway-specific standard deviations.
* **Why Rejected**: Analysis of 642 historical field visits revealed that **60.7% of dispatches found no fault**, and **100% of visits triggered by "unusual statistics" (Auffaellige Statistik) were false alarms**. Healthy gateways with near-zero baseline variance spike past 3-sigma on benign blips. Meanwhile, true physical defects (such as power supply failures requiring *Netzteil* swaps, which accounted for 39 replacements) exhibit massive power-cycling durations and 288x increases in `no_conn_importance`. Most critically, unread meter penalties stem directly from LoRa packet collapse, making `rx_nr_pkts` drops the primary business risk indicator.

---

### Decision 4: Asset Register Cross-Referencing & Decommissioning Temporal Filter
* **Choice**: Filter candidate gateways at each evaluation week against the `installed_on` and `decommissioned_on` timestamps in `gateway_master.csv`.
* **Alternatives Considered**: Allowing the anomaly model to score all gateways present in historical telemetry.
* **Why Rejected**: 12 gateways in the fleet were decommissioned during the observation window (e.g. `02:EB:C6:CD:43:98` on 2026-02-04). Retiring gateways exhibit bursty disconnects and eventual silence right around shutdown, making them prime false targets for anomaly algorithms. Dispatching technicians to decommissioned hardware wastes €380 with 0% recovery probability.

---

### Decision 5: Modular Engine Architecture & Part 2 Preparation
* **Choice**: Decouple the codebase into clean layers: ingestion (`load_master`, `load_telemetry`), domain logic (`evaluate_week`), and presentation/CLI (`build_all_predictions`, `run.py`).
* **Alternatives Considered**: Maintaining a single monolithic script similar to `baseline_3sigma.py`.
* **Why Rejected**: Part 1 requires single-command reliability across diverse host environments (`Makefile`, `docker-compose.yml`, direct Python). More importantly, the upcoming 35-minute live session requires modifying the system live under inspection (e.g. altering thresholds, exposing new API endpoints, or handling corrupted inputs). A decoupled modular structure guarantees that domain heuristics can be modified in minutes without risking ingestion regressions.
