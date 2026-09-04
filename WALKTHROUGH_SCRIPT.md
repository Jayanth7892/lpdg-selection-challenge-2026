# 6-to-8 Minute Screen Recording Script & Walkthrough Guide

Use this structured script to record your 6–8 minute submission video.

---

### Timing Breakdown (Target: 7 minutes)

| Timestamp | Section | Key Visual on Screen | What to Say |
|---|---|---|---|
| **0:00 – 1:00** | **Introduction & Problem Context** | Code editor showing workspace and `README.txt` | *"Hello, my name is [Your Name]. This is my submission for the LPDG Innovation Hub Selection Challenge 2026. LPDG operates a fleet of ~320 LoRaWAN gateways across Europe. With a strict capacity of 15 visits per week, our job is to prioritize sites where physical hardware intervention prevents unread meters and avoids compounding €600/week penalties."* |
| **1:00 – 2:15** | **Single-Command Run & Validation** | Terminal | Open terminal. Run `python run.py --data data --out predictions.csv`. Show it processing the 8 scored weeks and generating `predictions.csv`. Then run `python validate_submission.py predictions.csv`. Highlight the clean `predictions.csv: OK (15 ranked gateways for each of 8 weeks)`. Show the `Makefile` and `docker-compose.yml` for containerized execution. |
| **2:15 – 4:00** | **The Flaws of Naive Baselines & Our Solution** | Show `src/predictor.py` and comparison table from `DECISIONS.md` | Explain why `baseline_3sigma.py` fails: *"When an engineer reviewed 120 gateways in mid-February, the naive 3-sigma baseline flagged 15 healthy gateways and only 12 defective ones. Even worse, if a gateway suffers complete power failure and goes silent, naive grouping produces zero rows, completely missing dead gateways. We built active fleet completeness tracking that immediately flags silent gateways, measures LoRa packet collapse, and handles Latin-1 encoding and ID formatting."* |
| **4:00 – 5:15** | **Walkthrough of Key Decisions (DECISIONS.md)** | `DECISIONS.md` file open | Quickly walk through the 5 decisions: (1) Dead gateway recovery, (2) Resilient ingestion without manual re-encoding, (3) Packet drop vs raw counts, (4) Filtering decommissioned units, and (5) Modular separation for live session readiness. |
| **5:15 – 6:15** | **AI-USAGE & Errors Caught** | `AI-USAGE.md` file open | Share how AI was used and the specific mistakes caught: *"When profiling the data, AI models naively assumed UTF-8 and crashed on German Eszett characters in gateway_master.csv. Furthermore, AI attempted to compute hourly outage rates on `offline_duration_sec`, failing to realize it is a cumulative firmware counter running up to 726,000 seconds. Catching these prevented fatal ingestion bugs."* |
| **6:15 – 7:15** | **Limitations & Conclusion** | `LIMITATIONS.md` open | Conclude by discussing current limits: *"Today, the engine weights all gateways equally, but some serve 900 meters while others serve 40. With two more weeks, we would integrate meter-weighted expected loss and carrier outage spatial clustering. Thank you for your time, and I look forward to the live session!"* |
