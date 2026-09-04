#!/usr/bin/env python3
"""Bootstrap Uncertainty Quantification & Out-of-Gateway Validation.

Computes 95% empirical confidence intervals via 1,000 bootstrap resamplings
to report performance as a rigorous statistical range rather than a single point estimate.
Explicitly documents the mathematical boundaries of what the test cannot measure.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.data_science.cost_model import COST_VISIT, PENALTY_WEEKLY, AVERAGE_PERSISTENCE_WKS, evaluate_threshold
from src.data_science.definition import evaluate_definitions_on_ground_truth


@dataclasses.dataclass
class MetricInterval:
    name: str
    point_estimate: float
    ci_lower: float
    ci_upper: float
    std_error: float
    unit: str = ""

    def format_range(self) -> str:
        if self.unit == "€":
            return f"€{self.point_estimate:,.0f} [95% CI: €{self.ci_lower:,.0f} – €{self.ci_upper:,.0f}] (SE: €{self.std_error:,.0f})"
        elif self.unit == "%":
            return f"{self.point_estimate:.1%} [95% CI: {self.ci_lower:.1%} – {self.ci_upper:.1%}] (SE: {self.std_error:.1%})"
        else:
            return f"{self.point_estimate:.1f} [95% CI: {self.ci_lower:.1f} – {self.ci_upper:.1f}] (SE: {self.std_error:.1f})"


TEST_LIMITATIONS = [
    (
        "Counterfactual Censoring",
        "We only have formal engineer review labels for 120 of the ~320 fleet gateways. "
        "For the unreviewed ~200 gateways, their true operational status is unobserved. "
        "The test cannot observe counterfactual outcomes: what would have happened to unvisited "
        "gateways had a technician been sent, or what unaddressed damage accrued on gateways we missed."
    ),
    (
        "Post-Intervention Telemetry Masking",
        "When an engineer fixes a fault (e.g. Netzteil replacement), the telemetry changes immediately. "
        "Our cross-sectional test captures a single snapshot in mid-February 2026 and cannot simulate "
        "multi-week recursive feedback loops where a visit removes a gateway from next week's candidate pool."
    ),
    (
        "Carrier Outage Confounding",
        "The ground-truth review was performed by a single engineer across several regions on a single day. "
        "If a regional telecom operator (e.g. VodafoneDE) experienced a regional tower hiccup during that week, "
        "the test cannot distinguish between a defective gateway antenna vs a temporary cellular carrier degradation."
    ),
]


def run_bootstrap_simulation(
    df: pd.DataFrame,
    threshold: float = 0.65,
    n_iterations: int = 1000,
    random_seed: int = 42,
) -> Tuple[Dict[str, MetricInterval], pd.DataFrame]:
    """Execute non-parametric bootstrap resampling across gateways."""
    rng = np.random.default_rng(random_seed)
    n_samples = len(df)

    point_outcome = evaluate_threshold(df, threshold)

    boot_records = []
    for i in range(n_iterations):
        # Resample with replacement across gateways
        sample_indices = rng.choice(n_samples, size=n_samples, replace=True)
        boot_df = df.iloc[sample_indices].copy()

        # Re-evaluate on bootstrap sample
        out = evaluate_threshold(boot_df, threshold)
        boot_records.append({
            "iteration": i,
            "total_cost": out.total_cost,
            "precision": out.precision,
            "recall": out.recall,
            "true_positives": out.true_positives,
            "false_positives": out.false_positives,
            "false_negatives": out.false_negatives,
            "visits": out.visits_recommended,
        })

    df_boot = pd.DataFrame(boot_records)

    intervals = {}
    metric_configs = [
        ("total_cost", point_outcome.total_cost, "€"),
        ("precision", point_outcome.precision, "%"),
        ("recall", point_outcome.recall, "%"),
        ("true_positives", point_outcome.true_positives, "dispatches"),
        ("false_positives", point_outcome.false_positives, "dispatches"),
        ("false_negatives", point_outcome.false_negatives, "gateways"),
        ("visits", point_outcome.visits_recommended, "dispatches"),
    ]

    for key, pt, unit in metric_configs:
        series = df_boot[key]
        ci_low = float(np.percentile(series, 2.5))
        ci_high = float(np.percentile(series, 97.5))
        se = float(np.std(series, ddof=1))
        intervals[key] = MetricInterval(
            name=key,
            point_estimate=pt,
            ci_lower=ci_low,
            ci_upper=ci_high,
            std_error=se,
            unit=unit,
        )

    return intervals, df_boot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap uncertainty analysis for LPDG challenge.")
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    parser.add_argument("--data", type=pathlib.Path, default=here / "data", help="Data directory")
    parser.add_argument("--threshold", type=float, default=0.65, help="Decision threshold")
    parser.add_argument("--iterations", type=int, default=1000, help="Number of bootstrap iterations")
    args = parser.parse_args(argv)

    print(f"Loading ground truth data and executing {args.iterations} bootstrap resamplings...", file=sys.stderr)
    df_eval = evaluate_definitions_on_ground_truth(args.data)
    intervals, df_boot = run_bootstrap_simulation(df_eval, args.threshold, args.iterations)

    print("\n" + "=" * 76)
    print("BOOTSTRAP UNCERTAINTY QUANTIFICATION (A RANGE, NOT ONE NUMBER)")
    print(f"Evaluated over {args.iterations:,} Bootstrap Resamplings (95% Empirical Confidence Intervals)")
    print("=" * 76)

    print(f"\n[KEY PERFORMANCE METRICS AS EMPIRICAL RANGES]")
    print(f"  • Total Operating Cost : {intervals['total_cost'].format_range()}")
    print(f"  • Dispatch Precision   : {intervals['precision'].format_range()}")
    print(f"  • Fleet Defect Recall  : {intervals['recall'].format_range()}")
    print(f"  • True Defect Catches  : {intervals['true_positives'].format_range()}")
    print(f"  • False Alarm Dispatches: {intervals['false_positives'].format_range()}")
    print(f"  • Missed Broken Units  : {intervals['false_negatives'].format_range()}")

    print("\n" + "-" * 76)
    print("WHAT THIS TEST CANNOT TELL YOU (RIGOROUS METHODOLOGICAL BOUNDARIES)")
    print("-" * 76)
    for idx, (title, desc) in enumerate(TEST_LIMITATIONS, 1):
        print(f"\n{idx}. {title}:")
        print(f"   {desc}")
    print("\n" + "=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
