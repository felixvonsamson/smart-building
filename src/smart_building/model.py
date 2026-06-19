import numpy as np
import pandas as pd
import pyomo.environ as pyo

from smart_building.config import SystemConfig


def build_model(
    df: pd.DataFrame,
    cfg: SystemConfig,
    ev_sessions: pd.DataFrame | None = None,
    price_import: np.ndarray | None = None,
    price_export: np.ndarray | float | None = None,
) -> pyo.ConcreteModel:
    dt = cfg.timestep_minutes / 60  # hours per timestep
    n = len(df)
    pv = df["productPower"].values
    base_demand = df["base_power"].values
    batt = cfg.battery

    if price_import is None:
        price_import = df[cfg.grid.import_tariff_column].values
    if price_export is None:
        price_export = cfg.grid.export_tariff_chf_kwh

    # Broadcast scalar export price to array
    if np.isscalar(price_export):
        price_export_arr = np.full(n, price_export)
    else:
        price_export_arr = np.asarray(price_export)

    grid_max = float(max(base_demand.max() + batt.max_charge_kw + 15, pv.max() + batt.max_discharge_kw, 50))

    m = pyo.ConcreteModel()
    m.T = pyo.RangeSet(0, n - 1)

    # --- Battery variables ---
    m.batt_charge = pyo.Var(m.T, within=pyo.NonNegativeReals, bounds=(0, batt.max_charge_kw))
    m.batt_discharge = pyo.Var(m.T, within=pyo.NonNegativeReals, bounds=(0, batt.max_discharge_kw))
    m.soc = pyo.Var(m.T, bounds=(batt.soc_min_kwh, batt.soc_max_kwh))

    # Prevent simultaneous battery charge/discharge
    m.batt_dir = pyo.Var(m.T, within=pyo.Binary)

    def batt_charge_limit_rule(m, t):
        return m.batt_charge[t] <= batt.max_charge_kw * m.batt_dir[t]
    m.batt_charge_limit = pyo.Constraint(m.T, rule=batt_charge_limit_rule)

    def batt_discharge_limit_rule(m, t):
        return m.batt_discharge[t] <= batt.max_discharge_kw * (1 - m.batt_dir[t])
    m.batt_discharge_limit = pyo.Constraint(m.T, rule=batt_discharge_limit_rule)

    # --- Grid variables ---
    m.grid_import = pyo.Var(m.T, within=pyo.NonNegativeReals, bounds=(0, grid_max))
    m.grid_export = pyo.Var(m.T, within=pyo.NonNegativeReals, bounds=(0, grid_max))

    # Prevent simultaneous import/export only where arbitrage is possible
    arb_steps = [int(t) for t in range(n) if price_import[t] < price_export_arr[t]]
    if arb_steps:
        m.arb_set = pyo.Set(initialize=arb_steps)
        m.grid_dir = pyo.Var(m.arb_set, within=pyo.Binary)

        def import_limit_rule(m, t):
            return m.grid_import[t] <= grid_max * m.grid_dir[t]
        m.import_limit = pyo.Constraint(m.arb_set, rule=import_limit_rule)

        def export_limit_rule(m, t):
            return m.grid_export[t] <= grid_max * (1 - m.grid_dir[t])
        m.export_limit = pyo.Constraint(m.arb_set, rule=export_limit_rule)

    # --- EV variables ---
    optimize_ev = cfg.ev.optimize and ev_sessions is not None and len(ev_sessions) > 0
    if optimize_ev:
        ev_max_power = _build_ev_availability(df, ev_sessions, cfg)
        m.ev_charge = pyo.Var(m.T, within=pyo.NonNegativeReals)
    else:
        ev_fixed = df["ev_power"].values

    # --- Constraints ---

    def balance_rule(m, t):
        ev_term = m.ev_charge[t] if optimize_ev else ev_fixed[t]
        return (
            pv[t] + m.grid_import[t] + m.batt_discharge[t]
            == base_demand[t] + ev_term + m.grid_export[t] + m.batt_charge[t]
        )
    m.balance = pyo.Constraint(m.T, rule=balance_rule)

    def soc_rule(m, t):
        if t == 0:
            return pyo.Constraint.Skip
        return m.soc[t] == (
            m.soc[t - 1]
            + (m.batt_charge[t - 1] * batt.efficiency - m.batt_discharge[t - 1] / batt.efficiency) * dt
        )
    m.soc_dynamics = pyo.Constraint(m.T, rule=soc_rule)

    m.soc_cyclic = pyo.Constraint(
        expr=m.soc[n - 1] == m.soc[0]
        + (m.batt_charge[n - 1] * batt.efficiency - m.batt_discharge[n - 1] / batt.efficiency) * dt
    )

    # --- EV constraints ---
    if optimize_ev:
        def ev_power_limit_rule(m, t):
            return m.ev_charge[t] <= ev_max_power[t]
        m.ev_power_limit = pyo.Constraint(m.T, rule=ev_power_limit_rule)

        timestamps = df.index
        m.ev_energy_constraints = pyo.ConstraintList()
        for _, sess in ev_sessions.iterrows():
            mask = (timestamps >= sess["arrival"]) & (timestamps <= sess["departure"])
            indices = np.where(mask)[0]
            if len(indices) > 0:
                m.ev_energy_constraints.add(
                    sum(m.ev_charge[int(i)] for i in indices) * dt == sess["energy_kwh"]
                )

    # --- Objective ---
    m.cost = pyo.Objective(
        expr=sum(
            (price_import[t] * m.grid_import[t] - price_export_arr[t] * m.grid_export[t]) * dt
            for t in m.T
        ),
        sense=pyo.minimize,
    )

    return m


def solve_model(m: pyo.ConcreteModel, time_limit: int = 600):
    solver = pyo.SolverFactory("appsi_highs")
    solver.options["time_limit"] = time_limit
    solver.options["mip_rel_gap"] = 0.005
    return solver.solve(m, tee=False)


def extract_results(
    m: pyo.ConcreteModel,
    df: pd.DataFrame,
    price_import: np.ndarray,
    price_export: np.ndarray | float,
) -> pd.DataFrame:
    n = len(df)
    results = pd.DataFrame(index=df.index)
    results["pv_kw"] = df["productPower"].values
    results["base_demand_kw"] = df["base_power"].values
    results["price_import"] = price_import
    if np.isscalar(price_export):
        results["price_export"] = price_export
    else:
        results["price_export"] = price_export
    results["batt_charge_kw"] = [pyo.value(m.batt_charge[t]) for t in range(n)]
    results["batt_discharge_kw"] = [pyo.value(m.batt_discharge[t]) for t in range(n)]
    results["soc_kwh"] = [pyo.value(m.soc[t]) for t in range(n)]
    results["grid_import_kw"] = [pyo.value(m.grid_import[t]) for t in range(n)]
    results["grid_export_kw"] = [pyo.value(m.grid_export[t]) for t in range(n)]

    if hasattr(m, "ev_charge"):
        results["ev_charge_kw"] = [pyo.value(m.ev_charge[t]) for t in range(n)]
    else:
        results["ev_charge_kw"] = df["ev_power"].values

    return results


def _build_ev_availability(
    df: pd.DataFrame,
    ev_sessions: pd.DataFrame,
    cfg: SystemConfig,
) -> np.ndarray:
    """Build per-timestep max EV charging power (0 when unplugged)."""
    timestamps = df.index
    max_power = np.zeros(len(timestamps))
    for _, sess in ev_sessions.iterrows():
        mask = (timestamps >= sess["arrival"]) & (timestamps <= sess["departure"])
        max_power[mask] = np.maximum(max_power[mask], cfg.ev.max_charge_kw)
    return max_power
