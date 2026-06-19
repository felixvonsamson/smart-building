"""Compare optimized vs baseline across tariff scenarios (Q1: Jan-Mar)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from smart_building.config import load_config
from smart_building.data_loader import load_energy_data, load_ev_sessions
from smart_building.baseline import compute_baseline_cost
from smart_building.model import build_model, solve_model, extract_results


def run_scenario(df, cfg, ev_sessions, price_import, price_export, label):
    dt = cfg.timestep_minutes / 60
    n = len(df)

    if np.isscalar(price_export):
        pe_arr = np.full(n, price_export)
    else:
        pe_arr = np.asarray(price_export)

    baseline = compute_baseline_cost(df, price_import, pe_arr, cfg.timestep_minutes)

    print(f"  Building model ({n} timesteps)...")
    m = build_model(df, cfg, ev_sessions, price_import=price_import, price_export=pe_arr)
    print(f"  Solving...")
    result = solve_model(m)
    status = str(result.solver.termination_condition)
    print(f"  Solver: {status}")

    res = extract_results(m, df, price_import, pe_arr)

    opt_import_cost = (price_import * res["grid_import_kw"].values * dt).sum()
    opt_export_rev = (pe_arr * res["grid_export_kw"].values * dt).sum()
    opt_net = opt_import_cost - opt_export_rev
    opt_import_kwh = (res["grid_import_kw"].values * dt).sum()
    opt_export_kwh = (res["grid_export_kw"].values * dt).sum()
    total_pv = (res["pv_kw"].values * dt).sum()
    pv_self = total_pv - opt_export_kwh

    return {
        "label": label,
        "baseline": baseline,
        "optimized": {
            "net_cost_chf": opt_net,
            "import_cost_chf": opt_import_cost,
            "export_revenue_chf": opt_export_rev,
            "total_import_kwh": opt_import_kwh,
            "total_export_kwh": opt_export_kwh,
            "self_consumption_rate": pv_self / total_pv if total_pv > 0 else 0,
        },
    }


def main():
    cfg = load_config(Path("config/house_default.yaml"))
    print("Loading data...")
    df = load_energy_data(cfg)
    ev_sessions = load_ev_sessions(cfg)

    # Filter to Q1 (Jan-Mar)
    q1_mask = df.index < "2026-04-01"
    df_q1 = df.loc[q1_mask].copy()
    ev_q1 = ev_sessions[ev_sessions["departure"] < "2026-04-01"].copy()
    print(f"Q1 data: {len(df_q1)} timesteps, {len(ev_q1)} EV sessions\n")

    # --- Scenario 1: Variable tariff (import=integrated, export=grid_tariff) ---
    print("=== Scenario 1: Variable tariff (export = grid market price) ===")
    s1 = run_scenario(
        df_q1, cfg, ev_q1,
        price_import=df_q1["integrated_tariff_CHF_kWh"].values,
        price_export=df_q1["grid_tariff_CHF_kWh"].values,
        label="Variable tariff",
    )

    # --- Scenario 2: Dual tariff (import=dual_tariff, export=0.11 fixed) ---
    print("\n=== Scenario 2: Dual tariff (export = 0.11 CHF/kWh) ===")
    s2 = run_scenario(
        df_q1, cfg, ev_q1,
        price_import=df_q1["dual_tariff_CHF_kWh"].values,
        price_export=0.11,
        label="Dual tariff",
    )

    # --- Print comparison table ---
    scenarios = [s1, s2]
    print("\n" + "=" * 80)
    print("RESULTS COMPARISON — Q1 (January–March 2026)")
    print("=" * 80)

    header = f"{'Metric':<30}"
    for s in scenarios:
        header += f" {'Baseline':>12} {'Optimized':>12} |"
    print(f"\n{'':30}", end="")
    for s in scenarios:
        label = s["label"]
        print(f" {label:^25s} |", end="")
    print()
    print(f"{'Metric':<30}", end="")
    for _ in scenarios:
        print(f" {'Baseline':>12} {'Optimized':>12} |", end="")
    print()
    print("-" * 80)

    def row(label, baseline_key, opt_key=None, fmt=".2f", unit=""):
        if opt_key is None:
            opt_key = baseline_key
        line = f"{label:<30}"
        for s in scenarios:
            bv = s["baseline"][baseline_key]
            ov = s["optimized"][opt_key]
            line += f" {bv:>12{fmt}}{unit} {ov:>12{fmt}}{unit} |"
        print(line)

    row("Grid import (kWh)", "total_import_kwh", fmt=".1f")
    row("Grid export (kWh)", "total_export_kwh", fmt=".1f")
    row("Import cost (CHF)", "import_cost_chf")
    row("Export revenue (CHF)", "export_revenue_chf")
    row("Net cost (CHF)", "net_cost_chf")
    row("Self-consumption rate", "self_consumption_rate", fmt=".1%")

    print("-" * 80)
    line = f"{'SAVINGS (CHF)':<30}"
    for s in scenarios:
        sav = s["baseline"]["net_cost_chf"] - s["optimized"]["net_cost_chf"]
        pct = sav / s["baseline"]["net_cost_chf"] * 100 if s["baseline"]["net_cost_chf"] else 0
        line += f" {'':>12} {sav:>9.2f} ({pct:.1f}%) |"
    print(line)
    print("=" * 80)


if __name__ == "__main__":
    main()
