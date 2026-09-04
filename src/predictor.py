#!/usr/bin/env python3
"""LPDG Gateway Visit Predictor.

A robust operational ranking engine that overcomes the failure modes of naive
anomaly baselines:
1. Dead gateway detection (catches silent gateways with zero or near-zero telemetry).
2. Packet collapse detection (identifies LoRa packet drops that cause unread meters).
3. System severity integration (leverages firmware-reported no_conn_importance and reboot_importance).
4. Asset master integration (filters decommissioned gateways and handles encoding/ID normalization).
5. Clear, human-readable operational reasons for field technicians.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

SCORED_WEEKS = [dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)]
VISITS_PER_WEEK = 15
BASELINE_DAYS = 28
RECENT_DAYS = 7
MAX_REASON_CHARS = 300

_BARE = re.compile(r"^[0-9A-Fa-f]{12}$")
_COLON = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def normalise_id(val: str | None) -> str:
    """Standardise any gateway ID to 12 uppercase hex characters without colons."""
    if val is None:
        return ""
    text = str(val).strip()
    if _COLON.match(text):
        return text.replace(":", "").upper()
    if _BARE.match(text):
        return text.upper()
    return text.replace(":", "").upper()


def load_master(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load gateway master table with encoding fallback and normalized IDs."""
    master_path = data_dir / "gateway_master.csv"
    if not master_path.exists():
        return pd.DataFrame()

    df: Optional[pd.DataFrame] = None
    for enc in ["latin1", "cp1252", "iso-8859-1", "utf-8"]:
        try:
            df = pd.read_csv(master_path, encoding=enc)
            break
        except (UnicodeDecodeError, Exception):
            continue

    if df is None:
        raise RuntimeError(f"Unable to read {master_path} with supported encodings.")

    df["norm_id"] = df["gateway_id"].apply(normalise_id)
    if "decommissioned_on" in df.columns:
        df["decom_dt"] = pd.to_datetime(df["decommissioned_on"], errors="coerce")
    else:
        df["decom_dt"] = pd.NaT

    if "installed_on" in df.columns:
        df["installed_dt"] = pd.to_datetime(df["installed_on"], errors="coerce")
    else:
        df["installed_dt"] = pd.NaT

    return df


def load_telemetry(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load required telemetry columns from Parquet partitions."""
    telemetry_dir = data_dir / "telemetry"
    cols = [
        "gateway_id",
        "ts_utc",
        "rx_nr_pkts",
        "disconnection_cnt",
        "no_conn_importance",
        "offline_duration_sec",
        "reboot_cnt",
        "reboot_importance",
        "r_dur_power_cycle",
    ]
    frame = pd.read_parquet(telemetry_dir, columns=cols)
    frame["norm_id"] = frame["gateway_id"].apply(normalise_id)
    frame["ts"] = pd.to_datetime(frame["ts_utc"], utc=True)
    return frame.drop(columns=["ts_utc", "gateway_id"])


def evaluate_week(
    frame: pd.DataFrame,
    master: pd.DataFrame,
    monday: dt.date,
) -> pd.DataFrame:
    """Score and rank gateways for a single target week."""
    end = pd.Timestamp(monday, tz="UTC")
    recent_start = end - dt.timedelta(days=RECENT_DAYS)
    baseline_start = end - dt.timedelta(days=BASELINE_DAYS)

    # 1. Determine active gateways on this Monday
    if not master.empty:
        active_master = master[
            (master["decom_dt"].isna() | (master["decom_dt"] > pd.Timestamp(monday)))
            & (master["installed_dt"].isna() | (master["installed_dt"] <= pd.Timestamp(monday)))
        ]
        active_ids = set(active_master["norm_id"])
    else:
        active_ids = set(frame["norm_id"].unique())

    # 2. Window telemetry
    window = frame[(frame["ts"] >= baseline_start) & (frame["ts"] < end)]
    recent = window[window["ts"] >= recent_start]

    # Baseline 28-day stats for comparison
    base_stats = window.groupby("norm_id").agg(
        base_hours=("ts", "count"),
        base_rx_mean=("rx_nr_pkts", "mean"),
    )

    # Recent 7-day stats
    recent_stats = recent.groupby("norm_id").agg(
        recent_hours=("ts", "count"),
        recent_rx_mean=("rx_nr_pkts", "mean"),
        disconnections=("disconnection_cnt", "sum"),
        no_conn_imp_mean=("no_conn_importance", "mean"),
        reboots=("reboot_cnt", "sum"),
        reboot_imp_mean=("reboot_importance", "mean"),
        power_cycle_dur=("r_dur_power_cycle", "sum"),
    )

    # Combine metrics across all active gateways
    records = []
    for gid in active_ids:
        # Check if gateway had history in baseline
        b_hours = base_stats.loc[gid, "base_hours"] if gid in base_stats.index else 0
        b_rx = base_stats.loc[gid, "base_rx_mean"] if gid in base_stats.index else 0.0

        if gid not in recent_stats.index or recent_stats.loc[gid, "recent_hours"] == 0:
            # GATEWAY WENT COMPLETELY DARK
            # If it was active in baseline but has 0 recent hours, it is a critical failure.
            if b_hours > 24:
                score = 100000.0 + float(b_rx)
                reason = (
                    f"CRITICAL: Gateway went completely dark (0 telemetry hours in last 7d vs "
                    f"{int(b_hours)}h in baseline); unread meters accumulating €600/wk penalty"
                )
            else:
                score = 10.0
                reason = "Low historical reporting volume; potential commissioning/site outage"
            records.append({
                "gateway_id": gid,
                "score": score,
                "reason": reason[:MAX_REASON_CHARS],
                "flag": "DARK",
            })
            continue

        r = recent_stats.loc[gid]
        r_hours = r["recent_hours"]
        r_rx = r["recent_rx_mean"]
        disc = r["disconnections"]
        conn_imp = r["no_conn_imp_mean"]
        reboots = r["reboots"]
        reb_imp = r["reboot_imp_mean"]
        pwr_dur = r["power_cycle_dur"]

        # A) Severe reporting blackout (< 50% of expected 168 hours)
        if r_hours < 84 and b_hours > 200:
            score = 80000.0 + (168 - r_hours) * 100.0
            reason = (
                f"HIGH OUTAGE: Reported only {int(r_hours)}h in last 7d (expected 168h, >50% data loss); "
                f"severe backhaul or power interruptions detected"
            )
            records.append({
                "gateway_id": gid,
                "score": score,
                "reason": reason[:MAX_REASON_CHARS],
                "flag": "PARTIAL_DARK",
            })
            continue

        # B) Radio Packet Collapse (LoRa packet drop)
        rx_drop_ratio = (b_rx - r_rx) / (b_rx + 1.0) if b_rx > 100 else 0.0
        if rx_drop_ratio > 0.70 and r_rx < 200:
            score = 50000.0 + float(rx_drop_ratio * 10000.0) + float(disc)
            reason = (
                f"RADIO COLLAPSE: LoRa packet throughput dropped {int(rx_drop_ratio*100)}% "
                f"(from {int(b_rx)} to {int(r_rx)} pkts/hr); meters behind gateway failing to relay"
            )
            records.append({
                "gateway_id": gid,
                "score": score,
                "reason": reason[:MAX_REASON_CHARS],
                "flag": "RADIO_DROP",
            })
            continue

        # C) Severe Connection Instability & Firmware Score
        if conn_imp > 50000.0 or disc > 50:
            score = 20000.0 + float(conn_imp / 100.0) + float(disc * 10.0)
            reason = (
                f"BACKHAUL SEVERITY: Disconnect severity score {int(conn_imp):,} with {int(disc)} "
                f"disconnect events in trailing 7d; high risk of ongoing backhaul failure"
            )
            records.append({
                "gateway_id": gid,
                "score": score,
                "reason": reason[:MAX_REASON_CHARS],
                "flag": "CONN_SEVERITY",
            })
            continue

        # D) Power Cycle & Reboot Loops
        if pwr_dur > 60 or (reboots > 20 and reb_imp > 500):
            score = 10000.0 + float(pwr_dur * 50.0) + float(reb_imp)
            reason = (
                f"HARDWARE INSTABILITY: {int(pwr_dur)}s power cycling duration with {int(reboots)} "
                f"reboots; indicative of failing power supply unit (Netzteil) or thermal tripping"
            )
            records.append({
                "gateway_id": gid,
                "score": score,
                "reason": reason[:MAX_REASON_CHARS],
                "flag": "HARDWARE_REBOOT",
            })
            continue

        # E) Baseline residual score
        residual_score = float(disc * 2.0 + reboots * 3.0 + (168 - r_hours))
        records.append({
            "gateway_id": gid,
            "score": residual_score,
            "reason": (
                f"Routine monitoring: {int(disc)} disconnects, {int(reboots)} reboots in trailing 7d; "
                f"packet rate steady at {int(r_rx)} pkts/hr"
            )[:MAX_REASON_CHARS],
            "flag": "NORMAL",
        })

    df_scored = pd.DataFrame(records)
    df_ranked = df_scored.sort_values("score", ascending=False).reset_index(drop=True)
    return df_ranked


def build_all_predictions(data_dir: pathlib.Path) -> pd.DataFrame:
    """Generate validated predictions for all 8 scored weeks."""
    print("Loading gateway master...", file=sys.stderr)
    master = load_master(data_dir)
    print("Loading telemetry partitions...", file=sys.stderr)
    telemetry = load_telemetry(data_dir)

    rows = []
    for monday in SCORED_WEEKS:
        print(f"Scoring week {monday}...", file=sys.stderr)
        ranked = evaluate_week(telemetry, master, monday)
        top15 = ranked.head(VISITS_PER_WEEK)

        for rank, row in enumerate(top15.itertuples(index=False), 1):
            rows.append({
                "week_start": monday.isoformat(),
                "rank": rank,
                "gateway_id": row.gateway_id,
                "score": round(float(row.score), 2),
                "reason": row.reason,
            })

    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    here = pathlib.Path(__file__).resolve().parent.parent
    default_data = here / "data"
    parser.add_argument("--data", type=pathlib.Path, default=default_data, help="Path to data folder")
    parser.add_argument("--out", type=pathlib.Path, default=here / "predictions.csv", help="Output CSV path")
    args = parser.parse_args(argv)

    if not args.data.exists():
        print(f"Error: Data directory not found at {args.data}", file=sys.stderr)
        return 1

    predictions = build_all_predictions(args.data)
    predictions.to_csv(args.out, index=False)
    print(f"Successfully wrote {len(predictions)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
