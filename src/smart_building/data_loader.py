from pathlib import Path

import pandas as pd

from smart_building.config import SystemConfig


POWER_COLUMNS = [
    "productPower",
    "usePower",
    "selfUsePower",
    "chargePower",
    "dischargePower",
]


def load_energy_data(cfg: SystemConfig) -> pd.DataFrame:
    df = pd.read_csv(cfg.data_file)
    df["timestamp"] = pd.to_datetime(
        df["timestamp"].str.replace(" DST", "", regex=False)
    )
    for col in POWER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.interpolate(method="linear").bfill()
    df = df.set_index("timestamp").sort_index()
    return df


def load_ev_sessions(cfg: SystemConfig) -> pd.DataFrame:
    ev = pd.read_csv(cfg.ev.sessions_file)
    ev["start"] = pd.to_datetime(ev["start"].str.replace(" DST", "", regex=False))
    ev["end"] = pd.to_datetime(ev["end"].str.replace(" DST", "", regex=False))
    sessions = (
        ev.groupby("event")
        .agg(
            arrival=("start", "min"),
            departure=("end", "max"),
            energy_kwh=("energy_kwh", "sum"),
            max_power_kw=("ev_power_kw", "max"),
        )
        .reset_index()
    )
    return sessions


def compute_grid_flows(df: pd.DataFrame) -> pd.DataFrame:
    """Derive actual grid import/export from measured FusionSolar data."""
    net = (
        df["usePower"]
        + df["chargePower"]
        - df["productPower"]
        - df["dischargePower"]
    )
    df = df.copy()
    df["grid_import_kw"] = net.clip(lower=0)
    df["grid_export_kw"] = (-net).clip(lower=0)
    return df
