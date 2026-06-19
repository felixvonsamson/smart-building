"""Run battery (+ optional EV) dispatch optimization and compare to baseline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from smart_building.config import load_config
from smart_building.data_loader import load_energy_data, load_ev_sessions
from smart_building.baseline import compute_baseline_cost
from smart_building.model import build_model, solve_model, extract_results


def main():
    cfg = load_config(Path("config/house_default.yaml"))
    print("Loading data...")
    df = load_energy_data(cfg)
    ev_sessions = load_ev_sessions(cfg)
    dt = cfg.timestep_minutes / 60

    # --- Baseline (actual FusionSolar dispatch) ---
    print("Computing baseline cost from measured dispatch...")
    baseline = compute_baseline_cost(df, cfg)

    # --- Optimized dispatch ---
    print(f"Building optimization model ({len(df)} timesteps, EV optimize={cfg.ev.optimize})...")
    m = build_model(df, cfg, ev_sessions if cfg.ev.optimize else None)

    print("Solving...")
    result = solve_model(m)
    status = str(result.solver.termination_condition)
    print(f"Solver status: {status}")
    if status not in ("optimal", "maxTimeLimit"):
        print("Solver did not find a feasible solution. Exiting.")
        return

    results = extract_results(m, df, cfg)

    # --- Optimized KPIs ---
    opt_import_cost = (results["price_import"] * results["grid_import_kw"] * dt).sum()
    opt_export_revenue = (cfg.grid.export_tariff_chf_kwh * results["grid_export_kw"] * dt).sum()
    opt_net_cost = opt_import_cost - opt_export_revenue
    opt_import_kwh = (results["grid_import_kw"] * dt).sum()
    opt_export_kwh = (results["grid_export_kw"] * dt).sum()
    total_pv = (results["pv_kw"] * dt).sum()
    total_demand = (results["base_demand_kw"] * dt).sum() + (results["ev_charge_kw"] * dt).sum()
    pv_self_consumed = total_pv - opt_export_kwh

    # --- Print comparison ---
    savings = baseline["net_cost_chf"] - opt_net_cost
    savings_pct = savings / baseline["net_cost_chf"] * 100 if baseline["net_cost_chf"] != 0 else 0

    print("\n" + "=" * 60)
    print("RESULTS COMPARISON (6-month period)")
    print("=" * 60)

    print(f"\n{'Metric':<35} {'Baseline':>12} {'Optimized':>12}")
    print("-" * 60)
    print(f"{'Grid import (kWh)':<35} {baseline['total_import_kwh']:>12.1f} {opt_import_kwh:>12.1f}")
    print(f"{'Grid export (kWh)':<35} {baseline['total_export_kwh']:>12.1f} {opt_export_kwh:>12.1f}")
    print(f"{'Import cost (CHF)':<35} {baseline['import_cost_chf']:>12.2f} {opt_import_cost:>12.2f}")
    print(f"{'Export revenue (CHF)':<35} {baseline['export_revenue_chf']:>12.2f} {opt_export_revenue:>12.2f}")
    print(f"{'Net cost (CHF)':<35} {baseline['net_cost_chf']:>12.2f} {opt_net_cost:>12.2f}")
    print(f"{'Self-consumption rate':<35} {baseline['self_consumption_rate']:>11.1%} {pv_self_consumed / total_pv:>11.1%}")
    print(f"{'Self-sufficiency rate':<35} {baseline['self_sufficiency_rate']:>11.1%} {pv_self_consumed / total_demand:>11.1%}")

    print(f"\n{'SAVINGS':>35} {savings:>12.2f} CHF ({savings_pct:.1f}%)")
    print("=" * 60)

    results.to_parquet("data/processed/optimized_dispatch.parquet")
    print("\nOptimized dispatch saved to data/processed/optimized_dispatch.parquet")


if __name__ == "__main__":
    main()
