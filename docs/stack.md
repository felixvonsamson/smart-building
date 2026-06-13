# Technology Stack & Modeling Design

## Overview

```
                ┌──────────────────────────┐
 Open data ───▶ │  Data ingestion (pandas)  │ ── full-year hourly time series
 (PVGIS, OPSD,  │  pvlib, demandlib-style,  │    (PV gen/kWp, elec demand,
  weather)      │  heating-degree model)    │     heat demand, T_amb, prices)
                └──────────────┬────────────┘
                                ▼
                ┌──────────────────────────┐
                │ Representative days (tsam)│ ── ~8-12 typical days + weights
                └──────────────┬────────────┘
                                ▼
                ┌──────────────────────────┐
                │ Optimization (Pyomo+HiGHS)│ ── cost-minimal dispatch per day
                │ + rule-based baseline     │
                └──────────────┬────────────┘
                                ▼
                ┌──────────────────────────┐
                │ Scenarios & KPIs (pandas) │ ── annualized cost, savings,
                │                            │    self-consumption, etc.
                └──────────────┬────────────┘
                                ▼
                ┌──────────────────────────┐
                │ Dashboard (Streamlit +    │ ── time series, flow diagrams,
                │ Plotly)                    │    scenario comparison
                └──────────────────────────┘
```

## Stack components & rationale

| Layer | Choice | Why |
|---|---|---|
| Optimization modeling | [Pyomo](http://www.pyomo.org/) | Mature, declarative LP/MILP modeling in Python; easy to express storage dynamics, balances and bounds per component; large community/docs. |
| Solver | [HiGHS](https://highs.dev/) via `highspy` | Open-source, fast for LP/MILP at this scale (single house, hourly, a handful of representative days); no license needed. |
| Data handling | pandas / numpy | Standard for time-series wrangling and alignment. |
| Config | pydantic + YAML | Typed, validated house/system configuration; one YAML file per house scenario. |
| PV generation profile | [pvlib](https://pvlib-python.readthedocs.io/) (`get_pvgis_hourly`) | Free PVGIS TMY data by location, no API key; also provides ambient temperature for the heat pump COP and heating-demand model. |
| Electricity prices | [Open Power System Data](https://open-power-system-data.org/) day-ahead price series | Free historical day-ahead prices per bidding zone, no API key — used as the variable-price input. |
| Electricity demand profile | Standard load profile (BDEW-style), scaled to an annual consumption target | Realistic shape without requiring smart-meter data. |
| Heating/DHW demand | Simple heating-degree model from ambient temperature + stylized DHW profile, scaled to an annual heat demand target | Avoids building a full thermal building model; good enough to drive the heat pump / tank dispatch problem. |
| Representative day selection | [tsam](https://github.com/FZJ-IEK3-VSA/tsam) | Purpose-built for clustering multi-attribute annual time series into typical periods with weights — standard in energy system models. |
| Dashboard | Streamlit + Plotly | Fast to build interactive pages (sliders, dropdowns, KPI cards) with good charting (stacked areas, Sankey flow diagrams). |

## Modeling design decisions

These choices keep the optimization a **linear program** (no nonlinear or
mixed-integer terms unless explicitly noted), which keeps solves fast and
robust with HiGHS.

### Time resolution
Hourly, for one representative day at a time (24 timesteps). Matches the
native resolution of PVGIS and day-ahead price data. Can be revisited
(e.g. 15-min) later if EV/battery dynamics need finer resolution.

### Heat pump / COP
The COP is **precomputed as an exogenous time series** `COP(t)` from the
ambient temperature profile (using a fixed manufacturer-style correlation),
*not* a decision-dependent variable. This makes the heat output
`Q_hp(t) = COP(t) * P_hp_elec(t)` linear in the electrical input. The
simplification: COP is assumed independent of the tank (sink) temperature,
using a representative mean sink temperature.

### Hot water tank (thermal storage)
State variable is **usable thermal energy** `E_tank(t)` in kWh, derived
from tank volume, water density/specific heat, and the usable temperature
range (`E_max = V · ρ · c_p · (T_max − T_min) / 3600`). Heat losses are
linear in `E_tank(t)`. Balance:

```
E_tank(t+1) = E_tank(t) + (Q_hp(t) - Q_demand(t) - Q_loss(t)) * Δt
E_min <= E_tank(t) <= E_max
```

`Q_demand(t)` covers both space heating and domestic hot water draw.

### Batteries (static + EV)
Both modeled the same way: SOC dynamics with charge/discharge efficiencies
and power limits.

```
SOC(t+1) = SOC(t) + (P_charge(t)*eta_c - P_discharge(t)/eta_d) * Δt / E_capacity
SOC_min <= SOC(t) <= SOC_max
0 <= P_charge(t) <= P_charge_max
0 <= P_discharge(t) <= P_discharge_max
```

The EV additionally has an **availability parameter** `avail(t)` (plugged
in or away — charge/discharge forced to 0 when away) and a **minimum SOC
requirement at departure time**.

### Cyclic storage constraint
For each representative day, storage SOC (battery, EV, tank) at the end of
the day is constrained to equal its SOC at the start. This prevents the
optimizer from "borrowing" free energy across day boundaries when each
representative day is solved independently.

### Electrical energy balance (per timestep)
```
PV(t) + P_grid_import(t) + P_batt_dis(t) + P_ev_dis(t)
  = demand_elec(t) + P_grid_export(t) + P_batt_chg(t) + P_ev_chg(t)
    + P_hp_elec(t) + P_pv_curtail(t)
```

### Objective
Minimize the weighted sum (by tsam representative-day weight) of daily
electricity cost:

```
minimize  Σ_days weight_day * Σ_t ( price_import(t)*P_grid_import(t)
                                   - price_export(t)*P_grid_export(t) )
```

### Baseline (for savings comparison)
A simple rule-based controller with no price foresight: PV is consumed
directly, then charges the battery, then exports; the battery discharges to
cover shortfalls; the heat pump runs thermostatically to keep the tank
within its band; the EV charges at maximum power whenever plugged in. The
optimized model's cost is compared against this baseline to quantify
savings from price-aware dispatch.
