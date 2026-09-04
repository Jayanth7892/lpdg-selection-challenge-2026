#!/usr/bin/env python3
"""Economic Cost Model & Decision Threshold Optimizer.

Formulates the decision theory turning €380 visit costs and compounding €600/wk
unread penalties into an optimal dispatch threshold, and simulates the marginal
cost of shifting the threshold in either direction.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import pathlib
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.data_science.definition import evaluate_definitions_on_ground_truth

COST_VISIT = 380.0          # €380 flat visit cost
PENALTY_WEEKLY = 600.0      # €600/week unattended broken gateway penalty
AVERAGE_PERSISTENCE_WKS = 2.4  # average weeks a broken gateway lingers without automated dispatch
MAX_VISITS_WEEKLY = 15


@dataclasses.dataclass
class ThresholdOutcome:
    threshold: float
    visits_recommended: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    visit_expenditure: float
    penalty_incurred: float
    total_cost: float
    precision: float
    recall: float


def compute_expected_loss(
    p_defect: float,
    dispatch: bool,
    persistence_weeks: float = AVERAGE_PERSISTENCE_WKS,
) -> float:
    """Compute expected economic loss in Euros for a single gateway decision."""
    if dispatch:
        # We pay €380 regardless. If defective, we prevent future penalty.
        return COST_VISIT
    else:
        # If we do not dispatch, cost is 0 if healthy, or penalty * weeks if defective
        return p_defect * (PENALTY_WEEKLY * persistence_weeks)


def evaluate_threshold(
    df: pd.DataFrame,
    threshold: float,
    max_visits: int = MAX_VISITS_WEEKLY,
    persistence_weeks: float = AVERAGE_PERSISTENCE_WKS,
) -> ThresholdOutcome:
    """Simulate operational outcomes at a given probability threshold."""
    # Filter candidates meeting threshold
    candidates = df[df["prob_defect"] >= threshold].copy()
    candidates = candidates.sort_values("prob_defect", ascending=False)

    # Apply capacity limit
    dispatched = candidates.head(max_visits)
    dispatched_ids = set(dispatched["gateway_id"])

    tp = int(((df["gateway_id"].isin(dispatched_ids)) & (df["actual_defective"] == 1)).sum())
    fp = int(((df["gateway_id"].isin(dispatched_ids)) & (df["actual_defective"] == 0)).sum())
    fn = int(((~df["gateway_id"].isin(dispatched_ids)) & (df["actual_defective"] == 1)).sum())
    tn = int(((~df["gateway_id"].isin(dispatched_ids)) & (df["actual_defective"] == 0)).sum())

    visit_cost = (tp + fp) * COST_VISIT
    # Compounding penalty on unvisited defective units
    penalty_cost = fn * (PENALTY_WEEKLY * persistence_weeks)
    total_cost = visit_cost + penalty_cost

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return ThresholdOutcome(
        threshold=threshold,
        visits_recommended=tp + fp,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        visit_expenditure=visit_cost,
        penalty_incurred=penalty_cost,
        total_cost=total_cost,
        precision=precision,
        recall=recall,
    )


def simulate_threshold_curve(
    df: pd.DataFrame,
    min_t: float = 0.10,
    max_t: float = 0.95,
    steps: int = 50,
) -> pd.DataFrame:
    """Generate the full economic cost curve across decision thresholds."""
    thresholds = np.linspace(min_t, max_t, steps)
    records = []
    for t in thresholds:
        out = evaluate_threshold(df, t)
        records.append({
            "threshold": round(float(t), 3),
            "visits": out.visits_recommended,
            "tp": out.true_positives,
            "fp": out.false_positives,
            "fn": out.false_negatives,
            "visit_cost": out.visit_expenditure,
            "penalty_cost": out.penalty_incurred,
            "total_cost": out.total_cost,
            "precision": out.precision,
            "recall": out.recall,
        })
    return pd.DataFrame(records)


def analyze_threshold_shift(
    df: pd.DataFrame,
    current_t: float = 0.65,
    delta: float = 0.10,
) -> Dict[str, ThresholdOutcome]:
    """Calculate the exact economic cost of shifting threshold in each direction."""
    t_base = current_t
    t_higher = min(0.95, current_t + delta)
    t_lower = max(0.10, current_t - delta)

    return {
        "lower": evaluate_threshold(df, t_lower),
        "current": evaluate_threshold(df, t_base),
        "higher": evaluate_threshold(df, t_higher),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Economic cost threshold optimizer for LPDG gateway dispatches."
    )
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    parser.add_argument("--data", type=pathlib.Path, default=here / "data", help="Data directory")
    parser.add_argument("--threshold", type=float, default=0.65, help="Current probability threshold (default 0.65)")
    parser.add_argument("--step", type=float, default=0.10, help="Step size for sensitivity analysis (default 0.10)")
    args = parser.parse_args(argv)

    print("Evaluating ground truth data...", file=sys.stderr)
    df_eval = evaluate_definitions_on_ground_truth(args.data)
    results = analyze_threshold_shift(df_eval, args.threshold, args.step)

    cur = results["current"]
    low = results["lower"]
    high = results["higher"]

    print("\n" + "=" * 76)
    print("ECONOMIC DECISION THRESHOLD ANALYSIS: €380 VISIT VS €600 COMPOUNDING PENALTY")
    print("=" * 76)
    print(f"Current Operating Threshold : {cur.threshold:.2f}")
    print(f"Capacity Limit              : {MAX_VISITS_WEEKLY} visits/week")
    print(f"Average Outage Persistence  : {AVERAGE_PERSISTENCE_WKS} weeks without automated dispatch")
    print("-" * 76)

    print(f"\n[CURRENT BASELINE: Threshold = {cur.threshold:.2f}]")
    print(f"  Dispatches Allocated      : {cur.visits_recommended} / {MAX_VISITS_WEEKLY}")
    print(f"  True Defect Catches (TP)  : {cur.true_positives}")
    print(f"  Wasted Dispatches (FP)    : {cur.false_positives} (€{cur.false_positives * COST_VISIT:,.0f} wasted)")
    print(f"  Missed Defects (FN)       : {cur.false_negatives} (€{cur.penalty_incurred:,.0f} compounding penalty)")
    print(f"  Precision / Recall        : {cur.precision:.1%} / {cur.recall:.1%}")
    print(f"  TOTAL FLEET OPERATING COST: €{cur.total_cost:,.0f}")

    print(f"\n[DIRECTION 1: LOWER THRESHOLD -> {low.threshold:.2f} (More Aggressive / Higher Sensitivity)]")
    d_vis = low.visits_recommended - cur.visits_recommended
    d_cost = low.total_cost - cur.total_cost
    d_tp = low.true_positives - cur.true_positives
    d_fp = low.false_positives - cur.false_positives
    print(f"  Dispatches Shift          : {d_vis:+d} visits ({low.visits_recommended} total)")
    print(f"  Defects Caught Shift      : {d_tp:+d} true defects caught")
    print(f"  False Alarms Shift        : {d_fp:+d} false alarms")
    print(f"  Financial Impact          : {d_cost:+,.0f} € (Total: €{low.total_cost:,.0f})")
    if d_cost > 0:
        print(f"  EXPLANATION: Lowering the threshold sends {abs(d_vis)} more technicians. While it catches")
        print(f"  {d_tp} more defect(s), the extra false alarms cost more in €380 visit fees than they save.")
    else:
        print(f"  EXPLANATION: Lowering the threshold saves €{abs(d_cost):,.0f} because preventing €600 compounding")
        print(f"  penalties outweighs the added visit expenditures.")

    print(f"\n[DIRECTION 2: HIGHER THRESHOLD -> {high.threshold:.2f} (More Conservative / Higher Specificity)]")
    d_vis_h = high.visits_recommended - cur.visits_recommended
    d_cost_h = high.total_cost - cur.total_cost
    d_tp_h = high.true_positives - cur.true_positives
    d_fn_h = high.false_negatives - cur.false_negatives
    print(f"  Dispatches Shift          : {d_vis_h:+d} visits ({high.visits_recommended} total)")
    print(f"  Defects Caught Shift      : {d_tp_h:+d} true defects caught")
    print(f"  Missed Defect Penalties   : {d_fn_h:+d} unaddressed broken units")
    print(f"  Financial Impact          : {d_cost_h:+,.0f} € (Total: €{high.total_cost:,.0f})")
    if d_cost_h > 0:
        print(f"  EXPLANATION: Raising the threshold saves technician dispatch costs, BUT every missed defect")
        print(f"  compounds at €600/week (total €{high.penalty_incurred:,.0f}). The penalty exceeds visit savings by €{d_cost_h:,.0f}!")
    else:
        print(f"  EXPLANATION: Raising the threshold eliminates low-confidence visits, saving €{abs(d_cost_h):,.0f}.")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
