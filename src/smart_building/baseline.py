import numpy as np
import pandas as pd

from smart_building.data_loader import compute_grid_flows


def compute_baseline_cost(
    df: pd.DataFrame,
    price_import: np.ndarray,
    price_export: np.ndarray | float,
    timestep_minutes: int = 5,
) -> dict:
    """Compute electricity cost from the actual measured FusionSolar dispatch."""
    dt = timestep_minutes / 60
    df = compute_grid_flows(df)

    if np.isscalar(price_export):
        price_export = np.full(len(df), price_export)

    import_cost = (price_import * df["grid_import_kw"].values * dt).sum()
    export_revenue = (price_export * df["grid_export_kw"].values * dt).sum()
    net_cost = import_cost - export_revenue

    total_consumption = (df["usePower"].values * dt).sum()
    total_pv = (df["productPower"].values * dt).sum()
    self_consumed = (df["selfUsePower"].values * dt).sum()

    return {
        "import_cost_chf": import_cost,
        "export_revenue_chf": export_revenue,
        "net_cost_chf": net_cost,
        "total_import_kwh": (df["grid_import_kw"].values * dt).sum(),
        "total_export_kwh": (df["grid_export_kw"].values * dt).sum(),
        "total_consumption_kwh": total_consumption,
        "total_pv_kwh": total_pv,
        "self_consumption_rate": self_consumed / total_pv if total_pv > 0 else 0,
        "self_sufficiency_rate": self_consumed / total_consumption if total_consumption > 0 else 0,
    }
