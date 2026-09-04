#!/usr/bin/env python3
"""Operational Definition of 'Needs a Visit' for LPDG Gateway Fleet.

This module formalizes the decision rule for what constitutes a gateway failure
requiring physical on-site technician intervention, contrasts it against rejected
alternative definitions, and evaluates each against ground-truth field data.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import pathlib
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

from src.predictor import load_master, load_telemetry, normalise_id


@dataclasses.dataclass(frozen=True)
class DefectCriteria:
    """Operational thresholds defining a physical defect."""
    min_baseline_hours: int = 24
    dark_max_recent_hours: int = 0
    partial_dark_max_hours: int = 84  # < 50% of expected 168h
    radio_drop_threshold: float = 0.70  # > 70% drop in LoRa packets
    radio_drop_max_pkts: float = 200.0
    power_cycle_duration_sec: float = 60.0
    conn_importance_threshold: float = 50000.0
    min_disconnects: int = 50


REJECTED_DEFINITIONS = {
    "Def_3Sigma_Outlier": (
        "Any gateway where disconnects, reboots, or offline duration exceed 3 standard "
        "deviations from its own 28-day baseline. REJECTED because: In 642 historical field "
        "visits, 100% of visits triggered by 'Auffaellige Statistik' (87/87) found no defect. "
        "It penalizes low-noise healthy gateways on routine hiccups while ignoring chronically "
        "failing gateways whose baseline variance is already inflated."
    ),
    "Def_Transient_Dropout": (
        "Any gateway experiencing backhaul disconnections or reboots in the trailing 7 days. "
        "REJECTED because: Cellular backhaul and RF propagation inherently exhibit transient "
        "fluctuations. Flagging transient blips causes extreme false alarm rates, overwhelming "
        "the fixed 15-visit weekly budget with benign visits that cost €380 each."
    ),
    "Def_Lagged_Meter_Success": (
        "Any gateway where weekly meter reading success drops below 90%. "
        "REJECTED because: Meter reading success is a lagging trailing indicator compiled "
        "after billing cycles close. By the time a drop registers in meter reports, 2 to 4 weeks "
        "of unread meter penalties (€600/wk) have already compounded irreversibly. Telemetry "
        "must be used as a leading physical indicator."
    ),
}


ACCEPTED_DEFINITION = (
    "A gateway 'NEEDS A VISIT' if it exhibits a physical hardware or transmission impairment "
    "that prevents telemetry or LoRa meter packets from reaching the utility backhaul, specifically: "
    "(1) Complete communication silence ('Dark Gateway') during an active billing period; "
    "(2) Sustained LoRa packet throughput collapse (>70% drop vs baseline); "
    "(3) Power cycle instability (r_dur_power_cycle > 60s, matching physical PSU failure); or "
    "(4) Severe chronic backhaul outage (no_conn_importance > 50,000). "
    "These conditions represent actionable physical failures that, if left unattended, generate "
    "the compounding €600/week unread penalty."
)


def classify_gateway_state(
    gid: str,
    recent_hours: int,
    base_hours: int,
    recent_rx: float,
    base_rx: float,
    conn_imp: float,
    disc_cnt: int,
    power_dur: float,
    reboots: int,
    criteria: DefectCriteria = DefectCriteria(),
) -> Tuple[bool, str, float]:
    """Classify whether a single gateway needs a visit under our accepted definition.
    
    Returns:
        (needs_visit: bool, primary_cause: str, defect_probability: float)
    """
    # 1. Total Silence / Dead Gateway
    if recent_hours <= criteria.dark_max_recent_hours:
        if base_hours >= criteria.min_baseline_hours:
            return True, "DARK_SILENT_FAILURE", 0.98
        return False, "NEW_UNCOMMISSIONED", 0.10

    # 2. Severe Partial Reporting Blackout
    if recent_hours < criteria.partial_dark_max_hours and base_hours > 200:
        return True, "PARTIAL_REPORTING_BLACKOUT", 0.92

    # 3. LoRa Radio Packet Collapse
    rx_drop_ratio = (base_rx - recent_rx) / (base_rx + 1.0) if base_rx > 100 else 0.0
    if rx_drop_ratio > criteria.radio_drop_threshold and recent_rx < criteria.radio_drop_max_pkts:
        prob = min(0.95, 0.70 + (rx_drop_ratio * 0.25))
        return True, "LORA_PACKET_COLLAPSE", prob

    # 4. Chronic Backhaul Severity
    if conn_imp > criteria.conn_importance_threshold or disc_cnt > criteria.min_disconnects:
        prob = min(0.90, 0.65 + (disc_cnt / 200.0))
        return True, "BACKHAUL_SEVERITY_OUTAGE", prob

    # 5. Hardware Power Cycle / Dying PSU
    if power_dur > criteria.power_cycle_duration_sec or (reboots > 25 and power_dur > 20):
        prob = min(0.92, 0.70 + (power_dur / 300.0))
        return True, "POWER_SUPPLY_FAILURE", prob

    # 6. Normal healthy / minor routine noise
    base_prob = min(0.15, max(0.01, disc_cnt * 0.005 + reboots * 0.01))
    return False, "HEALTHY_OPERATIONAL", base_prob


def evaluate_definitions_on_ground_truth(
    data_dir: pathlib.Path,
    monday: dt.date = dt.date(2026, 2, 16),
) -> pd.DataFrame:
    """Compare the accepted definition against 3-sigma on the 120 reviewed gateways."""
    # Load engineer review
    er_path = data_dir / "engineer_review_2026-02.xlsx"
    er = pd.read_excel(er_path)
    er["norm_id"] = er["gateway_id"].apply(normalise_id)
    er["actual_defective"] = (er["Kategorie"] == "Schlecht").astype(int)

    # Load master and telemetry
    master = load_master(data_dir)
    telemetry = load_telemetry(data_dir)

    end = pd.Timestamp(monday, tz="UTC")
    recent_start = end - dt.timedelta(days=7)
    baseline_start = end - dt.timedelta(days=28)

    window = telemetry[(telemetry["ts"] >= baseline_start) & (telemetry["ts"] < end)]
    recent = window[window["ts"] >= recent_start]

    base_stats = window.groupby("norm_id").agg(
        base_hours=("ts", "count"),
        base_rx_mean=("rx_nr_pkts", "mean"),
        base_disc_std=("disconnection_cnt", "std"),
        base_disc_mean=("disconnection_cnt", "mean"),
    )

    recent_stats = recent.groupby("norm_id").agg(
        recent_hours=("ts", "count"),
        recent_rx_mean=("rx_nr_pkts", "mean"),
        disconnections=("disconnection_cnt", "sum"),
        no_conn_imp_mean=("no_conn_importance", "mean"),
        reboots=("reboot_cnt", "sum"),
        reboot_imp_mean=("reboot_importance", "mean"),
        power_cycle_dur=("r_dur_power_cycle", "sum"),
    )

    results = []
    for row in er.itertuples():
        gid = row.norm_id
        actual = row.actual_defective

        b_hours = int(base_stats.loc[gid, "base_hours"]) if gid in base_stats.index else 0
        b_rx = float(base_stats.loc[gid, "base_rx_mean"]) if gid in base_stats.index else 0.0
        b_disc_mean = float(base_stats.loc[gid, "base_disc_mean"]) if gid in base_stats.index else 0.0
        b_disc_std = float(base_stats.loc[gid, "base_disc_std"]) if gid in base_stats.index else 1.0

        if gid in recent_stats.index:
            r = recent_stats.loc[gid]
            r_hours = int(r["recent_hours"])
            r_rx = float(r["recent_rx_mean"])
            disc = int(r["disconnections"])
            conn_imp = float(r["no_conn_imp_mean"])
            reboots = int(r["reboots"])
            power_dur = float(r["power_cycle_dur"])
        else:
            r_hours = 0
            r_rx = 0.0
            disc = 0
            conn_imp = 0.0
            reboots = 0
            power_dur = 0.0

        # Accepted Definition
        needs_visit, cause, prob = classify_gateway_state(
            gid, r_hours, b_hours, r_rx, b_rx, conn_imp, disc, power_dur, reboots
        )

        # Baseline 3-Sigma Simulation
        is_3sigma = False
        if b_disc_std > 0 and r_hours > 0:
            if (disc / max(1, r_hours) - b_disc_mean) > (3.0 * b_disc_std):
                is_3sigma = True

        results.append({
            "gateway_id": gid,
            "actual_defective": actual,
            "pred_accepted": int(needs_visit),
            "cause_accepted": cause,
            "prob_defect": prob,
            "pred_3sigma": int(is_3sigma),
        })

    return pd.DataFrame(results)


def print_comparison_report(df: pd.DataFrame) -> None:
    """Print precision, recall, and cost metrics comparing definitions."""
    print("=" * 70)
    print("GROUND TRUTH EVALUATION: ACCEPTED DEFINITION VS NAIVE 3-SIGMA")
    print("Evaluated against 120 Gateways (60 Normal, 60 Schlecht)")
    print("=" * 70)

    for name, col in [("Accepted Definition", "pred_accepted"), ("Naive 3-Sigma", "pred_3sigma")]:
        tp = int(((df[col] == 1) & (df["actual_defective"] == 1)).sum())
        fp = int(((df[col] == 1) & (df["actual_defective"] == 0)).sum())
        fn = int(((df[col] == 0) & (df["actual_defective"] == 1)).sum())
        tn = int(((df[col] == 0) & (df["actual_defective"] == 0)).sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # Economic impact on sample
        # Each TP costs €380 (successful fix)
        # Each FP costs €380 wasted
        # Each FN costs €600 (missed failure for 1 week)
        cost = (tp + fp) * 380 + fn * 600

        print(f"\n{name}:")
        print(f"  True Positives (Defects caught):   {tp:2d} / 60")
        print(f"  False Positives (Wasted €380):     {fp:2d} / 60")
        print(f"  False Negatives (Missed €600/wk):  {fn:2d} / 60")
        print(f"  Precision:                         {precision:.1%}")
        print(f"  Recall:                            {recall:.1%}")
        print(f"  F1-Score:                          {f1:.3f}")
        print(f"  Total Cost on Sample:              €{cost:,.0f}")
    print("=" * 70)


if __name__ == "__main__":
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    df_eval = evaluate_definitions_on_ground_truth(here / "data")
    print_comparison_report(df_eval)
