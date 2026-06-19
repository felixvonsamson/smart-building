import pandas as pd

from smart_building.config import SystemConfig
from smart_building.data_loader import compute_grid_flows


def compute_baseline_cost(df: pd.DataFrame, cfg: SystemConfig) -> dict:
    """Compute electricity cost from the actual measured FusionSolar dispatch."""
    dt = cfg.timestep_minutes / 60
    df = compute_grid_flows(df)
    price_import = df[cfg.grid.import_tariff_column]
    price_export = cfg.grid.export_tariff_chf_kwh

    import_cost = (price_import * df["grid_import_kw"] * dt).sum()
    export_revenue = (price_export * df["grid_export_kw"] * dt).sum()
    net_cost = import_cost - export_revenue

    total_consumption = (df["usePower"] * dt).sum()
    total_pv = (df["productPower"] * dt).sum()
    self_consumed = (df["selfUsePower"] * dt).sum()

    return {
        "import_cost_chf": import_cost,
        "export_revenue_chf": export_revenue,
        "net_cost_chf": net_cost,
        "total_import_kwh": (df["grid_import_kw"] * dt).sum(),
        "total_export_kwh": (df["grid_export_kw"] * dt).sum(),
        "total_consumption_kwh": total_consumption,
        "total_pv_kwh": total_pv,
        "self_consumption_rate": self_consumed / total_pv if total_pv > 0 else 0,
        "self_sufficiency_rate": self_consumed / total_consumption if total_consumption > 0 else 0,
    }
