#!/usr/bin/env python3
"""Visualization Suite for Operations Manager Report.

Generates high-resolution publication-quality visual plots:
1. cost_vs_threshold.png - Economic U-curve balancing €380 visit cost vs €600 compounding penalty.
2. bootstrap_distribution.png - 95% Confidence Interval distribution over 1,000 bootstrap resamplings.
3. feature_separability.png - Empirical distribution of LoRa packet collapse and power cycles.
4. historical_bias_breakdown.png - Historical field visit outcome breakdown proving 60.7% waste on naive anomalies.
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")  # Headless backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.data_science.bootstrap import run_bootstrap_simulation
from src.data_science.cost_model import simulate_threshold_curve
from src.data_science.definition import evaluate_definitions_on_ground_truth


def setup_style() -> None:
    """Set professional, clean plotting aesthetic."""
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.labelweight": "bold",
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 15,
        "figure.titleweight": "bold",
    })


def plot_cost_vs_threshold(df_eval: pd.DataFrame, out_dir: pathlib.Path) -> None:
    """Plot 1: Economic U-curve of fleet cost vs probability threshold."""
    curve = simulate_threshold_curve(df_eval, min_t=0.10, max_t=0.95, steps=40)

    fig, ax1 = plt.subplots(figsize=(10, 6))

    color_total = "#1A365D"  # Deep navy
    color_visit = "#E53E3E"  # Red
    color_penalty = "#DD6B20"  # Orange

    ax1.plot(curve["threshold"], curve["total_cost"] / 1000.0, color=color_total, lw=3, label="Total Net Cost (k€)")
    ax1.plot(curve["threshold"], curve["visit_cost"] / 1000.0, color=color_visit, lw=2, linestyle="--", label="Technician Visit Cost (€380 each)")
    ax1.plot(curve["threshold"], curve["penalty_cost"] / 1000.0, color=color_penalty, lw=2, linestyle=":", label="Compounding Unread Penalty (€600/wk)")

    # Find optimal minimum cost threshold
    min_idx = curve["total_cost"].idxmin()
    opt_t = curve.loc[min_idx, "threshold"]
    opt_cost = curve.loc[min_idx, "total_cost"] / 1000.0

    ax1.axvline(opt_t, color="#319795", linestyle="-.", lw=2, label=f"Optimal Operational Threshold ({opt_t:.2f})")
    ax1.scatter([opt_t], [opt_cost], color="#319795", s=100, zorder=5)
    ax1.annotate(
        f"Minimum Cost: €{opt_cost*1000:,.0f}\nat threshold = {opt_t:.2f}",
        xy=(opt_t, opt_cost),
        xytext=(opt_t + 0.08, opt_cost + 8),
        arrowprops=dict(facecolor="#319795", shrink=0.08, width=1.5, headwidth=8),
        fontweight="bold",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#E6FFFA", edgecolor="#319795"),
    )

    ax1.set_xlabel("Decision Threshold (Minimum Defect Probability to Dispatch)")
    ax1.set_ylabel("Fleet Operating Cost (Thousands of Euros - k€)")
    ax1.set_title("Operational Cost vs. Dispatch Threshold: Balancing €380 Visits vs. €600 Penalties")
    ax1.set_xlim(0.10, 0.95)
    ax1.legend(loc="upper center", frameon=True, facecolor="white", framealpha=0.9)

    plt.tight_layout()
    out_path = out_dir / "cost_vs_threshold.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


def plot_bootstrap_distribution(df_eval: pd.DataFrame, out_dir: pathlib.Path) -> None:
    """Plot 2: 1,000-sample bootstrap distribution with 95% CI."""
    intervals, df_boot = run_bootstrap_simulation(df_eval, threshold=0.65, n_iterations=1000)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Total Cost distribution
    cost_data = df_boot["total_cost"] / 1000.0
    ci_low_c = intervals["total_cost"].ci_lower / 1000.0
    ci_high_c = intervals["total_cost"].ci_upper / 1000.0
    pt_c = intervals["total_cost"].point_estimate / 1000.0

    sns.histplot(cost_data, kde=True, ax=ax1, color="#2B6CB0", bins=25, alpha=0.6)
    ax1.axvline(pt_c, color="#1A365D", lw=2.5, label=f"Point Estimate: €{pt_c*1000:,.0f}")
    ax1.axvline(ci_low_c, color="#E53E3E", linestyle="--", lw=2, label=f"2.5% CI: €{ci_low_c*1000:,.0f}")
    ax1.axvline(ci_high_c, color="#E53E3E", linestyle="--", lw=2, label=f"97.5% CI: €{ci_high_c*1000:,.0f}")
    ax1.axvspan(ci_low_c, ci_high_c, color="#E2E8F0", alpha=0.5)
    ax1.set_title("Fleet Operating Cost Uncertainty (1,000 Resamplings)")
    ax1.set_xlabel("Total Cost (k€)")
    ax1.set_ylabel("Bootstrap Sample Frequency")
    ax1.legend(loc="upper right", fontsize=9)

    # Precision distribution
    prec_data = df_boot["precision"] * 100.0
    ci_low_p = intervals["precision"].ci_lower * 100.0
    ci_high_p = intervals["precision"].ci_upper * 100.0
    pt_p = intervals["precision"].point_estimate * 100.0

    sns.histplot(prec_data, kde=True, ax=ax2, color="#38A169", bins=25, alpha=0.6)
    ax2.axvline(pt_p, color="#22543D", lw=2.5, label=f"Point Estimate: {pt_p:.1f}%")
    ax2.axvline(ci_low_p, color="#DD6B20", linestyle="--", lw=2, label=f"2.5% CI: {ci_low_p:.1f}%")
    ax2.axvline(ci_high_p, color="#DD6B20", linestyle="--", lw=2, label=f"97.5% CI: {ci_high_p:.1f}%")
    ax2.axvspan(ci_low_p, ci_high_p, color="#E6FFFA", alpha=0.5)
    ax2.set_title("Dispatch Precision Uncertainty (1,000 Resamplings)")
    ax2.set_xlabel("Precision (%) - True Defects per 15 Dispatches")
    ax2.set_ylabel("Bootstrap Sample Frequency")
    ax2.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    out_path = out_dir / "bootstrap_distribution.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


def plot_feature_separability(data_dir: pathlib.Path, out_dir: pathlib.Path) -> None:
    """Plot 3: Empirical distributions separating Normal vs Schlecht gateways."""
    er_path = data_dir / "engineer_review_2026-02.xlsx"
    er = pd.read_excel(er_path)
    er_dict = dict(zip(er["gateway_id"].str.replace(":", "").str.upper(), er["Kategorie"]))

    feb = pd.read_parquet(data_dir / "telemetry" / "month=2026-02" / "part-0.parquet")
    feb["norm_id"] = feb["gateway_id"].str.replace(":", "").str.upper()
    feb["ts"] = pd.to_datetime(feb["ts_utc"], utc=True)
    feb_pre = feb[(feb["ts"] >= "2026-02-01") & (feb["ts"] < "2026-02-15")].copy()
    feb_pre["kategorie"] = feb_pre["norm_id"].map(er_dict)
    sub = feb_pre[feb_pre["kategorie"].isin(["Normal", "Schlecht"])].copy()

    # Aggregate per gateway
    gw = sub.groupby(["norm_id", "kategorie"]).agg(
        mean_rx=("rx_nr_pkts", "mean"),
        power_dur=("r_dur_power_cycle", "sum"),
        conn_imp=("no_conn_importance", "mean"),
    ).reset_index()

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))

    # 1. Packet throughput
    sns.boxplot(x="kategorie", y="mean_rx", data=gw, ax=ax1, palette=["#38A169", "#E53E3E"])
    ax1.set_title("A. LoRa Packet Throughput\n(rx_nr_pkts/hr)")
    ax1.set_xlabel("Engineer Verdict")
    ax1.set_ylabel("Mean Packets / Hour")

    # 2. Power cycle duration
    sns.boxplot(x="kategorie", y="power_dur", data=gw, ax=ax2, palette=["#38A169", "#E53E3E"])
    ax2.set_title("B. Power Cycle Duration\n(r_dur_power_cycle sec)")
    ax2.set_xlabel("Engineer Verdict")
    ax2.set_ylabel("Cumulative Seconds (Power Cycles)")

    # 3. Disconnect severity
    gw["log_conn_imp"] = np.log10(gw["conn_imp"] + 1.0)
    sns.boxplot(x="kategorie", y="log_conn_imp", data=gw, ax=ax3, palette=["#38A169", "#E53E3E"])
    ax3.set_title("C. Backhaul Severity\n(log10 no_conn_importance)")
    ax3.set_xlabel("Engineer Verdict")
    ax3.set_ylabel("Log10 Severity Score")

    plt.tight_layout()
    out_path = out_dir / "feature_separability.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


def plot_historical_bias(data_dir: pathlib.Path, out_dir: pathlib.Path) -> None:
    """Plot 4: Historical field visit waste breakdown."""
    fv = pd.read_csv(data_dir / "field_visits.csv")
    ct = pd.crosstab(fv["reason_reported"], fv["outcome"], normalize="index") * 100.0

    # Sort by percentage of "Fehler behoben"
    ct = ct.sort_values("Fehler behoben", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ["#38A169", "#E53E3E", "#A0AEC0"]
    ct[["Fehler behoben", "Kein Fehler gefunden", "Kein Zugang"]].plot(
        kind="barh", stacked=True, color=colors, ax=ax, width=0.7
    )

    ax.set_title("Historical Field Visits Outcome by Trigger Reason (642 Work Orders)\nHighlighting 100% Waste on 'Auffaellige Statistik'")
    ax.set_xlabel("Percentage of Historical Dispatches (%)")
    ax.set_ylabel("Reported Trigger Reason")
    ax.axvline(50, color="gray", linestyle=":", alpha=0.7)
    ax.legend(["Fehler behoben (Defect Resolved)", "Kein Fehler gefunden (€380 Wasted)", "Kein Zugang (No Access)"], loc="lower right")

    plt.tight_layout()
    out_path = out_dir / "historical_bias_breakdown.png"
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


def main() -> int:
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    data_dir = here / "data"
    out_dir = here / "reports" / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    setup_style()
    print(f"Generating charts into {out_dir}...", file=sys.stderr)

    df_eval = evaluate_definitions_on_ground_truth(data_dir)

    plot_cost_vs_threshold(df_eval, out_dir)
    plot_bootstrap_distribution(df_eval, out_dir)
    plot_feature_separability(data_dir, out_dir)
    plot_historical_bias(data_dir, out_dir)

    print("All charts successfully generated!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
