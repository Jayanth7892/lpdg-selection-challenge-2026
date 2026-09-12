# LPDG Innovation Hub — Selection Challenge 2026

> **Field Visit Prioritization Service for LoRaWAN Utility Gateway Fleet**  
> Candidate: **Jayanth** | Selected Track: **Part 2: Track D — Data Science**

---

## 📺 Walkthrough Video Recording

**Watch the screen walkthrough recording here:**  
🔗 **[Google Drive Video Walkthrough](https://drive.google.com/file/d/1eYEAsDNR5rJTPEV4qTYfHK8wXxdWPUGW/view)**

---

## Quick Start (Single-Command Execution)

Run the full prediction pipeline and validate the output:

```bash
# 1. Run prediction pipeline across all 8 scored weeks
python run.py --data data --out predictions.csv

# 2. Run official grader validation
python validate_submission.py predictions.csv
```

### Or using Make / Docker:
```bash
make run        # Run pipeline locally
make validate   # Validate predictions.csv
make docker-run # Run inside Docker container
```

---

## Project Structure & Deliverables

* **`predictions.csv`**: Exactly 120 rows (15 ranked gateways per week $\times$ 8 weeks from Feb 2 to Mar 23, 2026), verified with `validate_submission.py` (exit code 0).
* **`REPORT_OPERATIONS_MANAGER.md`**: Executive write-up with charts for the Operations Manager explaining the failure definition, economic cost curve, and recommended threshold ($p^* = 0.65$).
* **`DECISIONS.md`**: The 5 key engineering choices made, alternatives considered, and why they were rejected.
* **`AI-USAGE.md`**: Transparent account of pair-programming with Gemini and Claude, including the 3 real mistakes caught and fixed.
* **`LIMITATIONS.md`**: Honest breakdown of current edge cases and what another two weeks would fix.
* **`reports/charts/`**: High-resolution visual plots:
  * `cost_vs_threshold.png`: U-shaped economic cost curve balancing €380 visits vs. compounding €600 penalties.
  * `bootstrap_distribution.png`: 95% Confidence Interval distribution over 1,000 bootstrap resamplings.
  * `feature_separability.png`: Boxplots showing packet collapse, power cycles, and disconnect severity.
  * `historical_bias_breakdown.png`: 642-visit audit proving 60.7% waste on historical gut-feel dispatches.

---

## Live Session Interactive Threshold Command

To demonstrate threshold shifting in the 35-minute live session:

```bash
python -m src.data_science.cost_model --threshold 0.65 --step 0.10
```
This simulates the exact financial impact in euros and technician hours of moving the sensitivity threshold in either direction.
