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


def _project_root() -> Path:
    """Walk up from this file to find the directory containing pyproject.toml."""
    d = Path(__file__).resolve().parent
    while d != d.parent:
        if (d / "pyproject.toml").exists():
            return d
        d = d.parent
    return Path.cwd()


def load_config(path: Path | str | None = None) -> SystemConfig:
    root = _project_root()
    if path is not None:
        path = root / path if not Path(path).is_absolute() else Path(path)
        with open(path) as f:
            cfg = SystemConfig(**yaml.safe_load(f))
    else:
        cfg = SystemConfig()
    cfg.data_file = str(root / cfg.data_file)
    cfg.ev.sessions_file = str(root / cfg.ev.sessions_file)
    return cfg
