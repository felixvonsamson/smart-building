from pathlib import Path

import yaml
from pydantic import BaseModel


class BatteryConfig(BaseModel):
    capacity_kwh: float = 20.0
    max_charge_kw: float = 10.0
    max_discharge_kw: float = 10.0
    efficiency: float = 0.88
    soc_min_kwh: float = 0.0
    soc_max_kwh: float = 20.0


class EVConfig(BaseModel):
    optimize: bool = True
    max_charge_kw: float = 12.2
    sessions_file: str = "data/processed/ev_sessions.csv"


class GridConfig(BaseModel):
    export_tariff_chf_kwh: float = 0.14
    import_tariff_column: str = "integrated_tariff_CHF_kWh"


class SystemConfig(BaseModel):
    battery: BatteryConfig = BatteryConfig()
    ev: EVConfig = EVConfig()
    grid: GridConfig = GridConfig()
    data_file: str = "data/processed/energy_balance_separated.csv"
    timestep_minutes: int = 5


def load_config(path: Path | str | None = None) -> SystemConfig:
    if path is None:
        return SystemConfig()
    with open(path) as f:
        return SystemConfig(**yaml.safe_load(f))
